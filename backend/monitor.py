import os
import sys
import json
import time
import sqlite3
from datetime import datetime, timedelta
from auditor import SiteAuditor
from gbp_auditor import GBPAuditor

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'tonaia.db')
HISTORICO_PATH = os.path.join(os.path.dirname(__file__), '..', 'cerebro', 'monitoramento')

os.makedirs(HISTORICO_PATH, exist_ok=True)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def listar_clientes_ativos():
    conn = get_db()
    rows = conn.execute('''
        SELECT DISTINCT nome_cliente, url FROM auditorias
        WHERE nome_cliente != 'anônimo' AND nome_cliente != 'sem nome'
        ORDER BY created_at DESC
    ''').fetchall()
    conn.close()
    vistos = set()
    clientes = []
    for r in rows:
        key = f"{r['nome_cliente']}|{r['url']}"
        if key not in vistos:
            vistos.add(key)
            clientes.append(dict(r))
    return clientes


def reauditar_cliente(nome, url):
    resultado = {'nome_cliente': nome, 'url': url, 'timestamp': datetime.now().isoformat()}

    if url and url.startswith('http'):
        try:
            auditor = SiteAuditor(url)
            site_res = auditor.audit()
            resultado['nota_site'] = site_res.get('nota', 0)
            resultado['detalhes_site'] = site_res.get('detalhes', [])
            resultado['checks'] = site_res.get('checks', {})
        except Exception as e:
            resultado['nota_site'] = 0
            resultado['erro_site'] = str(e)

    conn = get_db()
    conn.execute('''
        INSERT INTO auditorias (nome_cliente, url, tipo, nota, resultado, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (nome, url, 'monitoramento', resultado.get('nota_site', 0),
          json.dumps(resultado), datetime.now().isoformat()))
    conn.commit()
    conn.close()

    historico_path = os.path.join(HISTORICO_PATH, f"{nome.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.json")
    with open(historico_path, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    return resultado


def executar_ciclo():
    print(f'[Monitor] Iniciando ciclo em {datetime.now().strftime("%d/%m/%Y %H:%M")}')
    clientes = listar_clientes_ativos()
    print(f'[Monitor] {len(clientes)} clientes encontrados')

    resultados = []
    for c in clientes:
        print(f'[Monitor] Reauditando {c["nome_cliente"]}...')
        try:
            r = reauditar_cliente(c['nome_cliente'], c.get('url', ''))
            resultados.append(r)
            print(f'[Monitor]   Nota: {r.get("nota_site", "erro")}')
        except Exception as e:
            print(f'[Monitor]   Erro: {e}')
        time.sleep(2)

    resumo = {
        'timestamp': datetime.now().isoformat(),
        'total': len(resultados),
        'resultados': resultados,
    }
    with open(os.path.join(HISTORICO_PATH, '_ultimo_ciclo.json'), 'w', encoding='utf-8') as f:
        json.dump(resumo, f, ensure_ascii=False, indent=2)

    print(f'[Monitor] Ciclo concluido. {len(resultados)} auditados.')
    return resultados


def historico_evolucao(nome_cliente):
    arquivos = sorted(os.listdir(HISTORICO_PATH))
    pontos = []
    for arq in arquivos:
        if arq.startswith(nome_cliente.replace(' ', '_')) and arq.endswith('.json'):
            with open(os.path.join(HISTORICO_PATH, arq)) as f:
                data = json.load(f)
            pontos.append({
                'data': data.get('timestamp', ''),
                'nota': data.get('nota_site', 0),
            })
    return pontos


if __name__ == '__main__':
    executar_ciclo()
