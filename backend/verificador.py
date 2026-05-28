"""
Verificador independente de presenca digital.
Usa Google Places API + requisicoes HTTP para VERIFICAR dados
ao inves de confiar apenas em auto-declaracao do cliente.

Objetivo: a ferramenta precisa REALMENTE analisar e verificar
quais criterios faltam ou sao necessarios otimizar.
"""

import requests
import os
import re
import json
from datetime import datetime
from urllib.parse import quote

GOOGLE_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', '')

UA = 'TonaIA-Verifier/1.0 (+https://tonaia.com.br)'


def _fetch(url, timeout=10):
    try:
        r = requests.get(url, timeout=timeout, headers={'User-Agent': UA},
                         allow_redirects=True)
        return r
    except:
        return None


def _similaridade(a, b):
    """Similaridade por intersecao de caracteres."""
    if not a or not b:
        return 0
    set_a, set_b = set(a), set(b)
    if not set_a or not set_b:
        return 0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0


def _extrair_username_instagram(texto):
    if not texto:
        return ''
    texto = texto.strip().replace('@', '').split('/')[-1].split('?')[0]
    return texto


def _extrair_page_facebook(texto):
    if not texto:
        return ''
    texto = texto.strip().split('/')[-1].split('?')[0]
    return texto


# ─── VERIFICACAO GBP via Google Places API ────────────────────────────────────

def verificar_gbp(nome, endereco='', cidade='', telefone=''):
    """
    Verifica a existencia e completude do GBP via Google Places API.
    Retorna dict com dados verificados pela API.
    """
    if not GOOGLE_API_KEY:
        return {
            'status': 'erro',
            'mensagem': 'GOOGLE_MAPS_API_KEY nao configurada',
            'fonte': 'configuracao'
        }

    termos = list(filter(None, [nome, cidade, endereco[:60] if endereco else '']))
    query = ' '.join(termos)

    url = 'https://places.googleapis.com/v1/places:searchText'
    headers = {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': GOOGLE_API_KEY,
        'X-Goog-FieldMask': (
            'places.id,places.displayName,places.formattedAddress,'
            'places.internationalPhoneNumber,places.rating,'
            'places.userRatingCount,places.websiteUri,places.photos,'
            'places.regularOpeningHours,places.editorialSummary,'
            'places.googleMapsUri,places.types,places.nationalPhoneNumber,'
            'places.priceLevel'
        ),
    }
    body = {
        'textQuery': query,
        'pageSize': 5,
        'languageCode': 'pt-BR',
    }

    try:
        r = requests.post(url, json=body, headers=headers, timeout=15)
        if r.status_code != 200:
            return {
                'status': 'erro',
                'mensagem': f'API retornou {r.status_code}',
                'detalhe': r.text[:300],
                'fonte': 'Google Places API'
            }

        data = r.json()
        places = data.get('places', [])

        if not places:
            return {
                'status': 'nao_encontrado',
                'mensagem': f'Nenhum estabelecimento encontrado para "{query}"',
                'fonte': 'Google Places API'
            }

        # Try to find best match by name + phone
        place = None
        melhor_confianca = 0

        for p in places:
            pname = p.get('displayName', {}).get('text', '')
            sim = _similaridade(nome.lower(), pname.lower())
            pphone = p.get('internationalPhoneNumber', '') or p.get('nationalPhoneNumber', '')

            # Boost confidence if phone matches
            if telefone and pphone:
                tel_digits = ''.join(filter(str.isdigit, telefone))
                pphone_digits = ''.join(filter(str.isdigit, pphone))
                if tel_digits and pphone_digits and tel_digits[-8:] == pphone_digits[-8:]:
                    sim += 0.3

            if sim > melhor_confianca:
                melhor_confianca = sim
                place = p

        if not place or melhor_confianca < 0.2:
            return {
                'status': 'nao_encontrado',
                'mensagem': f'Melhor resultado ("{places[0].get("displayName", {}).get("text", "")}") nao corresponde ao nome informado',
                'fonte': 'Google Places API'
            }

        # Build verification result
        nome_api = place.get('displayName', {}).get('text', '')
        tem_fotos = len(place.get('photos', [])) > 0
        qtd_fotos = len(place.get('photos', []))
        tem_horario = place.get('regularOpeningHours') is not None
        tem_website = bool(place.get('websiteUri'))
        website_url = place.get('websiteUri', '')
        tem_descricao = bool(place.get('editorialSummary', {}).get('text'))
        descricao = (place.get('editorialSummary') or {}).get('text', '')
        tipos = place.get('types', [])

        return {
            'status': 'encontrado',
            'confianca': round(melhor_confianca, 2),
            'place_id': place.get('id'),
            'nome_gbp': nome_api,
            'endereco': place.get('formattedAddress', ''),
            'telefone': place.get('internationalPhoneNumber', '') or place.get('nationalPhoneNumber', ''),
            'rating': place.get('rating'),
            'total_reviews': place.get('userRatingCount', 0),
            'tem_fotos': tem_fotos,
            'qtd_fotos': qtd_fotos,
            'tem_horario': tem_horario,
            'tem_website': tem_website,
            'website_url': website_url,
            'tem_descricao': tem_descricao,
            'descricao': descricao,
            'gbp_url': place.get('googleMapsUri', ''),
            'tipos': tipos,
            'fonte': 'Google Places API (verificacao em tempo real)',
        }

    except requests.exceptions.Timeout:
        return {'status': 'erro', 'mensagem': 'Timeout na requisicao Google Places API', 'fonte': 'Google Places API'}
    except Exception as e:
        return {'status': 'erro', 'mensagem': str(e), 'fonte': 'Google Places API'}


