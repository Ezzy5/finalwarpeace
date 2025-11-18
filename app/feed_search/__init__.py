from flask import Blueprint

bp = Blueprint(
    "feed_search",
    __name__,
    url_prefix="/api/feed/search",
    static_folder="static",
    static_url_path="/static/feed-search"
)

from . import api  # noqa: E402
