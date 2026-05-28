import sqlite3
import json
import os
from datetime import datetime
from verificador import verificar_gbp, verificar_plataformas
from multi_llm_checker import query_google_search

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'tonaia.db')

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_concorrentes_db():
    conn = get_db()
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
            created_at TEXT,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
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
            created_at TEXT,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        )
    ''')
    conn.commit()
    conn.close()


def quick_score(nome, cidade):
    score = 0
    max_score = 10
    detalhes = []
    gbp = {}
    plataformas = {}
    busca = {}

    try:
        gbp = verificar_gbp(nome, '', cidade, '')
        plataformas = verificar_plataformas(nome, cidade)
        busca = query_google_search(nome, cidade)
    except Exception:
        pass

    if gbp.get('status') == 'encontrado':
        score += 3
        detalhes.append('Negocio encontrado no Google Maps')
        rating = gbp.get('rating')
        if rating is not None and rating >= 4.0:
            score += 1.5
        elif rating is not None:
            score += 1
        total_reviews = gbp.get('total_reviews', 0) or 0
        if total_reviews >= 10:
            score += 1
        if gbp.get('tem_horario'):
            score += 0.5
        if gbp.get('tem_fotos'):
            score += 0.5
    else:
        detalhes.append('Negocio nao encontrado no Google Maps')

    plataformas_detectadas = plataformas.get('busca_google', {}).get('plataformas_detectadas', [])
    if plataformas_detectadas:
        score += min(len(plataformas_detectadas) * 0.5, 2)

    if busca.get('knowledge_panel'):
        score += 1

    nota = round((score / max_score) * 10, 1)
    return {'nota': min(nota, 10), 'detalhes': detalhes,
            'gbp_encontrado': gbp.get('status') == 'encontrado'}


def adicionar_concorrente(cliente_id, nome, cidade):
    conn = get_db()
    c = conn.execute(
        'INSERT INTO concorrentes (cliente_id, nome, cidade, created_at) VALUES (?, ?, ?, ?)',
        (cliente_id, nome, cidade, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    return c.lastrowid


def listar_concorrentes(cliente_id):
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM concorrentes WHERE cliente_id = ? ORDER BY nota DESC',
        (cliente_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def remover_concorrente(concorrente_id):
    conn = get_db()
    conn.execute('DELETE FROM concorrentes WHERE id = ?', (concorrente_id,))
    conn.commit()
    conn.close()


def verificar_concorrentes(cliente_id):
    conn = get_db()
    concorrentes = conn.execute(
        'SELECT * FROM concorrentes WHERE cliente_id = ?', (cliente_id,)
    ).fetchall()
    agora = datetime.now().isoformat()

    for c in concorrentes:
        result = quick_score(c['nome'], c.get('cidade', ''))
        conn.execute(
            'UPDATE concorrentes SET nota=?, detalhes=?, gbp_encontrado=?, data_verificacao=? WHERE id=?',
            (result['nota'], json.dumps(result['detalhes']),
             1 if result['gbp_encontrado'] else 0, agora, c['id'])
        )

    conn.commit()
    conn.close()
    return comparar_scores(cliente_id)


def comparar_scores(cliente_id):
    conn = get_db()
    cliente = conn.execute('SELECT nome, cidade FROM clientes WHERE id = ?', (cliente_id,)).fetchone()
    concorrentes = conn.execute(
        'SELECT * FROM concorrentes WHERE cliente_id = ? ORDER BY nota DESC', (cliente_id,)
    ).fetchall()

    if not cliente:
        conn.close()
        return {'alerta': None, 'concorrentes': [], 'cliente_nota': 0}

    cliente_score = quick_score(cliente['nome'], cliente.get('cidade', ''))
    concorrentes_list = [dict(r) for r in concorrentes]

    alerta = None
    for c in concorrentes_list:
        if c.get('nota', 0) > cliente_score['nota']:
            msg = (f'Concorrente {c["nome"]} esta com nota {c["nota"]}/10 '
                   f'enquanto voce esta com {cliente_score["nota"]}/10. '
                   f'Precisa de acao urgente!')
            alerta = {'tipo': 'concorrente_melhor', 'mensagem': msg,
                      'concorrente_id': c['id']}
            gerar_alerta(cliente_id, alerta['tipo'], alerta['mensagem'], c['id'])
            break

    conn.close()
    return {
        'cliente_nota': cliente_score['nota'],
        'cliente_detalhes': cliente_score['detalhes'],
        'concorrentes': concorrentes_list,
        'alerta': alerta,
    }


def gerar_alerta(cliente_id, tipo, mensagem, concorrente_id=None):
    conn = get_db()
    existing = conn.execute(
        'SELECT id FROM alertas WHERE cliente_id=? AND tipo=? AND concorrente_id=? AND created_at > datetime("now", "-7 days")',
        (cliente_id, tipo, concorrente_id)
    ).fetchone()
    if not existing:
        conn.execute(
            'INSERT INTO alertas (cliente_id, tipo, mensagem, concorrente_id, created_at) VALUES (?, ?, ?, ?, ?)',
            (cliente_id, tipo, mensagem, concorrente_id, datetime.now().isoformat())
        )
        conn.commit()
    conn.close()


def listar_alertas(cliente_id=None, apenas_nao_lidas=False):
    conn = get_db()
    if cliente_id:
        sql = 'SELECT a.*, c.nome as cliente_nome FROM alertas a LEFT JOIN clientes c ON a.cliente_id=c.id WHERE a.cliente_id=?'
        params = [cliente_id]
        if apenas_nao_lidas:
            sql += ' AND a.lida=0'
        rows = conn.execute(sql + ' ORDER BY a.created_at DESC', params).fetchall()
    else:
        sql = 'SELECT a.*, c.nome as cliente_nome FROM alertas a LEFT JOIN clientes c ON a.cliente_id=c.id'
        if apenas_nao_lidas:
            sql += ' WHERE a.lida=0'
        rows = conn.execute(sql + ' ORDER BY a.created_at DESC').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def marcar_alerta_lida(alerta_id):
    conn = get_db()
    conn.execute('UPDATE alertas SET lida=1 WHERE id=?', (alerta_id,))
    conn.commit()
    conn.close()


def executar_monitoramento():
    conn = get_db()
    clientes_ativos = conn.execute(
        'SELECT id, nome, cidade FROM clientes WHERE plano IS NOT NULL AND plano != "" AND status = "ativo"'
    ).fetchall()
    total_alertas = 0

    for cli in clientes_ativos:
        resultado = comparar_scores(cli['id'])
        if resultado.get('alerta'):
            total_alertas += 1

    conn.close()
    return {'clientes_monitorados': len(clientes_ativos), 'alertas_geradas': total_alertas}


init_concorrentes_db()
