import requests
from bs4 import BeautifulSoup
import json
import re
import os
import ssl
import socket
from urllib.parse import urlparse, urljoin
from datetime import datetime
from verificador import verificar_tudo, merge_verified_data
from multi_llm_checker import verificar_multi_llm

# ─── HELPERS ──────────────────────────────────────────────────────────────────

UA = 'TonaIA-Audit/1.0 (+https://tonaia.com.br/bot)'
TIMEOUT = 15

def _fetch(url, timeout=TIMEOUT):
    try:
        r = requests.get(url, timeout=timeout, headers={'User-Agent': UA},
                         allow_redirects=True)
        return r
    except:
        return None

def _soup(url):
    r = _fetch(url)
    if r and r.status_code == 200:
        return BeautifulSoup(r.text, 'html.parser'), r.text
    return None, ''

def _score(val, max_val):
    return {'score': min(val, max_val), 'max': max_val}

def _pct(score, max_val):
    return min(score / max_val, 1) if max_val > 0 else 0

def _clamp(val, lo=0, hi=10):
    return max(lo, min(hi, val))


# ─── 1. FUNDACAO TECNICA ─────────────────────────────────────────────────────

class FundacaoChecker:
    def __init__(self, url, domain):
        self.url = url
        self.domain = domain
        self.robots_txt = ''
        self.llms_txt = ''
        self.base_url = f'{urlparse(url).scheme}://{domain}'

    def check_robots(self):
        r = _fetch(urljoin(self.base_url, '/robots.txt'))
        if r and r.status_code == 200:
            self.robots_txt = r.text
            return {'score': 1, 'max': 1, 'found': True}
        return {'score': 0, 'max': 1, 'found': False}

    def check_llms(self):
        r = _fetch(urljoin(self.base_url, '/llms.txt'))
        if r and r.status_code == 200:
            self.llms_txt = r.text
            return {'score': 1, 'max': 1, 'found': True}
        r2 = _fetch(urljoin(self.base_url, '/.well-known/llms.txt'))
        if r2 and r2.status_code == 200:
            self.llms_txt = r2.text
            return {'score': 1, 'max': 1, 'found': True}
        return {'score': 0, 'max': 1, 'found': False}

    def check_ai_crawlers_allowed(self):
        if not self.robots_txt:
            return {'score': 0.5, 'max': 1, 'msg': 'sem robots.txt'}
        agents = ['GPTBot', 'OAI-SearchBot', 'ClaudeBot', 'PerplexityBot',
                  'Google-Extended', 'CCBot', 'Anthropic-IA']
        allowed = []
        denied = []
        for agent in agents:
            pattern = rf'User-agent:\s*{re.escape(agent)}'
            if re.search(pattern, self.robots_txt, re.I):
                lines = self.robots_txt.split('\n')
                in_block = False
                block_disallows = []
                for line in lines:
                    if re.match(rf'User-agent:\s*{re.escape(agent)}', line, re.I):
                        in_block = True
                        continue
                    if in_block and re.match(r'User-agent:', line, re.I):
                        break
                    if in_block and re.match(r'Disallow:\s*(.+)?', line, re.I):
                        d = re.match(r'Disallow:\s*(.+)?', line, re.I)
                        if d and d.group(1) and d.group(1).strip() != '':
                            block_disallows.append(d.group(1).strip())
                if block_disallows:
                    denied.append(agent)
                else:
                    allowed.append(agent)
            else:
                # No specific rule: allowed by default
                allowed.append(agent)
        score = max(0, 1 - len(denied) / len(agents))
        return {'score': round(score, 2), 'max': 1, 'allowed': allowed, 'denied': denied}

    def check_https(self):
        parsed = urlparse(self.url)
        if parsed.scheme == 'https':
            return {'score': 1, 'max': 1}
        r = _fetch(f'https://{self.domain}')
        if r and r.status_code < 400:
            return {'score': 0.5, 'max': 1, 'msg': 'HTTP redireciona para HTTPS'}
        return {'score': 0, 'max': 1}

    def check_crawlability(self, soup):
        if not soup:
            return {'score': 0, 'max': 1}
        meta_robots = soup.find('meta', attrs={'name': 'robots'})
        if meta_robots:
            content = meta_robots.get('content', '').lower()
            if 'noindex' in content:
                return {'score': 0, 'max': 1, 'msg': 'noindex detectado'}
            if 'nofollow' in content:
                return {'score': 0.3, 'max': 1, 'msg': 'nofollow'}
        return {'score': 1, 'max': 1}

    def audit(self, soup):
        checks = {
            'robots_txt': self.check_robots(),
            'llms_txt': self.check_llms(),
            'ai_crawlers': self.check_ai_crawlers_allowed(),
            'https': self.check_https(),
            'crawlability': self.check_crawlability(soup),
        }
        total = sum(c['score'] for c in checks.values())
        max_t = sum(c['max'] for c in checks.values())
        nota = _clamp(round((total / max_t) * 10, 1)) if max_t > 0 else 0
        return {'nota': nota, 'checks': checks, 'robots_txt': self.robots_txt[:500]}


# ─── 2. DADOS ESTRUTURADOS ────────────────────────────────────────────────────

# Schema types that matter most for GEO, grouped by relevance
HIGH_VALUE_SCHEMAS = {
    'LocalBusiness': 3.0, 'Organization': 2.0, 'Service': 2.5, 'Product': 2.0,
    'FAQPage': 2.5, 'Article': 1.5, 'Review': 1.5, 'AggregateRating': 1.5,
    'BreadcrumbList': 1.0, 'SiteNavigationElement': 0.5,
    'OpeningHoursSpecification': 1.5, 'GeoCoordinates': 1.5,
    'PostalAddress': 1.0, 'ContactPoint': 1.5, 'Person': 1.0,
    'Event': 1.0, 'VideoObject': 0.5, 'ImageObject': 0.5,
    'HowTo': 2.0, 'MedicalBusiness': 2.0, 'HealthAndBeautyBusiness': 2.0,
    'PriceSpecification': 1.0, 'SpecialOpeningHoursSpecification': 1.0,
    'Question': 1.0, 'Answer': 1.0,
}

REQUIRED_SERVICE_FIELDS = ['name', 'description']
REQUIRED_LOCALBUSINESS_FIELDS = ['name', 'address', 'telephone', 'url']
REQUIRED_FAQ_FIELDS = ['mainEntity', 'name', 'acceptedAnswer']


