import requests
import sqlite3
import os
import json
import time
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'prospectos.db')
API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', '')

NICHOS_SUGERIDOS = [
    'cabeleireiro', 'barbeiro', 'clinica estetica', 'dentista',
    'advogado', 'contador', 'personal trainer', 'nutricionista',
    'fisioterapeuta', 'psicologo', 'veterinario', 'petshop',
    'restaurante', 'pizzaria', 'academia', 'oficina mecanica',
    'consultorio medico', 'ortopedista', 'oftalmologista',
]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            telefone TEXT,
            endereco TEXT,
            rating REAL,
            total_ratings INTEGER,
            website TEXT,
            categoria TEXT,
            cidade TEXT,
            place_id TEXT UNIQUE,
            created_at TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS prospeccoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nicho TEXT,
            cidade TEXT,
            total_encontrados INTEGER,
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()


def buscar_estabelecimentos(nicho, cidade, max_resultados=20):
    if not API_KEY:
        raise ValueError('GOOGLE_MAPS_API_KEY nao configurada. Crie uma em https://console.cloud.google.com/')

    query = f'{nicho} em {cidade}'
    url = 'https://places.googleapis.com/v1/places:searchText'
    headers = {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': API_KEY,
        'X-Goog-FieldMask': 'places.id,places.displayName,places.formattedAddress,places.internationalPhoneNumber,places.rating,places.userRatingCount,places.websiteUri',
    }
    body = {
        'textQuery': query,
        'pageSize': min(max_resultados, 20),
        'languageCode': 'pt-BR',
    }

    estabelecimentos = []
    next_page_token = None

    for _ in range((max_resultados // 20) + 1):
        if next_page_token:
            body['pageToken'] = next_page_token
            time.sleep(2)

        resp = requests.post(url, headers=headers, json=body)

        if resp.status_code == 403:
            raise PermissionError('API key invalida ou sem permissao. Habilite Places API no Google Cloud Console.')
        elif resp.status_code == 429:
            raise RuntimeError('Limite de requisicoes excedido. Aguarde e tente novamente.')
        elif resp.status_code != 200:
            raise RuntimeError(f'Erro na API: {resp.status_code} - {resp.text}')

        data = resp.json()
        places = data.get('places', [])

        for p in places:
            estabelecimentos.append({
                'place_id': p.get('id', ''),
                'nome': p.get('displayName', {}).get('text', ''),
                'endereco': p.get('formattedAddress', ''),
                'telefone': p.get('internationalPhoneNumber', ''),
                'rating': p.get('rating', 0),
                'total_ratings': p.get('userRatingCount', 0),
                'website': p.get('websiteUri', ''),
                'categoria': nicho,
                'cidade': cidade,
            })

        next_page_token = data.get('nextPageToken')
        if not next_page_token or len(estabelecimentos) >= max_resultados:
            break

    return estabelecimentos[:max_resultados]


def salvar_leads(estabelecimentos):
    conn = get_db()
    salvos = 0
    for e in estabelecimentos:
        try:
            conn.execute('''
                INSERT OR IGNORE INTO leads (nome, telefone, endereco, rating, total_ratings,
                    website, categoria, cidade, place_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                e['nome'], e['telefone'], e['endereco'], e['rating'],
                e['total_ratings'], e['website'], e['categoria'],
                e['cidade'], e['place_id'], datetime.now().isoformat()
            ))
            if conn.total_changes:
                salvos += 1
        except Exception:
            pass
    conn.commit()
    conn.close()
    return salvos


def registrar_prospeccao(nicho, cidade, total):
    conn = get_db()
    conn.execute('''
        INSERT INTO prospeccoes (nicho, cidade, total_encontrados, created_at)
        VALUES (?, ?, ?, ?)
    ''', (nicho, cidade, total, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def listar_leads(categoria=None, cidade=None, com_telefone=None, limit=50):
    conn = get_db()
    sql = 'SELECT * FROM leads WHERE 1=1'
    params = []
    if categoria:
        sql += ' AND categoria = ?'
        params.append(categoria)
    if cidade:
        sql += ' AND cidade = ?'
        params.append(cidade)
    if com_telefone:
        sql += ' AND telefone != ""'
    sql += ' ORDER BY total_ratings DESC LIMIT ?'
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def exportar_csv(caminho):
    leads = listar_leads(limit=9999)
    if not leads:
        return
    import csv
    with open(caminho, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['nome', 'telefone', 'endereco', 'rating',
                                          'total_ratings', 'website', 'categoria', 'cidade'])
        w.writeheader()
        for l in leads:
            w.writerow({k: l.get(k, '') for k in w.fieldnames})


def resumo():
    conn = get_db()
    total = conn.execute('SELECT COUNT(*) FROM leads').fetchone()[0]
    com_tel = conn.execute('SELECT COUNT(*) FROM leads WHERE telefone != ""').fetchone()[0]
    categorias = conn.execute('SELECT categoria, COUNT(*) as qtd FROM leads GROUP BY categoria ORDER BY qtd DESC').fetchall()
    conn.close()
    return {
        'total_leads': total,
        'com_telefone': com_tel,
        'categorias': [dict(c) for c in categorias],
    }


init_db()
