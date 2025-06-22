import pytest
from app.models import User
from flask_jwt_extended import create_access_token

@pytest.fixture
def auth_headers(client, session, app):
    """Crée un utilisateur et retourne un header avec JWT token"""
    with app.app_context():
        # Créer et sauvegarder l'utilisateur
        user = User(email='testuser@example.com', username='testuser')
        user.set_password('testpassword')
        session.add(user)
        session.commit()

        # Token avec identity sous forme de string (json-serializable)
        access_token = create_access_token(identity=str(user.id))

        return {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

def test_register(client):
    response = client.post('/api/auth/register', json={
        'email': 'newuser@example.com',
        'password': 'testpassword',
        'username': 'newuser'
    })

    assert response.status_code == 201
    assert 'api_key' in response.json


def test_login(client):
    client.post('/api/auth/register', json={
        'email': 'loginuser@example.com',
        'password': 'testpassword',
        'username': 'loginuser'
    })

    response = client.post('/api/auth/login', json={
        'email': 'loginuser@example.com',
        'password': 'testpassword'
    })

    assert response.status_code == 200
    assert 'access_token' in response.json


def test_protected_route(client, auth_headers):
    """Test d'accès à la route protégée avec JWT valide"""
    response = client.get('/api/auth/me', headers=auth_headers)

    if response.status_code != 200:
        print("⚠️ Échec de /api/auth/me:", response.status_code, response.json)

    assert response.status_code == 200
    assert 'email' in response.json
    assert 'username' in response.json
