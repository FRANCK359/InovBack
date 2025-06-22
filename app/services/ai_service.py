import time
import re
import torch
from flask import current_app
from transformers import pipeline
from tenacity import retry, stop_after_attempt, wait_exponential

class AIService:
    model = None

    @staticmethod
    def initialize():
        try:
            device = 0 if torch.cuda.is_available() else -1
            AIService.model = pipeline("question-answering", model="illuin/camembert-base-fquad", device=device)
            current_app.logger.info(f"✅ CamemBERT chargé en local avec succès sur device {device}.")
        except Exception as e:
            current_app.logger.error(f"❌ Erreur chargement modèle local : {e}")

    @staticmethod
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
    def enrich_search_results(query, results):
        if not results or not AIService.model:
            return []

        enriched = []
        for result in results:
            try:
                context = result.get('snippet', '')[:512].strip()
                if not context:
                    enriched.append({
                        **result,
                        'ai_summary': "Résumé indisponible",
                        'relevance_score': 5,
                        'topics': [],
                        'enriched': False
                    })
                    continue

                summary_answer = AIService.model(question="Donne un résumé court de ce texte.", context=context)
                if isinstance(summary_answer, list):
                    summary_answer = summary_answer[0] if summary_answer else None
                summary = summary_answer.get('answer') if summary_answer else 'Résumé indisponible'

                relevance_answer = AIService.model(
                    question=f"Sur une échelle de 1 à 10, quelle est la pertinence de ce texte pour : {query} ?",
                    context=context
                )
                if isinstance(relevance_answer, list):
                    relevance_answer = relevance_answer[0] if relevance_answer else None
                relevance_text = relevance_answer.get('answer') if relevance_answer else ''
                relevance_nums = re.findall(r'\d+', relevance_text)
                score = int(relevance_nums[0]) if relevance_nums else 5

                words = re.findall(r'\w+', context.lower())
                stopwords = {"le", "la", "les", "de", "des", "et", "un", "une", "à",
                             "pour", "dans", "du", "est", "sur", "avec", "en", "ce", "il", "elle"}
                keywords = [w for w in words if w not in stopwords]
                freq = {}
                for w in keywords:
                    freq[w] = freq.get(w, 0) + 1
                topics = sorted(freq, key=freq.get, reverse=True)[:5]

                enriched.append({
                    **result,
                    'ai_summary': summary,
                    'relevance_score': score,
                    'topics': topics,
                    'enriched': True
                })

                time.sleep(0.3)

            except Exception as e:
                current_app.logger.warning(f"[Local AI Error] {e} - context: {context[:100]}")
                enriched.append({
                    **result,
                    'ai_summary': "Résumé indisponible",
                    'relevance_score': 5,
                    'topics': [],
                    'enriched': False
                })

        return sorted(enriched, key=lambda x: x['relevance_score'], reverse=True)

    @staticmethod
    def get_suggestions(query):
        keywords = re.findall(r'\w+', query.lower())
        if not keywords:
            return []
        kw = keywords[0]
        return [
            f"{kw} actualités",
            f"{kw} résumé",
            f"{kw} explication",
            f"{kw} en détail",
            f"{kw} 2025"
        ]
