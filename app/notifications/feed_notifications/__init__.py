from flask import Blueprint

bp = Blueprint(
    "feed_notify_api",
    __name__,
    url_prefix="/api/notifications/feed"
)

from . import api  # noqa: E402