class SchemaChecker:
    def __init__(self, url, html):
        self.url = url
        self.html = html
        self.schemas = []
        self.extracted_types = []

    def extract(self):
        pattern = re.compile(
            r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
            re.DOTALL
        )
        for match in pattern.finditer(self.html):
            try:
                data = json.loads(match.group(1))
                self.schemas.append(data)
            except:
                pass
        return self.schemas

    def analyze_types(self):
        types = []
        for s in self.schemas:
            if '@type' in s:
                t = s['@type']
                types.extend([t] if isinstance(t, str) else t)
            if '@graph' in s:
                for item in s['@graph']:
                    if '@type' in item:
                        t = item['@type']
                        types.extend([t] if isinstance(t, str) else t)
        self.extracted_types = list(set(types))
        return self.extracted_types

    def score_type_coverage(self):
        found_types = set(t.lower() for t in self.extracted_types)
        score = 0
        max_score = 5
        found_valuable = []
        for stype, weight in HIGH_VALUE_SCHEMAS.items():
            if stype.lower() in found_types:
                score += weight
                found_valuable.append(stype)
        return {
            'score': min(score, max_score),
            'max': max_score,
            'found_types': sorted(found_valuable),
            'all_types': sorted(self.extracted_types)
        }

    def check_field_completeness(self):
        results = {}
        product_count = 0
        for s in self.schemas:
            stype = s.get('@type', '')
            if isinstance(stype, list):
                stype = stype[0]
            if stype == 'LocalBusiness' or 'LocalBusiness' in s.get('@type', []):
                has_name = bool(s.get('name'))
                has_address = bool(s.get('address'))
                has_phone = bool(s.get('telephone'))
                has_url_url = bool(s.get('url'))
                score = sum([has_name, has_address, has_phone, has_url_url])
                results['localbusiness'] = {
                    'score': score, 'max': 4,
                    'fields': {
                        'name': has_name, 'address': has_address,
                        'telephone': has_phone, 'url': has_url_url
                    }
                }
            if stype == 'FAQPage':
                entities = s.get('mainEntity', [])
                if isinstance(entities, dict):
                    entities = [entities]
                q_count = 0
                for e in entities:
                    if e.get('name') and e.get('acceptedAnswer', {}).get('text'):
                        q_count += 1
                results['faqpage'] = {
                    'score': min(q_count, 10), 'max': 10,
                    'question_count': q_count
                }
            if stype in ('Service', 'Product') or 'Service' in s.get('@type', []):
                has_name = bool(s.get('name'))
                has_desc = bool(s.get('description'))
                has_offers = bool(s.get('offers'))
                has_price = False
                if has_offers:
                    offers = s['offers']
                    if isinstance(offers, list):
                        has_price = any(o.get('price') for o in offers)
                    elif isinstance(offers, dict):
                        has_price = bool(offers.get('price'))
                score = sum([has_name, has_desc, has_price])
                key = 'service' if 'Service' in (s.get('@type', '') if isinstance(s.get('@type'), str) else str(s.get('@type', []))) else 'product'
                if key == 'product':
                    product_count += 1
                results[key] = {
                    'score': score, 'max': 3,
                    'fields': {'name': has_name, 'description': has_desc, 'price': has_price}
                }
            if stype == 'AggregateRating' or 'AggregateRating' in s.get('@type', []):
                has_rating = bool(s.get('ratingValue'))
                has_review_count = bool(s.get('reviewCount'))
                score = sum([has_rating, has_review_count])
                results['aggregaterating'] = {
                    'score': score, 'max': 2,
                    'fields': {'ratingValue': has_rating, 'reviewCount': has_review_count}
                }
            if 'offers' in s and isinstance(s['offers'], dict) and s['offers'].get('@type') == 'Offer':
                has_price_offer = bool(s['offers'].get('price'))
                has_currency = bool(s['offers'].get('priceCurrency'))
                score = sum([has_price_offer, has_currency])
                results['offer'] = {
                    'score': score, 'max': 2,
                    'fields': {'price': has_price_offer, 'currency': has_currency}
                }
        results['product_count'] = product_count
        return results

    def audit(self):
        self.extract()
        self.analyze_types()
        type_coverage = self.score_type_coverage()
        completeness = self.check_field_completeness()
        has_schema = len(self.schemas) > 0

        checks = {
            'schema_presente': _score(1 if has_schema else 0, 1),
            'tipos_schema': type_coverage,
        }
        for key, val in completeness.items():
            checks[f'schema_{key}'] = val

        total = sum(c['score'] for c in checks.values())
        max_t = sum(c['max'] for c in checks.values())
        nota = _clamp(round((total / max_t) * 10, 1)) if max_t > 0 else 0

        return {
            'nota': nota,
            'checks': checks,
            'schemas_encontrados': len(self.schemas),
            'tipos_encontrados': sorted(set(self.extracted_types)),
            'missing_high_value': [
                t for t in ['LocalBusiness', 'FAQPage', 'Service', 'AggregateRating', 'HowTo']
                if t.lower() not in set(x.lower() for x in self.extracted_types)
            ]
        }


# ─── 3. ARQUITETURA DE CONTEUDO ─────────────────────────────────────────────

class ContentChecker:
    def __init__(self, soup, url):
        self.soup = soup
        self.url = url

    def check_title(self):
        if not self.soup:
            return _score(0, 2)
        title = self.soup.find('title')
        if not title:
            return _score(0, 2)
        text = title.get_text(strip=True)
        score = 0
        if len(text) >= 20:
            score += 1
        if len(text) <= 70:
            score += 1
        return {'score': score, 'max': 2, 'title': text[:100]}

    def check_meta_description(self):
        if not self.soup:
            return _score(0, 2)
        meta = self.soup.find('meta', attrs={'name': 'description'})
        if not meta:
            return _score(0, 2)
        content = meta.get('content', '')
        score = 0
        if len(content) >= 50:
            score += 1
        if len(content) >= 120:
            score += 1
        return {'score': score, 'max': 2, 'desc': content[:150]}

    def check_opening_definition(self):
        if not self.soup:
            return _score(0, 3)
        body = self.soup.find('body')
        if not body:
            return _score(0, 3)
        text = body.get_text(strip=True)
        first_words = text[:300].lower()
        score = 0
        patterns = [
            r'\b(é|sou|somos|empresa|profissional\s+de|especialista\s+em)\b',
            r'\b(atendemos|oferecemos|trabalhamos|realizamos|fazemos)\b',
            r'\b(há|desde|anos|experiência|referência|tradição)\b',
        ]
        for p in patterns:
            if re.search(p, first_words):
                score += 1
        return {'score': score, 'max': 3, 'msg': 'primeiros 300 caracteres analisados'}

    def check_h2_questions(self):
        if not self.soup:
            return _score(0, 3)
        h2s = self.soup.find_all('h2')
        question_count = 0
        q_words = ['como', 'o que', 'qual', 'quanto', 'onde', 'quando',
                   'por que', 'para que', 'quem', 'vale a pena']
        for h2 in h2s:
            text = h2.get_text(strip=True).lower()
            if any(text.startswith(qw) for qw in q_words):
                question_count += 1
            if '?' in text:
                question_count += 1
        score = min(question_count, 3)
        return {'score': score, 'max': 3, 'h2_count': len(h2s), 'question_h2s': question_count}

    def check_faq_block(self):
        if not self.soup:
            return _score(0, 2)
        text = self.soup.get_text().lower()
        faq_markers = ['perguntas frequentes', 'faq', 'dúvidas frequentes',
                       'pergunta', 'resposta', '📌']
        score = 0
        for m in faq_markers[:4]:
            if m in text:
                score += 0.5
        return {'score': min(score, 2), 'max': 2}

    def check_tables_and_lists(self):
        if not self.soup:
            return _score(0, 3)
        tables = self.soup.find_all('table')
        lists = self.soup.find_all(['ul', 'ol'])
        score = 0
        if len(tables) > 0:
            score += 1.5
        if len(lists) >= 2:
            score += 1.5
        elif len(lists) >= 1:
            score += 0.5
        return {'score': min(score, 3), 'max': 3, 'tables': len(tables), 'lists': len(lists)}

    def check_entities_mentioned(self):
        if not self.soup:
            return _score(0, 2)
        text = self.soup.get_text().lower()
        entity_signals = [
            'cnpj', 'endereço', 'telefone', 'whatsapp',
            'segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado',
            'horário', 'funcionamento', 'agende', 'agendar',
        ]
        found = sum(1 for e in entity_signals if e in text)
        score = min(found / 3, 2)
        return {'score': round(score, 1), 'max': 2, 'signals_found': found}

    def check_word_count(self):
        if not self.soup:
            return _score(0, 2)
        body = self.soup.find('body')
        if not body:
            return _score(0, 2)
        words = len(body.get_text(strip=True).split())
        score = 0
        if words >= 150:
            score = 0.5
        if words >= 300:
            score = 1
        if words >= 600:
            score = 1.5
        if words >= 1000:
            score = 2
        return {'score': score, 'max': 2, 'word_count': words}

    def audit(self):
        checks = {
            'titulo': self.check_title(),
            'meta_descricao': self.check_meta_description(),
            'abertura_definicao': self.check_opening_definition(),
            'h2_perguntas': self.check_h2_questions(),
            'faq': self.check_faq_block(),
            'tabelas_listas': self.check_tables_and_lists(),
            'entidades_mencionadas': self.check_entities_mentioned(),
            'quantidade_texto': self.check_word_count(),
        }
        total = sum(c['score'] for c in checks.values())
        max_t = sum(c['max'] for c in checks.values())
        nota = _clamp(round((total / max_t) * 10, 1)) if max_t > 0 else 0
        return {'nota': nota, 'checks': checks}


# ─── 4. AUTORIDADE DA ENTIDADE ──────────────────────────────────────────────

