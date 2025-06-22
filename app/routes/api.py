from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from bson.objectid import ObjectId, InvalidId
from app.extensions import mongo

bp = Blueprint('api', __name__)

@bp.route('/status', methods=['GET'])
def api_status():
    return jsonify({
        'status': 'running',
        'version': '1.0.0'
    }), 200

@bp.route('/config', methods=['GET'])
@jwt_required()
def get_config():
    user_id = get_jwt_identity()
    try:
        obj_user_id = ObjectId(user_id)
    except InvalidId:
        return jsonify({'error': 'Invalid user ID'}), 400

    user = mongo.db.users.find_one({'_id': obj_user_id})

    if not user:
        return jsonify({'error': 'User not found'}), 404

    return jsonify({
        'search': {
            'default_limit': 10,
            'max_limit': 50,
            'supported_types': ['text', 'image', 'news']
        },
        'user': {
            'is_admin': user.get('is_admin', False),
            'api_key': user.get('api_key', '')
        }
    }), 200
