from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
from auditor import SiteAuditor
from gbp_auditor import GBPAuditor
from relatorio import gerar_relatorio
from prospector import buscar_estabelecimentos, salvar_leads, registrar_prospeccao, listar_leads, resumo, exportar_csv
import sqlite3
import json
import os
from datetime import datetime

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

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
            plano TEXT,
            status TEXT DEFAULT 'lead',
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return send_from_directory('../frontend', 'index.html')

@app.route('/api/auditar/site', methods=['POST'])
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
def auditar_completo():
    data = request.json
    site_url = data.get('url', '')
    gbp_data = {
        'nome': data.get('nome_cliente', ''),
        'endereco': data.get('endereco', ''),
        'telefone': data.get('telefone', ''),
        'categoria': data.get('categoria', '')
    }
    nome = data.get('nome_cliente', 'anônimo')

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
        'nome_cliente': nome
    }

    conn = get_db()
    conn.execute('''
        INSERT INTO auditorias (nome_cliente, url, tipo, nota, resultado, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (nome, site_url or f'GBP: {nome}', 'completo', nota_final, json.dumps(resultado), datetime.now().isoformat()))
    conn.commit()
    conn.close()

    return jsonify(resultado)

@app.route('/api/historico', methods=['GET'])
def historico():
    conn = get_db()
    rows = conn.execute('SELECT * FROM auditorias ORDER BY created_at DESC LIMIT 50').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/backup', methods=['GET'])
def backup():
    conn = get_db()
    rows = conn.execute('SELECT * FROM auditorias').fetchall()
    clientes = conn.execute('SELECT * FROM clientes').fetchall()
    conn.close()
    backup = {
        'data': datetime.now().isoformat(),
        'auditorias': [dict(r) for r in rows],
        'clientes': [dict(r) for r in clientes]
    }
    caminho = os.path.join(os.path.dirname(__file__), '..', 'cerebro', 'backup.json')
    with open(caminho, 'w', encoding='utf-8') as f:
        json.dump(backup, f, ensure_ascii=False, indent=2)
    return jsonify({'status': 'ok', 'caminho': caminho})

@app.route('/api/relatorio-pdf', methods=['POST'])
def gerar_relatorio_pdf():
    data = request.json
    auditoria_id = data.get('auditoria_id')
    nome_cliente = data.get('nome_cliente', 'Cliente')
    url = data.get('url', '')

    if auditoria_id:
        conn = get_db()
        row = conn.execute('SELECT * FROM auditorias WHERE id = ?', (auditoria_id,)).fetchone()
        conn.close()
        if row:
            dados = json.loads(row['resultado'])
            dados['nome_cliente'] = row['nome_cliente']
        else:
            dados = {'nota': 0, 'nome_cliente': nome_cliente, 'url': url, 'detalhes': ['Auditoria nao encontrada']}
    else:
        dados = {
            'nota_final': data.get('nota', 0),
            'nota_site': data.get('nota_site', 0),
            'nota_gbp': data.get('nota_gbp', 0),
            'nome_cliente': nome_cliente,
            'url': url,
            'telefone': data.get('telefone', ''),
            'endereco': data.get('endereco', ''),
            'detalhes_site': data.get('detalhes', [])
        }

    pdf_bytes = gerar_relatorio(dados)
    return Response(pdf_bytes, mimetype='application/pdf',
        headers={'Content-Disposition': 'attachment; filename=relatorio_tonaia.pdf'})

@app.route('/api/prospectar', methods=['POST'])
def prospectar():
    data = request.json
    nicho = data.get('nicho', '').strip()
    cidade = data.get('cidade', '').strip()
    max_res = int(data.get('max_resultados', 20))
    if not nicho or not cidade:
        return jsonify({'erro': 'nicho e cidade sao obrigatorios'}), 400
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
def leads_resumo():
    return jsonify(resumo())

@app.route('/api/leads/exportar', methods=['GET'])
def leads_exportar():
    caminho = os.path.join(os.path.dirname(__file__), '..', 'data', 'leads_export.csv')
    exportar_csv(caminho)
    return send_from_directory(os.path.join(os.path.dirname(__file__), '..', 'data'), 'leads_export.csv', as_attachment=True)

if __name__ == '__main__':
    init_db()
    print('='*50)
    print('  TôNaIA - Motor de Auditoria B2AI')
    print('  Rodando em http://localhost:5000')
    print('='*50)
    app.run(host='0.0.0.0', port=5000, debug=True)
