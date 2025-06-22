from datetime import datetime, timedelta
from flask import current_app
from bson.objectid import ObjectId

class DashboardService:
    @staticmethod
    def get_user_stats(user_id, start_date, end_date):
        """Statistiques pour un utilisateur donné"""
        mongo = current_app.mongo
        stats = {}

        # Comptage des recherches par date
        pipeline = [
            {"$match": {
                "user_id": ObjectId(user_id),
                "timestamp": {"$gte": start_date, "$lte": end_date}
            }},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]
        search_counts = list(mongo.db.search_history.aggregate(pipeline))
        stats['search_counts'] = {
            "dates": [item['_id'] for item in search_counts],
            "counts": [item['count'] for item in search_counts]
        }

        # Répartition des types de recherche
        type_pipeline = [
            {"$match": {
                "user_id": ObjectId(user_id),
                "timestamp": {"$gte": start_date, "$lte": end_date}
            }},
            {"$group": {"_id": "$search_type", "count": {"$sum": 1}}}
        ]
        type_counts = list(mongo.db.search_history.aggregate(type_pipeline))
        stats['search_types'] = {
            "types": [item['_id'] for item in type_counts],
            "counts": [item['count'] for item in type_counts]
        }

        # Nombre de favoris
        favorites_count = mongo.db.favorites.count_documents({
            "user_id": ObjectId(user_id),
            "added_at": {"$gte": start_date, "$lte": end_date}
        })
        stats['favorites_count'] = favorites_count

        # Jour le plus actif
        top_day_pipeline = [
            {"$match": {
                "user_id": ObjectId(user_id),
                "timestamp": {"$gte": start_date, "$lte": end_date}
            }},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 1}
        ]
        most_active = list(mongo.db.search_history.aggregate(top_day_pipeline))
        if most_active:
            stats['most_active_day'] = {
                "date": most_active[0]['_id'],
                "count": most_active[0]['count']
            }

        return stats

    @staticmethod
    def get_global_stats(start_date, end_date):
        """Statistiques globales (admin)"""
        mongo = current_app.mongo
        stats = {}

        stats['total_users'] = mongo.db.users.estimated_document_count()

        stats['new_users'] = mongo.db.users.count_documents({
            "created_at": {"$gte": start_date, "$lte": end_date}
        })

        stats['total_searches'] = mongo.db.search_history.count_documents({
            "timestamp": {"$gte": start_date, "$lte": end_date}
        })

        # Requêtes populaires
        popular_pipeline = [
            {"$match": {
                "timestamp": {"$gte": start_date, "$lte": end_date}
            }},
            {"$group": {
                "_id": "$query",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]
        popular = list(mongo.db.search_history.aggregate(popular_pipeline))
        stats['popular_queries'] = [{"query": item['_id'], "count": item['count']} for item in popular]

        stats['system_load'] = {
            "cpu": 35.2,
            "memory": 68.5,
            "response_time": 0.42
        }

        return stats

    @staticmethod
    def get_system_stats():
        mongo = current_app.mongo
        stats = {}
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)
        daily_stats = []

        for i in range(7):
            date = start_date + timedelta(days=i)
            next_day = date + timedelta(days=1)

            searches = mongo.db.search_history.count_documents({
                "timestamp": {"$gte": date, "$lt": next_day}
            })

            new_users = mongo.db.users.count_documents({
                "created_at": {"$gte": date, "$lt": next_day}
            })

            daily_stats.append({
                "date": date.strftime('%Y-%m-%d'),
                "searches": searches,
                "new_users": new_users
            })

        stats['daily_stats'] = daily_stats

        stats['totals'] = {
            "users": mongo.db.users.estimated_document_count(),
            "searches": mongo.db.search_history.estimated_document_count(),
            "favorites": mongo.db.favorites.estimated_document_count(),
            "messages": mongo.db.contacts.estimated_document_count()
        }

        return stats

    @staticmethod
    def update_daily_analytics():
        mongo = current_app.mongo
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)

        exists = mongo.db.analytics.find_one({"date": str(yesterday)})
        if exists:
            return

        total_searches = mongo.db.search_history.count_documents({
            "timestamp": {"$gte": datetime.combine(yesterday, datetime.min.time()),
                          "$lt": datetime.combine(today, datetime.min.time())}
        })

        unique_users = len(mongo.db.search_history.distinct("user_id", {
            "timestamp": {"$gte": datetime.combine(yesterday, datetime.min.time()),
                          "$lt": datetime.combine(today, datetime.min.time())}
        }))

        top_query = mongo.db.search_history.aggregate([
            {"$match": {
                "timestamp": {"$gte": datetime.combine(yesterday, datetime.min.time()),
                              "$lt": datetime.combine(today, datetime.min.time())}
            }},
            {"$group": {
                "_id": "$query",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 1}
        ])
        top_query_result = next(top_query, None)

        avg_response_time = 0.35 + (0.1 if total_searches > 1000 else 0)

        mongo.db.analytics.insert_one({
            "date": str(yesterday),
            "total_searches": total_searches,
            "unique_users": unique_users,
            "avg_response_time": avg_response_time,
            "most_popular_query": top_query_result['_id'] if top_query_result else None
        })
