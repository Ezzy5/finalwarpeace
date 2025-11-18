from flask import Blueprint

bp = Blueprint(
    "feed_api",
    __name__,
    url_prefix="/api/feed",
    static_folder="static",
    static_url_path="/feed/static",
    template_folder="templates",
)

from app.feed import routes  # <-- IMPORTANT
