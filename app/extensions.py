# app/extensions.py
from flask_pymongo import PyMongo
from flask_mail import Mail
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_mail import Mail

mongo = PyMongo()
mail = Mail()
jwt = JWTManager()
cors = CORS()
mail = Mail()