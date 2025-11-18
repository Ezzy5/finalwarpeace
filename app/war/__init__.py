from flask import Blueprint

war_bp = Blueprint(
    "war",
    __name__,
    url_prefix="/war",
    template_folder="templates",
    static_folder="static",
    static_url_path="/war/static",
)

from . import routes  # noqa
