from sqlalchemy.sql import func

from app.extensions import db


class ErasureLog(db.Model):
    """Proof that a record was permanently destroyed.

    Blocker 11. Article 17 requires erasure; accountability requires being
    able to show it happened. This row is what survives, so it holds the case
    identifier and counts only — never the personal data that was erased, and
    no foreign key to the deleted case.
    """

    __tablename__ = "erasure_logs"

    id = db.Column(db.Integer, primary_key=True)
    # The human-facing case reference (e.g. "SOTS-0042"), not a database id,
    # because the row it pointed at no longer exists.
    case_identifier = db.Column(db.String(100), nullable=False)
    requested_by_user_id = db.Column(db.Integer, nullable=True)
    # "erasure_request", "retention_policy", or an operator-supplied reason.
    reason = db.Column(db.String(200), nullable=False)
    records_deleted = db.Column(db.Integer, nullable=False, default=0)
    files_deleted = db.Column(db.Integer, nullable=False, default=0)
    purged_at = db.Column(db.DateTime(timezone=True), default=func.now())

    def __repr__(self):
        return f"<ErasureLog {self.case_identifier} at {self.purged_at}>"
