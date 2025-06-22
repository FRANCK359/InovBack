from functools import wraps
from flask import request, jsonify, current_app
from flask_jwt_extended import get_jwt_identity
from cerberus import Validator

def validate_json(schema):
    """Decorator to validate JSON request data against a schema"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not request.is_json:
                return jsonify({'error': 'Request must be JSON'}), 400
            
            data = request.get_json()
            validator = Validator(schema)
            
            if not validator.validate(data):
                return jsonify({
                    'error': 'Validation failed',
                    'details': validator.errors
                }), 400
            
            return f(*args, **kwargs)
        return wrapper
    return decorator

def admin_required(f):
    """Decorator to restrict access to admin users (MongoDB version)"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        user_id = get_jwt_identity()
        user = current_app.mongo.db.users.find_one({"_id": user_id})
        if not user or not user.get("is_admin", False):
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return wrapper

def cache_response(timeout=60):
    """Decorator to cache responses (stub - production ready)"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Cache key can be more sophisticated using path, params, headers, etc.
            cache_key = f"{request.path}?{request.query_string.decode()}"
            
            # Placeholder: implement Redis or Flask-Caching in production
            return f(*args, **kwargs)
        return wrapper
    return decorator
