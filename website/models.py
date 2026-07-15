from . import db
from flask_login import UserMixin
from sqlalchemy.sql import func

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String(1000))
    date = db.Column(db.DateTime(timezone=True), default=func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    first_name = db.Column(db.String(50))
    notes = db.relationship('Note')
    cases = db.relationship('Case')

class Case(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    caseFirstName = db.Column(db.String(150))
    caseSurname = db.Column(db.String(1000))
    caseDOB = db.Column(db.DateTime)
    caseGender = db.Column(db.String(20))
    casePhoneNum = db.Column(db.String(12))
    caseLocation = db.Column(db.String(200))
    caseNotes = db.Column(db.String(1500))
    casePhysDesc = db.Column(db.String(400))
    caseAttach = db.Column(db.String(10000))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))