"""
Sistema de rastreamento de custos da TonaIA.
Registra gastos com APIs, dominios, ferramentas e tempo.
Armazenamento em JSON simples.
"""

import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'custos.json')


def _carregar():
    if not os.path.exists(DB_PATH):
        return []
    try:
        with open(DB_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []


def _salvar(dados):
    with open(DB_PATH, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


CATEGORIAS_CUSTO = [
    'Google Maps API',
    'Dominio',
    'Hospedagem',
    'Ferramentas',
    'Chip WhatsApp',
    'Internet',
    'Energia',
    'Tempo (hora)',
    'Outros',
]


def adicionar(data, categoria, descricao, valor, tipo='variavel'):
    db = _carregar()
    entry = {
        'id': len(db) + 1,
        'data': data,
        'categoria': categoria,
        'descricao': descricao,
        'valor': round(valor, 2),
        'tipo': tipo,
        'created_at': datetime.now().isoformat(),
    }
    db.append(entry)
    _salvar(db)
    return entry


def listar():
    return _carregar()


def resumo():
    db = _carregar()
    total = sum(e['valor'] for e in db)
    by_cat = {}
    for e in db:
        cat = e['categoria']
        by_cat[cat] = by_cat.get(cat, 0) + e['valor']
    by_tipo = {}
    for e in db:
        t = e['tipo']
        by_tipo[t] = by_tipo.get(t, 0) + e['valor']
    return {
        'total': round(total, 2),
        'por_categoria': {k: round(v, 2) for k, v in sorted(by_cat.items(), key=lambda x: -x[1])},
        'por_tipo': {k: round(v, 2) for k, v in by_tipo.items()},
        'qtd_registros': len(db),
        'categorias_disponiveis': CATEGORIAS_CUSTO,
    }


def remover(custo_id):
    db = _carregar()
    db = [e for e in db if e['id'] != custo_id]
    _salvar(db)


def custos_padrao_iniciais():
    """Registra custos iniciais conhecidos se ainda nao existirem."""
    db = _carregar()
    if db:
        return  # ja tem dados
    exemplos = [
        ('2026-05-15', 'Dominio', 'Registro tonaia.com.br (1 ano)', 49.90, 'fixo'),
        ('2026-05-15', 'Ferramentas', 'Playwright/browser dependencies', 0, 'fixo'),
        ('2026-05-20', 'Google Maps API', 'Creditos iniciais (gratuito ate 200$/mes)', 0, 'variavel'),
    ]
    for data, cat, desc, val, tipo in exemplos:
        adicionar(data, cat, desc, val, tipo)
