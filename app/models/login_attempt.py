from sqlalchemy.sql import func

from app.extensions import db


class LoginAttempt(db.Model):
    """A single login attempt, successful or not.

    Blocker 3. Throttling state lives in the database rather than in process
    memory because production runs multiple gunicorn workers — an in-memory
    counter would give an attacker one full allowance per worker.
    """

    __tablename__ = "login_attempts"

    id = db.Column(db.Integer, primary_key=True)
    # Stored lowercased. Not a foreign key: attempts against addresses that
    # do not exist are exactly the ones worth counting.
    email = db.Column(db.String(150), nullable=True, index=True)
    ip_address = db.Column(db.String(45), nullable=True, index=True)
    successful = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(
        db.DateTime(timezone=True), default=func.now(), index=True
    )

    def __repr__(self):
        outcome = "ok" if self.successful else "failed"
        return f"<LoginAttempt {self.email} {outcome}>"
