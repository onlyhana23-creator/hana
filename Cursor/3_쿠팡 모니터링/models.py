# -*- coding: utf-8 -*-
"""Flask-SQLAlchemy 모델."""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class CoupangProduct(db.Model):
    __tablename__ = "coupang_products"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Integer)
    url = db.Column(db.Text)
