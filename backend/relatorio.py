import os
import io
import base64
import math
import atexit
from datetime import datetime
from playwright.sync_api import sync_playwright

LOGO_PATH = os.path.join(os.path.dirname(__file__), '..', 'Logo', 'logo_tonaia.png')
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), 'templates', 'relatorio.html')

_browser = None
_playwright = None

def _get_browser():
    global _browser, _playwright
    if _browser is None:
        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch()
        atexit.register(_cleanup)
    return _browser

def _cleanup():
    global _browser, _playwright
    if _browser:
        _browser.close()
        _browser = None
    if _playwright:
        _playwright.stop()
        _playwright = None

FONTES = {
    1: 'OpenAI, dados de uso do ChatGPT, 2026. 800M usuarios semanais.',
    2: 'Search Engine Journal, "GEO Case Studies", 2025.',
    3: 'Gartner, "AI Overviews Impact on Search", 2026.',
    4: 'Forbes, "Generative Engine Optimization ROI", 2025.',
    5: 'MarketsandMarkets, "GEO Market Report", 2026. $7.3B.',
    6: 'CEI, "ChatGPT Citation Analysis", 2025.',
    7: 'DataReportal / TonaIA, "Invisibilidade Digital BR", 2026.',
}

SCORE_VERDE = '#00B894'
SCORE_AMARELO = '#FDCB6E'
SCORE_VERMELHO = '#FF6B6B'


def cores_nota(nota):
    if nota >= 7:
        return SCORE_VERDE, 'ÓTIMO', 'Seu negócio está bem posicionado para ser encontrado por IAs'
    elif nota >= 4:
        return SCORE_AMARELO, 'ATENÇÃO', 'Seu negócio corre o risco de não ser encontrado por IAs'
    else:
        return SCORE_VERMELHO, 'CRÍTICO', 'Seu negócio está invisível para Inteligência Artificial'


CATEGORIAS_GEO = [
    ('fundacao_tecnica', 'Fundação Técnica', '#6C5CE7'),
    ('dados_estruturados', 'Dados Estruturados', '#00B894'),
    ('arquitetura_conteudo', 'Arquitetura de Conteúdo', '#FDCB6E'),
    ('autoridade_entidade', 'Autoridade da Entidade', '#E17055'),
    ('sinais_confianca', 'Sinais de Confiança', '#0984E3'),
    ('preparacao_ia', 'Preparação para IA', '#FD79A8'),
    ('autoridade_externa', 'Autoridade Externa', '#00CEC9'),
]


def html_geo_breakdown(categorias):
    if not categorias:
        return ''
    h = '<div class="section-subtitle">Detalhamento por categoria</div>'
    for key, label, cor in CATEGORIAS_GEO:
        cat = categorias.get(key, {})
        nota = cat.get('nota', 0)
        pct = (nota / 10) * 100
        h += f'<div class="cat-row">'
        h += f'<span class="cat-label">{label}</span>'
        h += f'<div class="cat-bar-wrap"><div class="cat-bar-fill" style="width:{pct}%;background:{cor}"></div></div>'
        h += f'<span class="cat-score" style="color:{cor}">{nota:.1f}</span>'
        h += '</div>'
    h += '</div>'

    h += '''
    <style>
    .cat-row { display:flex; align-items:center; gap:10px; margin:4px 0; padding:4px 0; page-break-inside:avoid; }
    .cat-label { font-size:9pt; font-weight:600; min-width:110px; color:#333; }
    .cat-bar-wrap { flex:1; height:8px; background:#e8e8f0; border-radius:4px; overflow:hidden; }
    .cat-bar-fill { height:100%; border-radius:4px; }
    .cat-score { font-size:10pt; font-weight:700; min-width:24px; text-align:right; }
    </style>
    '''
    return h


