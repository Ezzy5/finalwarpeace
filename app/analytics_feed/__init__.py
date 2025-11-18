from flask import Blueprint

bp = Blueprint(
    "feed_analytics",
    __name__,
    url_prefix="/api/feed/analytics"
)

from . import api  # noqa: E402
