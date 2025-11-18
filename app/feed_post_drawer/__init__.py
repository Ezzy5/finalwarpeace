from flask import Blueprint

bp = Blueprint(
    "feed_post_drawer",
    __name__,
    static_folder="static",
    static_url_path="/static/feed-drawer"
)
# Static-only: mount CSS/JS into your SPA; no routes here.