def html_trend_bars():
    trends = [
        ('Google', 57, '#FDCB6E'),
        ('IAs (ChatGPT, Gemini, Perplexity)', 37, '#6C5CE7'),
        ('Negócios brasileiros invisíveis', 94, '#FF6B6B'),
    ]
    h = '<div class="trend-group">'
    for label, pct, cor in trends:
        h += f'<div class="trend-row">'
        h += f'<span class="trend-label">{label}</span>'
        h += f'<span class="trend-bar-wrap"><div class="trend-bar-fill" style="width:{pct}%;background:{cor}"></div></span>'
        h += f'<span class="trend-pct" style="color:{cor}">{pct}%</span>'
        h += '</div>'
    h += '</div>'
    return h


def html_metric_cards(checks, mapeamento):
    h = ''
    for chave, config in mapeamento.items():
        if chave in checks:
            v = checks[chave]
            if isinstance(v, dict) and 'score' in v:
                pct = min(v['score'] / v['max'], 1) if v['max'] > 0 else 0
                if pct >= 0.8:
                    cor = SCORE_VERDE
                elif pct >= 0.4:
                    cor = SCORE_AMARELO
                else:
                    cor = SCORE_VERMELHO
                h += f'<div class="metric-card" style="border-left-color:{cor}">'
                h += f'<div class="metric-header">'
                h += f'<span class="metric-label">{config["label"]}</span>'
                h += f'<span class="metric-score" style="color:{cor}">{v["score"]}/{v["max"]}</span>'
                h += '</div>'
                h += f'<div class="bar-bg"><div class="bar-fill" style="width:{pct*100}%;background:{cor}"></div></div>'
                h += f'<div class="metric-desc">{config["explica"]}</div>'
                h += '</div>'
    return h


def html_stats(stats):
    h = ''
    for valor, desc in stats:
        h += f'<div class="stat-item">'
        h += f'<span class="stat-val">{valor}</span>'
        h += f'<span class="stat-desc">{desc}</span>'
        h += '</div>'
    return h


def html_planos(planos):
    h = ''
    for nome, preco, desc in planos:
        h += f'<div class="plano-item">'
        h += f'<span class="plano-name">{nome}</span>'
        h += f'<span class="plano-price">{preco}</span>'
        h += f'<span class="plano-desc">{desc}</span>'
        h += '</div>'
    return h


def html_acessos(acessos):
    h = ''
    for tit, desc in acessos:
        h += f'<div class="access-item"><div class="title">{tit}</div><div class="desc">{desc}</div></div>'
    return h


def html_fontes():
    h = ''
    for k in sorted(FONTES):
        h += f'<div class="source-item">{FONTES[k]}</div>'
    return h


