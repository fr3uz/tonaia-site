from flask import Flask, request, jsonify, send_from_directory, Response, session, redirect
from flask_cors import CORS
from dotenv import load_dotenv
from functools import wraps
import hashlib
import secrets

load_dotenv()

from auditor import SiteAuditor
from gbp_auditor import GBPAuditor
from auditor_engine import GeoAuditor, DigitalPresenceAuditor
from relatorio import gerar_relatorio
from prospector import buscar_estabelecimentos, salvar_leads, registrar_prospeccao, listar_leads, resumo, exportar_csv
from questionario import CAMPO_QA, validar_respostas, formatar_questionario, salvar as salvar_questionario, gerar_recomendacoes, gerar_perfil_geo
import sqlite3
import json
import os
from datetime import datetime, timedelta

app = Flask(__name__, static_folder='../frontend', static_url_path='')
app.secret_key = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32))
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=12)
CORS(app)

# ─── AUTH ─────────────────────────────────────────────────────────────────────
APP_PASSWORD = os.getenv('APP_PASSWORD', 'tonaia2026')
tokens_ativos = {}

def gerar_token():
    return secrets.token_hex(32)

def requer_auth(f):
    @wraps(f)
    def decorada(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token or token not in tokens_ativos:
            return jsonify({'erro': 'Nao autorizado'}), 401
        return f(*args, **kwargs)
    return decorada

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    data = request.json
    senha = data.get('senha', '')
    if senha != APP_PASSWORD:
        return jsonify({'erro': 'Senha incorreta'}), 401
    token = gerar_token()
    tokens_ativos[token] = datetime.now().isoformat()
    return jsonify({'token': token, 'status': 'ok'})

@app.route('/api/quick-check', methods=['POST'])
def quick_check():
    data = request.json
    nome = data.get('nome', data.get('nome_negocio', '')).strip()
    cidade = data.get('cidade', '').strip()
    whatsapp = data.get('whatsapp', data.get('telefone', '')).strip()

    if not nome or not cidade:
        return jsonify({'erro': 'Nome e cidade sao obrigatorios'}), 400

    from verificador import verificar_gbp, verificar_plataformas
    from multi_llm_checker import query_google_search

    gbp = verificar_gbp(nome, '', cidade, whatsapp)
    plataformas = verificar_plataformas(nome, cidade)
    busca = query_google_search(nome, cidade)

    score = 0
    max_score = 10
    detalhes = []

    if gbp.get('status') == 'encontrado':
        score += 3
        detalhes.append('Negocio encontrado no Google Maps')
        rating = gbp.get('rating')
        if rating is not None and rating >= 4.0:
            score += 1.5
            detalhes.append(f'Nota {rating}/5 no Google')
        elif rating is not None:
            score += 1
            detalhes.append(f'Nota {rating}/5 no Google')
        total_reviews = gbp.get('total_reviews', 0) or 0
        if total_reviews >= 10:
            score += 1
            detalhes.append(f'{total_reviews} avaliacoes no Google')
        if gbp.get('tem_horario'):
            score += 0.5
        if gbp.get('tem_fotos'):
            score += 0.5
    else:
        detalhes.append('Negocio nao encontrado no Google Maps')

    plataformas_detectadas = plataformas.get('busca_google', {}).get('plataformas_detectadas', [])
    if plataformas_detectadas:
        score += min(len(plataformas_detectadas) * 0.5, 2)
        detalhes.append(f'Presente em {len(plataformas_detectadas)} plataformas')

    if busca.get('knowledge_panel'):
        score += 1
        detalhes.append('Painel de conhecimento do Google identificado')

    # Salvar lead se WhatsApp foi fornecido
    lead_salvo = False
    if whatsapp:
        try:
            conn = get_db()
            existing = conn.execute('SELECT id FROM clientes WHERE telefone = ?', (whatsapp,)).fetchone()
            if not existing:
                conn.execute('''
                    INSERT INTO clientes (nome, telefone, status, created_at)
                    VALUES (?, ?, 'lead', ?)
                ''', (nome, whatsapp, datetime.now().isoformat()))
                conn.commit()
            conn.close()
            lead_salvo = True
        except:
            pass

    nota = round((score / max_score) * 10, 1)

    return jsonify({
        'nota': min(nota, 10),
        'score': score,
        'max_score': max_score,
        'detalhes': detalhes,
        'gbp_encontrado': gbp.get('status') == 'encontrado',
        'lead_salvo': lead_salvo,
    })


@app.route('/api/auth/check', methods=['GET'])
def auth_check():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if token and token in tokens_ativos:
        return jsonify({'valido': True})
    return jsonify({'valido': False}), 401


@app.route('/questionario')
def questionario_publico():
    return send_from_directory('../frontend', 'questionario_publico.html')


@app.route('/api/questionario/publico/salvar', methods=['POST'])
def questionario_publico_salvar():
    data = request.json
    respostas = data.get('respostas', {})
    cliente = data.get('cliente', 'anonimo')

    erros = validar_respostas(respostas)
    if erros:
        return jsonify({'erro': 'Campos invalidos', 'detalhes': erros}), 400

    formatted = formatar_questionario(respostas)
    perfil = gerar_perfil_geo(respostas)
    recomendacoes = gerar_recomendacoes(respostas)

    conn = get_db()
    cur = conn.execute('''
        INSERT INTO questionarios (cliente, respostas, perfil, created_at)
        VALUES (?, ?, ?, ?)
    ''', (cliente, json.dumps(formatted), json.dumps(perfil),
          datetime.now().isoformat()))
    conn.commit()
    conn.close()

    return jsonify({
        'status': 'ok',
        'recomendacoes': recomendacoes,
        'perfil': perfil,
    })

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'tonaia.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS auditorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_cliente TEXT,
            url TEXT,
            tipo TEXT,
            nota REAL,
            resultado TEXT,
            created_at TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            telefone TEXT,
            email TEXT,
            site_url TEXT,
            cidade TEXT,
            plano TEXT,
            status TEXT DEFAULT 'lead',
            created_at TEXT
        )
    ''')
    try:
        conn.execute('ALTER TABLE clientes ADD COLUMN cidade TEXT')
    except:
        pass
    conn.execute('''
        CREATE TABLE IF NOT EXISTS questionarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT,
            respostas TEXT,
            perfil TEXT,
            created_at TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS concorrentes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            cidade TEXT,
            nota REAL DEFAULT 0,
            detalhes TEXT,
            gbp_encontrado INTEGER DEFAULT 0,
            data_verificacao TEXT,
            created_at TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS alertas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            mensagem TEXT,
            concorrente_id INTEGER,
            lida INTEGER DEFAULT 0,
            created_at TEXT
        )
    ''')
    try:
        conn.execute('ALTER TABLE clientes ADD COLUMN agencia_id INTEGER')
    except:
        pass
    conn.execute('''
        CREATE TABLE IF NOT EXISTS agencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            logo_url TEXT,
            cor_primaria TEXT DEFAULT '#6C5CE7',
            whatsapp TEXT,
            email TEXT,
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()


