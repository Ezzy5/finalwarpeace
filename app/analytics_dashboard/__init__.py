from flask import Blueprint

bp = Blueprint(
    "analytics_dashboard",
    __name__,
    static_folder="static",
    static_url_path="/static/analytics"
)
# Static-only: include the JS/CSS in your SPA.
