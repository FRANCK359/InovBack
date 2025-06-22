from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from collections import defaultdict
from bson.objectid import ObjectId
from app.services.dashboard_service import DashboardService

bp = Blueprint('dashboard', __name__, url_prefix='/api/v1/dashboard')

@bp.route('/stats', methods=['GET'])
@jwt_required()
def get_stats():
    user_id = get_jwt_identity()
    time_range = request.args.get('range', 'week')

    end_date = datetime.utcnow()
    if time_range == 'week':
        start_date = end_date - timedelta(days=7)
    elif time_range == 'month':
        start_date = end_date - timedelta(days=30)
    else:
        start_date = end_date - timedelta(days=365)

    mongo = current_app.mongo
    users_collection = mongo.db.users
    current_user = users_collection.find_one({"_id": ObjectId(user_id)})

    user_stats = DashboardService.get_user_stats(user_id, start_date, end_date)

    global_stats = {}
    if current_user and current_user.get('is_admin', False):
        global_stats = DashboardService.get_global_stats(start_date, end_date)

    return jsonify({
        'user_stats': user_stats,
        'global_stats': global_stats,
        'time_range': time_range
    })

@bp.route('/history/analytics', methods=['GET'])
@jwt_required()
def get_history_analytics():
    user_id = get_jwt_identity()
    limit = request.args.get('limit', 10, type=int)
    mongo = current_app.mongo.db

    pipeline = [
        {"$match": {"user_id": ObjectId(user_id)}},
        {"$group": {
            "_id": {"query": "$query", "search_type": "$search_type"},
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}},
        {"$limit": limit}
    ]

    results = list(mongo.search_history.aggregate(pipeline))

    top_queries = [{
        "query": r["_id"]["query"],
        "type": r["_id"]["search_type"],
        "count": r["count"]
    } for r in results]

    return jsonify({'top_queries': top_queries})

@bp.route('/favorites/analytics', methods=['GET'])
@jwt_required()
def get_favorites_analytics():
    user_id = get_jwt_identity()
    mongo = current_app.mongo.db

    pipeline_type = [
        {"$match": {"user_id": ObjectId(user_id)}},
        {"$group": {"_id": "$fav_type", "count": {"$sum": 1}}}
    ]
    favorites_by_type_agg = list(mongo.favorites.aggregate(pipeline_type))

    favorites = list(mongo.favorites.find({"user_id": ObjectId(user_id)}, {"tags": 1}))
    all_tags = []
    for fav in favorites:
        tags_field = fav.get("tags", [])
        if isinstance(tags_field, list):
            all_tags.extend(tags_field)
        elif isinstance(tags_field, str):
            tags = [t.strip() for t in tags_field.split(",") if t.strip()]
            all_tags.extend(tags)

    tag_counts = defaultdict(int)
    for tag in all_tags:
        tag_counts[tag] += 1

    top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    return jsonify({
        'by_type': [{'type': item['_id'], 'count': item['count']} for item in favorites_by_type_agg],
        'top_tags': [{'tag': tag, 'count': count} for tag, count in top_tags]
    })

@bp.route('/system/stats', methods=['GET'])
@jwt_required()
def get_system_stats():
    user_id = get_jwt_identity()
    mongo = current_app.mongo
    users_collection = mongo.db.users
    current_user = users_collection.find_one({"_id": ObjectId(user_id)})

    if not current_user or not current_user.get('is_admin', False):
        return jsonify({'error': 'Unauthorized'}), 403

    stats = DashboardService.get_system_stats()

    return jsonify(stats)
