import requests
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urlparse

class SiteAuditor:
    def __init__(self, url):
        self.url = url if url.startswith('http') else f'https://{url}'
        self.domain = urlparse(self.url).netloc
        self.soup = None
        self.schemas = []
        self.results = {}

    def fetch(self):
        try:
            r = requests.get(self.url, timeout=15, 
                headers={'User-Agent': 'Mozilla/5.0'})
            self.soup = BeautifulSoup(r.text, 'html.parser')
            return r.text
        except Exception as e:
            return str(e)

    def extract_schemas(self, html):
        schemas = []
        pattern = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL)
        for match in pattern.finditer(html):
            try:
                data = json.loads(match.group(1))
                schemas.append(data)
            except:
                pass
        self.schemas = schemas
        return schemas

    def check_schema_types(self):
        types = []
        for s in self.schemas:
            if '@type' in s:
                t = s['@type']
                if isinstance(t, list):
                    types.extend(t)
                else:
                    types.append(t)
            if '@graph' in s:
                for item in s['@graph']:
                    if '@type' in item:
                        t = item['@type']
                        if isinstance(t, list):
                            types.extend(t)
                        else:
                            types.append(t)
        return list(set(types))

    def check_description(self):
        if not self.soup:
            return {'score': 0, 'desc': 'site não carregado'}
        meta_desc = self.soup.find('meta', attrs={'name': 'description'})
        title = self.soup.find('title')
        h1 = self.soup.find('h1')
        body = self.soup.find('body')
        text_len = len(body.get_text(strip=True)) if body else 0

        score = 0
        if title and len(title.get_text(strip=True)) > 10:
            score += 2
        if meta_desc and len(meta_desc.get('content', '')) > 50:
            score += 2
        if h1 and len(h1.get_text(strip=True)) > 5:
            score += 1
        if text_len > 200:
            score += 2
        if text_len > 500:
            score += 1

        return {'score': score, 'max': 8, 'desc': f'{text_len} chars'}

    def check_service_listing(self):
        keywords = ['serviço', 'serviços', 'service', 'tratamento', 'procedimento', 
                    'produto', 'categoria', 'preço', 'a partir de', 'consulte']
        if not self.soup:
            return {'score': 0, 'found': []}
        text = self.soup.get_text().lower()
        found = [k for k in keywords if k in text]
        score = min(len(found), 5)
        return {'score': score, 'max': 5, 'found': found}

    def check_contact(self):
        if not self.soup:
            return {'score': 0}
        score = 0
        text = self.soup.get_text().lower()
        if re.search(r'\(\d{2}\)\s?\d{4,5}-?\d{4}', text):
            score += 2
        if 'whatsapp' in text or 'wa.me' in text or 'api.whatsapp' in text:
            score += 2
        if '@' in text and '.com' in text:
            score += 1
        if 'cep' in text or 'endereço' in text or 'rua' in text or 'avenida' in text:
            score += 1
        return {'score': score, 'max': 6}

    def check_social(self):
        if not self.soup:
            return {'score': 0}
        score = 0
        html = str(self.soup)
        if 'instagram.com' in html: score += 1
        if 'facebook.com' in html: score += 1
        if 'youtube.com' in html: score += 1
        if 'tiktok.com' in html: score += 0.5
        return {'score': score, 'max': 3.5}

    def audit(self):
        html = self.fetch()
        if not self.soup:
            return {'error': 'falha ao acessar site', 'nota': 0}

        schemas = self.extract_schemas(html)
        types = self.check_schema_types()

        checks = {
            'schema_jsonld': {'score': 1 if len(schemas) > 0 else 0, 'max': 1},
            'schema_tipos': {'score': min(len(types) / 3, 1), 'max': 1,
                'tipos': types[:5]},
            'descricao': self.check_description(),
            'servicos': self.check_service_listing(),
            'contato': self.check_contact(),
            'social': self.check_social(),
        }

        if 'LocalBusiness' in types: checks['tem_localbusiness'] = {'score': 1, 'max': 1}
        if 'Product' in types: checks['tem_product'] = {'score': 1, 'max': 1}
        if 'Service' in types: checks['tem_service'] = {'score': 1, 'max': 1}
        if 'Review' in types or 'AggregateRating' in types:
            checks['tem_avaliacoes'] = {'score': 1, 'max': 1}

        total = sum(c['score'] for c in checks.values() if isinstance(c, dict) and 'score' in c)
        max_total = sum(c['max'] for c in checks.values() if isinstance(c, dict) and 'max' in c)
        nota = round((total / max_total) * 10, 1) if max_total > 0 else 0

        self.results = {
            'url': self.url,
            'domain': self.domain,
            'nota': nota,
            'checks': checks,
            'schemas_encontrados': len(schemas),
            'tipos_schema': types,
            'detalhes': self._gerar_detalhes(checks)
        }
        return self.results

    def _gerar_detalhes(self, checks):
        detalhes = []
        if checks.get('schema_jsonld', {}).get('score') == 0:
            detalhes.append('Seu site não está falando a língua das IAs (ChatGPT, Gemini, Perplexity)')
        if 'tem_localbusiness' not in checks:
            detalhes.append('As IAs não identificam seu negócio como uma empresa local')
        if 'tem_product' not in checks and 'tem_service' not in checks:
            detalhes.append('As IAs não encontram seus serviços ou produtos')
        if checks.get('descricao', {}).get('score', 0) < 4:
            detalhes.append('A descrição do seu negócio é muito vaga pras IAs entenderem')
        if checks.get('contato', {}).get('score', 0) < 3:
            detalhes.append('As IAs não conseguem achar seus contatos (WhatsApp, telefone, endereço)')
        if checks.get('servicos', {}).get('score', 0) < 2:
            detalhes.append('Seus serviços não estão organizados do jeito que as IAs leem')
        if not detalhes:
            detalhes.append('Seu site tem o básico, mas podemos deixar ele imbatível pras IAs')
        return detalhes