def html_radar_chart(categorias, use_local=True):
    if not categorias:
        return ''
    if use_local:
        dims = [
            ('gbp_qualidade', 'GBP\nQualidade', '#00B894'),
            ('reputacao', 'Reputacao', '#FDCB6E'),
            ('entidade', 'Entidade', '#6C5CE7'),
            ('presenca_externa', 'Presenca\nExterna', '#0984E3'),
            ('sinais_sociais', 'Sinais\nSociais', '#E17055'),
        ]
    else:
        dims = [
            ('fundacao_tecnica', 'Fundacao\nTecnica', '#6C5CE7'),
            ('dados_estruturados', 'Dados\nEstrut.', '#00B894'),
            ('arquitetura_conteudo', 'Arquitetura\nConteudo', '#FDCB6E'),
            ('autoridade_entidade', 'Autoridade\nEntidade', '#E17055'),
            ('sinais_confianca', 'Sinais\nConfianca', '#0984E3'),
            ('preparacao_ia', 'Prep.\nIA', '#FD79A8'),
            ('autoridade_externa', 'Autoridade\nExterna', '#00CEC9'),
        ]

    n = len(dims)
    cx, cy = 165, 145
    r = 110
    size = 340

    scores = []
    for key, _, _ in dims:
        cat = categorias.get(key, {})
        scores.append(cat.get('nota', 0))

    svg = f'<svg width="{size}" height="{size+10}" viewBox="0 0 {size} {size+10}" style="display:block;margin:8px auto;font-family:Segoe UI,Arial,sans-serif">'

    for level in [0.25, 0.5, 0.75, 1.0]:
        pts = []
        for i in range(n):
            angle = -90 + (360 / n) * i
            rad = math.radians(angle)
            x = cx + r * level * math.cos(rad)
            y = cy + r * level * math.sin(rad)
            pts.append(f'{x:.1f},{y:.1f}')
        svg += f'<polygon points="{" ".join(pts)}" fill="none" stroke="#ddd" stroke-width="0.5"/>'

    for i in range(n):
        angle = -90 + (360 / n) * i
        rad = math.radians(angle)
        x = cx + r * math.cos(rad)
        y = cy + r * math.sin(rad)
        lx = cx + (r + 30) * math.cos(rad)
        ly = cy + (r + 30) * math.sin(rad)
        svg += f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#ddd" stroke-width="0.5"/>'
        anchor = 'middle'
        if -15 < angle < 15 or angle > 165 or angle < -165:
            anchor = 'middle'
        elif angle > 15 and angle < 165:
            anchor = 'start' if angle < 90 else 'end'
        else:
            anchor = 'end' if angle > -165 else 'start'
        label = dims[i][1].replace('\n', ' ')
        svg += f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" font-size="7" fill="{dims[i][2]}" font-weight="600">{label}</text>'

    data_pts = []
    for i in range(n):
        angle = -90 + (360 / n) * i
        rad = math.radians(angle)
        pct = scores[i] / 10.0
        x = cx + r * pct * math.cos(rad)
        y = cy + r * pct * math.sin(rad)
        data_pts.append(f'{x:.1f},{y:.1f}')
    svg += f'<polygon points="{" ".join(data_pts)}" fill="rgba(108,92,231,0.15)" stroke="#6C5CE7" stroke-width="1.5"/>'

    for i in range(n):
        angle = -90 + (360 / n) * i
        rad = math.radians(angle)
        pct = scores[i] / 10.0
        x = cx + r * pct * math.cos(rad)
        y = cy + r * pct * math.sin(rad)
        svg += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#6C5CE7"/>'
        sx = cx + (r + 14) * pct * math.cos(rad)
        sy = cy + (r + 14) * pct * math.sin(rad)
        svg += f'<text x="{sx:.1f}" y="{sy:.1f}" text-anchor="middle" font-size="8" fill="#333" font-weight="700">{scores[i]:.1f}</text>'

    svg += '</svg>'
    return svg


def html_verificacao_automatica(dados):
    v = dados.get('verificacao_automatica', {})
    if not v:
        return ''

    h = '<div class="page-break"></div>'
    h += '<div class="section-title">VERIFICACAO AUTOMATICA</div>'
    h += '<div class="p">Dados verificados em tempo real via Google Places API, confrontados com as informacoes autodeclaradas pelo cliente.</div>'

    gbp = v.get('gbp', {})
    if gbp.get('status') == 'encontrado':
        d = gbp.get('dados', {})
        h += '<div class="section-subtitle">Google Business Profile — Dados Reais</div>'
        h += '<table class="verif-table">'
        for label, key in [
            ('Nome no GBP', 'nome_gbp'),
            ('Endereco', 'endereco'),
            ('Rating Real', 'rating'),
            ('Total Reviews', 'total_reviews'),
            ('Fotos no Perfil', 'tem_fotos'),
            ('Horario Cadastrado', 'tem_horario'),
            ('Descricao do Negocio', 'tem_descricao'),
            ('Website Vinculado', 'tem_website'),
        ]:
            val = d.get(key, '-')
            if isinstance(val, bool):
                val = 'Sim' if val else 'Nao'
            elif key == 'rating' and val != '-':
                val = f'{val} / 5.0'
            h += f'<tr><td class="verif-label">{label}</td><td class="verif-val">{val}</td></tr>'
        h += '</table>'

    comp = v.get('comparacao', {})
    if comp:
        h += '<div class="section-subtitle">Comparacao: Cliente Disse vs Verificado</div>'
        h += '<table class="comp-table"><tr><th>Criterio</th><th>Autodeclarado</th><th>Verificado</th></tr>'
        for key, val in comp.items():
            nomes = {'nota_media': 'Nota Media', 'quantidade_avaliacoes': 'Qtd Reviews', 'gbp_completo': 'GBP Completo'}
            sev = ''
            if val['autodeclarado'] != val['verificado']:
                sev = '<span style="color:#e74c3c"> ⚠</span>'
            h += f'<tr><td>{nomes.get(key, key)}</td><td>{val["autodeclarado"]}</td><td>{val["verificado"]}{sev}</td></tr>'
        h += '</table>'

    disc = dados.get('discrepancias', [])
    if disc:
        h += '<div class="section-subtitle">Discrepancias Identificadas</div>'
        for d in disc:
            sev = d.get('severidade', 'info')
            cor = '#e74c3c' if sev == 'alta' else '#f39c12'
            h += f'<div class="disc-item" style="border-left:3px solid {cor}">'
            h += f'<span class="disc-sev" style="color:{cor}">[{sev.upper()}]</span>'
            h += f'<span class="disc-msg">{d.get("resumo", d.get("mensagem", ""))}</span>'
            h += '</div>'

    return h


