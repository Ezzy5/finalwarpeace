# app/email/admin.py
"""
Admin dashboard integration for the Email feature.

This tries to attach an admin-facing view that lists *all* connected
email accounts across users, highlights insecure setups, and shows basic health.

If your app already has an "admin" blueprint, we'll mount under it at:
    /admin/email/connections
Otherwise, we'll fall back to registering under the email blueprint at:
    /email/admin/connections
"""
from flask import current_app, render_template
from flask_login import login_required, current_user

from app.email.models.connection import EmailConnection
from app.email.permissions import require_admin_or_email_manage
from app.email import bp as email_bp


def _register_under_admin_blueprint(app):
    admin_bp = app.blueprints.get("admin")
    if not admin_bp:
        return False

    @admin_bp.route("/email/connections", methods=["GET"])
    @login_required
    @require_admin_or_email_manage
    def email_connections_admin():
        accounts = EmailConnection.query.order_by(EmailConnection.created_at.desc()).all()
        # Reuse the same table template; it works with a list of accounts
        return render_template(
            "email/status.html",
            accounts=accounts,
            user=current_user,
        )

    return True


def _register_under_email_blueprint(app):
    @email_bp.route("/admin/connections", methods=["GET"])
    @login_required
    @require_admin_or_email_manage
    def email_connections_admin_fallback():
        accounts = EmailConnection.query.order_by(EmailConnection.created_at.desc()).all()
        return render_template(
            "email/status.html",
            accounts=accounts,
            user=current_user,
        )


def register_admin_views(app):
    """
    Call from app.email.init_app(app). Attempts to hook into your existing
    admin blueprint; if unavailable, falls back to /email/admin/connections.
    """
    mounted = _register_under_admin_blueprint(app)
    if not mounted:
        _register_under_email_blueprint(app)
