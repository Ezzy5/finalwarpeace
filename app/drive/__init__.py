from flask import Blueprint

bp = Blueprint(
    "drive",
    __name__,
    url_prefix="/drive",
    template_folder="templates",
    static_folder="static",
)

from . import routes  # noqa
