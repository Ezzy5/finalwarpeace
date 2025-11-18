# app/attachments/__init__.py
from flask import Blueprint

bp = Blueprint("attachments", __name__, url_prefix="/attachments")

from . import routes  # noqa: E402,F401
