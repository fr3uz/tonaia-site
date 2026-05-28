import json
import os
import re
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'questionarios.json')

def carregar():
    if not os.path.exists(DB_PATH):
        return []
    with open(DB_PATH, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except:
            return []

def salvar(dados):
    db = carregar()
    db.append(dados)
    with open(DB_PATH, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

CAMPO_QA = [
    {
        'id': 'nome_negocio',
        'pergunta': 'Qual o nome EXATO do seu negócio? (como aparece no Google Business)',
        'tipo': 'text',
        'obrigatorio': True,
        'check': None,
    },
    {
        'id': 'site_url',
        'pergunta': 'Qual o URL do seu site? (se tiver)',
        'tipo': 'text',
        'obrigatorio': False,
        'check': None,
    },
    {
        'id': 'categoria',
        'pergunta': 'Qual a categoria do seu negócio? (ex: estética, cabeleireiro, dentista, advogado)',
        'tipo': 'text',
        'obrigatorio': True,
        'check': None,
    },
    {
        'id': 'servicos',
        'pergunta': 'Quais serviços/produtos você oferece? (liste separando por vírgula)',
        'tipo': 'text',
        'obrigatorio': True,
        'check': None,
    },
    {
        'id': 'cidade',
        'pergunta': 'Qual cidade e estado você atende? (ex: Curitiba, PR)',
        'tipo': 'text',
        'obrigatorio': True,
        'check': None,
    },
    {
        'id': 'bairros',
        'pergunta': 'Quais bairros ou regiões você atende? (ex: Batel, Centro, Água Verde)',
        'tipo': 'text',
        'obrigatorio': False,
        'check': None,
    },
    {
        'id': 'endereco',
        'pergunta': 'Qual seu endereço completo? (rua, número, bairro, cidade)',
        'tipo': 'text',
        'obrigatorio': True,
        'check': None,
    },
    {
        'id': 'telefone',
        'pergunta': 'Qual seu telefone/WhatsApp? (com DDD)',
        'tipo': 'text',
        'obrigatorio': True,
        'check': lambda v: bool(re.search(r'\(\d{2}\)\s?\d', v)),
    },
    {
        'id': 'tem_whatsapp_business',
        'pergunta': 'Você usa WhatsApp Business?',
        'tipo': 'boolean',
        'obrigatorio': False,
        'check': None,
    },
    {
        'id': 'instagram',
        'pergunta': 'Qual seu @ do Instagram? (se tiver)',
        'tipo': 'text',
        'obrigatorio': False,
        'check': None,
    },
    {
        'id': 'facebook',
        'pergunta': 'Tem página no Facebook? (URL ou nome)',
        'tipo': 'text',
        'obrigatorio': False,
        'check': None,
    },
    {
        'id': 'tem_google_business',
        'pergunta': 'Você tem Google Business Profile (antigo Google Meu Negócio)?',
        'tipo': 'boolean',
        'obrigatorio': False,
        'check': None,
    },
    {
        'id': 'tem_site_wix',
        'pergunta': 'Seu site é no Wix, WordPress, ou outra plataforma?',
        'tipo': 'text',
        'obrigatorio': False,
        'check': None,
    },
    {
        'id': 'avaliacoes_google',
        'pergunta': 'Quantas avaliações você tem no Google? (estimativa)',
        'tipo': 'select',
        'opcoes': ['nenhuma', '1-10', '11-30', '31-100', '100+'],
        'obrigatorio': True,
        'check': None,
    },
    {
        'id': 'nota_media',
        'pergunta': 'Qual sua nota média no Google?',
        'tipo': 'select',
        'opcoes': ['não sei', '3.0 ou menos', '3.1-4.0', '4.1-4.5', '4.6-5.0'],
        'obrigatorio': True,
        'check': None,
    },
    {
        'id': 'responde_avaliacoes',
        'pergunta': 'Você responde as avaliações dos clientes?',
        'tipo': 'boolean',
        'obrigatorio': False,
        'check': None,
    },
    {
        'id': 'review_recencia',
        'pergunta': 'Você recebeu avaliações novas nos últimos 3 meses?',
        'tipo': 'boolean',
        'obrigatorio': False,
        'check': None,
    },
    {
        'id': 'gbp_completa',
        'pergunta': 'Seu Google Business Profile está 100% completo? (fotos, descrição, serviços, atributos, horários)',
        'tipo': 'boolean',
        'obrigatorio': False,
        'check': None,
    },
    {
        'id': 'gbp_posts',
        'pergunta': 'Você publica posts no Google Business Profile regularmente?',
        'tipo': 'boolean',
        'obrigatorio': False,
        'check': None,
    },
    {
        'id': 'foursquare',
        'pergunta': 'Sua empresa está cadastrada no Foursquare? (ChatGPT usa Foursquare como principal fonte)',
        'tipo': 'boolean',
        'obrigatorio': False,
        'check': None,
    },
    {
        'id': 'outras_plataformas',
        'pergunta': 'Quais outras plataformas sua empresa aparece? (ex: Yelp, Apple Maps, Bing Places, TripAdvisor)',
        'tipo': 'text',
        'obrigatorio': False,
        'check': None,
    },
    {
        'id': 'concorrentes',
        'pergunta': 'Quem são seus principais concorrentes? (nomes dos negócios)',
        'tipo': 'text',
        'obrigatorio': False,
        'check': None,
    },
    {
        'id': 'diferenciais',
        'pergunta': 'O que torna seu negócio diferente dos concorrentes?',
        'tipo': 'textarea',
        'obrigatorio': False,
        'check': None,
    },
    {
        'id': 'publico_alvo',
        'pergunta': 'Qual seu público-alvo? (ex: mulheres 25-50, empresários, atletas)',
        'tipo': 'text',
        'obrigatorio': False,
        'check': None,
    },
    {
        'id': 'horario_funcionamento',
        'pergunta': 'Qual seu horário de funcionamento? (ex: seg-sex 9-18, sáb 9-13)',
        'tipo': 'text',
        'obrigatorio': False,
        'check': None,
    },
    {
        'id': 'duvidas_comuns',
        'pergunta': 'Quais as 3 perguntas que seus clientes mais fazem antes de contratar?',
        'tipo': 'textarea',
        'obrigatorio': False,
        'check': None,
    },
    {
        'id': 'imagens_trabalhos',
        'pergunta': 'Você tem fotos dos seus trabalhos para colocar no perfil?',
        'tipo': 'boolean',
        'obrigatorio': False,
        'check': None,
    },
    {
        'id': 'observacoes',
        'pergunta': 'Algo mais que você acha importante sabermos? (restrições, preferências)',
        'tipo': 'textarea',
        'obrigatorio': False,
        'check': None,
    },
]


def validar_respostas(respostas):
    erros = []
    for campo in CAMPO_QA:
        if campo.get('obrigatorio'):
            val = respostas.get(campo['id'], '').strip()
            if not val:
                erros.append(f'{campo["pergunta"]} é obrigatório')
                continue
            if campo.get('check') and not campo['check'](val):
                erros.append(f'{campo["pergunta"]} parece inválido')
    return erros


def formatar_questionario(respostas):
    return {
        'respondido_em': datetime.now().isoformat(),
        'respostas': respostas,
        'servicos_lista': [s.strip() for s in respostas.get('servicos', '').split(',') if s.strip()],
    }


def gerar_recomendacoes(respostas):
    recs = []
    avaliacoes = respostas.get('avaliacoes_google', '')
    nota = respostas.get('nota_media', '')

    if avaliacoes in ('nenhuma', '1-10'):
        recs.append('urgente: precisa de avaliações no Google — IAs priorizam negócios com 20+ reviews')
    elif avaliacoes in ('11-30',):
        recs.append('avaliacoes em crescimento — continue pedindo reviews. Meta: 150+ para ser citado por IAs como ChatGPT')

    if nota in ('não sei', '3.0 ou menos', '3.1-4.0'):
        recs.append('nota baixa ou sem monitoramento — precisa melhorar reputação online')

    if not respostas.get('tem_google_business'):
        recs.append('CRÍTICO: sem Google Business Profile — IAs não encontram seu negócio')
    else:
        if not respostas.get('gbp_completa'):
            recs.append('GBP incompleto — preencha fotos, descrição, serviços, atributos e horários. GBP completo representa ~32% dos fatores de ranqueamento em IA')
        if not respostas.get('gbp_posts'):
            recs.append('publique posts semanais no GBP — IAs interpretam atividade como sinal de negócio ativo')
        if not respostas.get('fotos_gbp') or respostas.get('fotos_gbp', '') in ('nenhuma', 'menos de 5'):
            recs.append('adicione fotos ao GBP — ideal 20+ fotos com dados de localização')

    if not respostas.get('instagram') and not respostas.get('facebook'):
        recs.append('sem redes sociais — IAs têm menos fontes para confirmar seus dados')

    if not respostas.get('review_recencia'):
        recs.append('sem avaliações recentes — IAs favorecem negócios com reviews nos últimos 3 meses')

    if not respostas.get('foursquare'):
        recs.append('cadastre-se no Foursquare — ChatGPT usa Foursquare como ~70% da fonte de dados locais')

    outras = respostas.get('outras_plataformas', '')
    plataformas_essenciais = ['yelp', 'apple', 'bing', 'tripadvisor']
    encontradas = sum(1 for p in plataformas_essenciais if p in outras.lower())
    if encontradas < 2:
        recs.append('pouca presença em diretórios — cadastre-se em Yelp, Apple Maps e Bing Places para consistência de dados')

    if not respostas.get('site_url'):
        recs.append('sem site — IAs tem menos fontes de informacao. GBP + redes sociais ajudam mas um site melhora muito a visibilidade')

    servicos = respostas.get('servicos', '')
    if len(servicos.split(',')) < 2:
        recs.append('poucos serviços listados — detalhe mais serviços para as IAs indexarem')

    duvidas = respostas.get('duvidas_comuns', '')
    if len(duvidas.split('\n')) < 2:
        recs.append('adicione perguntas frequentes — FAQ é o formato preferido das IAs para extrair respostas')

    return recs


def gerar_perfil_geo(respostas):
    return {
        'nome': respostas.get('nome_negocio', ''),
        'url': respostas.get('site_url', ''),
        'categoria': respostas.get('categoria', ''),
        'servicos': [s.strip() for s in respostas.get('servicos', '').split(',') if s.strip()],
        'cidade': respostas.get('cidade', ''),
        'endereco': respostas.get('endereco', ''),
        'telefone': respostas.get('telefone', ''),
        'redes': {
            'instagram': respostas.get('instagram', ''),
            'facebook': respostas.get('facebook', ''),
        },
        'avaliacoes': {
            'quantidade': respostas.get('avaliacoes_google', ''),
            'nota': respostas.get('nota_media', ''),
            'recencia': respostas.get('review_recencia', ''),
        },
        'gbp': {
            'tem': respostas.get('tem_google_business', ''),
            'completo': respostas.get('gbp_completa', ''),
            'posts': respostas.get('gbp_posts', ''),
        },
        'plataformas': {
            'foursquare': respostas.get('foursquare', ''),
            'outras': respostas.get('outras_plataformas', ''),
        },
        'concorrentes': [c.strip() for c in respostas.get('concorrentes', '').split(',') if c.strip()],
        'publico_alvo': respostas.get('publico_alvo', ''),
        'horario': respostas.get('horario_funcionamento', ''),
        'faq': [q.strip() for q in respostas.get('duvidas_comuns', '').split('\n') if q.strip()],
    }
