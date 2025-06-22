from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId, InvalidId
from datetime import datetime, timedelta
import re
from app.utils.helpers import generate_api_key

bp = Blueprint('auth', __name__)

@bp.route('/register', methods=['POST'])
def register():
    mongo = current_app.mongo
    users_collection = mongo.db.users

    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email and password required'}), 400

    email = data['email'].strip().lower()
    password = data['password']
    username = data.get('username', email.split('@')[0])

    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        return jsonify({'error': 'Invalid email format'}), 400

    if users_collection.find_one({'email': email}):
        return jsonify({'error': 'Email already registered'}), 400

    try:
        user_doc = {
            'email': email,
            'username': username,
            'password_hash': generate_password_hash(password),
            'is_admin': False,
            'created_at': datetime.utcnow(),
        }
        inserted = users_collection.insert_one(user_doc)
        user_id = inserted.inserted_id

        api_key = generate_api_key(str(user_id))
        users_collection.update_one({'_id': user_id}, {'$set': {'api_key': api_key}})

        return jsonify({'message': 'User created successfully', 'api_key': api_key}), 201

    except Exception as e:
        return jsonify({'error': 'Database error', 'details': str(e)}), 500


@bp.route('/login', methods=['POST'])
def login():
    mongo = current_app.mongo
    users_collection = mongo.db.users

    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email and password required'}), 400

    user = users_collection.find_one({'email': data['email'].strip().lower()})
    if not user or not check_password_hash(user['password_hash'], data['password']):
        return jsonify({'error': 'Invalid credentials'}), 401

    access_token = create_access_token(identity=str(user['_id']), expires_delta=timedelta(days=7))

    return jsonify({
        'access_token': access_token,
        'user': {
            'id': str(user['_id']),
            'email': user['email'],
            'username': user.get('username'),
            'api_key': user.get('api_key')
        }
    }), 200


@bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    mongo = current_app.mongo
    users_collection = mongo.db.users

    try:
        user_id = get_jwt_identity()
        try:
            obj_user_id = ObjectId(user_id)
        except InvalidId:
            return jsonify({'error': 'Invalid user ID'}), 400

        user = users_collection.find_one({'_id': obj_user_id})
        if not user:
            return jsonify({'error': 'User not found'}), 404

        return jsonify({
            'id': str(user['_id']),
            'email': user['email'],
            'username': user.get('username'),
            'is_admin': user.get('is_admin', False),
            'created_at': user.get('created_at').isoformat() if user.get('created_at') else None
        }), 200

    except Exception as e:
        return jsonify({'error': 'Unable to retrieve user', 'details': str(e)}), 500


@bp.route('/refresh-api-key', methods=['POST'])
@jwt_required()
def refresh_api_key():
    mongo = current_app.mongo
    users_collection = mongo.db.users

    try:
        user_id = get_jwt_identity()
        try:
            obj_user_id = ObjectId(user_id)
        except InvalidId:
            return jsonify({'error': 'Invalid user ID'}), 400

        user = users_collection.find_one({'_id': obj_user_id})
        if not user:
            return jsonify({'error': 'User not found'}), 404

        new_api_key = generate_api_key(str(user['_id']))
        users_collection.update_one({'_id': obj_user_id}, {'$set': {'api_key': new_api_key}})

        return jsonify({'message': 'API key refreshed', 'api_key': new_api_key}), 200

    except Exception as e:
        return jsonify({'error': 'Failed to refresh API key', 'details': str(e)}), 500