init_db()


@app.route('/')
def index():
    return send_from_directory('../frontend', 'index.html')

@app.route('/site')
def site_publico():
    return send_from_directory('../docs', 'index.html')


# ─── AUDITORIA HERDADA (Site + GBP básica) ───────────────────────────────────

@app.route('/api/auditar/site', methods=['POST'])
@requer_auth
def auditar_site():
    data = request.json
    url = data.get('url', '')
    nome = data.get('nome_cliente', 'anônimo')
    if not url:
        return jsonify({'erro': 'URL é obrigatória'}), 400
    auditor = SiteAuditor(url)
    resultado = auditor.audit()
    conn = get_db()
    conn.execute('''
        INSERT INTO auditorias (nome_cliente, url, tipo, nota, resultado, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (nome, url, 'site', resultado.get('nota', 0), json.dumps(resultado), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify(resultado)


@app.route('/api/auditar/gbp', methods=['POST'])
@requer_auth
def auditar_gbp():
    data = request.json
    nome = data.get('nome', '')
    endereco = data.get('endereco', '')
    telefone = data.get('telefone', '')
    categoria = data.get('categoria', '')
    if not nome:
        return jsonify({'erro': 'Nome é obrigatório'}), 400
    auditor = GBPAuditor(nome, endereco, telefone, categoria)
    resultado = auditor.audit()
    conn = get_db()
    conn.execute('''
        INSERT INTO auditorias (nome_cliente, url, tipo, nota, resultado, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (nome, f'GBP: {nome}', 'gbp', resultado.get('nota', 0), json.dumps(resultado), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify(resultado)


@app.route('/api/auditar/completo', methods=['POST'])
@requer_auth
def auditar_completo():
    data = request.json
    site_url = data.get('url', '')
    nome = data.get('nome_cliente', 'anônimo')
    gbp_data = {
        'nome': data.get('nome_cliente', ''),
        'endereco': data.get('endereco', ''),
        'telefone': data.get('telefone', ''),
        'categoria': data.get('categoria', '')
    }

    resultado_site = {'nota': 0, 'checks': {}}
    if site_url:
        auditor = SiteAuditor(site_url)
        resultado_site = auditor.audit()

    resultado_gbp = {'nota': 0, 'checks': {}}
    if gbp_data['nome']:
        auditor = GBPAuditor(**gbp_data)
        resultado_gbp = auditor.audit()

    nota_site = resultado_site.get('nota', 0) if site_url else 0
    nota_gbp = resultado_gbp.get('nota', 0) if gbp_data['nome'] else 0

    pesos = {'site': 0.6, 'gbp': 0.4}
    if not site_url:
        pesos = {'site': 0, 'gbp': 1}
    if not gbp_data['nome']:
        pesos = {'site': 1, 'gbp': 0}

    nota_final = round((nota_site * pesos['site'] + nota_gbp * pesos['gbp']), 1)

    resultado = {
        'nota_final': nota_final,
        'nota_site': nota_site,
        'nota_gbp': nota_gbp,
        'detalhes_site': resultado_site.get('detalhes', []),
        'detalhes_gbp': resultado_gbp.get('detalhes', []),
        'tipos_schema': resultado_site.get('tipos_schema', []),
        'url': site_url or 'sem site',
        'nome_cliente': nome,
        'checks': resultado_site.get('checks', {}),
    }

    conn = get_db()
    conn.execute('''
        INSERT INTO auditorias (nome_cliente, url, tipo, nota, resultado, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (nome, site_url or f'GBP: {nome}', 'completo', nota_final,
          json.dumps(resultado), datetime.now().isoformat()))
    conn.commit()
    conn.close()

    return jsonify(resultado)


# ─── AUDITORIA DE PRESENCA DIGITAL (funciona com/sem site) ─────────────────

@app.route('/api/presenca/auditar', methods=['POST'])
@requer_auth
def presenca_auditar():
    data = request.json
    perfil = data.get('perfil', data)

    if not perfil.get('nome_negocio') and not perfil.get('nome'):
        return jsonify({'erro': 'Nome do negocio e obrigatorio'}), 400

    auditor = DigitalPresenceAuditor(perfil)
    resultado = auditor.run()
    resultado['nome_cliente'] = perfil.get('nome_negocio', perfil.get('nome', 'anônimo'))

    # Salvar auditoria
    conn = get_db()
    conn.execute('''
        INSERT INTO auditorias (nome_cliente, url, tipo, nota, resultado, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (resultado['nome_cliente'], perfil.get('site_url', 'sem-site'),
          'presenca', resultado.get('nota_final', 0),
          json.dumps(resultado), datetime.now().isoformat()))
    conn.commit()
    conn.close()

    return jsonify(resultado)


# ─── NOVA AUDITORIA GEO ──────────────────────────────────────────────────────

@app.route('/api/geo/auditar', methods=['POST'])
@requer_auth
def geo_auditar():
    data = request.json
    url = data.get('url', '')
    nome = data.get('nome_cliente', 'anônimo')
    questionario_id = data.get('questionario_id')

    questionario = None
    if questionario_id:
        conn = get_db()
        row = conn.execute('SELECT * FROM questionarios WHERE id = ?',
                           (questionario_id,)).fetchone()
        conn.close()
        if row:
            questionario = json.loads(row['respostas'])

    if not url:
        resultado = {
            'nota_final': 0,
            'erro': 'URL é obrigatória',
            'detalhes': ['URL do site é necessária para auditoria GEO'],
            'categorias': {}
        }
        return jsonify(resultado)

    auditor = GeoAuditor(url, questionario)
    resultado = auditor.run()
    resultado['nome_cliente'] = nome

    conn = get_db()
    conn.execute('''
        INSERT INTO auditorias (nome_cliente, url, tipo, nota, resultado, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (nome, url, 'geo', resultado.get('nota_final', 0),
          json.dumps(resultado), datetime.now().isoformat()))
    conn.commit()
    conn.close()

    return jsonify(resultado)


# ─── QUESTIONÁRIO ─────────────────────────────────────────────────────────────

@app.route('/api/questionario/campos', methods=['GET'])
def questionario_campos():
    campos_json = []
    for c in CAMPO_QA:
        cj = {k: v for k, v in c.items() if k != 'check'}
        campos_json.append(cj)
    return jsonify(campos_json)


@app.route('/api/questionario/salvar', methods=['POST'])
@requer_auth
def questionario_salvar():
    data = request.json
    respostas = data.get('respostas', {})
    cliente = data.get('cliente', 'anônimo')

    erros = validar_respostas(respostas)
    if erros:
        return jsonify({'erro': 'Campos inválidos', 'detalhes': erros}), 400

    formatted = formatar_questionario(respostas)
    perfil = gerar_perfil_geo(respostas)
    recomendacoes = gerar_recomendacoes(respostas)

    conn = get_db()
    cur = conn.execute('''
        INSERT INTO questionarios (cliente, respostas, perfil, created_at)
        VALUES (?, ?, ?, ?)
    ''', (cliente, json.dumps(formatted), json.dumps(perfil),
          datetime.now().isoformat()))
    conn.commit()
    qid = cur.lastrowid
    conn.close()

    salvar_questionario(formatted)

    return jsonify({
        'id': qid,
        'status': 'ok',
        'recomendacoes': recomendacoes,
        'perfil': perfil,
    })


# ─── HISTÓRICO / BACKUP ──────────────────────────────────────────────────────

@app.route('/api/historico', methods=['GET'])
@requer_auth
def historico():
    conn = get_db()
    tipo = request.args.get('tipo', '')
    sql = 'SELECT id, nome_cliente, url, tipo, nota, created_at FROM auditorias'
    params = []
    if tipo:
        sql += ' WHERE tipo = ?'
        params.append(tipo)
    sql += ' ORDER BY created_at DESC LIMIT 50'
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/backup', methods=['GET'])
@requer_auth
def backup():
    conn = get_db()
    rows = conn.execute('SELECT * FROM auditorias').fetchall()
    clientes = conn.execute('SELECT * FROM clientes').fetchall()
    quests = conn.execute('SELECT * FROM questionarios').fetchall()
    conn.close()
    backup_data = {
        'data': datetime.now().isoformat(),
        'auditorias': [dict(r) for r in rows],
        'clientes': [dict(r) for r in clientes],
        'questionarios': [dict(r) for r in quests],
    }
    caminho = os.path.join(os.path.dirname(__file__), '..', 'cerebro', 'backup.json')
    with open(caminho, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2)
    return jsonify({'status': 'ok', 'caminho': caminho})


# ─── RELATÓRIO PDF ───────────────────────────────────────────────────────────

@app.route('/api/relatorio-pdf', methods=['POST'])
@requer_auth
def gerar_relatorio_pdf():
    data = request.json
    auditoria_id = data.get('auditoria_id')
    nome_cliente = data.get('nome_cliente', 'Cliente')
    url = data.get('url', '')
    modo = data.get('modo', 'completo')

    if auditoria_id:
        conn = get_db()
        row = conn.execute('SELECT * FROM auditorias WHERE id = ?',
                           (auditoria_id,)).fetchone()
        conn.close()
        if row:
            dados = json.loads(row['resultado'])
            dados['nome_cliente'] = row['nome_cliente']
        else:
            dados = {'nota': 0, 'nome_cliente': nome_cliente, 'url': url,
                     'detalhes': ['Auditoria não encontrada']}
    else:
        dados = {
            'nota_final': data.get('nota', 0),
            'nota_site': data.get('nota_site', 0),
            'nota_gbp': data.get('nota_gbp', 0),
            'nome_cliente': nome_cliente,
            'url': url,
            'telefone': data.get('telefone', ''),
            'endereco': data.get('endereco', ''),
            'detalhes_site': data.get('detalhes', []),
            'categorias': data.get('categorias', {}),
            'breakdown': data.get('breakdown', {}),
        }

    pdf_bytes = gerar_relatorio(dados, modo=modo)
    return Response(pdf_bytes, mimetype='application/pdf',
                    headers={'Content-Disposition':
                             f'attachment; filename=relatorio_tonaia_{modo}.pdf'})


@app.route('/api/relatorio-gratis', methods=['POST'])
def relatorio_gratis():
    data = request.json
    estado = data.get('estado', 'PR')

    # Modo 1: dados pre-computados (vem do quick-check, sem re-verificar)
    nota_pre = data.get('nota')
    detalhes_pre = data.get('detalhes')
    nome_pre = data.get('nome')
    cidade_pre = data.get('cidade')

    if nota_pre is not None and detalhes_pre and nome_pre and cidade_pre:
        dados = {
            'nome_cliente': nome_pre,
            'cidade': cidade_pre,
            'estado': estado,
            'nota_final': nota_pre,
            'detalhes': detalhes_pre,
        }
        pdf_bytes = gerar_relatorio(dados, modo='gratis')
        return Response(pdf_bytes, mimetype='application/pdf',
                        headers={'Content-Disposition':
                                 'attachment; filename=relatorio_gratuito_tonaia.pdf'})

    # Modo 2: fallback — precisa rodar verificação
    nome = data.get('nome', data.get('nome_negocio', '')).strip()
    cidade = data.get('cidade', '').strip()
    whatsapp = data.get('whatsapp', data.get('telefone', '')).strip()

    if not nome or not cidade:
        return jsonify({'erro': 'Nome e cidade sao obrigatorios'}), 400

    score = 0
    max_score = 10
    detalhes = []
    gbp = {}
    plataformas = {}
    busca = {}

    try:
        from verificador import verificar_gbp, verificar_plataformas
        from multi_llm_checker import query_google_search
        gbp = verificar_gbp(nome, '', cidade, whatsapp)
        plataformas = verificar_plataformas(nome, cidade)
        busca = query_google_search(nome, cidade)
    except Exception:
        detalhes.append('Verificacao temporariamente indisponivel')

    if gbp.get('status') == 'encontrado':
        score += 3
        detalhes.append('Negocio encontrado no Google Maps')
        rating = gbp.get('rating')
        if rating is not None and rating >= 4.0:
            score += 1.5
            detalhes.append(f'Nota {rating}/5 no Google')
        elif rating is not None:
            score += 1
            detalhes.append(f'Nota {rating}/5 no Google')
        total_reviews = gbp.get('total_reviews', 0) or 0
        if total_reviews >= 10:
            score += 1
            detalhes.append(f'{total_reviews} avaliacoes no Google')
        if gbp.get('tem_horario'):
            score += 0.5
        if gbp.get('tem_fotos'):
            score += 0.5
    else:
        detalhes.append('Negocio nao encontrado no Google Maps')

    plataformas_detectadas = plataformas.get('busca_google', {}).get('plataformas_detectadas', [])
    if plataformas_detectadas:
        score += min(len(plataformas_detectadas) * 0.5, 2)
        detalhes.append(f'Presente em {len(plataformas_detectadas)} plataformas')

    if busca.get('knowledge_panel'):
        score += 1
        detalhes.append('Painel de conhecimento do Google identificado')

    nota = round((score / max_score) * 10, 1)
    nota = min(nota, 10)

    dados = {
        'nome_cliente': nome,
        'cidade': cidade,
        'estado': estado,
        'nota_final': nota,
        'detalhes': detalhes,
    }

    pdf_bytes = gerar_relatorio(dados, modo='gratis')
    return Response(pdf_bytes, mimetype='application/pdf',
                    headers={'Content-Disposition':
                             'attachment; filename=relatorio_gratuito_tonaia.pdf'})


# ─── PROSPECÇÃO ──────────────────────────────────────────────────────────────

@app.route('/api/prospectar', methods=['POST'])
@requer_auth
def prospectar():
    data = request.json
    nicho = data.get('nicho', '').strip()
    cidade = data.get('cidade', '').strip()
    max_res = int(data.get('max_resultados', 20))
    if not nicho or not cidade:
        return jsonify({'erro': 'nicho e cidade são obrigatórios'}), 400
    try:
        leads = buscar_estabelecimentos(nicho, cidade, max_res)
        salvos = salvar_leads(leads)
        registrar_prospeccao(nicho, cidade, len(leads))
        return jsonify({'encontrados': len(leads), 'salvos': salvos, 'leads': leads})
    except ValueError as e:
        return jsonify({'erro': str(e)}), 400
    except PermissionError as e:
        return jsonify({'erro': str(e)}), 403
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@app.route('/api/leads', methods=['GET'])
@requer_auth
def leads_listar():
    categoria = request.args.get('categoria', '')
    cidade = request.args.get('cidade', '')
    com_telefone = request.args.get('com_telefone', '')
    leads = listar_leads(
        categoria=categoria or None,
        cidade=cidade or None,
        com_telefone=bool(com_telefone),
    )
    return jsonify(leads)


@app.route('/api/leads/resumo', methods=['GET'])
@requer_auth
def leads_resumo():
    return jsonify(resumo())


@app.route('/api/leads/exportar', methods=['GET'])
@requer_auth
def leads_exportar():
    caminho = os.path.join(os.path.dirname(__file__), '..', 'data',
                           'leads_export.csv')
    exportar_csv(caminho)
    return send_from_directory(
        os.path.join(os.path.dirname(__file__), '..', 'data'),
        'leads_export.csv', as_attachment=True)


# ─── CONCORRENTES ────────────────────────────────────────────────────────────

from concorrentes import (
    adicionar_concorrente, listar_concorrentes, remover_concorrente,
    verificar_concorrentes, comparar_scores, listar_alertas,
    marcar_alerta_lida, executar_monitoramento
)


@app.route('/api/concorrentes/<int:cliente_id>', methods=['GET'])
@requer_auth
def api_listar_concorrentes(cliente_id):
    return jsonify(listar_concorrentes(cliente_id))


@app.route('/api/concorrentes/adicionar', methods=['POST'])
@requer_auth
def api_adicionar_concorrente():
    data = request.json
    cliente_id = data.get('cliente_id')
    nome = data.get('nome', '').strip()
    cidade = data.get('cidade', '').strip()
    if not cliente_id or not nome:
        return jsonify({'erro': 'cliente_id e nome obrigatórios'}), 400
    id_ = adicionar_concorrente(cliente_id, nome, cidade)
    return jsonify({'id': id_, 'status': 'ok'})


@app.route('/api/concorrentes/<int:concorrente_id>', methods=['DELETE'])
@requer_auth
def api_remover_concorrente(concorrente_id):
    remover_concorrente(concorrente_id)
    return jsonify({'status': 'ok'})


@app.route('/api/concorrentes/verificar/<int:cliente_id>', methods=['POST'])
@requer_auth
def api_verificar_concorrentes(cliente_id):
    try:
        result = verificar_concorrentes(cliente_id)
    except Exception as e:
        result = {'erro': str(e), 'concorrentes': []}
    return jsonify(result)


@app.route('/api/concorrentes/comparar/<int:cliente_id>', methods=['GET'])
@requer_auth
def api_comparar_scores(cliente_id):
    try:
        result = comparar_scores(cliente_id)
    except Exception as e:
        result = {'erro': str(e), 'cliente_nota': 0, 'concorrentes': [], 'alerta': None}
    return jsonify(result)


@app.route('/api/alertas', methods=['GET'])
@requer_auth
def api_listar_alertas():
    cliente_id = request.args.get('cliente_id')
    nao_lidas = request.args.get('nao_lidas') == '1'
    alertas = listar_alertas(cliente_id=int(cliente_id) if cliente_id else None,
                             apenas_nao_lidas=nao_lidas)
    return jsonify(alertas)


@app.route('/api/alertas/<int:alerta_id>/lida', methods=['POST'])
@requer_auth
def api_marcar_alerta_lida(alerta_id):
    marcar_alerta_lida(alerta_id)
    return jsonify({'status': 'ok'})


@app.route('/api/monitoramento/executar', methods=['POST'])
@requer_auth
def api_executar_monitoramento():
    result = executar_monitoramento()
    return jsonify(result)


# ─── AGENCIAS (WHITE-LABEL) ─────────────────────────────────────────────────

@app.route('/api/agencias', methods=['GET'])
@requer_auth
def api_listar_agencias():
    conn = get_db()
    rows = conn.execute('SELECT * FROM agencias ORDER BY created_at DESC').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/agencias', methods=['POST'])
@requer_auth
def api_criar_agencia():
    data = request.json
    nome = data.get('nome', '').strip()
    if not nome:
        return jsonify({'erro': 'Nome da agencia obrigatorio'}), 400
    conn = get_db()
    c = conn.execute(
        'INSERT INTO agencias (nome, logo_url, cor_primaria, whatsapp, email, created_at) VALUES (?, ?, ?, ?, ?, ?)',
        (nome, data.get('logo_url', ''), data.get('cor_primaria', '#6C5CE7'),
         data.get('whatsapp', ''), data.get('email', ''), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    return jsonify({'id': c.lastrowid, 'status': 'ok'})


@app.route('/api/agencias/<int:agencia_id>', methods=['DELETE'])
@requer_auth
def api_remover_agencia(agencia_id):
    conn = get_db()
    conn.execute('DELETE FROM agencias WHERE id=?', (agencia_id,))
    conn.execute('UPDATE clientes SET agencia_id=NULL WHERE agencia_id=?', (agencia_id,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})


@app.route('/api/clientes/<int:cliente_id>/agencia', methods=['PUT'])
@requer_auth
def api_vincular_agencia(cliente_id):
    data = request.json
    agencia_id = data.get('agencia_id')
    conn = get_db()
    conn.execute('UPDATE clientes SET agencia_id=? WHERE id=?', (agencia_id, cliente_id))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})


@app.route('/api/agencias/<int:agencia_id>/clientes', methods=['GET'])
@requer_auth
def api_clientes_agencia(agencia_id):
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM clientes WHERE agencia_id=? ORDER BY created_at DESC', (agencia_id,)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ─── DASHBOARD ───────────────────────────────────────────────────────────────

@app.route('/dashboard')
def dashboard_page():
    return send_from_directory('../frontend', 'dashboard.html')


@app.route('/api/dashboard/clientes')
@requer_auth
def dashboard_clientes():
    conn = get_db()
    rows = conn.execute('''
        SELECT nome_cliente, url, tipo,
               MAX(created_at) as ultima_auditoria,
               COUNT(*) as total_auditorias,
               ROUND(AVG(nota), 1) as media_nota,
               (SELECT nota FROM auditorias a2
                WHERE a2.nome_cliente = auditorias.nome_cliente
                AND a2.url = auditorias.url
                ORDER BY a2.created_at DESC LIMIT 1) as ultima_nota
        FROM auditorias
        WHERE nome_cliente NOT IN ('anônimo', 'sem nome', '')
        GROUP BY nome_cliente, url
        ORDER BY ultima_auditoria DESC
    ''').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/dashboard/evolucao/<path:nome_cliente>')
@requer_auth
def dashboard_evolucao(nome_cliente):
    conn = get_db()
    rows = conn.execute('''
        SELECT id, created_at, nota, tipo
        FROM auditorias
        WHERE nome_cliente = ?
        ORDER BY created_at ASC
    ''', (nome_cliente,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ─── CLIENTES ──────────────────────────────────────────────────────────────────

@app.route('/api/clientes', methods=['GET'])
@requer_auth
def listar_clientes():
    conn = get_db()
    rows = conn.execute('''
        SELECT c.*, q.id as questionario_id, q.created_at as questionario_data
        FROM clientes c
        LEFT JOIN questionarios q ON q.cliente = c.nome
        ORDER BY c.created_at DESC
    ''').fetchall()
    conn.close()
    clientes = []
    seen = {}
    for r in rows:
        d = dict(r)
        nome = d['nome']
        if nome in seen:
            continue
        seen[nome] = True
        clientes.append({
            'id': d['id'],
            'nome': nome,
            'telefone': d['telefone'] or '',
            'site_url': d.get('site_url', '') or '',
            'plano': d.get('plano', '') or '',
            'status': d.get('status', 'lead'),
            'questionario_respondido': d['questionario_id'] is not None,
            'questionario_data': d['questionario_data'] or '',
            'created_at': d['created_at'] or '',
        })
    return jsonify(clientes)


@app.route('/api/clientes', methods=['POST'])
@requer_auth
def criar_cliente():
    data = request.json
    nome = data.get('nome', '').strip()
    if not nome:
        return jsonify({'erro': 'Nome é obrigatório'}), 400

    conn = get_db()
    existing = conn.execute('SELECT id FROM clientes WHERE nome = ?', (nome,)).fetchone()
    if existing:
        conn.close()
        return jsonify({'erro': 'Cliente já existe', 'id': existing['id']}), 409

    conn.execute('''
        INSERT INTO clientes (nome, telefone, email, site_url, plano, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (nome, data.get('telefone', ''), data.get('email', ''),
          data.get('site_url', ''), data.get('plano', ''),
          data.get('status', 'lead'), datetime.now().isoformat()))
    conn.commit()
    novo_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    conn.close()
    return jsonify({'status': 'ok', 'id': novo_id}), 201


@app.route('/api/clientes/<int:cliente_id>', methods=['GET'])
@requer_auth
def detalhe_cliente(cliente_id):
    conn = get_db()
    cli = conn.execute('SELECT * FROM clientes WHERE id = ?', (cliente_id,)).fetchone()
    if not cli:
        conn.close()
        return jsonify({'erro': 'Cliente nao encontrado'}), 404

    cli = dict(cli)
    nome = cli['nome']

    # check questionnaire
    q = conn.execute('''
        SELECT * FROM questionarios WHERE cliente = ? ORDER BY created_at DESC LIMIT 1
    ''', (nome,)).fetchone()

    plano_acao = []
    perfil = None
    questionario_respondido = False

    if q:
        qd = dict(q)
        respostas_raw = json.loads(qd.get('respostas', '{}')) if qd.get('respostas') else {}
        respostas = respostas_raw.get('respostas', respostas_raw)
        perfil_raw = json.loads(qd.get('perfil', '{}')) if qd.get('perfil') else {}
        plano_acao = gerar_recomendacoes(respostas)
        if not plano_acao:
            plano_acao = ['Seu negocio esta bem posicionado! Continue mantendo as informacoes atualizadas e incentivando avaliacoes.']
        perfil = perfil_raw
        questionario_respondido = True

    conn.close()
    return jsonify({
        'cliente': cli,
        'questionario_respondido': questionario_respondido,
        'perfil': perfil,
        'plano_acao': plano_acao,
    })


@app.route('/api/clientes/<int:cliente_id>', methods=['DELETE'])
@requer_auth
def deletar_cliente(cliente_id):
    conn = get_db()
    conn.execute('DELETE FROM clientes WHERE id = ?', (cliente_id,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})


@app.route('/api/clientes/<int:cliente_id>/diagnosticar', methods=['POST'])
@requer_auth
def diagnosticar_cliente(cliente_id):
    conn = get_db()
    cli = conn.execute('SELECT * FROM clientes WHERE id = ?', (cliente_id,)).fetchone()
    if not cli:
        conn.close()
        return jsonify({'erro': 'Cliente nao encontrado'}), 404
    cli = dict(cli)
    nome = cli['nome']

    q = conn.execute('''
        SELECT * FROM questionarios WHERE cliente = ? ORDER BY created_at DESC LIMIT 1
    ''', (nome,)).fetchone()
    conn.close()

    if not q:
        return jsonify({'erro': 'Cliente ainda nao respondeu o questionario'}), 400

    qd = dict(q)
    respostas_raw = json.loads(qd.get('respostas', '{}')) if qd.get('respostas') else {}
    respostas = respostas_raw.get('respostas', respostas_raw)

    auditor = DigitalPresenceAuditor(respostas)
    resultado = auditor.run()

    conn = get_db()
    conn.execute('''
        INSERT INTO auditorias (nome_cliente, url, tipo, nota, resultado, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (nome, respostas.get('site_url', 'questionario'),
          'diagnostico', resultado.get('nota_final', 0),
          json.dumps(resultado), datetime.now().isoformat()))
    conn.commit()
    conn.close()

    return jsonify(resultado)


@app.route('/api/dashboard/estatisticas')
@requer_auth
def dashboard_estatisticas():
    conn = get_db()
    total_clientes = conn.execute('''
        SELECT COUNT(DISTINCT nome_cliente || COALESCE(url, ''))
        FROM auditorias
        WHERE nome_cliente NOT IN ('anônimo', 'sem nome', '')
    ''').fetchone()[0]
    total_auditorias = conn.execute(
        'SELECT COUNT(*) FROM auditorias').fetchone()[0]
    media_geral = conn.execute(
        'SELECT ROUND(AVG(nota), 1) FROM auditorias').fetchone()[0]
    hoje = datetime.now().isoformat()[:10]
    auditorias_hoje = conn.execute(
        'SELECT COUNT(*) FROM auditorias WHERE created_at LIKE ?',
        (f'{hoje}%',)).fetchone()[0]
    top_clientes = conn.execute('''
        SELECT nome_cliente, ROUND(AVG(nota), 1) as media
        FROM auditorias
        WHERE nome_cliente NOT IN ('anônimo', 'sem nome', '')
        GROUP BY nome_cliente
        ORDER BY media DESC LIMIT 5
    ''').fetchall()
    conn.close()
    return jsonify({
        'total_clientes': total_clientes,
        'total_auditorias': total_auditorias,
        'media_geral': media_geral or 0,
        'auditorias_hoje': auditorias_hoje,
        'top_clientes': [dict(r) for r in top_clientes],
    })


# ─── CUSTOS ──────────────────────────────────────────────────────────────────────

from custos import adicionar as custo_adicionar, listar as custo_listar, resumo as custo_resumo, remover as custo_remover, CATEGORIAS_CUSTO, custos_padrao_iniciais

@app.route('/api/custos', methods=['GET'])
@requer_auth
def listar_custos():
    return jsonify(custo_listar())


@app.route('/api/custos/resumo', methods=['GET'])
@requer_auth
def resumo_custos():
    return jsonify(custo_resumo())


@app.route('/api/custos', methods=['POST'])
@requer_auth
def criar_custo():
    data = request.json
    if not data.get('descricao') or data.get('valor') is None:
        return jsonify({'erro': 'descricao e valor sao obrigatorios'}), 400
    result = custo_adicionar(
        data=data.get('data', datetime.now().strftime('%Y-%m-%d')),
        categoria=data.get('categoria', 'Outros'),
        descricao=data['descricao'],
        valor=float(data['valor']),
        tipo=data.get('tipo', 'variavel'),
    )
    return jsonify(result), 201


@app.route('/api/custos/<int:custo_id>', methods=['DELETE'])
@requer_auth
def deletar_custo(custo_id):
    custo_remover(custo_id)
    return jsonify({'status': 'ok'})


@app.route('/api/custos/categorias', methods=['GET'])
def listar_categorias_custo():
    return jsonify(CATEGORIAS_CUSTO)


if __name__ == '__main__':
    init_db()
    try:
        custos_padrao_iniciais()
    except:
        pass
    print('=' * 50)
    print('  TôNaIA - Motor de Auditoria B2AI v2.0 (GEO)')
    print('  Rodando em http://localhost:5000')
    print('=' * 50)
    app.run(host='0.0.0.0', port=5000, debug=True)
