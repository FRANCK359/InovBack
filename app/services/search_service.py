from flask import current_app
from datetime import datetime, timedelta
from pymongo import DESCENDING
from transformers import CamembertTokenizer, CamembertForMaskedLM
import torch
import re


class SearchService:

    # Chargement modèle et tokenizer CamemBERT une seule fois (classe statique)
    _tokenizer = None
    _model = None

    @classmethod
    def _load_camembert(cls):
        if cls._tokenizer is None or cls._model is None:
            cls._tokenizer = CamembertTokenizer.from_pretrained('camembert-base')
            cls._model = CamembertForMaskedLM.from_pretrained('camembert-base')
        return cls._tokenizer, cls._model

    @staticmethod
    def apply_filters(results, filters):
        # (Ta logique inchangée)
        if not results:
            return results

        filtered = results.copy()

        if filters.get('domain'):
            domain = filters['domain'].lower()
            filtered = [r for r in filtered if domain in r.get('url', '').lower()]

        date_filter = filters.get('date', 'any')
        if date_filter != 'any':
            now = datetime.utcnow()
            if date_filter == 'day':
                cutoff = now - timedelta(days=1)
            elif date_filter == 'week':
                cutoff = now - timedelta(weeks=1)
            elif date_filter == 'month':
                cutoff = now - timedelta(days=30)
            elif date_filter == 'year':
                cutoff = now - timedelta(days=365)
            filtered = [r for r in filtered if 'date' in r and r['date'] >= cutoff]

        type_filter = filters.get('type', 'all')
        if type_filter != 'all':
            filtered = [r for r in filtered if r.get('type', '').lower() == type_filter]

        lang_filter = filters.get('language', 'fr')
        if lang_filter != 'any':
            filtered = [r for r in filtered if r.get('language', 'fr') == lang_filter]

        return filtered

    @staticmethod
    def get_suggestions(query, limit=5):
        """Retourne des suggestions de recherche basées sur l'historique + IA locale."""
        if len(query) < 2:
            return []

        collection = current_app.mongo.db.search_history
        pipeline = [
            {"$match": {"query": {"$regex": query, "$options": "i"}}},
            {"$group": {"_id": "$query", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": limit * 2}
        ]
        results = collection.aggregate(pipeline)
        suggestions = {item['_id'] for item in results}

        if len(suggestions) < limit:
            try:
                ai_suggestions = SearchService.get_ai_suggestions_local(query, limit)
                suggestions.update(ai_suggestions)
            except Exception as e:
                current_app.logger.error(f"Local AI suggestion error: {e}")

        return list(suggestions)[:limit]

    @classmethod
    def get_ai_suggestions_local(cls, query, limit=5):
        """Génère des suggestions basiques via CamemBERT localement."""

        tokenizer, model = cls._load_camembert()
        model.eval()

        # Format de la phrase avec un [MASK] pour deviner un mot-clé
        # Exemple : "Je cherche des informations sur [MASK]"
        # Ou on peut simplement essayer de prédire des mots masqués autour du query
        prompt_template = f"{query} [MASK]"

        input_text = prompt_template
        input_ids = tokenizer.encode(input_text, return_tensors='pt')

        mask_token_index = torch.where(input_ids == tokenizer.mask_token_id)[1]

        with torch.no_grad():
            output = model(input_ids)
        logits = output.logits

        mask_token_logits = logits[0, mask_token_index, :]
        top_tokens = torch.topk(mask_token_logits, limit, dim=1).indices[0].tolist()

        suggestions = []
        for token_id in top_tokens:
            token = tokenizer.decode([token_id]).strip()
            # Nettoyage basique : pas de ponctuation, pas de tokens vides
            if token and re.match(r'^\w+$', token):
                suggestion = f"{query} {token}"
                suggestions.append(suggestion)

        return suggestions[:limit]

    @staticmethod
    def log_search(user_id, query, search_type='text', source='web'):
        collection = current_app.mongo.db.search_history
        search_data = {
            "user_id": user_id,
            "query": query,
            "search_type": search_type,
            "source": source,
            "timestamp": datetime.utcnow()
        }
        collection.insert_one(search_data)
        return search_data

    @staticmethod
    def get_popular_searches(days=7, limit=10):
        collection = current_app.mongo.db.search_history
        cutoff = datetime.utcnow() - timedelta(days=days)

        pipeline = [
            {"$match": {"timestamp": {"$gte": cutoff}}},
            {"$group": {"_id": "$query", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": limit}
        ]

        results = collection.aggregate(pipeline)
        return [{"query": item["_id"], "count": item["count"]} for item in results]

    @staticmethod
    def get_search_trends(days=30):
        collection = current_app.mongo.db.search_history
        cutoff = datetime.utcnow() - timedelta(days=days)

        pipeline = [
            {"$match": {"timestamp": {"$gte": cutoff}}},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]

        results = collection.aggregate(pipeline)
        trends_dict = {item["_id"]: item["count"] for item in results}

        date_range = [cutoff + timedelta(days=i) for i in range(days)]
        trends = []
        for date in date_range:
            date_str = date.strftime("%Y-%m-%d")
            trends.append({
                "date": date_str,
                "count": trends_dict.get(date_str, 0)
            })

        return trends
