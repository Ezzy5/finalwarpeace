# app/departments/__init__.py
from flask import Blueprint

bp = Blueprint(
    "departments",
    __name__,
    url_prefix="/departments",
    template_folder="templates",
    static_folder="static",
)

# 🚨 IMPORTANT: import routes so endpoints attach to bp
# Keep this import at the BOTTOM to avoid circular imports.
from . import routes  # noqa: E402,F401
