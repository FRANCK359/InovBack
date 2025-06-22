from datetime import datetime
from app.models import User, SearchHistory, Favorite, ContactMessage

def test_user_model(session):
    """Test User model creation"""
    user = User(
        email='test@example.com',
        username='testuser',
        password_hash='hashedpassword'
    )
    session.add(user)
    session.commit()
    
    assert user.id is not None
    assert user.email == 'test@example.com'
    assert user.created_at is not None

def test_search_history_model(session):
    """Test SearchHistory model creation"""
    user = User(email='test@example.com', username='testuser', password_hash='hashed')
    session.add(user)
    session.commit()
    
    search = SearchHistory(
        user_id=user.id,
        query='test query',
        search_type='text',
        source='web'
    )
    session.add(search)
    session.commit()
    
    assert search.id is not None
    assert search.query == 'test query'
    assert search.user_id == user.id

def test_favorite_model(session):
    """Test Favorite model creation"""
    user = User(email='test@example.com', username='testuser', password_hash='hashed')
    session.add(user)
    session.commit()
    
    favorite = Favorite(
        user_id=user.id,
        title='Test Favorite',
        url='http://example.com',
        snippet='Test snippet',
        fav_type='result'
    )
    session.add(favorite)
    session.commit()
    
    assert favorite.id is not None
    assert favorite.title == 'Test Favorite'
    assert favorite.user_id == user.id

def test_contact_message_model(session):
    """Test ContactMessage model creation"""
    message = ContactMessage(
        name='Test User',
        email='test@example.com',
        subject='Test Subject',
        message='Test message content'
    )
    session.add(message)
    session.commit()
    
    assert message.id is not None
    assert message.name == 'Test User'
    assert message.is_read == False  # par défaut
