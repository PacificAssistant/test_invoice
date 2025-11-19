from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

from config import Config

class Base(DeclarativeBase):
    pass

app = Flask(__name__)


app.config['SQLALCHEMY_DATABASE_URI'] = Config.SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False 
app.config['SECRET_KEY'] = Config.SECRET_KEY


db = SQLAlchemy(app, model_class=Base)

from application import routes, models