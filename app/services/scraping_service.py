import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import os
import torch
from langdetect import detect, LangDetectException

try:
    from flask import current_app, has_app_context
except ImportError:
    current_app = None
    def has_app_context():
        return False

from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

class ScrapingService:
    DEFAULT_TIMEOUT = 10

    NEWS_CATEGORIES = {
        'world': ['monde', 'international', 'global'],
        'nation': ['national', 'pays', 'france', 'cameroon', 'cameroun'],
        'business': ['business', 'économie', 'finance', 'bourse', 'entreprise'],
        'technology': ['tech', 'technologie', 'informatique', 'innovation'],
        'entertainment': ['cinéma', 'musique', 'spectacle', 'divertissement'],
        'sports': ['sport', 'football', 'rugby', 'tennis', 'basket'],
        'science': ['science', 'recherche', 'découverte', 'espace'],
        'health': ['santé', 'médecine', 'bien-être', 'virus', 'covid'],
    }

    _summarizer_tokenizer = None
    _summarizer_model = None

    @classmethod
    def _load_summarizer_model(cls):
        if cls._summarizer_tokenizer is None or cls._summarizer_model is None:
            model_name = "mrm8488/bert2bert_shared-french-summarization"
            cls._summarizer_tokenizer = AutoTokenizer.from_pretrained(model_name)
            cls._summarizer_model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        return cls._summarizer_tokenizer, cls._summarizer_model

    @classmethod
    def enrich_with_ai_summary(cls, text, lang="fr"):
        if not text or len(text.split()) < 5:
            return "Résumé indisponible."
        try:
            tokenizer, model = cls._load_summarizer_model()
            model.eval()
            inputs = tokenizer([text], max_length=512, return_tensors="pt", truncation=True)
            with torch.no_grad():
                summary_ids = model.generate(
                    inputs["input_ids"],
                    num_beams=4,
                    min_length=10,
                    max_length=60,
                    early_stopping=True
                )
            summary = tokenizer.decode(summary_ids[0], skip_special_tokens=True)
            return summary
        except Exception as e:
            cls._log_error("enrich_with_ai_summary", e)
            return "Résumé indisponible."

    @classmethod
    def get_timeout(cls):
        try:
            if current_app:
                return current_app.config.get('SCRAPE_TIMEOUT', cls.DEFAULT_TIMEOUT)
        except RuntimeError:
            pass
        return cls.DEFAULT_TIMEOUT

    @classmethod
    def _log_error(cls, context, error):
        msg = f"[{context}] Scraping error: {str(error)}"
        if has_app_context() and current_app:
            with current_app.app_context():
                current_app.logger.error(msg)
        else:
            print(msg)

    @classmethod
    def detect_language(cls, text, default="fr"):
        try:
            lang = detect(text)
            return lang if lang in ['fr', 'en', 'es', 'de', 'it'] else default
        except LangDetectException:
            return default

    @classmethod
    def detect_news_category(cls, query):
        query_lower = query.lower()
        for category, keywords in cls.NEWS_CATEGORIES.items():
            if any(kw in query_lower for kw in keywords):
                return category
        return None

    @classmethod
    def reformulate_query(cls, query, lang="fr", debug=False):
        q = query.lower()
        # Reformulation : remplace les questions "c'est quoi", "qu'est-ce que" par "définition"
        if re.search(r"c'est quoi|qu'est-ce que|qu est ce que|c est quoi", q):
            q = re.sub(r"c'est quoi|qu'est-ce que|qu est ce que|c est quoi", 'définition', q)
        if debug:
            print(f"[reformulate_query] Reformulé en: {q.strip()}")
        return q.strip()

    @classmethod
    def extract_keywords(cls, query):
        # Stopwords limités pour ne pas enlever les mots interrogatifs importants
        stopwords = [
            r"qu'est-ce que", r"qu'est ce que", r"définition de",
            r"définir", r"expliquez", r"comment fonctionne", r"à quoi sert",
        ]
        q = query.strip().lower()
        for word in stopwords:
            q = re.sub(re.escape(word), '', q, flags=re.IGNORECASE)
        cleaned = re.sub(r"[^\w\s\.-]", '', q).strip()
        return re.sub(r'\s+', ' ', cleaned) or query

    @classmethod
    def detect_query_type(cls, query):
        q = query.lower()
        if any(x in q for x in ['qu’est-ce', 'qu est ce', 'définition', 'c’est quoi', 'c est quoi', 'définir', "c'est quoi", "c est quoi"]):
            return 'definition'
        elif any(x in q for x in ['actualités', 'news', 'breaking', 'infos', 'actualité']):
            return 'news'
        elif any(x in q for x in ['comment', 'pourquoi', 'fonctionne', 'utilise']):
            return 'how'
        elif any(x in q for x in ['qui', 'où', 'quand']):
            return 'fact'
        return 'general'

    @classmethod
    def _clean_google_url(cls, url):
        parsed = urlparse(url)
        if parsed.netloc.endswith('google.com'):
            qs = parse_qs(parsed.query)
            return qs.get('q', [url])[0]
        return url

    @classmethod
    def _scrape_gnews(cls, query, limit, lang=None, debug=False, category=None):
        try:
            api_key = os.getenv("GNEWS_API_KEY") or (current_app.config.get("GNEWS_API_KEY") if current_app else None)
            if not api_key:
                if debug:
                    print("[_scrape_gnews] Clé API GNews non définie")
                return []
            q = quote_plus(query)
            url = f"https://gnews.io/api/v4/search?q={q}&lang={lang or 'fr'}&max={limit}&token={api_key}"
            if category:
                url += f"&topic={category}"
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=cls.get_timeout())
            if response.status_code != 200:
                return []
            articles = response.json().get('articles', [])[:limit]
            return [ {
                'title': a.get('title'),
                'url': a.get('url'),
                'snippet': a.get('description') or a.get('content') or '',
                'source': 'gnews',
                'ai_summary': cls.enrich_with_ai_summary(a.get('description') or '', lang),
                'enriched': True,
                'image': a.get('image'),
                'language': lang
            } for a in articles ]
        except Exception as e:
            cls._log_error("_scrape_gnews", e)
            return []

    @classmethod
    def _scrape_google(cls, query, limit, lang=None, debug=False):
        try:
            q = quote_plus(query)
            url = f"https://www.google.com/search?q={q}&num={limit}"
            if lang:
                url += f"&hl={lang}"
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=cls.get_timeout())
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            for result in soup.select('div.g'):
                title = result.find('h3')
                link = result.find('a', href=True)
                snippet_tag = result.find('div', class_='IsZvec')
                if title and link:
                    snippet = snippet_tag.get_text(strip=True) if snippet_tag else ''
                    results.append({
                        'title': title.get_text(strip=True),
                        'url': cls._clean_google_url(link['href']),
                        'snippet': snippet,
                        'source': 'google',
                        'ai_summary': cls.enrich_with_ai_summary(snippet, lang),
                        'enriched': True,
                        'image': None,
                        'language': lang
                    })
                    if len(results) >= limit:
                        break
            return results
        except Exception as e:
            cls._log_error("_scrape_google", e)
            return []

    @classmethod
    def _scrape_duckduckgo(cls, query, limit, lang=None, debug=False):
        try:
            url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_html=1&skip_disambig=1"
            data = requests.get(url, timeout=cls.get_timeout()).json()
            if data.get('AbstractText'):
                return [{
                    'title': data.get('Heading', query),
                    'url': data.get('AbstractURL'),
                    'snippet': data['AbstractText'],
                    'source': 'duckduckgo',
                    'ai_summary': cls.enrich_with_ai_summary(data['AbstractText'], lang),
                    'enriched': True,
                    'image': None,
                    'language': lang
                }][:limit]
            return []
        except Exception as e:
            cls._log_error("_scrape_duckduckgo", e)
            return []

    @classmethod
    def _scrape_bing(cls, query, limit, lang=None, debug=False):
        try:
            url = f"https://www.bing.com/search?q={quote_plus(query)}&count={limit}"
            soup = BeautifulSoup(requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=cls.get_timeout()).text, 'html.parser')
            results = []
            for result in soup.find_all('li', class_='b_algo'):
                title = result.find('h2')
                link = result.find('a', href=True)
                snippet = result.find('p')
                if title and link:
                    results.append({
                        'title': title.get_text(strip=True),
                        'url': link['href'],
                        'snippet': snippet.get_text(strip=True) if snippet else '',
                        'source': 'bing',
                        'ai_summary': cls.enrich_with_ai_summary(snippet.get_text(strip=True) if snippet else '', lang),
                        'enriched': True,
                        'image': None,
                        'language': lang
                    })
                    if len(results) >= limit:
                        break
            return results
        except Exception as e:
            cls._log_error("_scrape_bing", e)
            return []

    @classmethod
    def _scrape_wikipedia(cls, query, lang="fr", debug=False):
        try:
            url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote_plus(query)}"
            data = requests.get(url, timeout=cls.get_timeout()).json()
            return [{
                'title': data.get('title'),
                'url': data.get('content_urls', {}).get('desktop', {}).get('page'),
                'snippet': data.get('extract', ''),
                'source': 'wikipedia',
                'ai_summary': cls.enrich_with_ai_summary(data.get('extract', ''), lang),
                'enriched': True,
                'image': data.get('thumbnail', {}).get('source'),
                'language': lang
            }]
        except Exception as e:
            cls._log_error("_scrape_wikipedia", e)
            return []

    @classmethod
    def scrape_web(cls, query, limit=10, lang=None, debug=False):
        try:
            lang = lang or cls.detect_language(query)
            rewritten = cls.reformulate_query(query, lang, debug)

            # IMPORTANT : on ne nettoie PAS la requête reformulée pour garder tous les mots utiles
            cleaned_query = rewritten

            if debug:
                print(f"🔍 Query utilisée pour scraping: '{cleaned_query}', langue: {lang}")

            query_type = cls.detect_query_type(query)
            category = cls.detect_news_category(cleaned_query) if query_type == 'news' else None

            if query_type == 'definition':
                sources = [
                    lambda q, l, ln, d: cls._scrape_wikipedia(q, lang=ln, debug=d),
                    cls._scrape_google,
                ]
            elif query_type == 'news':
                sources = [
                    lambda q, l, ln, d: cls._scrape_gnews(q, l, ln, d, category),
                    cls._scrape_google,
                ]
            else:
                sources = [
                    cls._scrape_google,
                    cls._scrape_duckduckgo,
                    cls._scrape_bing,
                    lambda q, l, ln, d: cls._scrape_wikipedia(q, lang=ln, debug=d),
                ]

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {
                    executor.submit(s, cleaned_query, limit, lang, debug): str(s)
                    for s in sources
                }
                for future in as_completed(futures):
                    res = future.result()
                    if res:
                        return res[:limit]

        except Exception as e:
            cls._log_error("scrape_web", e)

        # Fallback IA local si rien trouvé
        summary = cls.enrich_with_ai_summary(f"{query} est un sujet intéressant. Recherche plus approfondie en cours...", lang)
        return [{
            'title': f'Contenu généré pour {query}',
            'url': None,
            'snippet': summary,
            'source': 'ia-local',
            'ai_summary': summary,
            'enriched': True,
            'image': None,
            'language': lang
        }]

    @classmethod
    def scrape_news(cls, query, limit=10, lang='fr', debug=False):
        category = cls.detect_news_category(query)
        return cls._scrape_gnews(query, limit, lang=lang, debug=debug, category=category)
