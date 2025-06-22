import re
from urllib.parse import urlparse
from datetime import datetime, timedelta
from flask import current_app
from app.models import User
import jwt

def is_valid_url(url):
    """Check if a string is a valid URL"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def generate_api_key(user_id):
    """Generate a unique API key for a user"""
    secret = current_app.config['SECRET_KEY']
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(days=365)
    }
    return jwt.encode(payload, secret, algorithm='HS256')

def verify_api_key(api_key):
    """Verify an API key and return the user if valid"""
    try:
        secret = current_app.config['SECRET_KEY']
        payload = jwt.decode(api_key, secret, algorithms=['HS256'])
        return User.query.get(payload['user_id'])
    except:
        return None

def normalize_query(query):
    """Normalize search query by removing extra spaces and special chars"""
    query = query.strip()
    query = re.sub(r'[^\w\s-]', '', query)
    query = re.sub(r'\s+', ' ', query)
    return query.lower()

def format_timestamp(timestamp):
    """Format timestamp for API responses"""
    if isinstance(timestamp, datetime):
        return timestamp.isoformat() + 'Z'
    return timestamp

def paginate_query(query, page, per_page):
    """Helper for paginating SQLAlchemy queries"""
    return query.paginate(page=page, per_page=per_page, error_out=False)