class EntityAuthorityChecker:
    def __init__(self, domain, soup, url, questionario=None):
        self.domain = domain
        self.soup = soup
        self.url = url
        self.q = questionario or {}

    def check_nap_consistency(self):
        score = 0
        max_s = 4
        nap_signals = []
        if not self.soup:
            return _score(0, max_s)
        text = self.soup.get_text().lower()

        phone_pattern = re.compile(r'\(\d{2}\)\s?\d{4,5}-?\d{4}')
        phones = phone_pattern.findall(text)
        if phones:
            score += 1.5
            nap_signals.append(f'telefone: {phones[0]}')

        address_pattern = re.compile(
            r'(rua|avenida|av|travessa|praça|alameda|rodovia)\s[\w\s]+\d+',
            re.I
        )
        addresses = address_pattern.findall(text)
        if addresses:
            score += 1.5
            nap_signals.append(f'endereço: {addresses[0][:60]}')

        if re.search(r'\bcep\b', text, re.I):
            score += 1
            nap_signals.append('cep mencionado')

        return {'score': min(score, max_s), 'max': max_s, 'signals': nap_signals}

    def check_gbp_presence(self):
        if not self.soup:
            return _score(0, 2)
        html = str(self.soup)
        gbp_signals = []
        score = 0
        if 'google.com/maps' in html or 'goo.gl/maps' in html:
            score += 1
            gbp_signals.append('link google maps')
        if 'business.google.com' in html or 'google.com/business' in html:
            score += 1
            gbp_signals.append('link google business')
        return {'score': score, 'max': 2, 'signals': gbp_signals}

    def check_whatsapp_presence(self):
        if not self.soup:
            return _score(0, 1)
        html = str(self.soup)
        if 'wa.me' in html or 'api.whatsapp.com' in html or 'whatsapp' in html.lower():
            return {'score': 1, 'max': 1, 'found': True}
        return {'score': 0, 'max': 1, 'found': False}

    def check_social_profiles(self):
        if not self.soup:
            return _score(0, 3)
        html = str(self.soup)
        profiles = []
        score = 0
        if 'instagram.com' in html:
            score += 1
            profiles.append('instagram')
        if 'facebook.com' in html:
            score += 0.5
            profiles.append('facebook')
        if 'linkedin.com' in html:
            score += 0.5
            profiles.append('linkedin')
        if 'youtube.com' in html:
            score += 0.5
            profiles.append('youtube')
        if 'tiktok.com' in html:
            score += 0.5
            profiles.append('tiktok')
        return {'score': score, 'max': 3, 'profiles': profiles}

    def audit(self):
        checks = {
            'nap_consistencia': self.check_nap_consistency(),
            'gbp_presenca': self.check_gbp_presence(),
            'whatsapp': self.check_whatsapp_presence(),
            'redes_sociais': self.check_social_profiles(),
        }
        total = sum(c['score'] for c in checks.values())
        max_t = sum(c['max'] for c in checks.values())
        nota = _clamp(round((total / max_t) * 10, 1)) if max_t > 0 else 0
        return {'nota': nota, 'checks': checks}


# ─── 5. SINAIS DE CONFIANCA ─────────────────────────────────────────────────

class TrustChecker:
    def __init__(self, soup, schemas):
        self.soup = soup
        self.schemas = schemas

    def check_eeat_signals(self):
        if not self.soup:
            return _score(0, 3)
        text = self.soup.get_text().lower()
        score = 0
        signals = []
        eeat_kw = [
            ('registro', 'registro|crm|crea|cro|cfbm|oab'),  # professional registry
            ('formacao', 'formação|graduado|pós-graduação|especialista'),
            ('experiencia', r'anos de experiência|desde \d{4}|há \d+ anos'),
            ('artigos', 'publicou|artigo|pesquisa|estudo'),
            ('premios', 'prêmio|reconhecimento|destaque|top'),
            ('equipe', 'equipe|time|profissionais|especialistas'),
            ('associacao', 'associação|conselho|sindicato|federação'),
        ]
        for label, pattern in eeat_kw:
            if re.search(pattern, text, re.I):
                score += 0.5
                signals.append(label)
        return {'score': min(score, 3), 'max': 3, 'signals': signals}

    def check_about_page(self):
        if not self.soup:
            return _score(0, 1)
        text = self.soup.get_text().lower()
        if 'sobre' in text or 'about' in text or 'quem somos' in text:
            return {'score': 1, 'max': 1, 'found': True}
        return {'score': 0, 'max': 1, 'found': False}

    def check_review_signals(self):
        if not self.soup:
            return _score(0, 3)
        text = self.soup.get_text().lower()
        html = str(self.soup)
        score = 0
        signals = []

        has_review_schema = any(
            s.get('@type') in ('Review', 'AggregateRating')
            for s in self.schemas
            if isinstance(s, dict)
        )
        if has_review_schema:
            score += 1.5
            signals.append('schema de avaliação')

        review_words = ['avaliação', 'depoimento', 'recomendação', 'feedback',
                        'cliente diz', 'o que dizem']
        found = sum(1 for w in review_words if w in text)
        if found >= 2:
            score += 1
            signals.append(f'{found} indicadores de avaliação')
        elif found >= 1:
            score += 0.5

        # Check for review platform embeds
        if 'google.com/maps' in html and 'review' in html.lower():
            score += 0.5
            signals.append('review google maps')

        return {'score': min(score, 3), 'max': 3, 'signals': signals}

    def check_freshness(self):
        if not self.soup:
            return {'score': 0, 'max': 2, 'days_since_update': None}
        html = str(self.soup)
        date_patterns = [
            r'\b(\d{2}/\d{2}/202[5-9])\b',
            r'\b(\d{4}-\d{2}-\d{2})\b',
            r'<time[^>]*datetime="([^"]+)"',
            r'"datePublished"\s*:\s*"([^"]+)"',
            r'"dateModified"\s*:\s*"([^"]+)"',
        ]
        found_dates = []
        for p in date_patterns:
            matches = re.findall(p, html)
            found_dates.extend(matches[:3])
        score = 0
        if found_dates:
            score += 1
        if len(found_dates) > 1:
            score += 0.5
        if score > 0:
            score += 0.5
        return {'score': min(score, 2), 'max': 2, 'dates_found': found_dates[:5]}

    def audit(self):
        checks = {
            'eeat': self.check_eeat_signals(),
            'pagina_sobre': self.check_about_page(),
            'avaliacoes': self.check_review_signals(),
            'atualizacao': self.check_freshness(),
        }
        total = sum(c['score'] for c in checks.values())
        max_t = sum(c['max'] for c in checks.values())
        nota = _clamp(round((total / max_t) * 10, 1)) if max_t > 0 else 0
        return {'nota': nota, 'checks': checks}


# ─── 6. PREPARACAO PARA IA ───────────────────────────────────────────────────

class AIPreparationChecker:
    def __init__(self, base_url, robots_txt, llms_txt):
        self.base_url = base_url
        self.robots_txt = robots_txt
        self.llms_txt = llms_txt

    def check_llms_content(self):
        if not self.llms_txt:
            return _score(0, 2)
        score = 0
        lines = self.llms_txt.strip().split('\n')
        content_lines = [l for l in lines if l.strip() and not l.startswith('#')]
        if len(content_lines) >= 3:
            score += 1
        if any(l.startswith('http') for l in content_lines):
            score += 0.5
        if len(content_lines) >= 10:
            score += 0.5
        return {'score': score, 'max': 2, 'lines': len(content_lines)}

    def check_ai_txt(self):
        r = _fetch(urljoin(self.base_url, '/ai.txt'))
        if r and r.status_code == 200:
            return {'score': 1, 'max': 1, 'found': True}
        return {'score': 0, 'max': 1, 'found': False}

    def check_llms_json(self):
        r = _fetch(urljoin(self.base_url, '/.well-known/llms.json'))
        if r and r.status_code == 200:
            return {'score': 1, 'max': 1, 'found': True}
        return {'score': 0, 'max': 1, 'found': False}

    def check_ai_training_optout(self):
        if not self.robots_txt:
            return {'score': 0, 'max': 1, 'msg': 'sem robots.txt'}
        optouts = ['CCBot', 'GPTBot', 'ClaudeBot', 'anthropic-ai']
        for agent in optouts:
            if re.search(rf'User-agent:\s*{re.escape(agent)}', self.robots_txt, re.I):
                return {'score': 1, 'max': 1, 'found': True}
        return {'score': 0.5, 'max': 1, 'msg': 'nenhum opt-out de treinamento'}

    def check_sitemap(self):
        r = _fetch(urljoin(self.base_url, '/sitemap.xml'))
        if r and r.status_code == 200:
            return {'score': 1, 'max': 1, 'found': True}
        r2 = _fetch(urljoin(self.base_url, '/sitemap_index.xml'))
        if r2 and r2.status_code == 200:
            return {'score': 1, 'max': 1, 'found': True}
        # Try to find sitemap in robots.txt
        if self.robots_txt and 'sitemap' in self.robots_txt.lower():
            return {'score': 0.5, 'max': 1, 'found': False, 'msg': 'sitemap mencionado em robots.txt'}
        return {'score': 0, 'max': 1, 'found': False}

    def audit(self):
        checks = {
            'llms_txt_conteudo': self.check_llms_content(),
            'ai_txt': self.check_ai_txt(),
            'llms_json': self.check_llms_json(),
            'optout_treinamento': self.check_ai_training_optout(),
            'sitemap': self.check_sitemap(),
        }
        total = sum(c['score'] for c in checks.values())
        max_t = sum(c['max'] for c in checks.values())
        nota = _clamp(round((total / max_t) * 10, 1)) if max_t > 0 else 0
        return {'nota': nota, 'checks': checks}


