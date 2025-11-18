from flask import Blueprint

bp = Blueprint(
    "notifications",           # endpoint name prefix
    __name__,
    url_prefix="/notifications",
    template_folder="templates",
    static_folder="static",
)

from . import routes  # noqa: E402,F401  (register routes)
