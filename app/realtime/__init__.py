from flask import Blueprint

bp = Blueprint(
    "realtime",
    __name__,
    url_prefix="/api/realtime",
    static_folder="static",
    static_url_path="/static/realtime"
)

from . import api  # noqa: E402
