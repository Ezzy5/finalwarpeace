# app/email/routes/status.py
from flask import render_template, flash, request
from flask_login import login_required, current_user

from app.email import bp
from app.email.models.connection import EmailConnection


def _is_spa_request() -> bool:
    return (
        request.headers.get("X-Requested-With") in {"fetch", "XMLHttpRequest"}
        or request.headers.get("HX-Request") == "true"
    )


@bp.route("/status", methods=["GET"])
@login_required
def status_list():
    """
    Step 5: Show list of connected accounts, their status,
    and allow manage/reconnect/remove.
    """
    accounts = EmailConnection.query.filter_by(user_id=current_user.id).all()

    if not accounts:
        flash("No connected email accounts yet. Add one to get started.", "info")

    panel_html = render_template("email/status.html", accounts=accounts, user=current_user)
    if _is_spa_request():
        return panel_html
    return render_template("dashboard.html", initial_panel=panel_html)
