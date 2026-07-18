from flask_login import UserMixin
from sqlalchemy.sql import func

from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())

    # Relationships
    cases = db.relationship("Case", backref="worker", lazy="dynamic")

    def __repr__(self):
        return f"<User {self.email}>"
