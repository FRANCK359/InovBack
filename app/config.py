import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-123')
    MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/intellisearch')

    # 🔑 Clés et accès API
    GNEWS_API_KEY = os.environ.get('GNEWS_API_KEY', None)
    HF_TOKEN = os.environ.get('HF_TOKEN', None)
    DEEPSEEK_API_URL = os.environ.get('DEEPSEEK_API_URL', 'http://localhost:8000/deepseek/search')  # ✅ DeepSeek ici

    # ⚙️ Scraping / limites
    SCRAPE_TIMEOUT = int(os.environ.get('SCRAPE_TIMEOUT', 10))
    MAX_SCRAPE_RESULTS = int(os.environ.get('MAX_SCRAPE_RESULTS', 20))
    RATE_LIMIT_DEFAULT = os.environ.get('RATE_LIMIT_DEFAULT', '100 per day;10 per hour')

    # 📧 Mail
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.googlemail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@intellisearch.com')

    # 📊 Analytics
    ANALYTICS_DATA_RETENTION_DAYS = int(os.environ.get('ANALYTICS_DATA_RETENTION_DAYS', 30))

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    MAIL_SUPPRESS_SEND = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
