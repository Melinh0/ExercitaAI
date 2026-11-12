import json

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    ollama_keys = db.Column(db.Text, default='[]')
    ocr_keys = db.Column(db.Text, default='[]')
    reset_token_hash = db.Column(db.String(64), nullable=True, index=True)
    reset_expires_at = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_ollama_keys(self):
        return json.loads(self.ollama_keys) if self.ollama_keys else []

    def set_ollama_keys(self, keys):
        self.ollama_keys = json.dumps(keys)

    def get_ocr_keys(self):
        return json.loads(self.ocr_keys) if self.ocr_keys else []

    def set_ocr_keys(self, keys):
        self.ocr_keys = json.dumps(keys)