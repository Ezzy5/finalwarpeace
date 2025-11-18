# app/plan/__init__.py
from flask import Blueprint

bp = Blueprint(
    "plan",
    __name__,
    url_prefix="/plan",
    template_folder="templates",
    static_folder="static",
)

from . import routes  # noqa: E402,F401
