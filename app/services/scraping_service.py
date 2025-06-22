import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import os

try:
    from flask import current_app, has_app_context
except ImportError:
    current_app = None
    def has_app_context():
        return False


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
        if has_app_context() and current_app:
            with current_app.app_context():
                current_app.logger.error(f"[{context}] Scraping error: {str(error)}")
        else:
            print(f"[{context}] Scraping error: {str(error)}")

    @classmethod
    def enrich_with_ai_summary(cls, text, lang="fr"):
        if not text:
            return ""
        if len(text) > 120:
            return text[:117] + "..."
        return text

    @classmethod
    def detect_news_category(cls, query):
        query_lower = query.lower()
        for category, keywords in cls.NEWS_CATEGORIES.items():
            for kw in keywords:
                if kw in query_lower:
                    return category
        return None

    @classmethod
    def reformulate_query(cls, query, lang="fr", debug=False):
        if debug:
            print(f"[reformulate_query] Entrée: {query}")
        return query.strip()

    @classmethod
    def extract_keywords(cls, query):
        stopwords = [
            r"qu'est-ce que", r"qu'est ce que", r"c'est quoi", r"définition de",
            r"définir", r"explique", r"expliquez", r"comment fonctionne", r"à quoi sert",
            r"quelle est", r"qui est", r"où se trouve", r"où est", r"quand", r"comment", r"pourquoi"
        ]
        q = query.strip()
        lower_q = q.lower()
        for word in stopwords:
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            lower_q = pattern.sub(' ', lower_q)
        cleaned = re.sub(r"[^\w\s\.-]", '', lower_q).strip()
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned or query

    @classmethod
    def _scrape_gnews(cls, query, limit, lang=None, debug=False, category=None):
        try:
            api_key = current_app.config.get('GNEWS_API_KEY') if current_app else os.environ.get('GNEWS_API_KEY')
            if not api_key:
                if debug:
                    print("[_scrape_gnews] Clé API GNews non définie")
                return []

            q = quote_plus(query)
            url = f"https://gnews.io/api/v4/search?q={q}&lang={lang or 'fr'}&max={limit}&token={api_key}"
            if category:
                url += f"&topic={category}"

            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=cls.get_timeout())
            if response.status_code != 200:
                return []

            data = response.json()
            return [{
                'title': a.get('title'),
                'url': a.get('url'),
                'snippet': a.get('description') or a.get('content') or '',
                'source': 'gnews',
                'ai_summary': cls.enrich_with_ai_summary(a.get('description') or '', lang),
                'enriched': True,
                'image': a.get('image')
            } for a in data.get('articles', [])][:limit]
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
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=cls.get_timeout())
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
                        'url': link['href'],
                        'snippet': snippet,
                        'source': 'google',
                        'ai_summary': cls.enrich_with_ai_summary(snippet, lang),
                        'enriched': True,
                        'image': None
                    })
            return results[:limit]
        except Exception as e:
            cls._log_error("_scrape_google", e)
            return []

    @classmethod
    def _scrape_duckduckgo(cls, query, limit, lang=None, debug=False):
        try:
            q = quote_plus(query)
            url = f"https://api.duckduckgo.com/?q={q}&format=json&no_html=1&skip_disambig=1"
            response = requests.get(url, timeout=cls.get_timeout())
            data = response.json()
            results = []
            if data.get('AbstractText'):
                results.append({
                    'title': data.get('Heading', query),
                    'url': data.get('AbstractURL'),
                    'snippet': data['AbstractText'],
                    'source': 'duckduckgo',
                    'ai_summary': cls.enrich_with_ai_summary(data['AbstractText'], lang),
                    'enriched': True,
                    'image': None
                })
            return results[:limit]
        except Exception as e:
            cls._log_error("_scrape_duckduckgo", e)
            return []

    @classmethod
    def _scrape_bing(cls, query, limit, lang=None, debug=False):
        try:
            q = quote_plus(query)
            url = f"https://www.bing.com/search?q={q}&count={limit}"
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=cls.get_timeout())
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            for result in soup.find_all('li', class_='b_algo'):
                title = result.find('h2')
                link = result.find('a', href=True)
                snippet = result.find('p')
                if title and link:
                    snippet_text = snippet.get_text(strip=True) if snippet else ''
                    results.append({
                        'title': title.get_text(strip=True),
                        'url': link['href'],
                        'snippet': snippet_text,
                        'source': 'bing',
                        'ai_summary': cls.enrich_with_ai_summary(snippet_text, lang),
                        'enriched': True,
                        'image': None
                    })
            return results[:limit]
        except Exception as e:
            cls._log_error("_scrape_bing", e)
            return []

    @classmethod
    def _scrape_wikipedia(cls, query, lang="fr", debug=False):
        try:
            url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote_plus(query)}"
            response = requests.get(url, timeout=cls.get_timeout())
            if response.status_code != 200:
                return []
            data = response.json()
            return [{
                'title': data.get('title'),
                'url': data.get('content_urls', {}).get('desktop', {}).get('page'),
                'snippet': data.get('extract', ''),
                'source': 'wikipedia',
                'ai_summary': cls.enrich_with_ai_summary(data.get('extract', ''), lang),
                'enriched': True,
                'image': data.get('thumbnail', {}).get('source')
            }]
        except Exception as e:
            cls._log_error("_scrape_wikipedia", e)
            return []

    @classmethod
    def scrape_news(cls, query, limit=10, lang='fr', debug=False):
        return cls._scrape_gnews(query, limit, lang=lang, debug=debug)

    @classmethod
    def scrape_web(cls, query, limit=10, lang='fr', debug=False):
        try:
            rewritten = cls.reformulate_query(query, lang, debug)
            cleaned_query = cls.extract_keywords(rewritten)
            if debug:
                print(f"🔍 Query nettoyée: '{cleaned_query}'")

            is_news_query = any(kw in cleaned_query.lower() for kw in [
                "actualité", "nouvelles", "infos", "news", "breaking", "événements", "politique", "économie", "sport"
            ])

            category = cls.detect_news_category(cleaned_query) if is_news_query else None

            def wikipedia_wrapper(q, l, ln, d):
                return cls._scrape_wikipedia(q, lang=ln, debug=d)

            sources = [
                (lambda q, l, ln, d: cls._scrape_gnews(q, l, ln, d, category)) if is_news_query else None,
                (cls._scrape_google, "google"),
                (cls._scrape_duckduckgo, "duckduckgo"),
                (cls._scrape_bing, "bing"),
                (wikipedia_wrapper, "wikipedia")
            ]

            sources = [s for s in sources if s is not None]

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {
                    executor.submit(func, cleaned_query, limit, lang, debug): name
                    for func, name in sources if func is not None
                }

                for future in as_completed(futures):
                    try:
                        res = future.result()
                        if res:
                            for result in res:
                                result['language'] = lang
                            return res[:limit]
                    except Exception as e:
                        cls._log_error(futures[future], e)

            return [{
                'title': f'Définition de {cleaned_query}',
                'url': f'https://{lang}.wikipedia.org/wiki/{quote_plus(cleaned_query)}',
                'snippet': f"{cleaned_query.capitalize()} est un concept dont la définition peut varier selon le contexte.",
                'source': 'fallback',
                'ai_summary': "Résumé IA non disponible.",
                'enriched': True,
                'language': lang,
                'image': None
            }]
        except Exception as e:
            cls._log_error("scrape_web", e)
            return []