# ─── VERIFICACAO DE URLs ──────────────────────────────────────────────────────

def verificar_url_existe(url):
    """Verifica se uma URL esta acessivel (status < 400)."""
    if not url:
        return {'existe': False, 'status': None}
    if not url.startswith('http'):
        url = f'https://{url}'
    try:
        r = requests.get(url, timeout=10, headers={'User-Agent': UA}, allow_redirects=True)
        return {
            'existe': r.status_code < 400,
            'status': r.status_code,
            'url_final': r.url,
            'respondeu': r.status_code < 500,
        }
    except Exception as e:
        return {'existe': False, 'status': None, 'erro': str(e)}


def verificar_instagram(username):
    """Verifica se perfil do Instagram existe."""
    username = _extrair_username_instagram(username)
    if not username:
        return {'encontrado': False, 'username': '', 'fonte': 'nao informado'}
    result = verificar_url_existe(f'https://www.instagram.com/{username}/')
    result['encontrado'] = result.get('existe', False)
    result['username'] = username
    result['fonte'] = 'HTTP request direto ao Instagram'
    return result


def verificar_facebook(page):
    """Verifica se pagina do Facebook existe."""
    page = _extrair_page_facebook(page)
    if not page:
        return {'encontrado': False, 'page': '', 'fonte': 'nao informado'}
    if 'facebook.com' in page.lower():
        result = verificar_url_existe(page)
    else:
        result = verificar_url_existe(f'https://www.facebook.com/{page}/')
    result['encontrado'] = result.get('existe', False)
    result['page'] = page
    result['fonte'] = 'HTTP request direto ao Facebook'
    return result


# ─── VERIFICACAO MULTI-PLATAFORMA ─────────────────────────────────────────────

