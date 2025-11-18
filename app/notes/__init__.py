# app/notes/__init__.py
from flask import Blueprint

bp = Blueprint(
    "notes",
    __name__,
    url_prefix="/notes",
    template_folder="templates",
    static_folder="static",
)

from . import routes  # noqa: E402,F401
