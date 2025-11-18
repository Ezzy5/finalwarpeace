# app/email/__init__.py
from __future__ import annotations

from flask import Blueprint, current_app

# -----------------------------------------------------------------------------
# Blueprint
# -----------------------------------------------------------------------------
bp = Blueprint(
    "email",
    __name__,
    url_prefix="/email",
    template_folder="templates",
    static_folder="static",
)

# -----------------------------------------------------------------------------
# Default config (can be overridden in app.config)
# -----------------------------------------------------------------------------
DEFAULTS = {
    # Security posture
    "EMAIL_ALLOW_INSECURE": False,          # Admin can flip to True to allow plain text/no-cert
    "EMAIL_RATE_LIMIT_VERIFY_PER_HOUR": 10, # Throttle verification attempts
    "EMAIL_MAX_ATTACHMENT_MB": 25,          # Outgoing size guardrail
    "EMAIL_DEFAULT_SYNC_WINDOW_DAYS": 30,   # Initial IMAP sync horizon
    "EMAIL_IDLE_ENABLED": True,             # Enable IMAP IDLE when supported
    # Diagnostics
    "EMAIL_DNS_TIMEOUT_SEC": 5,
    "EMAIL_TCP_TIMEOUT_SEC": 8,
    "EMAIL_TLS_TIMEOUT_SEC": 8,
    "EMAIL_AUTH_TIMEOUT_SEC": 8,
}

def _ensure_defaults():
    for k, v in DEFAULTS.items():
        current_app.config.setdefault(k, v)

# -----------------------------------------------------------------------------
# Import route modules so their @bp.route decorators register with the blueprint
# (Keep at end to avoid circular imports.)
# -----------------------------------------------------------------------------
def _register_routes():
    # Landing and steps
    from .routes import provider       # /email
    from .routes import protocol       # /email/protocol
    from .routes import config         # /email/config
    from .routes import verify         # /email/verify
    from .routes import status         # /email/status
    from .routes import mailbox     # NEW
    from .routes import compose     # NEW
    from .routes import dnd_move 
    from .routes import folders  
    # (No explicit usage needed; importing registers the routes with `bp`.)

# -----------------------------------------------------------------------------
# Public init hook to be called from your app factory
# -----------------------------------------------------------------------------
def init_app(app):
    """
    Call this from your application factory after creating `app`.

    Example:
        from app.email import init_app as init_email
        init_email(app)
    """
    with app.app_context():
        _ensure_defaults()
        _register_routes()
        app.register_blueprint(bp)

        # Optional: attach admin integration if present
        try:
            from .admin import register_admin_views
            register_admin_views(app)
        except Exception:
            # Admin panel is optional; ignore if not wired yet
            pass

# -----------------------------------------------------------------------------
# (Optional) Jinja filters or globals can be added here
# -----------------------------------------------------------------------------
@bp.app_template_filter("email_security_badge")
def email_security_badge(security: str | None) -> str:
    """
    Render a tiny badge label from a security value: 'ssl', 'starttls', 'none'.
    Intended for use inside email templates.
    """
    val = (security or "").lower()
    if val in {"ssl", "ssl/tls", "tls"}:
        return "🔒 SSL/TLS"
    if val in {"starttls"}:
        return "🔒 STARTTLS"
    return "🔓 Not Secure"
