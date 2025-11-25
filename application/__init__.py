from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from flask_migrate import Migrate
from sqlalchemy.sql import text

from config import Config

class Base(DeclarativeBase):
    pass

app = Flask(__name__)


app.config['SQLALCHEMY_DATABASE_URI'] = Config.SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False 
app.config['SECRET_KEY'] = Config.SECRET_KEY


db = SQLAlchemy(app, model_class=Base)

migrate = Migrate(app, db)

def initialize_sequences(app, db):
    with app.app_context():
        sequences = ["doc_order_seq", "doc_invoice_seq", "doc_incoming_seq", "doc_outgoing_seq", "doc_tax_invoice_seq"]
        
        for seq in sequences:
            sql_command = text(f"CREATE SEQUENCE IF NOT EXISTS {seq} START 1 INCREMENT 1;")
            try:
                db.session.execute(sql_command)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"Помилка створення послідовності {seq}: {e}")\
        

initialize_sequences(app, db)


from application import routes, models