def gerar_relatorio(dados, caminho=None, modo='completo'):
    nome = dados.get('nome_cliente', 'Cliente')
    nota = dados.get('nota_final', dados.get('nota', 0))
    data_aud = datetime.now().strftime('%d/%m/%Y às %H:%M')
    cidade = dados.get('cidade', '')
    estado = dados.get('estado', '')
    telefone = dados.get('telefone', '')
    servicos = dados.get('servicos', [])
    detalhes = dados.get('detalhes_site', dados.get('detalhes', []))
    checks = dados.get('checks', {})
    categorias = dados.get('categorias', {})

    local = f'{cidade}{" - " + estado if estado else ""}' if cidade else ''

    cor_score, label_score, msg_principal = cores_nota(nota)

    mapeamento = {
        'schema_jsonld': {'label': 'Código invisível para IAs', 'explica': 'Se seu site tem o código que as IAs leem'},
        'schema_tipos': {'label': 'Tipos de dados corretos', 'explica': 'Se os códigos são do tipo certo'},
        'descricao': {'label': 'Descrição do negócio', 'explica': 'Texto que as IAs podem ler sobre você'},
        'servicos': {'label': 'Serviços listados', 'explica': 'Se seus serviços estão organizados'},
        'contato': {'label': 'Informações de contato', 'explica': 'Se telefone e endereço estão visíveis'},
        'social': {'label': 'Redes sociais', 'explica': 'Presença em Instagram e Facebook'},
        'tem_localbusiness': {'label': 'Tipo LocalBusiness', 'explica': 'Código que identifica seu negócio'},
        'tem_product': {'label': 'Schema de Produto', 'explica': 'Código que descreve seus produtos'},
        'tem_service': {'label': 'Schema de Serviço', 'explica': 'Código que lista seus serviços'},
        'tem_avaliacoes': {'label': 'Avaliações', 'explica': 'Schema de avaliações e reviews'},
        'robots_txt': {'label': 'Robots.txt', 'explica': 'Arquivo que controla crawlers'},
        'llms_txt': {'label': 'llms.txt', 'explica': 'Arquivo de instruções para IAs'},
        'ai_crawlers': {'label': 'Crawlers de IA permitidos', 'explica': 'Se GPTBot, ClaudeBot etc. podem acessar'},
        'https': {'label': 'HTTPS ativo', 'explica': 'Conexão segura'},
        'crawlability': {'label': 'Crawlabilidade', 'explica': 'Se o site pode ser indexado'},
        'titulo': {'label': 'Título da página', 'explica': 'Tag title otimizada'},
        'meta_descricao': {'label': 'Meta description', 'explica': 'Descrição visível nos buscadores'},
        'abertura_definicao': {'label': 'Definição inicial', 'explica': 'Primeiros caracteres definem o negócio'},
        'h2_perguntas': {'label': 'Perguntas em H2', 'explica': 'Formato Q&A que IAs preferem'},
        'faq': {'label': 'Bloco FAQ', 'explica': 'Perguntas frequentes no conteúdo'},
        'tabelas_listas': {'label': 'Tabelas e listas', 'explica': 'Dados estruturados visualmente'},
        'entidades_mencionadas': {'label': 'Entidades mencionadas', 'explica': 'CNPJ, endereço, horário etc.'},
        'quantidade_texto': {'label': 'Quantidade de texto', 'explica': 'Volume de conteúdo textual'},
        'nap_consistencia': {'label': 'Consistência NAP', 'explica': 'Nome, endereço, telefone consistentes'},
        'gbp_presenca': {'label': 'Presença GBP', 'explica': 'Link para Google Business Profile'},
        'whatsapp': {'label': 'WhatsApp no site', 'explica': 'Link direto para WhatsApp'},
        'redes_sociais': {'label': 'Redes sociais', 'explica': 'Presença em Instagram, Facebook, LinkedIn'},
        'eeat': {'label': 'Sinais E-E-A-T', 'explica': 'Experiência, autoridade, confiança'},
        'pagina_sobre': {'label': 'Página Sobre', 'explica': 'Seção quem somos / sobre'},
        'avaliacoes': {'label': 'Avaliações', 'explica': 'Depoimentos e reviews'},
        'atualizacao': {'label': 'Atualização', 'explica': 'Conteúdo recente'},
        'llms_txt_conteudo': {'label': 'llms.txt com conteúdo', 'explica': 'Arquivo com instruções para IAs'},
        'ai_txt': {'label': 'ai.txt presente', 'explica': 'Arquivo de controle para AI crawlers'},
        'llms_json': {'label': 'llms.json', 'explica': 'Configuração avançada para IAs'},
        'optout_treinamento': {'label': 'Opt-out de treinamento', 'explica': 'Controle de uso para treinamento de IA'},
        'sitemap': {'label': 'Sitemap', 'explica': 'Mapa do site para crawlers'},
        'backlinks': {'label': 'Backlinks', 'explica': 'Links externos apontando para o site'},
        'diretorios': {'label': 'Diretórios', 'explica': 'Presença em diretórios online'},
        'mencoes_externas': {'label': 'Menções externas', 'explica': 'Citações em outras plataformas'},
        'product_schema': {'label': 'Schema de Produto', 'explica': 'Schema Product para rich snippets de e-commerce'},
        'offer_price': {'label': 'Preço no Schema', 'explica': 'Preço estruturado no schema Offer/Product'},
        'aggregate_rating': {'label': 'AggregateRating', 'explica': 'Schema de avaliação agregada (estrelas nos resultados)'},
        'multi_product': {'label': 'Múltiplos produtos', 'explica': 'Quantidade de produtos com schema estruturado'},
        'endereco': {'label': 'Endereço', 'explica': 'Endereço completo do negócio'},
        'telefone': {'label': 'Telefone', 'explica': 'Telefone/WhatsApp do negócio'},
    }

    # --- Build main content HTML ---
    pages = []

    if modo == 'gratis':
        p = '<div class="page-break"></div>'
        p += '<div class="section-title">SEU DIAGNÓSTICO RÁPIDO</div>'
        p += '<div class="section-subtitle">O jeito que as pessoas encontram negócios mudou</div>'
        p += '<div class="p">O Google, que antes era a porta de entrada para <strong>89%</strong> das descobertas online, hoje representa apenas <strong>57%</strong>. <strong>37%</strong> dos consumidores já começam a buscar produtos direto em IAs — ChatGPT, Gemini, Perplexity. Esse número cresce a cada trimestre.</div>'
        p += '<div class="section-subtitle" style="margin-top:10px">Onde as pessoas buscam hoje</div>'
        p += html_trend_bars()

        p += f'<div class="score-card" style="border-left-color:{cor_score}">'
        p += f'<div class="score-card-num" style="color:{cor_score}">{nota}/10</div>'
        p += f'<div class="score-card-info">'
        p += f'<div class="score-card-label" style="color:{cor_score}">{label_score}</div>'
        p += f'<div class="score-card-msg">{msg_principal}</div>'
        p += '</div></div>'

        p += '<div class="section-subtitle">Oportunidade de mercado</div>'
        stats = [
            ('800M+', 'Usuários ativos do ChatGPT por semana [1]'),
            ('58%', 'Das buscas terminam sem cliques (AI Overviews) [3]'),
            ('$7.3 Bi', 'Mercado Global de GEO crescendo 34% ao ano [5]'),
            ('94%', 'Dos negócios brasileiros são invisíveis para IAs [7]'),
        ]
        p += html_stats(stats)

        p += '<div class="cta-box" style="text-align:center;background:var(--accent)">'
        p += '<div class="title" style="font-size:13pt">QUER O DIAGNÓSTICO COMPLETO?</div>'
        p += '<div class="desc" style="margin:8px 0">Este relatório é apenas um resumo. O diagnóstico completo inclui:</div>'
        p += '<div class="desc" style="font-size:9pt">✅ Plano de ação personalizado</div>'
        p += '<div class="desc" style="font-size:9pt">✅ Análise detalhada por categoria</div>'
        p += '<div class="desc" style="font-size:9pt">✅ Comparação com concorrentes</div>'
        p += '<div class="desc" style="font-size:9pt">✅ Radar chart de desempenho</div>'
        p += '<div class="desc" style="margin:10px 0;font-size:11pt;font-weight:700">Por apenas R$ 97</div>'
        p += f'<div class="desc" style="margin-top:8px"><a href="https://wa.me/554196380298?text=Oi!%20Quero%20o%20diagn%C3%B3stico%20completo%20de%20R%2497%20para%20{nome}" style="color:#fff;text-decoration:underline">Fale conosco no WhatsApp</a></div>'
        p += '</div>'
        pages.append(p)
    else:
        # PAGE: Cenário + Diagnóstico
        p = '<div class="page-break"></div>'
        p += '<div class="section-title">CENÁRIO ATUAL E DIAGNÓSTICO</div>'
        p += '<div class="section-subtitle">O jeito que as pessoas encontram negócios mudou</div>'
        p += '<div class="p">Antes de apresentar o diagnóstico, é importante entender o que está acontecendo no mercado. O Google, que antes era a porta de entrada para 89% das descobertas online, hoje representa apenas 57%.</div>'
        p += '<div class="p">Hoje, 37% dos consumidores já começam a buscar produtos e serviços diretamente em Inteligência Artificial &mdash; ChatGPT, Perplexity, Gemini. Esse número cresce a cada trimestre.</div>'
        p += '<div class="p">No Brasil, 94% dos negócios locais ainda são invisíveis para essas tecnologias. Quem começa agora sai na frente.</div>'
        p += '<div class="section-subtitle" style="margin-top:10px">Onde as pessoas buscam hoje</div>'
        p += html_trend_bars()
        p += f'<div class="section-subtitle">O que encontramos no negócio de {nome}</div>'
        p += f'<div class="p">Realizamos uma análise detalhada na presença digital de {nome} para descobrir se as IAs conseguem encontrar e recomendar seu negócio.</div>'

        p += f'<div class="score-card" style="border-left-color:{cor_score}">'
        p += f'<div class="score-card-num" style="color:{cor_score}">{nota}/10</div>'
        p += f'<div class="score-card-info">'
        p += f'<div class="score-card-label" style="color:{cor_score}">{label_score}</div>'
        p += f'<div class="score-card-msg">{msg_principal}</div>'
        p += '</div></div>'

        if not detalhes:
            detalhes.append('Seu negocio tem o basico, mas podemos deixar otimizado pras IAs')
        p += '<div class="section-subtitle">O que identificamos</div>'
        for d in detalhes:
            p += f'<div class="detail-item">{d}</div>'

        if nota < 4:
            p += f'<div class="p">{nome} precisa de atencao urgente. As IAs tem dificuldade em encontrar informacoes basicas sobre o negocio.</div>'
        elif nota < 7:
            p += f'<div class="p">{nome} ja tem alguns pontos positivos, mas ainda perde clientes porque as IAs nao conseguem confirmar informacoes importantes.</div>'
        else:
            p += f'<div class="p">{nome} esta bem posicionado. As IAs conseguem encontrar e entender o negocio. Com monitoramento continuo, garantimos que essa posicao se mantenha.</div>'

        if categorias:
            tem_site = any(k in categorias for k in ['fundacao_tecnica', 'dados_estruturados'])
            p += '<div class="section-subtitle">Dashboard Visual</div>'
            p += html_radar_chart(categorias, use_local=not tem_site)

        if categorias:
            p += '<div class="section-subtitle">Breakdown por categoria</div>'
            p += '<div class="p-small">Cada categoria contribui com um peso diferente para a nota final.</div>'
            p += html_geo_breakdown(categorias)

        p += '<div class="section-subtitle">Detalhamento dos itens analisados</div>'
        p += '<div class="p-small">Cada item mostra um aspecto analisado. Quanto mais alto, melhor.</div>'
        p += html_metric_cards(checks, mapeamento)
        pages.append(p)

        pag_verif = html_verificacao_automatica(dados)
        if pag_verif:
            pages.append(pag_verif)

        p = '<div class="page-break"></div>'
        p += '<div class="section-title">PLANO DE AÇÃO PRIORIZADO</div>'
        p += f'<div class="section-subtitle">O que precisa ser feito para {nome}</div>'
        p += '<div class="p">Abaixo, as ações priorizadas por impacto e facilidade de implementação.</div>'

        plano_acoes = dados.get('detalhes', [])
        for i, acao in enumerate(plano_acoes, 1):
            p += f'<div class="detail-item">{i}. {acao}</div>'

        p += '<div class="cta-box">'
        p += '<div class="title">PRECISA DE AJUDA PARA IMPLEMENTAR?</div>'
        p += '<div class="desc">A TôNaIA faz tudo para você. Basta escolher o plano e damos inicio.</div>'
        p += '</div>'
        pages.append(p)

        p = '<div class="page-break"></div>'
        p += '<div class="section-title">PRÓXIMOS PASSOS</div>'
        p += '<div class="section-subtitle">Como a TôNaIA resolve isso pra você</div>'
        passos = [
            ('Instalação do código', 'Configuramos o código invisível que as IAs leem no seu site'),
            ('Google Business Profile', 'Otimizamos seu perfil completo com servicos, fotos e informacoes'),
            ('Foursquare e diretórios', 'Atualizamos seus dados nos lugares que alimentam as IAs'),
            ('Monitoramento semanal', 'Re-auditamos seu negocio toda semana e ajustamos se algo mudar'),
            ('Relatório mensal', 'Voce recebe um relatorio simples mostrando sua evolucao'),
        ]
        p += html_acessos(passos)

        p += '<div class="section-subtitle">Por que é mensal?</div>'
        p += '<div class="p">Diferente do SEO tradicional, a otimizacao para IAs exige acompanhamento constante. O ChatGPT, Perplexity e Gemini atualizam seus algoritmos com frequencia. E como um seguro de visibilidade digital.</div>'
        pages.append(p)

        p = '<div class="page-break"></div>'
        p += '<div class="section-title">DADOS QUE COMPROVAM</div>'
        p += '<div class="section-subtitle">O tamanho da oportunidade</div>'
        stats = [
            ('800M+', 'Usuarios ativos do ChatGPT por semana [1]'),
            ('40%', 'Mais visibilidade com conteudo otimizado para IAs [2]'),
            ('58%', 'Das buscas terminam sem cliques (AI Overviews) [3]'),
            ('4.4x', 'Mais conversoes vs SEO tradicional [4]'),
            ('$7.3 Bi', 'Mercado Global de GEO crescendo 34% ao ano [5]'),
            ('89%', 'Das citacoes do ChatGPT vem de alem da pagina 2 [6]'),
            ('94%', 'Dos negocios brasileiros sao invisiveis para IAs [7]'),
        ]
        p += html_stats(stats)

        p += '<div class="section-subtitle">Planos e investimento</div>'
        p += '<div class="p">Escolha o que faz sentido para seu momento:</div>'
        planos = [
            ('Diagnóstico', 'R$ 97', 'Auditoria completa + relatorio PDF + plano de acao'),
            ('Basico', 'R$ 340/mes', 'Monitoramento semanal + ajustes + suporte WhatsApp'),
            ('Premium', 'R$ 597/mes', 'Landing page otimizada + schema + concorrentes'),
        ]
        p += html_planos(planos)

        p += '<div class="cta-box" style="text-align:center">'
        p += '<div class="title">QUER COMECAR? ME CHAMA NO WHATSAPP</div>'
        p += '<div class="desc">Vou explicar como funciona, tirar suas duvidas e ja iniciamos. Sem compromisso.</div>'
        p += '<div class="title" style="margin-top:6px">(41) 99999-0000</div>'
        p += '</div>'
        pages.append(p)

    main_content = '\n'.join(pages)

    # --- Logo base64 ---
    logo_src = ''
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, 'rb') as f:
            logo_b64 = base64.b64encode(f.read()).decode()
        logo_src = f'data:image/png;base64,{logo_b64}'

    # --- Load and fill template ---
    with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
        html = f.read()

    html = html.replace('{LOGO_SRC}', logo_src)
    html = html.replace('{CLIENTE_NOME}', nome)
    html = html.replace('{CLIENTE_LOCAL}', local)
    html = html.replace('{SCORE_BG}', cor_score)
    html = html.replace('{NOTA}', str(nota))
    html = html.replace('{SCORE_LABEL}', label_score)
    html = html.replace('{STATUS_MSG}', msg_principal)
    html = html.replace('{DATA_AUD}', data_aud)
    html = html.replace('{MAIN_CONTENT}', main_content)
    html = html.replace('{FONTES}', html_fontes())

    # --- Render PDF via Playwright (browser cacheado) ---
    browser = _get_browser()
    page = browser.new_page()
    page.set_content(html, wait_until='networkidle')
    pdf_bytes = page.pdf(
        format='A4',
        margin={'top': '18mm', 'bottom': '22mm', 'left': '16mm', 'right': '16mm'},
        display_header_footer=True,
        header_template='<div style="width:100%;height:4px;background:#6C5CE7"></div>',
        footer_template='<div style="font-size:7pt;color:#999;text-align:center;width:100%;font-family:Segoe UI,Arial,sans-serif">TôNaIA  |  ' + nome + '  |  Pág <span class="pageNumber"></span></div>',
        print_background=True,
    )
    page.close()

    if caminho:
        with open(caminho, 'wb') as f:
            f.write(pdf_bytes)
        return caminho
    else:
        return pdf_bytes