# ─── 7. AUTORIDADE EXTERNA ──────────────────────────────────────────────────

class ExternalAuthorityChecker:
    def __init__(self, domain, soup):
        self.domain = domain
        self.soup = soup

    def check_backlinks_count(self):
        # Estimate from SEO meta
        if not self.soup:
            return _score(0, 1)
        text = str(self.soup)
        external_links = re.findall(r'href="https?://(?!' + re.escape(self.domain) + r')', text)
        return {'score': 1 if len(external_links) > 5 else 0.5 if len(external_links) > 0 else 0,
                'max': 1, 'external_links_count': len(external_links)}

    def check_directory_listings(self):
        # Check if site mentions directories
        if not self.soup:
            return _score(0, 2)
        text = self.soup.get_text().lower()
        directories = ['apontador', 'guia mais', 'yellowpages', 'páginas amarelas',
                       'infoisinfo', 'empresas', 'listagem']
        found = [d for d in directories if d in text]
        score = min(len(found) * 0.5, 2)
        return {'score': score, 'max': 2, 'directories_found': found}

    def check_third_party_mentions(self):
        if not self.soup:
            return _score(0, 1)
        html = str(self.soup).lower()
        platforms = ['reclame aqui', 'trustpilot', 'facebook.com/reviews',
                     'google.com/maps/place']
        found = [p for p in platforms if p in html]
        return {'score': 1 if found else 0, 'max': 1, 'platforms_found': found}

    def audit(self):
        checks = {
            'backlinks': self.check_backlinks_count(),
            'diretorios': self.check_directory_listings(),
            'mencoes_externas': self.check_third_party_mentions(),
        }
        total = sum(c['score'] for c in checks.values())
        max_t = sum(c['max'] for c in checks.values())
        nota = _clamp(round((total / max_t) * 10, 1)) if max_t > 0 else 0
        return {'nota': nota, 'checks': checks}


# ─── MAIN AUDIT ENGINE ───────────────────────────────────────────────────────

WEIGHTS = {
    'fundacao_tecnica': 0.15,
    'dados_estruturados': 0.20,
    'arquitetura_conteudo': 0.20,
    'autoridade_entidade': 0.15,
    'sinais_confianca': 0.15,
    'preparacao_ia': 0.10,
    'autoridade_externa': 0.05,
}


class GeoAuditor:
    def __init__(self, url, questionario=None):
        self.raw_url = url
        self.url = url if url.startswith('http') else f'https://{url}'
        self.domain = urlparse(self.url).netloc
        self.base_url = f'{urlparse(self.url).scheme}://{self.domain}'
        self.soup = None
        self.html = ''
        self.questionario = questionario or {}

    def run(self):
        self.soup, self.html = _soup(self.url)

        # Run all checkers sequentially
        fundacao = FundacaoChecker(self.url, self.domain)
        fundacao_result = fundacao.audit(self.soup)
        self.robots_txt = fundacao.robots_txt
        self.llms_txt = fundacao.llms_txt

        schema = SchemaChecker(self.url, self.html)
        schema_result = schema.audit()

        conteudo = ContentChecker(self.soup, self.url)
        conteudo_result = conteudo.audit()

        entidade = EntityAuthorityChecker(self.domain, self.soup, self.url, self.questionario)
        entidade_result = entidade.audit()

        confianca = TrustChecker(self.soup, schema.schemas)
        confianca_result = confianca.audit()

        preparacao = AIPreparationChecker(self.base_url, self.robots_txt, self.llms_txt)
        preparacao_result = preparacao.audit()

        externa = ExternalAuthorityChecker(self.domain, self.soup)
        externa_result = externa.audit()

        results = {
            'fundacao_tecnica': fundacao_result,
            'dados_estruturados': schema_result,
            'arquitetura_conteudo': conteudo_result,
            'autoridade_entidade': entidade_result,
            'sinais_confianca': confianca_result,
            'preparacao_ia': preparacao_result,
            'autoridade_externa': externa_result,
        }

        # Calculate weighted final score
        nota_final = 0
        max_possible = 0
        breakdown = {}
        for category, weight in WEIGHTS.items():
            if category in results:
                nota_cat = results[category].get('nota', 0)
                nota_final += nota_cat * weight
                max_possible += 10 * weight
                breakdown[category] = {
                    'nota': nota_cat,
                    'peso': weight,
                    'contribuicao': round(nota_cat * weight, 2)
                }

        nota_final = _clamp(round(nota_final, 1))

        # Generate detailed action items
        detalhes = self._gerar_detalhes(results)

        return {
            'nota_final': nota_final,
            'breakdown': breakdown,
            'detalhes': detalhes,
            'url': self.url,
            'domain': self.domain,
            'categorias': results,
            'schemas_detectados': schema.check_field_completeness(),
        }

    def _gerar_detalhes(self, results):
        detalhes = []

        # Fundação Técnica
        ft = results.get('fundacao_tecnica', {}).get('checks', {})
        if ft.get('ai_crawlers', {}).get('denied'):
            denied = ft['ai_crawlers']['denied']
            detalhes.append(f'IA agents bloqueados no robots.txt: {", ".join(denied)}')
        if ft.get('llms_txt', {}).get('score', 0) == 0:
            detalhes.append('Arquivo llms.txt ausente -- IAs tem dificuldade de entender seu conteudo')
        if ft.get('https', {}).get('score', 0) == 0:
            detalhes.append('Site sem HTTPS -- penalizado por IAs e navegadores')

        # Dados Estruturados
        de = results.get('dados_estruturados', {})
        missing = de.get('missing_high_value', [])
        if missing:
            detalhes.append(f'Schemas importantes ausentes: {", ".join(missing[:4])}')
        if de.get('schemas_encontrados', 0) == 0:
            detalhes.append('Nenhum schema JSON-LD encontrado -- IAs nao entendem seu negocio')

        # Conteudo
        ct = results.get('arquitetura_conteudo', {})
        if ct.get('nota', 10) < 5:
            detalhes.append('Conteudo mal estruturado para leitura por IA -- falta definicao clara e perguntas frequentes')
        if ct.get('checks', {}).get('h2_perguntas', {}).get('score', 0) < 2:
            detalhes.append('Poucas perguntas em H2 -- IAs priorizam conteudo em formato de Q&A')

        # Entidade
        en = results.get('autoridade_entidade', {})
        if en.get('checks', {}).get('nap_consistencia', {}).get('score', 0) < 2:
            detalhes.append('Informacoes NAP (nome, endereco, telefone) inconsistentes ou ausentes')
        if en.get('checks', {}).get('whatsapp', {}).get('score', 0) == 0:
            detalhes.append('WhatsApp nao detectado no site')

        # Confianca
        tr = results.get('sinais_confianca', {})
        if tr.get('checks', {}).get('avaliacoes', {}).get('score', 0) < 2:
            detalhes.append('Sinais de avaliacao fracos -- IAs preferem negocios com reviews ativas')
        if tr.get('checks', {}).get('atualizacao', {}).get('score', 0) < 1:
            detalhes.append('Conteudo parece desatualizado -- IAs penalizam informacoes antigas')

        # Preparacao IA
        ia = results.get('preparacao_ia', {})
        if ia.get('nota', 10) < 5:
            detalhes.append('Pouca ou nenhuma preparacao para crawlers de IA (llms.txt, ai.txt)')

        if not detalhes:
            detalhes.append('Seu negocio esta bem posicionado para ser encontrado por IAs')

        return detalhes


# ─── DIGITAL PRESENCE AUDITOR (works with or without website) ──────────────

NAO_VERIFICAVEL = {'nota': 0, 'checks': {}, 'msg': 'Sem site para analisar'}
NAO_VERIFICAVEL_PREP = {'nota': 0, 'checks': {}}