def verificar_plataformas(nome, cidade=''):
    """
    Tenta detectar o negocio em multiplas plataformas.
    Usa busca textual + verificacao de URLs candidatas.
    """
    resultados = {}

    # Foursquare — tentar buscar na API publica
    if cidade:
        try:
            url_fs = (
                f'https://api.foursquare.com/v3/places/search?'
                f'query={quote(nome)}&near={quote(cidade)}&limit=1'
            )
            # Foursquare v3 requires API key, so this will likely fail
            # but we try anyway
            r = requests.get(
                url_fs,
                headers={'Accept': 'application/json'},
                timeout=8
            )
            if r.status_code == 200:
                data = r.json()
                results = data.get('results', [])
                resultados['foursquare'] = {
                    'encontrado': len(results) > 0,
                    'qtd_resultados': len(results),
                    'fonte': 'Foursquare API',
                }
                if results:
                    resultados['foursquare']['nome'] = results[0].get('name', '')
            else:
                resultados['foursquare'] = {
                    'encontrado': None,
                    'mensagem': 'API Foursquare requer autenticacao',
                    'fonte': 'Foursquare API'
                }
        except:
            resultados['foursquare'] = {
                'encontrado': None,
                'mensagem': 'Nao foi possivel consultar Foursquare',
                'fonte': 'Foursquare API'
            }
    else:
        resultados['foursquare'] = {
            'encontrado': None,
            'mensagem': 'Cidade nao informada para buscar no Foursquare',
            'fonte': 'Foursquare API'
        }

    # Google search proxy: tenta buscar nome + cidade no Google
    # para detectar em quais plataformas aparece
    try:
        search_query = f'{quote(nome)} {quote(cidade)}' if cidade else quote(nome)
        search_url = f'https://www.google.com/search?q={search_query}&hl=pt-BR'
        r = requests.get(
            search_url,
            timeout=10,
            headers={
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/125.0.0.0 Safari/537.36'
                )
            }
        )
        if r.status_code == 200:
            text = r.text.lower()
            plataformas_detectadas = []
            plataforma_map = {
                'instagram.com': 'instagram',
                'facebook.com': 'facebook',
                'foursquare.com': 'foursquare',
                'yelp.com': 'yelp',
                'tripadvisor.com': 'tripadvisor',
                'bing.com/maps': 'bing_places',
                'apple.com/maps': 'apple_maps',
                'linkedin.com': 'linkedin',
                'reclameaqui.com': 'reclame_aqui',
                'youtube.com': 'youtube',
                'tiktok.com': 'tiktok',
            }
            for domain, nome_plat in plataforma_map.items():
                if domain in text:
                    plataformas_detectadas.append(nome_plat)

            resultados['busca_google'] = {
                'plataformas_detectadas': plataformas_detectadas,
                'qtd_mencoes': len(plataformas_detectadas),
                'fonte': 'Google Search (resultados organicos)',
            }
        else:
            resultados['busca_google'] = {
                'erro': f'Google retornou {r.status_code}',
                'fonte': 'Google Search'
            }
    except Exception as e:
        resultados['busca_google'] = {
            'erro': str(e),
            'fonte': 'Google Search'
        }

    return resultados


# ─── ORQUESTRADOR ──────────────────────────────────────────────────────────────

def verificar_tudo(perfil):
    """
    Executa TODAS as verificacoes disponiveis para um perfil de negocio.

    perfil: dict com chaves como nome, endereco, cidade, telefone,
            instagram, facebook, site_url, etc. (formato do questionario)

    Retorna dict completo com todos os resultados de verificacao.
    """
    nome = perfil.get('nome_negocio', perfil.get('nome', ''))
    endereco = perfil.get('endereco', '')
    cidade = perfil.get('cidade', '')
    telefone = perfil.get('telefone', '')
    instagram = perfil.get('instagram', '')
    facebook = perfil.get('facebook', '')
    site_url = perfil.get('site_url', perfil.get('url', ''))

    verificacao = {
        'timestamp': datetime.now().isoformat(),
        'nome_verificado': nome,
        'cidade': cidade,
        'gbp': verificar_gbp(nome, endereco, cidade, telefone),
    }

    # Redes sociais
    verificacao['redes_sociais'] = {}
    if instagram:
        verificacao['redes_sociais']['instagram'] = verificar_instagram(instagram)
    if facebook:
        verificacao['redes_sociais']['facebook'] = verificar_facebook(facebook)

    # Site
    if site_url:
        verificacao['site'] = verificar_url_existe(site_url)

    # Plataformas externas
    verificacao['plataformas'] = verificar_plataformas(nome, cidade)

    # Discrepancias
    verificacao['discrepancias'] = gerar_discrepancias(verificacao, perfil)
    verificacao['qtd_discrepancias'] = len(verificacao['discrepancias'])

    return verificacao


