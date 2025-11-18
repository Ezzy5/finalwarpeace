# app/users/__init__.py
from __future__ import annotations
from flask import Blueprint

# The blueprint (must exist before route modules import it)
bp = Blueprint(
    "users",
    __name__,
    url_prefix="/users",
    template_folder="templates",
    static_folder="static",
    static_url_path="/users/static",
)

# Import AFTER bp is created so route modules can attach @bp.route handlers
from .routes import load_routes as _load_user_routes  # noqa: E402
_load_user_routes()
