import sys
import os
import pytest
from sqlalchemy.orm import scoped_session, sessionmaker

# Ajouter le dossier 'backend' au PYTHONPATH pour que 'app' soit importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.config import TestingConfig
from app.extensions import db as _db

@pytest.fixture(scope='session')
def app():
    """Création de l'application Flask en mode test"""
    app = create_app(TestingConfig)
    with app.app_context():
        yield app

@pytest.fixture(scope='session')
def db(app):
    """Initialisation de la base de données pour la session de tests"""
    _db.app = app
    with app.app_context():
        _db.create_all()
    yield _db
    with app.app_context():
        _db.drop_all()

@pytest.fixture(scope='function')
def session(db):
    """Crée une session de base de données isolée pour chaque test"""
    connection = db.engine.connect()
    transaction = connection.begin()

    # Créer une scoped_session liée à la connexion transactionnelle
    session_factory = sessionmaker(bind=connection)
    session = scoped_session(session_factory)

    # Remplace la session par défaut par celle-ci dans le contexte test
    db.session = session

    yield session

    session.remove()  # Pour scoped_session, il faut remove() et non close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope='function')
def client(app, session):
    """Client de test Flask"""
    with app.test_client() as client:
        yield client

@pytest.fixture
def auth_headers(client, session):
    """Headers HTTP avec token d'authentification pour tests sécurisés"""
    from app.models import User
    from werkzeug.security import generate_password_hash

    # Création d'un utilisateur test
    user = User(
        email='test@example.com',
        username='testuser',
        password_hash=generate_password_hash('testpassword')
    )
    session.add(user)
    session.commit()

    # Connexion pour obtenir le token JWT
    response = client.post('/api/auth/login', json={
        'email': 'test@example.com',
        'password': 'testpassword'
    })
    token = response.json['access_token']

    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