def gerar_discrepancias(verificacao, perfil):
    """
    Compara dados autodeclarados vs verificados e gera discrepancias.
    """
    discrepancias = []
    gbp = verificacao.get('gbp', {})

    if gbp.get('status') != 'encontrado':
        return discrepancias

    # 1. Comparar rating
    rating_real = gbp.get('rating')
    rating_declarado = perfil.get('avaliacoes_nota', perfil.get('nota_media', ''))
    if rating_real is not None and rating_declarado:
        nota_map = {
            'não sei': None,
            '3.0 ou menos': (0, 3.0),
            '3.1-4.0': (3.1, 4.0),
            '4.1-4.5': (4.1, 4.5),
            '4.6-5.0': (4.6, 5.0),
        }
        faixa = nota_map.get(rating_declarado)
        if faixa:
            if rating_real < faixa[0] or rating_real > faixa[1]:
                discrepancias.append({
                    'criterio': 'nota_media',
                    'autodeclarado': rating_declarado,
                    'verificado': f'{rating_real:.1f}',
                    'severidade': 'alta',
                    'resumo': f'Nota real {rating_real:.1f} difere da faixa autodeclarada "{rating_declarado}"',
                })

    # 2. Comparar quantidade de reviews
    reviews_real = gbp.get('total_reviews')
    reviews_declarado = perfil.get('avaliacoes_google', '')
    if reviews_real is not None and reviews_declarado:
        qtd_map = {
            'nenhuma': (0, 0),
            '1-10': (1, 10),
            '11-30': (11, 30),
            '31-100': (31, 100),
            '100+': (100, 999999),
        }
        faixa = qtd_map.get(reviews_declarado)
        if faixa:
            if reviews_real < faixa[0] or reviews_real > faixa[1]:
                discrepancias.append({
                    'criterio': 'quantidade_avaliacoes',
                    'autodeclarado': reviews_declarado,
                    'verificado': str(reviews_real),
                    'severidade': 'media',
                    'resumo': f'Reviews reais ({reviews_real}) fora da faixa autodeclarada "{reviews_declarado}"',
                })

    # 3. GBP inexistente segundo cliente mas encontrado
    tem_gbp_declarado = perfil.get('tem_google_business', False)
    if isinstance(tem_gbp_declarado, str):
        tem_gbp_declarado = tem_gbp_declarado.lower() == 'sim'
    if not tem_gbp_declarado and gbp.get('status') == 'encontrado':
        discrepancias.append({
            'criterio': 'gbp_existencia',
            'autodeclarado': 'Nao tem GBP',
            'verificado': 'GBP encontrado no Google Maps',
            'severidade': 'baixa',
            'resumo': 'Cliente disse nao ter GBP mas encontramos no Google Maps',
        })

    # 4. GBP completo autodeclarado vs real
    completo_declarado = perfil.get('gbp_completa', False)
    if isinstance(completo_declarado, str):
        completo_declarado = completo_declarado.lower() == 'sim'
    if completo_declarado:
        itens_faltando = []
        if not gbp.get('tem_fotos'):
            itens_faltando.append('fotos')
        if not gbp.get('tem_horario'):
            itens_faltando.append('horario')
        if not gbp.get('tem_descricao'):
            itens_faltando.append('descricao')
        if itens_faltando:
            discrepancias.append({
                'criterio': 'gbp_completude',
                'autodeclarado': 'GBP completo',
                'verificado': f'Faltando: {", ".join(itens_faltando)}',
                'severidade': 'alta',
                'resumo': f'Cliente disse GBP completo mas faltam: {", ".join(itens_faltando)}',
            })

    # 5. Telefone confere? (com normalizacao inteligente)
    telefone_real = gbp.get('telefone', '')
    telefone_declarado = perfil.get('telefone', '')
    if telefone_real and telefone_declarado:
        tel_digits = ''.join(filter(str.isdigit, telefone_declarado))
        real_digits = ''.join(filter(str.isdigit, telefone_real))

        if tel_digits and real_digits:
            # Normaliza: remove leading country code (55) e DDD pra comparar apenas numero local
            def normalizar_local(digits):
                s = digits
                if s.startswith('55') and len(s) > 10:
                    s = s[2:]
                if len(s) > 9:
                    s = s[2:]  # remove DDD
                return s.lstrip('0')

            tel_local = normalizar_local(tel_digits)
            real_local = normalizar_local(real_digits)
            tel_8 = tel_digits[-8:]
            real_8 = real_digits[-8:]

            match = (
                tel_digits == real_digits
                or tel_8 == real_8
                or (tel_local and tel_local == real_local)
            )

            if not match:
                discrepancias.append({
                    'criterio': 'telefone',
                    'autodeclarado': telefone_declarado,
                    'verificado': telefone_real,
                    'severidade': 'alta',
                    'resumo': f'Telefone diferente no GBP: declarado {telefone_declarado} vs GBP {telefone_real}',
                })

    return discrepancias