WEIGHTS_LOCAL = {
    'gbp_qualidade': 0.30,
    'reputacao': 0.25,
    'entidade': 0.20,
    'presenca_externa': 0.15,
    'sinais_sociais': 0.10,
}

WEIGHTS_COM_SITE = {
    'fundacao_tecnica': 0.10,
    'dados_estruturados': 0.10,
    'arquitetura_conteudo': 0.10,
    'autoridade_entidade': 0.05,
    'sinais_confianca': 0.05,
    'preparacao_ia': 0.05,
    'autoridade_externa': 0.03,
    'ecommerce': 0.04,
    'gbp_qualidade': 0.14,
    'reputacao': 0.12,
    'entidade': 0.10,
    'presenca_externa': 0.07,
    'sinais_sociais': 0.05,
}


class DigitalPresenceAuditor:
    """
    Audita a presenca digital completa de um negocio para visibilidade em IA.
    Funciona com ou sem site.

    Baseado em pesquisas de 2026:
    - GBP ~32% dos fatores de ranqueamento em AI Overviews (BrightEdge, ClickRank)
    - Foursquare ~70% dos dados locais do ChatGPT (Pleiades Consultancy)
    - 150+ reviews = threshold para citacao por IA
    - Consistencia NAP = 2.4x mais visibilidade em IA (ZipTie.dev)
    - Conteudo de reviews (sentimento) correlaciona 6x mais que quantidade
    - 85% das citacoes de IA vêm de fontes terceiras (Lesli Rose)
    """

    def __init__(self, perfil):
        self.perfil = perfil
        self.nome = perfil.get('nome_negocio', perfil.get('nome', ''))
        self.url = perfil.get('site_url', perfil.get('url', ''))
        self.categoria = perfil.get('categoria', '')
        self.cidade = perfil.get('cidade', '')
        self.servicos = perfil.get('servicos_lista', [])
        if isinstance(perfil.get('servicos'), str):
            self.servicos = [s.strip() for s in perfil.get('servicos', '').split(',') if s.strip()]
        self.endereco = perfil.get('endereco', '')
        self.telefone = perfil.get('telefone', '')
        self.instagram = perfil.get('instagram', '')
        self.facebook = perfil.get('facebook', '')
        self.tem_gbp = perfil.get('tem_google_business', False)
        if isinstance(self.tem_gbp, str):
            self.tem_gbp = self.tem_gbp.lower() == 'sim'
        self.avaliacoes_qtd = perfil.get('avaliacoes_google', '')
        self.avaliacoes_nota = perfil.get('nota_media', '')
        self.horario = perfil.get('horario_funcionamento', '')
        self.duvidas = perfil.get('duvidas_comuns', '')
        self.responde_avaliacoes = perfil.get('responde_avaliacoes', False)
        if isinstance(self.responde_avaliacoes, str):
            self.responde_avaliacoes = self.responde_avaliacoes.lower() == 'sim'
        # Novos campos baseados em pesquisa
        self.gbp_completa = perfil.get('gbp_completa', False)
        if isinstance(self.gbp_completa, str):
            self.gbp_completa = self.gbp_completa.lower() == 'sim'
        self.gbp_posts = perfil.get('gbp_posts', False)
        if isinstance(self.gbp_posts, str):
            self.gbp_posts = self.gbp_posts.lower() == 'sim'
        self.foursquare = perfil.get('foursquare', False)
        if isinstance(self.foursquare, str):
            self.foursquare = self.foursquare.lower() == 'sim'
        self.outras_plataformas = perfil.get('outras_plataformas', '')
        self.review_recencia = perfil.get('review_recencia', False)
        if isinstance(self.review_recencia, str):
            self.review_recencia = self.review_recencia.lower() == 'sim'

        self.verificacao = None
        self.discrepancias = []

    def has_site(self):
        return bool(self.url and self.url.strip())

    def _aplicar_verificacao(self, perfil_atualizado):
        gbp = self.verificacao.get('gbp', {}) if self.verificacao else {}

        if gbp.get('status') == 'encontrado':
            self.tem_gbp = True
            if gbp.get('rating') is not None:
                rating = gbp['rating']
                if rating >= 4.6:
                    self.avaliacoes_nota = '4.6-5.0'
                elif rating >= 4.1:
                    self.avaliacoes_nota = '4.1-4.5'
                elif rating >= 3.1:
                    self.avaliacoes_nota = '3.1-4.0'
                else:
                    self.avaliacoes_nota = '3.0 ou menos'
            if gbp.get('total_reviews') is not None:
                count = gbp['total_reviews']
                if count >= 100:
                    self.avaliacoes_qtd = '100+'
                elif count >= 31:
                    self.avaliacoes_qtd = '31-100'
                elif count >= 11:
                    self.avaliacoes_qtd = '11-30'
                elif count >= 1:
                    self.avaliacoes_qtd = '1-10'
                else:
                    self.avaliacoes_qtd = 'nenhuma'
            completo = all([
                gbp.get('tem_fotos', False),
                gbp.get('tem_horario', False),
                gbp.get('tem_descricao', False),
            ])
            self.gbp_completa = completo
            if gbp.get('endereco'):
                self.endereco = gbp['endereco']
            if gbp.get('telefone'):
                self.telefone = gbp['telefone']
            if gbp.get('tem_horario'):
                self.horario = 'verificado via Google Places API'
            if gbp.get('total_reviews', 0) > 20:
                self.review_recencia = True

    def run(self, executar_verificacao=True):
        categorias = {}

        # ─── VERIFICACAO AUTOMATICA (REAL) ───────────────────────────
        # Antes de qualquer scoring, executa verificadores independentes
        # para confrontar dados autodeclarados com dados reais.
        self.verificacao = None
        self.discrepancias = []
        self.multi_llm = {}

        if executar_verificacao:
            try:
                self.verificacao = verificar_tudo(self.perfil)
                perfil_atualizado = merge_verified_data(self.perfil, self.verificacao)
                self.discrepancias = self.verificacao.get('discrepancias', [])

                # Atualiza perfil e atributos com dados verificados
                self.perfil = perfil_atualizado
                self._aplicar_verificacao(perfil_atualizado)
            except Exception as e:
                self.verificacao = {'erro': str(e), 'status': 'falha'}
                self.discrepancias = [{'criterio': 'verificador', 'erro': str(e)}]

            # Multi-LLM Checker (Gemini + Google Search)
            try:
                self.multi_llm = verificar_multi_llm(
                    self.nome, self.cidade, self.servicos
                )
            except Exception as e:
                self.multi_llm = {'status': 'erro', 'mensagem': str(e)}

        if self.has_site():
            return self._run_com_site(categorias)
        else:
            return self._run_sem_site(categorias)

    def _run_com_site(self, categorias):
        site_auditor = GeoAuditor(self.url)
        site_result = site_auditor.run()
        self._site_schemas = site_result.get('schemas_detectados', {})
        for k in ['fundacao_tecnica', 'dados_estruturados',
                   'arquitetura_conteudo', 'autoridade_entidade',
                   'sinais_confianca', 'preparacao_ia', 'autoridade_externa']:
            if k in site_result.get('categorias', {}):
                categorias[k] = site_result['categorias'][k]

        categorias['ecommerce'] = self._avaliar_ecommerce()
        categorias['gbp_qualidade'] = self._avaliar_gbp()
        categorias['reputacao'] = self._avaliar_reputacao()
        categorias['entidade'] = self._avaliar_entidade()
        categorias['presenca_externa'] = self._avaliar_presenca_externa()
        categorias['sinais_sociais'] = self._avaliar_sinais_sociais()

        return self._finalizar(categorias, use_local=False, com_site=True)

    def _run_sem_site(self, categorias):
        # 5 dimensoes para negocio local sem site
        # 1. GBP QUALIDADE
        categorias['gbp_qualidade'] = self._avaliar_gbp()
        # 2. REPUTACAO
        categorias['reputacao'] = self._avaliar_reputacao()
        # 3. ENTIDADE
        categorias['entidade'] = self._avaliar_entidade()
        # 4. PRESENCA EXTERNA
        categorias['presenca_externa'] = self._avaliar_presenca_externa()
        # 5. SINAIS SOCIAIS
        categorias['sinais_sociais'] = self._avaliar_sinais_sociais()

        return self._finalizar(categorias, use_local=True)

    def _avaliar_gbp(self):
        checks = {}
        gbp_verif = self.verificacao.get('gbp', {}) if self.verificacao else {}

        if gbp_verif.get('status') == 'encontrado':
            dados_reais = {
                'fotos': gbp_verif.get('tem_fotos', False),
                'horario': gbp_verif.get('tem_horario', False),
                'descricao': gbp_verif.get('tem_descricao', False),
            }
            presentes = [k for k, v in dados_reais.items() if v]
            ausentes = [k for k, v in dados_reais.items() if not v]
            score_completo = len(presentes) / len(dados_reais) if dados_reais else 0

            checks['gbp_cadastrado'] = {'score': 1, 'max': 1,
                'msg': f'GBP confirmado no Google Maps ({gbp_verif.get("nome_gbp", "")})',
                'fonte': 'Google Places API'}
            checks['gbp_completo'] = {
                'score': score_completo, 'max': 1,
                'presentes': presentes,
                'ausentes': ausentes,
                'fonte': 'Google Places API',
                'msg': f'GBP {len(presentes)}/{len(dados_reais)} completo (fotos, horario, descricao)' if ausentes else 'GBP 100% completo (fotos, horario, descricao)',
            }
            checks['gbp_fotos'] = {'score': 1 if dados_reais['fotos'] else 0, 'max': 1,
                'fonte': 'verificado', 'qtd': gbp_verif.get('qtd_fotos', 0)}
            checks['horario_registrado'] = {'score': 1 if dados_reais['horario'] else 0, 'max': 1,
                'fonte': 'Google Places API'}
            checks['categoria_definida'] = {'score': 1 if self.categoria else 0.5, 'max': 1,
                'msg': 'Categoria nao definida no questionario' if not self.categoria else ''}
        else:
            checks['gbp_cadastrado'] = {'score': 1 if self.tem_gbp else 0, 'max': 1,
                'msg': '' if self.tem_gbp else 'Google Business Profile nao cadastrado',
                'fonte': 'autodeclarado'}
            checks['gbp_completo'] = {'score': 1 if self.gbp_completa else 0, 'max': 1,
                'msg': '' if self.gbp_completa else 'GBP incompleto — faltam fotos, descricao, atributos',
                'fonte': 'autodeclarado'}
            checks['horario_registrado'] = {'score': 1 if self.horario else 0, 'max': 1,
                'fonte': 'autodeclarado'}
            checks['categoria_definida'] = {'score': 1 if self.categoria else 0, 'max': 1}

        checks['gbp_posts'] = {'score': 1 if self.gbp_posts else 0, 'max': 1,
            'msg': '' if self.gbp_posts else 'Sem posts no GBP — IAs interpretam como negocio inativo',
            'fonte': 'autodeclarado (nao verificavel via API)'}

        imagens = self.perfil.get('imagens_trabalhos', False)
        if isinstance(imagens, str):
            imagens = imagens.lower() == 'sim'
        checks['portfolio_fotos'] = {'score': 1 if imagens else 0, 'max': 1,
            'msg': '' if imagens else 'Sem fotos de trabalhos — IAs priorizam perfis com portfolio visual',
            'fonte': 'autodeclarado'}
        nota = self._calc_nota(checks)
        return {'nota': nota, 'checks': checks}

    def _avaliar_reputacao(self):
        checks = {}
        gbp_verif = self.verificacao.get('gbp', {}) if self.verificacao else {}

        # QUANTIDADE: usa dado verificado se disponivel
        if gbp_verif.get('status') == 'encontrado' and gbp_verif.get('total_reviews') is not None:
            count = gbp_verif['total_reviews']
            if count >= 150:
                checks['quantidade'] = {'score': 1.0, 'max': 1, 'valor_real': count, 'fonte': 'Google Places API'}
            elif count >= 100:
                checks['quantidade'] = {'score': 0.8, 'max': 1, 'valor_real': count, 'fonte': 'Google Places API'}
            elif count >= 50:
                checks['quantidade'] = {'score': 0.6, 'max': 1, 'valor_real': count, 'fonte': 'Google Places API'}
            elif count >= 30:
                checks['quantidade'] = {'score': 0.5, 'max': 1, 'valor_real': count, 'fonte': 'Google Places API'}
            elif count >= 10:
                checks['quantidade'] = {'score': 0.3, 'max': 1, 'valor_real': count, 'fonte': 'Google Places API'}
            elif count >= 1:
                checks['quantidade'] = {'score': 0.1, 'max': 1, 'valor_real': count, 'fonte': 'Google Places API'}
            else:
                checks['quantidade'] = {'score': 0, 'max': 1, 'valor_real': count, 'fonte': 'Google Places API',
                    'msg': 'Nenhuma avaliacao encontrada no Google Maps'}
        else:
            qtd = self.avaliacoes_qtd
            if qtd in ('100+',):
                checks['quantidade'] = {'score': 1.0, 'max': 1, 'fonte': 'autodeclarado'}
            elif qtd in ('31-100',):
                checks['quantidade'] = {'score': 0.7, 'max': 1, 'fonte': 'autodeclarado'}
            elif qtd in ('11-30',):
                checks['quantidade'] = {'score': 0.4, 'max': 1, 'fonte': 'autodeclarado'}
            elif qtd in ('1-10',):
                checks['quantidade'] = {'score': 0.15, 'max': 1, 'fonte': 'autodeclarado',
                    'msg': 'Poucas avaliacoes — meta 150+ para ser citado por IAs'}
            else:
                checks['quantidade'] = {'score': 0, 'max': 1, 'fonte': 'autodeclarado',
                    'msg': 'Sem avaliacoes no Google'}

        # NOTA MEDIA: usa dado verificado se disponivel
        if gbp_verif.get('status') == 'encontrado' and gbp_verif.get('rating') is not None:
            rating = gbp_verif['rating']
            if rating >= 4.6:
                checks['nota_media'] = {'score': 1.0, 'max': 1, 'valor_real': rating, 'fonte': 'Google Places API'}
            elif rating >= 4.1:
                checks['nota_media'] = {'score': 0.7, 'max': 1, 'valor_real': rating, 'fonte': 'Google Places API'}
            elif rating >= 3.1:
                checks['nota_media'] = {'score': 0.4, 'max': 1, 'valor_real': rating, 'fonte': 'Google Places API'}
            else:
                checks['nota_media'] = {'score': 0, 'max': 1, 'valor_real': rating, 'fonte': 'Google Places API',
                    'msg': f'Nota baixa ({rating})'}
        else:
            nota = self.avaliacoes_nota
            if nota in ('4.6-5.0',):
                checks['nota_media'] = {'score': 1.0, 'max': 1, 'fonte': 'autodeclarado'}
            elif nota in ('4.1-4.5',):
                checks['nota_media'] = {'score': 0.7, 'max': 1, 'fonte': 'autodeclarado'}
            elif nota in ('3.1-4.0',):
                checks['nota_media'] = {'score': 0.4, 'max': 1, 'fonte': 'autodeclarado'}
            else:
                checks['nota_media'] = {'score': 0, 'max': 1, 'fonte': 'autodeclarado',
                    'msg': 'Nota baixa ou sem informacao'}

        checks['responde'] = {'score': 1 if self.responde_avaliacoes else 0, 'max': 1,
            'msg': '' if self.responde_avaliacoes else 'Nao responde avaliacoes — IAs valorizam engajamento',
            'fonte': 'autodeclarado (nao verificavel via API)'}

        # RECENCIA: verificacao parcial
        if gbp_verif.get('status') == 'encontrado' and gbp_verif.get('total_reviews', 0) > 0:
            checks['recencia'] = {'score': 0.5, 'max': 1,
                'msg': 'GBP tem reviews, mas nao podemos confirmar data exata via API',
                'fonte': 'parcial'}
        elif self.review_recencia:
            checks['recencia'] = {'score': 1 if self.review_recencia else 0, 'max': 1,
                'fonte': 'autodeclarado'}
        else:
            checks['recencia'] = {'score': 0, 'max': 1,
                'msg': 'Sem reviews recentes — IAs favorecem negocios com atividade nos ultimos 3 meses',
                'fonte': 'autodeclarado'}

        nota = self._calc_nota(checks)
        return {'nota': nota, 'checks': checks}

    def _avaliar_entidade(self):
        checks = {}
        gbp_verif = self.verificacao.get('gbp', {}) if self.verificacao else {}

        endereco_real = gbp_verif.get('endereco', '') if gbp_verif.get('status') == 'encontrado' else ''
        telefone_real = gbp_verif.get('telefone', '') if gbp_verif.get('status') == 'encontrado' else ''

        endereco_uso = endereco_real or self.endereco
        telefone_uso = telefone_real or self.telefone

        if endereco_uso and len(endereco_uso) > 10:
            checks['endereco'] = {'score': 1, 'max': 1,
                'fonte': 'Google Places API' if endereco_real else 'autodeclarado'}
        else:
            checks['endereco'] = {'score': 0, 'max': 1, 'msg': 'Endereco nao informado',
                'fonte': 'autodeclarado'}
        if telefone_uso:
            digits = ''.join(filter(str.isdigit, telefone_uso))
            checks['telefone'] = {'score': 1 if len(digits) >= 10 else 0.5, 'max': 1,
                'fonte': 'Google Places API' if telefone_real else 'autodeclarado'}
        else:
            checks['telefone'] = {'score': 0, 'max': 1, 'msg': 'Telefone nao informado'}

        checks['servicos'] = {'score': min(len(self.servicos) / 5, 1), 'max': 1}
        checks['categoria'] = {'score': 1 if self.categoria else 0, 'max': 1}
        checks['cidade'] = {'score': 1 if self.cidade else 0, 'max': 1}

        bairros = self.perfil.get('bairros', '')
        checks['area_cobertura'] = {'score': 1 if bairros and len(bairros) > 5 else 0, 'max': 1,
            'msg': '' if bairros and len(bairros) > 5 else 'Bairros atendidos nao informados'}

        diferenciais = self.perfil.get('diferenciais', '')
        checks['diferenciais'] = {'score': 1 if diferenciais and len(diferenciais) > 10 else 0, 'max': 1,
            'msg': '' if diferenciais and len(diferenciais) > 10 else 'Diferenciais competitivos nao informados'}

        nota = self._calc_nota(checks)
        return {'nota': nota, 'checks': checks}

    def _avaliar_presenca_externa(self):
        checks = {}
        busca_google = self.verificacao.get('plataformas', {}).get('busca_google', {}) if self.verificacao else {}

        plataformas_detectadas = busca_google.get('plataformas_detectadas', [])

        # Foursquare
        tem_foursquare = self.foursquare or 'foursquare' in plataformas_detectadas
        checks['foursquare'] = {'score': 1 if tem_foursquare else 0, 'max': 1,
            'msg': '' if tem_foursquare else 'Nao esta no Foursquare — ~70% dos dados locais do ChatGPT vêm daqui',
            'fonte': 'verificacao via busca' if 'foursquare' in plataformas_detectadas else
                      ('autodeclarado' if not tem_foursquare else 'autodeclarado')}

        outras = self.outras_plataformas.lower() if self.outras_plataformas else ''
        yelp = 'yelp' in outras or 'yelp' in plataformas_detectadas
        apple = 'apple' in outras or 'apple_maps' in plataformas_detectadas
        bing = 'bing' in outras or 'bing_places' in plataformas_detectadas
        trip = 'tripadvisor' in outras or 'tripadvisor' in plataformas_detectadas

        checks['yelp'] = {'score': 1 if yelp else 0, 'max': 1,
            'fonte': 'detectado via busca' if 'yelp' in plataformas_detectadas else 'autodeclarado'}
        checks['apple_maps'] = {'score': 1 if apple else 0, 'max': 1}
        checks['bing_places'] = {'score': 1 if bing else 0, 'max': 1}
        checks['tripadvisor'] = {'score': 1 if trip else 0, 'max': 1,
            'fonte': 'detectado via busca' if 'tripadvisor' in plataformas_detectadas else 'autodeclarado'}

        concorrentes = self.perfil.get('concorrentes', '')
        checks['concorrentes_mapa'] = {'score': 0.5 if concorrentes and len(concorrentes) > 3 else 0, 'max': 1,
            'msg': '' if concorrentes and len(concorrentes) > 3 else 'Concorrentes nao mapeados'}

        nota = self._calc_nota(checks)
        return {'nota': nota, 'checks': checks}

    def _avaliar_sinais_sociais(self):
        checks = {}
        checks['instagram'] = {'score': 1 if self.instagram else 0, 'max': 1}
        checks['facebook'] = {'score': 1 if self.facebook else 0, 'max': 1}
        tem_wpp = self.perfil.get('tem_whatsapp_business', False)
        if isinstance(tem_wpp, str):
            tem_wpp = tem_wpp.lower() == 'sim'
        checks['whatsapp'] = {'score': 1 if tem_wpp else (0.5 if self.telefone else 0), 'max': 1,
            'msg': '' if tem_wpp else 'WhatsApp Business nao cadastrado'}
        duvidas_count = len([l for l in self.duvidas.split('\n') if l.strip()]) if self.duvidas else 0
        checks['faq'] = {'score': min(duvidas_count / 3, 1), 'max': 1}
        nota = self._calc_nota(checks)
        return {'nota': nota, 'checks': checks}

    def _avaliar_ecommerce(self):
        checks = {}
        site_schemas = getattr(self, '_site_schemas', None) or {}

        tem_product = site_schemas.get('product') is not None
        tem_service = site_schemas.get('service') is not None
        tem_offer = site_schemas.get('offer') is not None
        tem_aggregate_rating = site_schemas.get('aggregaterating') is not None

        is_ecommerce = self.perfil.get('tipo_negocio', '') == 'ecommerce' or self.perfil.get('vende_online', False)
        if isinstance(is_ecommerce, str):
            is_ecommerce = is_ecommerce.lower() in ('sim', 'true', '1', 'ecommerce', 'loja virtual')

        product_data = site_schemas.get('product', {})
        has_price = product_data.get('fields', {}).get('price', False) if isinstance(product_data, dict) else False
        has_name = product_data.get('fields', {}).get('name', False) if isinstance(product_data, dict) else False

        if not tem_product and not is_ecommerce:
            checks['product_schema'] = {'score': 0, 'max': 1,
                'msg': 'Nao detectado — se vende produtos, schema Product ajuda rich snippets'}
            checks['offer_price'] = {'score': 0, 'max': 1}
            checks['aggregate_rating'] = {'score': 0, 'max': 1}
            checks['multi_product'] = {'score': 0, 'max': 1}
        else:
            checks['product_schema'] = {'score': 1 if (tem_product or tem_service) else 0, 'max': 1,
                'msg': '' if (tem_product or tem_service) else 'Falta schema de Produto ou Servico'}
            checks['offer_price'] = {'score': 1 if (has_price or tem_offer) else 0, 'max': 1,
                'msg': '' if (has_price or tem_offer) else 'Falta preco no schema — essencial para rich snippets de produto'}
            checks['aggregate_rating'] = {'score': 1 if tem_aggregate_rating else 0, 'max': 1,
                'msg': '' if tem_aggregate_rating else 'Falta schema AggregateRating — mostra estrelas nos resultados'}
            product_count = site_schemas.get('product_count', 0) if isinstance(site_schemas, dict) else 0
            checks['multi_product'] = {'score': min(product_count / 5, 1) if product_count > 1 else 0.5 if tem_product else 0, 'max': 1,
                'msg': f'{product_count} produtos detectados' if product_count > 0 else 'Apenas um produto ou pagina sem produto'}

        nota = self._calc_nota(checks)
        return {'nota': nota, 'checks': checks}

    def _calc_nota(self, checks):
        t = sum(c['score'] for c in checks.values())
        m = sum(c['max'] for c in checks.values())
        return _clamp(round((t / m) * 10, 1)) if m > 0 else 0

    def _finalizar(self, categorias, use_local, com_site=False):
        if com_site:
            pesos = WEIGHTS_COM_SITE
        elif use_local:
            pesos = WEIGHTS_LOCAL
        else:
            pesos = WEIGHTS

        nota_final = 0
        breakdown = {}
        for category, weight in pesos.items():
            if category in categorias:
                nota_cat = categorias[category].get('nota', 0)
                nota_final += nota_cat * weight
                breakdown[category] = {
                    'nota': nota_cat,
                    'peso': weight,
                    'contribuicao': round(nota_cat * weight, 2)
                }

        nota_final = _clamp(round(nota_final, 1))

        detalhes = self._gerar_plano_acao(categorias, use_local)

        resultado = {
            'nota_final': nota_final,
            'breakdown': breakdown,
            'detalhes': detalhes,
            'categorias': categorias,
            'nome': self.nome,
            'tem_site': self.has_site(),
            'servicos': self.servicos,
        }

        if self.multi_llm:
            resultado['multi_llm'] = self.multi_llm

        # ─── ANEXAR VERIFICACAO AUTOMATICA ────────────────────────────
        if self.verificacao and self.verificacao.get('status') != 'falha':
            gbp_verif = self.verificacao.get('gbp', {})
            resultado['verificacao_automatica'] = {
                'gbp': {
                    'status': gbp_verif.get('status', 'nao_verificado'),
                    'mensagem': gbp_verif.get('mensagem', ''),
                    'fonte': gbp_verif.get('fonte', ''),
                },
                'redes_sociais': self.verificacao.get('redes_sociais', {}),
                'plataformas': self.verificacao.get('plataformas', {}),
            }

            # Dados detalhados do GBP se encontrado
            if gbp_verif.get('status') == 'encontrado':
                resultado['verificacao_automatica']['gbp']['dados'] = {
                    'nome_gbp': gbp_verif.get('nome_gbp'),
                    'endereco': gbp_verif.get('endereco'),
                    'rating': gbp_verif.get('rating'),
                    'total_reviews': gbp_verif.get('total_reviews'),
                    'tem_fotos': gbp_verif.get('tem_fotos'),
                    'qtd_fotos': gbp_verif.get('qtd_fotos'),
                    'tem_horario': gbp_verif.get('tem_horario'),
                    'tem_website': gbp_verif.get('tem_website'),
                    'tem_descricao': gbp_verif.get('tem_descricao'),
                    'gbp_url': gbp_verif.get('gbp_url'),
                }

                # Comparacao autodeclarado vs verificado
                originais = self.perfil.get('_dados_originais', {})
                comparacao = {}
                if originais.get('avaliacoes_nota'):
                    comparacao['nota_media'] = {
                        'autodeclarado': originais['avaliacoes_nota'],
                        'verificado': f'{gbp_verif.get("rating", "?")}'
                    }
                if originais.get('avaliacoes_google'):
                    comparacao['quantidade_avaliacoes'] = {
                        'autodeclarado': originais['avaliacoes_google'],
                        'verificado': str(gbp_verif.get('total_reviews', '?'))
                    }
                if originais.get('gbp_completa') is not None:
                    comparacao['gbp_completo'] = {
                        'autodeclarado': 'Sim' if originais.get('gbp_completa') else 'Nao',
                        'verificado': 'Sim' if gbp_verif.get('tem_fotos') and gbp_verif.get('tem_horario') and gbp_verif.get('tem_descricao') else 'Nao'
                    }
                if comparacao:
                    resultado['verificacao_automatica']['comparacao'] = comparacao

        # Discrepancias
        if self.discrepancias:
            resultado['discrepancias'] = self.discrepancias

        return resultado

    def _gerar_plano_acao(self, categorias, use_local):
        acoes = []

        # ─── DISCREPANCIAS DE VERIFICACAO ──────────────────────────
        if self.discrepancias:
            acoes.append('=== DISCREPANCIAS ENTRE AUTODECLARADO E VERIFICADO ===')
            for d in self.discrepancias:
                acoes.append(f'[{d.get("severidade", "info").upper()}] {d.get("resumo", d.get("mensagem", ""))}')
            acoes.append('')

        # ─── RESUMO DA VERIFICACAO AUTOMATICA ──────────────────────
        if self.verificacao and self.verificacao.get('gbp', {}).get('status') == 'encontrado':
            gbp = self.verificacao['gbp']
            acoes.append(f'GBP VERIFICADO: {gbp.get("nome_gbp", "")}')
            acoes.append(f'  Rating real: {gbp.get("rating", "?")} | Reviews: {gbp.get("total_reviews", "?")}')
            ausentes = []
            if not gbp.get('tem_fotos'): ausentes.append('fotos')
            if not gbp.get('tem_horario'): ausentes.append('horario')
            if not gbp.get('tem_descricao'): ausentes.append('descricao')
            if not gbp.get('tem_website'): ausentes.append('website no perfil')
            if ausentes:
                acoes.append(f'  Itens ausentes no GBP: {", ".join(ausentes)}')
            acoes.append('')

        if not self.has_site():
            acoes.append('Sem site — GBP e redes sociais ajudam, mas IAs tem acesso limitado a informacoes estruturadas.')
            acoes.append('Criar site mesmo simples com schema LocalBusiness + Service + FAQPage aumenta muito a visibilidade em IA.')

        if not self.tem_gbp:
            acoes.append('CRITICO: Sem Google Business Profile. IAs nao confirmam se o negocio existe.')
        else:
            if not self.gbp_completa:
                acoes.append('GBP incompleto — preencha fotos, descricao, servicos, atributos e horarios. GBP completo representa ~32% dos fatores de ranqueamento em IA.')
            if not self.gbp_posts:
                acoes.append('Publique posts semanais no GBP — IAs interpretam atividade como sinal de negocio ativo e confiavel.')

        qtd = self.avaliacoes_qtd
        if qtd in ('nenhuma', '1-10'):
            acoes.append('Poucas avaliacoes no Google. IAs priorizam negocios com 20+ reviews. Meta ideal: 150+ para ser citado por ChatGPT e Perplexity.')
        if not self.review_recencia:
            acoes.append('Sem avaliacoes recentes — IAs favorecem negocios com reviews nos ultimos 3 meses. Peça reviews ativamente.')
        if not self.responde_avaliacoes:
            acoes.append('Responda todas as avaliacoes — IAs analisam engajamento como sinal de qualidade.')

        if not self.foursquare:
            acoes.append('Cadastre-se no Foursquare (business.foursquare.com) — ~70% dos dados de negocios locais do ChatGPT vêm dessa plataforma.')

        outras = self.outras_plataformas.lower() if self.outras_plataformas else ''
        essenciais = ['yelp', 'apple', 'bing']
        encontradas = sum(1 for p in essenciais if p in outras)
        if encontradas < 2:
            acoes.append('Pouca presenca em diretorios — cadastre-se em Yelp, Apple Business Connect e Bing Places para consistencia de dados entre plataformas.')

        if not self.instagram and not self.facebook:
            acoes.append('Sem redes sociais — IAs tem menos fontes para confirmar seus dados. Crie ao menos Instagram ou Facebook.')

        if not self.servicos or len(self.servicos) < 3:
            acoes.append('Liste ao menos 3-5 servicos para as IAs indexarem e poderem recomendar.')

        duvidas_count = len([l for l in self.duvidas.split('\n') if l.strip()]) if self.duvidas else 0
        if duvidas_count < 2:
            acoes.append('FAQ nao preenchido — perguntas frequentes sao o formato favorito das IAs para extrair e citar respostas.')

        bairros = self.perfil.get('bairros', '')
        if not bairros or len(bairros) < 5:
            acoes.append('Defina os bairros/regioes atendidos — IAs usam area de cobertura para recomendar seu negocio.')

        publico = self.perfil.get('publico_alvo', '')
        if not publico or len(publico) < 5:
            acoes.append('Defina seu publico-alvo — IAs precisam saber quem voce atende para recomendar corretamente.')

        diffs = self.perfil.get('diferenciais', '')
        if not diffs or len(diffs) < 10:
            acoes.append('Destaque seus diferenciais — IAs usam diferencas competitivas para justificar recomendacoes.')

        concs = self.perfil.get('concorrentes', '')
        if not concs or len(concs) < 3:
            acoes.append('Mapeie seus concorrentes — saber contra quem voce compete ajuda a IA a posicionar seu negocio.')

        if self.has_site():
            ft = categorias.get('fundacao_tecnica', {}).get('checks', {})
            if ft.get('llms_txt', {}).get('score', 0) == 0:
                acoes.append('Criar arquivo llms.txt na raiz do site para instruir IAs.')
            if ft.get('ai_crawlers', {}).get('denied'):
                denied = ft['ai_crawlers']['denied']
                acoes.append(f'Liberar AI crawlers bloqueados no robots.txt: {", ".join(denied)}')
            de = categorias.get('dados_estruturados', {})
            missing = de.get('missing_high_value', [])
            if missing:
                acoes.append(f'Adicionar schemas: {", ".join(missing[:5])}')

        if not acoes:
            acoes.append('Negocio bem posicionado. Manter monitoramento continuo.')

        return acoes
