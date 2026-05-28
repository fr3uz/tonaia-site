import requests
import json
import os
import re
from urllib.parse import quote

from dotenv import load_dotenv
load_dotenv()

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
GOOGLE_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', '')

UA = 'TonaIA-MultiLLM/1.0 (+https://tonaia.com.br)'

def query_gemini(nome, cidade='', servicos=None):
    if not GEMINI_API_KEY:
        return {
            'status': 'nao_configurado',
            'mensagem': 'GEMINI_API_KEY nao configurada',
        }

    prompt = (
        f'Você é um assistente de busca local. '
        f'Responda apenas com JSON válido, sem formatação extra. '
        f'Sobre o negócio "{nome}"'
        f'{f" em {cidade}" if cidade else ""}'
        f'{f" que oferece {', '.join(servicos[:3])}" if servicos else ""}'
        f':\n'
        f'{{"conhece": true/false, "confianca": 0.0-1.0, '
        f'"categoria": "...", "rating_estimado": 0.0-5.0, '
        f'"sabe_endereco": true/false, "sabe_telefone": true/false, '
        f'"pode_recomendar": true/false, "resumo": "..."}}'
    )

    url = f'https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}'
    body = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {
            'temperature': 0.1,
            'maxOutputTokens': 300,
        }
    }

    try:
        r = requests.post(url, json=body, timeout=15,
                          headers={'Content-Type': 'application/json'})
        if r.status_code != 200:
            return {'status': 'erro', 'mensagem': f'Gemini API retornou {r.status_code}', 'detalhe': r.text[:300]}

        data = r.json()
        text = data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')

        match = re.search(r'\{.*\}', text, re.DOTALL)
        if not match:
            return {'status': 'erro', 'mensagem': 'Resposta sem JSON'}

        parsed = json.loads(match.group())
        return {
            'status': 'ok',
            'conhece': parsed.get('conhece', False),
            'confianca': parsed.get('confianca', 0),
            'categoria': parsed.get('categoria', ''),
            'rating_estimado': parsed.get('rating_estimado', 0),
            'sabe_endereco': parsed.get('sabe_endereco', False),
            'sabe_telefone': parsed.get('sabe_telefone', False),
            'pode_recomendar': parsed.get('pode_recomendar', False),
            'resumo': parsed.get('resumo', ''),
        }
    except Exception as e:
        return {'status': 'erro', 'mensagem': str(e)}

def query_google_search(nome, cidade=''):
    try:
        query = f'{quote(nome)} {quote(cidade)}' if cidade else quote(nome)
        url = f'https://www.google.com/search?q={query}&hl=pt-BR'
        r = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
        })
        if r.status_code != 200:
            return {'status': 'erro', 'mensagem': f'Google retornou {r.status_code}'}

        text = r.text.lower()
        knowledge_panel = any(x in text for x in ['google-knowledge', 'knowledge-panel', 'kp-header'])
        featured_snippet = any(x in text for x in ['featured_snippet', 'topstuff', 'rhscard'])

        mentions = []
        patterns = {
            'instagram': r'instagram\.com/\w+',
            'facebook': r'facebook\.com/\w+',
            'reclame_aqui': r'reclameaqui\.com\.br',
        }
        for platform, pat in patterns.items():
            if re.search(pat, text):
                mentions.append(platform)

        return {
            'status': 'ok',
            'knowledge_panel': knowledge_panel,
            'featured_snippet': featured_snippet,
            'plataformas_detectadas': mentions,
            'qtd_mencoes': len(mentions),
        }
    except Exception as e:
        return {'status': 'erro', 'mensagem': str(e)}

def verificar_multi_llm(nome, cidade='', servicos=None):
    resultados = {
        'gemini': query_gemini(nome, cidade, servicos),
        'busca_google': query_google_search(nome, cidade),
        'timestamp': __import__('datetime').datetime.now().isoformat(),
    }

    score_llm = 0
    max_score = 5

    gemini = resultados.get('gemini', {})
    if gemini.get('status') == 'ok':
        if gemini.get('conhece'):
            score_llm += 2
        if gemini.get('sabe_endereco'):
            score_llm += 0.5
        if gemini.get('sabe_telefone'):
            score_llm += 0.5
        if gemini.get('pode_recomendar'):
            score_llm += 1
        score_llm += gemini.get('confianca', 0)

    busca = resultados.get('busca_google', {})
    if busca.get('status') == 'ok':
        if busca.get('knowledge_panel'):
            score_llm += 1
        if busca.get('featured_snippet'):
            score_llm += 0.5
        score_llm += min(busca.get('qtd_mencoes', 0) * 0.3, 1)

    nota_llm = min(round((score_llm / max_score) * 10, 1), 10) if max_score > 0 else 0

    resultados['nota_llm'] = nota_llm
    resultados['score_llm'] = min(score_llm, max_score)
    resultados['max_score'] = max_score

    return resultados
