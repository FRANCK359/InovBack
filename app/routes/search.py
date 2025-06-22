from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from bson.objectid import ObjectId
from functools import wraps
import traceback

from app.services.search_service import SearchService
from app.services.scraping_service import ScrapingService
from app.services.ai_service import AIService
from app.utils.decorators import validate_json  # si utilisé dans ton projet

bp = Blueprint('search', __name__, url_prefix='/api/v1/search')


def handle_options(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == 'OPTIONS':
            response = jsonify({'message': 'Preflight request successful'})
            response.headers.add('Access-Control-Allow-Origin', '*')
            response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
            response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
            return response
        return f(*args, **kwargs)
    return decorated_function


@bp.route('', methods=['POST', 'OPTIONS'])  # PAS de slash final
@jwt_required()
@handle_options
@validate_json({
    'query': {'type': 'string', 'required': True, 'minlength': 3},
    'type': {'type': 'string', 'allowed': ['text', 'image', 'news'], 'default': 'text'},
    'limit': {'type': 'integer', 'min': 1, 'max': 50, 'default': 10},
    'filters': {
        'type': 'dict',
        'schema': {
            'date': {'type': 'string', 'allowed': ['any', 'day', 'week', 'month', 'year'], 'default': 'any'},
            'type': {'type': 'string', 'allowed': ['all', 'article', 'video', 'image', 'document'], 'default': 'all'},
            'domain': {'type': 'string', 'nullable': True, 'default': ''},
            'language': {'type': 'string', 'allowed': ['fr', 'en', 'es', 'de', 'it'], 'default': 'fr'},
            'category': {'type': 'string', 'nullable': True, 'default': ''}
        },
        'default': {
            'date': 'any',
            'type': 'all',
            'domain': '',
            'language': 'fr',
            'category': ''
        }
    }
})
def search_post():
    try:
        user_id = get_jwt_identity()
        current_app.logger.info(f"POST search by user_id: {user_id}")
        if not user_id:
            return jsonify({'success': False, 'error': 'Invalid or missing user identity'}), 401

        try:
            user_obj_id = ObjectId(user_id)
        except Exception as e:
            current_app.logger.error(f"Invalid user ID format: {user_id} - {str(e)}")
            return jsonify({'success': False, 'error': 'Invalid user ID format'}), 400

        data = request.get_json()
        query = data.get('query')
        search_type = data.get('type', 'text')
        limit = data.get('limit', 10)
        filters = data.get('filters', {
            'date': 'any',
            'type': 'all',
            'domain': '',
            'language': 'fr',
            'category': ''
        })

        mongo_db = current_app.mongo.db

        search_history_doc = {
            "user_id": user_obj_id,
            "query": query,
            "search_type": search_type,
            "source": "api-post",
            "timestamp": datetime.utcnow(),
            "results_count": 0,
            "filters": filters
        }
        inserted = mongo_db.search_history.insert_one(search_history_doc)

        if search_type == 'text':
            scraped_results = ScrapingService.scrape_web(query, limit, lang=filters.get('language', 'fr'))
            filtered_results = SearchService.apply_filters(scraped_results, filters)
            enriched_results = AIService.enrich_search_results(query, filtered_results)

            mongo_db.search_history.update_one(
                {"_id": inserted.inserted_id},
                {"$set": {"results_count": len(enriched_results)}}
            )

            return jsonify({
                'success': True,
                'results': enriched_results,
                'query': query,
                'count': len(enriched_results),
                'filters': filters
            }), 200

        elif search_type == 'image':
            images = AIService.generate_images(query, limit)
            if filters.get('language', 'any') != 'any':
                images = [img for img in images if img.get('language', 'en') == filters['language']]

            mongo_db.search_history.update_one(
                {"_id": inserted.inserted_id},
                {"$set": {"results_count": len(images)}}
            )

            return jsonify({
                'success': True,
                'images': images,
                'query': query,
                'count': len(images),
                'filters': filters
            }), 200

        elif search_type == 'news':
            news = ScrapingService.scrape_news(query, limit)
            filtered_news = SearchService.apply_filters(news, filters)

            mongo_db.search_history.update_one(
                {"_id": inserted.inserted_id},
                {"$set": {"results_count": len(filtered_news)}}
            )

            return jsonify({
                'success': True,
                'news': filtered_news,
                'query': query,
                'count': len(filtered_news),
                'filters': filters
            }), 200

        else:
            return jsonify({'success': False, 'error': 'Type de recherche non reconnu'}), 400

    except Exception as e:
        current_app.logger.error(f"Exception in POST /search: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        try:
            if 'inserted' in locals():
                mongo_db.search_history.delete_one({"_id": inserted.inserted_id})
        except Exception as delete_exc:
            current_app.logger.error(f"Error deleting search history on exception: {str(delete_exc)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@bp.route('', methods=['GET', 'OPTIONS'])  # PAS de slash final
@jwt_required()
@handle_options
def search_get():
    try:
        user_id = get_jwt_identity()
        current_app.logger.info(f"GET search by user_id: {user_id}")

        if not user_id:
            return jsonify({'success': False, 'error': 'Invalid or missing user identity'}), 401

        try:
            user_obj_id = ObjectId(user_id)
        except Exception as e:
            current_app.logger.error(f"Invalid user ID format: {user_id} - {str(e)}")
            return jsonify({'success': False, 'error': 'Invalid user ID format'}), 400

        query = request.args.get('query', '').strip()
        if len(query) < 3:
            return jsonify({'success': False, 'error': 'Query too short'}), 400

        search_type = request.args.get('type', 'text')
        limit = request.args.get('limit', 10, type=int)

        filters = {
            'date': request.args.get('date', 'any'),
            'type': request.args.get('type_filter', 'all'),
            'domain': request.args.get('domain', ''),
            'language': request.args.get('language', 'fr'),
            'category': request.args.get('category', '')
        }

        mongo_db = current_app.mongo.db

        search_history_doc = {
            "user_id": user_obj_id,
            "query": query,
            "search_type": search_type,
            "source": "api-get",
            "timestamp": datetime.utcnow(),
            "results_count": 0,
            "filters": filters
        }
        inserted = mongo_db.search_history.insert_one(search_history_doc)

        if search_type == 'text':
            scraped_results = ScrapingService.scrape_web(query, limit, lang=filters.get('language', 'fr'))
            filtered_results = SearchService.apply_filters(scraped_results, filters)
            enriched_results = AIService.enrich_search_results(query, filtered_results)

            mongo_db.search_history.update_one(
                {"_id": inserted.inserted_id},
                {"$set": {"results_count": len(enriched_results)}}
            )

            return jsonify({
                'success': True,
                'results': enriched_results,
                'query': query,
                'count': len(enriched_results),
                'filters': filters
            }), 200

        elif search_type == 'image':
            images = AIService.generate_images(query, limit)
            if filters.get('language', 'any') != 'any':
                images = [img for img in images if img.get('language', 'en') == filters['language']]

            mongo_db.search_history.update_one(
                {"_id": inserted.inserted_id},
                {"$set": {"results_count": len(images)}}
            )

            return jsonify({
                'success': True,
                'images': images,
                'query': query,
                'count': len(images),
                'filters': filters
            }), 200

        elif search_type == 'news':
            news = ScrapingService.scrape_news(query, limit)
            filtered_news = SearchService.apply_filters(news, filters)

            mongo_db.search_history.update_one(
                {"_id": inserted.inserted_id},
                {"$set": {"results_count": len(filtered_news)}}
            )

            return jsonify({
                'success': True,
                'news': filtered_news,
                'query': query,
                'count': len(filtered_news),
                'filters': filters
            }), 200

        else:
            return jsonify({'success': False, 'error': 'Type de recherche non reconnu'}), 400

    except Exception as e:
        current_app.logger.error(f"Exception in GET /search: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        try:
            if 'inserted' in locals():
                mongo_db.search_history.delete_one({"_id": inserted.inserted_id})
        except Exception as delete_exc:
            current_app.logger.error(f"Error deleting search history on exception: {str(delete_exc)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@bp.route('/filters', methods=['GET'])
def get_available_filters():
    return jsonify({
        'date_filters': [
            {'value': 'any', 'label': 'Toutes dates'},
            {'value': 'day', 'label': 'Dernier jour'},
            {'value': 'week', 'label': 'Dernière semaine'},
            {'value': 'month', 'label': 'Dernier mois'},
            {'value': 'year', 'label': 'Dernière année'}
        ],
        'type_filters': [
            {'value': 'all', 'label': 'Tous types'},
            {'value': 'article', 'label': 'Articles'},
            {'value': 'video', 'label': 'Vidéos'},
            {'value': 'image', 'label': 'Images'},
            {'value': 'document', 'label': 'Documents'}
        ],
        'language_filters': [
            {'value': 'fr', 'label': 'Français'},
            {'value': 'en', 'label': 'Anglais'},
            {'value': 'es', 'label': 'Espagnol'},
            {'value': 'de', 'label': 'Allemand'},
            {'value': 'it', 'label': 'Italien'}
        ]
    }), 200


@bp.route('/suggest', methods=['GET', 'OPTIONS'])
@jwt_required()
@handle_options
def suggest():
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify({'suggestions': []})

    suggestions = SearchService.get_suggestions(query)
    return jsonify({'suggestions': suggestions})


@bp.route('/history', methods=['GET'])
@jwt_required()
def get_history():
    user_id = get_jwt_identity()
    if not user_id:
        return jsonify({'success': False, 'error': 'Invalid or missing user identity'}), 401

    try:
        user_obj_id = ObjectId(user_id)
    except Exception:
        return jsonify({'success': False, 'error': 'Invalid user ID format'}), 400

    limit = request.args.get('limit', 10, type=int)
    mongo_db = current_app.mongo.db

    history_cursor = mongo_db.search_history.find(
        {"user_id": user_obj_id}
    ).sort("timestamp", -1).limit(limit)

    history = [{
        'id': str(item['_id']),
        'query': item['query'],
        'type': item['search_type'],
        'date': item['timestamp'].isoformat() if 'timestamp' in item else None,
        'results_count': item.get('results_count', 0),
        'filters': item.get('filters', {})
    } for item in history_cursor]

    return jsonify({'history': history})


@bp.route('/favorites', methods=['GET', 'POST', 'DELETE', 'OPTIONS'])
@jwt_required()
@handle_options
def manage_favorites():
    user_id = get_jwt_identity()
    if not user_id:
        return jsonify({'success': False, 'error': 'Invalid or missing user identity'}), 401

    try:
        user_obj_id = ObjectId(user_id)
    except Exception:
        return jsonify({'success': False, 'error': 'Invalid user ID format'}), 400

    mongo_db = current_app.mongo.db

    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight request successful'})

    if request.method == 'GET':
        favorites_cursor = mongo_db.favorites.find(
            {"user_id": user_obj_id}
        ).sort("added_at", -1)

        favorites = [{
            'id': str(fav['_id']),
            'title': fav.get('title'),
            'url': fav.get('url'),
            'snippet': fav.get('snippet'),
            'type': fav.get('fav_type'),
            'date': fav.get('added_at').isoformat() if fav.get('added_at') else None,
            'tags': fav.get('tags', [])
        } for fav in favorites_cursor]

        return jsonify({'favorites': favorites})

    elif request.method == 'POST':
        data = request.get_json()
        favorite_doc = {
            "user_id": user_obj_id,
            "title": data.get('title'),
            "url": data.get('url'),
            "snippet": data.get('snippet'),
            "fav_type": data.get('type', 'result'),
            "tags": data.get('tags', []),
            "added_at": datetime.utcnow()
        }
        inserted = mongo_db.favorites.insert_one(favorite_doc)

        return jsonify({
            'success': True,
            'favorite': {
                'id': str(inserted.inserted_id),
                'title': favorite_doc['title']
            }
        }), 201

    elif request.method == 'DELETE':
        favorite_id = request.args.get('id')
        if not favorite_id:
            return jsonify({'success': False, 'error': 'Missing favorite ID'}), 400

        delete_result = mongo_db.favorites.delete_one({
            "_id": ObjectId(favorite_id),
            "user_id": user_obj_id
        })

        if delete_result.deleted_count == 0:
            return jsonify({'success': False, 'error': 'Favorite not found'}), 404

        return jsonify({'success': True}), 200
