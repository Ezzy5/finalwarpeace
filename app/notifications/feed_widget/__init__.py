from flask import Blueprint

bp = Blueprint(
    "feed_notify_widget",
    __name__,
    static_folder="static",
    static_url_path="/static/feed-notify"
)
# No routes – static-only widget you can import in your SPA