if __name__ == '__main__':
    dados_teste = {
        'nota_final': 3.5,
        'nota_site': 2.0,
        'nota_gbp': 5.0,
        'nome_cliente': 'Clinica Dra. Yohanna Frois',
        'url': 'https://drayohannafrois.wixsite.com/harmonizacao',
        'cidade': 'Curitiba',
        'estado': 'PR',
        'telefone': '(41) 99999-0000',
        'endereco': 'Av. Batel, 1500',
        'categoria': 'esteticista',
        'servicos': ['Harmonizacao Facial', 'Aplicacao de Botox', 'Preenchimento Labial'],
        'detalhes_site': [
            'Seu site nao esta falando a lingua das IAs (ChatGPT, Gemini, Perplexity)',
            'As IAs nao identificam seu negocio como uma empresa local',
            'As IAs nao encontram seus servicos ou produtos',
            'As IAs nao conseguem achar seus contatos (WhatsApp, telefone, endereco)'
        ],
        'checks': {
            'schema_jsonld': {'score': 0, 'max': 1},
            'schema_tipos': {'score': 0, 'max': 1},
            'descricao': {'score': 6, 'max': 8},
            'servicos': {'score': 3, 'max': 5},
            'contato': {'score': 1, 'max': 6},
            'social': {'score': 1, 'max': 3.5}
        }
    }
    caminho_pdf = os.path.join(os.path.dirname(__file__), '..', 'relatorios', 'relatorio_teste.pdf')
    gerar_relatorio(dados_teste, caminho_pdf)
    print(f'Relatorio gerado: {caminho_pdf}')
