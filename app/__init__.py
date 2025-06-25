import os
from flask import Flask
from app.config import config
from app.extensions import mongo, mail, jwt, cors
from flask_swagger_ui import get_swaggerui_blueprint

def create_app(config_name=None):
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialisation des extensions
    mongo.init_app(app)
    mail.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, resources={
        r"/api/*": {
            "origins": ["http://localhost:3000"],
            "methods": ["GET", "POST", "OPTIONS", "PUT", "DELETE"],
            "allow_headers": ["Authorization", "Content-Type"],
            "supports_credentials": True
        }
    })

    # Injection mongo dans l'app
    app.mongo = mongo

    # Swagger UI config
    SWAGGER_URL = '/api/docs'
    API_URL = '/static/swagger.json'
    swaggerui_bp = get_swaggerui_blueprint(
        SWAGGER_URL,
        API_URL,
        config={'app_name': "IntelliSearch API"}
    )
    app.register_blueprint(swaggerui_bp, url_prefix=SWAGGER_URL)

    # Import blueprints
    from app.routes.api import bp as api_bp
    from app.routes.auth import bp as auth_bp
    from app.routes.contact import bp as contact_bp
    from app.routes.dashboard import bp as dashboard_bp
    from app.routes.search import bp as search_bp

    # Enregistrement blueprints
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(contact_bp, url_prefix='/api/v1/contact')
    app.register_blueprint(dashboard_bp, url_prefix='/api/v1/dashboard')
    app.register_blueprint(search_bp, url_prefix='/api/v1/search')

    # Initialisation des services dépendants du contexte Flask
    with app.app_context():
        from app.services.ai_service import AIService
        AIService.initialize()

    return app