# ─── FUNCAO PARA INTEGRACAO COM DigitalPresenceAuditor ────────────────────────

def merge_verified_data(perfil, verificacao):
    """
    Faz merge dos dados verificados no perfil do cliente.
    Retorna um NOVO perfil com dados verificados sobrescrevendo
    os autodeclarados onde temos verificacao confiavel.
    """
    perfil = dict(perfil)  # copy
    gbp = verificacao.get('gbp', {})
    originais = {}

    if gbp.get('status') == 'encontrado':
        # GBP existe — confirmado
        originais['tem_google_business'] = perfil.get('tem_google_business', '')
        perfil['tem_google_business'] = True
        perfil['gbp_verificado'] = True

        # Rating real
        if gbp.get('rating') is not None:
            originais['avaliacoes_nota'] = perfil.get('avaliacoes_nota', '')
            originais['nota_media'] = perfil.get('nota_media', '')
            rating = gbp['rating']
            if rating >= 4.6:
                perfil['avaliacoes_nota'] = '4.6-5.0'
                perfil['nota_media'] = '4.6-5.0'
            elif rating >= 4.1:
                perfil['avaliacoes_nota'] = '4.1-4.5'
                perfil['nota_media'] = '4.1-4.5'
            elif rating >= 3.1:
                perfil['avaliacoes_nota'] = '3.1-4.0'
                perfil['nota_media'] = '3.1-4.0'
            else:
                perfil['avaliacoes_nota'] = '3.0 ou menos'
                perfil['nota_media'] = '3.0 ou menos'

        # Review count real
        if gbp.get('total_reviews') is not None:
            originais['avaliacoes_google'] = perfil.get('avaliacoes_google', '')
            count = gbp['total_reviews']
            if count >= 100:
                perfil['avaliacoes_google'] = '100+'
            elif count >= 31:
                perfil['avaliacoes_google'] = '31-100'
            elif count >= 11:
                perfil['avaliacoes_google'] = '11-30'
            elif count >= 1:
                perfil['avaliacoes_google'] = '1-10'
            else:
                perfil['avaliacoes_google'] = 'nenhuma'

        # GBP completeza real
        completo = True
        if not gbp.get('tem_fotos'):
            completo = False
        if not gbp.get('tem_horario'):
            completo = False
        if not gbp.get('tem_descricao'):
            completo = False
        # website é bonus, nao obrigatorio para completude do GBP
        originais['gbp_completa'] = perfil.get('gbp_completa', '')
        perfil['gbp_completa'] = completo

        # Endereco verificado
        if gbp.get('endereco'):
            originais['endereco'] = perfil.get('endereco', '')
            perfil['endereco'] = gbp['endereco']

        # Telefone verificado (só sobrescreve se for realmente diferente)
        if gbp.get('telefone'):
            tel_atual = ''.join(filter(str.isdigit, perfil.get('telefone', '')))
            tel_api = ''.join(filter(str.isdigit, gbp['telefone']))
            if tel_atual and tel_api and tel_atual[-8:] != tel_api[-8:]:
                originais['telefone'] = perfil.get('telefone', '')
                perfil['telefone'] = gbp['telefone']

        # Review recencia — nao podemos verificar diretamente,
        # mas podemos inferir: se total_reviews > 0, provavelmente tem reviews recentes
        if gbp.get('total_reviews', 0) > 20:
            originais['review_recencia'] = perfil.get('review_recencia', '')
            perfil['review_recencia'] = True

    # Verificar URLs de redes sociais
    redes = verificacao.get('redes_sociais', {})
    if 'instagram' in redes:
        ig = redes['instagram']
        if ig.get('existe') is False:
            originais['instagram_verificado'] = False
    if 'facebook' in redes:
        fb = redes['facebook']
        if fb.get('existe') is False:
            originais['facebook_verificado'] = False

    # Marcar dados que foram alterados pela verificacao
    if originais:
        perfil['_dados_originais'] = originais

    return perfil
