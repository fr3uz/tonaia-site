import os
import io
import base64
from datetime import datetime
from playwright.sync_api import sync_playwright


LOGO_PATH = os.path.join(os.path.dirname(__file__), '..', 'Logo', 'logo_tonaia.png')
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), 'templates', 'relatorio.html')

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


def gerar_relatorio(dados, caminho=None):
    nome = dados.get('nome_cliente', 'Cliente')
    nota = dados.get('nota_final', dados.get('nota', 0))
    data_aud = datetime.now().strftime('%d/%m/%Y às %H:%M')
    cidade = dados.get('cidade', '')
    estado = dados.get('estado', '')
    telefone = dados.get('telefone', '')
    servicos = dados.get('servicos', [])
    detalhes = dados.get('detalhes_site', dados.get('detalhes', []))
    checks = dados.get('checks', {})

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
    }

    # --- Build main content HTML ---
    pages = []

    # PAGE: Cenário + Diagnóstico
    p = '<div class="page-break"></div>'
    p += '<div class="section-title">CENÁRIO ATUAL E DIAGNÓSTICO</div>'
    p += '<div class="section-subtitle">O jeito que as pessoas encontram negócios mudou</div>'
    p += '<div class="p">Antes de apresentar o diagnóstico, é importante entender o que está acontecendo no mercado. O Google, que antes era a porta de entrada para 89% das descobertas online, hoje representa apenas 57%.</div>'
    p += '<div class="p">Hoje, 37% dos consumidores já começam a buscar produtos e serviços diretamente em Inteligência Artificial &mdash; ChatGPT, Perplexity, Gemini. Esse número cresce a cada trimestre.</div>'
    p += '<div class="p">Lá fora, empresas já contratam agências especializadas em otimização para IA e estão investindo pesado nisso. No Brasil, 94% dos negócios locais ainda são invisíveis para essas tecnologias. Quem começa agora sai na frente.</div>'
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
        detalhes.append('Seu site tem o básico, mas podemos deixá-lo imbatível pras IAs')
    p += '<div class="section-subtitle">O que identificamos</div>'
    for d in detalhes:
        p += f'<div class="detail-item">{d}</div>'

    if nota < 4:
        p += f'<div class="p">{nome} precisa de atenção urgente. As IAs têm dificuldade em encontrar informações básicas sobre o negócio.</div>'
    elif nota < 7:
        p += f'<div class="p">{nome} já tem alguns pontos positivos, mas ainda perde clientes porque as IAs não conseguem confirmar informações importantes.</div>'
    else:
        p += f'<div class="p">{nome} está bem posicionado. As IAs conseguem encontrar e entender o negócio. Com monitoramento contínuo, garantimos que essa posição se mantenha.</div>'

    p += '<div class="section-subtitle">Detalhamento dos itens analisados</div>'
    p += '<div class="p-small">Cada item mostra um aspecto analisado. Quanto mais alto, melhor.</div>'
    p += html_metric_cards(checks, mapeamento)
    pages.append(p)

    # PAGE: Ajustes Técnicos
    p = '<div class="page-break"></div>'
    p += '<div class="section-title">AJUSTES TÉCNICOS NECESSÁRIOS</div>'
    p += f'<div class="section-subtitle">O que precisa ser ajustado no negócio de {nome}</div>'
    p += '<div class="p">Identificamos pontos específicos que precisam de intervenção técnica. São ajustes no código do site e nas plataformas que as IAs consultam para recomendar negócios. Nada visível para seus clientes &mdash; mas essencial para ser encontrado.</div>'

    if checks.get('schema_jsonld', {}).get('score', 1) == 0 or checks.get('schema_tipos', {}).get('score', 1) == 0:
        p += '<div class="alert-card">'
        p += '<div class="title">Dados que precisam ser estruturados no código do site:</div>'
        p += '<div class="item">- Identificação do tipo de negócio (LocalBusiness)</div>'
        p += '<div class="item">- Endereço e área de atendimento</div>'
        p += '<div class="item">- Serviços oferecidos</div>'
        p += '</div>'

    if checks.get('contato', {}).get('score', 0) < 3:
        p += '<div class="alert-card">'
        p += '<div class="title">Contatos que precisam ser ajustados:</div>'
        if telefone:
            p += f'<div class="item">- Telefone/WhatsApp ({telefone})</div>'
        else:
            p += '<div class="item">- Telefone ou WhatsApp</div>'
        p += '</div>'

    p += '<div class="section-subtitle">O que precisamos de você para começar</div>'
    p += '<div class="p">Para realizar as configurações e deixar tudo funcionando, vamos precisar de:</div>'
    acessos = [
        ('Acesso de gerente no Google Business Profile', 'Otimizar perfil com serviços, fotos e informações'),
        ('Acesso ao painel do site', 'Instalar o código invisível (ou damos passo a passo)'),
        ('Contato do WhatsApp', 'Alinhar os detalhes e tirar dúvidas'),
        ('Fotos do negócio (se tiver)', 'Incluir no perfil e nas plataformas'),
    ]
    p += html_acessos(acessos)

    p += '<div class="cta-box">'
    p += '<div class="title">E SE EU NÃO SOUBER FAZER ISSO?</div>'
    p += '<div class="desc">Não se preocupe. A TôNaIA faz todo o ajuste para você. Basta dar o acesso de gerente ao GBP que cuidamos do resto.</div>'
    p += '</div>'
    pages.append(p)

    # PAGE: Próximos Passos
    p = '<div class="page-break"></div>'
    p += '<div class="section-title">PRÓXIMOS PASSOS</div>'
    p += '<div class="section-subtitle">Como a TôNaIA resolve isso pra você</div>'
    p += '<div class="p">Resumindo o que entregamos no plano mensal:</div>'
    passos = [
        ('Instalação do código', 'Configuramos o código invisível que as IAs leem no seu site'),
        ('Google Business Profile', 'Otimizamos seu perfil completo com serviços, fotos e informações'),
        ('Foursquare e diretórios', 'Atualizamos seus dados nos lugares que alimentam as IAs'),
        ('Monitoramento semanal', 'Re-auditamos seu negócio toda semana e ajustamos se algo mudar'),
        ('Relatório mensal', 'Você recebe um relatório simples mostrando sua evolução'),
    ]
    p += html_acessos(passos)

    p += '<div class="section-subtitle">Por que é mensal?</div>'
    p += '<div class="p">Diferente do SEO tradicional (que você faz uma vez e pronto), a otimização para IAs exige acompanhamento constante. O ChatGPT, Perplexity e Gemini atualizam seus algoritmos com frequência &mdash; o que funciona hoje pode não funcionar amanhã. Fora isso, novas IAs surgem, suas informações podem ficar desatualizadas, concorrentes podem aparecer na sua frente.</div>'
    p += '<div class="p">Por isso o plano é mensal: estamos sempre de olho, ajustando e garantindo que você continue sendo encontrado. É como um seguro de visibilidade digital.</div>'
    pages.append(p)

    # PAGE: Dados
    p = '<div class="page-break"></div>'
    p += '<div class="section-title">DADOS QUE COMPROVAM</div>'
    p += '<div class="section-subtitle">O tamanho da oportunidade</div>'
    p += '<div class="p">Dados reais que mostram por que investir em visibilidade para IAs agora:</div>'
    stats = [
        ('800M+', 'Usuários ativos do ChatGPT por semana [1]'),
        ('40%', 'Mais visibilidade com conteúdo otimizado para IAs [2]'),
        ('58%', 'Das buscas terminam sem cliques (AI Overviews) [3]'),
        ('4.4x', 'Mais conversões vs SEO tradicional [4]'),
        ('$7.3 Bi', 'Mercado Global de GEO crescendo 34% ao ano [5]'),
        ('89%', 'Das citações do ChatGPT vêm de além da página 2 [6]'),
        ('94%', 'Dos negócios brasileiros são invisíveis para IAs [7]'),
    ]
    p += html_stats(stats)

    p += '<div class="cta-box">'
    p += '<div class="desc" style="font-size:10pt">Enquanto seus concorrentes ignoram, você pode estar na frente. Quem começa agora ganha vantagem de quem já estará lá quando o mercado explodir.</div>'
    p += '</div>'

    p += '<div class="section-subtitle">Planos e investimento</div>'
    p += '<div class="p">Escolha o que faz sentido para seu momento:</div>'
    planos = [
        ('Auditoria Única', 'Grátis', 'Diagnóstico completo + código gerado'),
        ('Mensal', 'R$ 200/mês', 'Tudo instalado + monitoramento semanal'),
        ('Premium', 'R$ 500/mês', 'Site criado do zero + tudo incluso'),
    ]
    p += html_planos(planos)

    p += '<div class="section-subtitle">Formas de pagamento</div>'
    p += '<div class="p">Aceitamos PIX, transferência bancária e cartão de crédito (via link). Para clientes do plano mensal, o pagamento é recorrente via PIX no início de cada mês.</div>'

    p += '<div class="cta-box" style="text-align:center">'
    p += '<div class="title">QUER COMEÇAR? ME CHAMA NO WHATSAPP</div>'
    p += '<div class="desc">Vou explicar como funciona, tirar suas dúvidas e já iniciamos. Sem compromisso.</div>'
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

    # --- Render PDF via Playwright ---
    buf = io.BytesIO()

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
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
        browser.close()

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
