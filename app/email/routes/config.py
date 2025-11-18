# app/email/routes/config.py
from flask import render_template, redirect, url_for, session, flash, request
from flask_login import login_required, current_user

from app.email import bp
from app.email.forms.config_form import ConfigForm


def _is_spa_request() -> bool:
    return (
        request.headers.get("X-Requested-With") in {"fetch", "XMLHttpRequest"}
        or request.headers.get("HX-Request") == "true"
    )


@bp.route("/config", methods=["GET", "POST"])
@login_required
def config_account():
    """
    Step 3: enter account credentials & server info.
    Supports both OAuth and manual IMAP/POP3 setups.
    """
    form = ConfigForm()

    if form.validate_on_submit():
        session["email_config"] = form.data
        return redirect(url_for("email.verify_connection"))

    panel_html = render_template("email/config.html", form=form, user=current_user)
    if _is_spa_request():
        return panel_html
    return render_template("dashboard.html", initial_panel=panel_html)
