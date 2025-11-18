# app/tickets/__init__.py
from flask import Blueprint

bp = Blueprint(
    "tickets",
    __name__,
    url_prefix="/tickets",
    template_folder="templates",
    static_folder="static",
)

# Ensure models are registered on import
from . import models  # noqa: F401
from . import routes  # noqa: F401
