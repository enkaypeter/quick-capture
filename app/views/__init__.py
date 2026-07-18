from flask import Blueprint

auth_bp = Blueprint("auth", __name__)
cases_bp = Blueprint("cases", __name__)

# Import routes to register them on the blueprints
from app.views import auth, cases  # noqa: E402, F401
