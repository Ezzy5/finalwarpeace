# app/email/routes/protocol.py
from flask import render_template, redirect, url_for, session, request
from flask_login import login_required, current_user

from app.email import bp
from app.email.forms.protocol_form import ProtocolForm


def _is_spa_request() -> bool:
    return (
        request.headers.get("X-Requested-With") in {"fetch", "XMLHttpRequest"}
        or request.headers.get("HX-Request") == "true"
    )


@bp.route("/protocol", methods=["GET", "POST"])
@login_required
def protocol_select():
    """
    Step 2: choose protocol (IMAP / POP3 / OAuth).
    """
    form = ProtocolForm()

    if form.validate_on_submit():
        session["email_protocol"] = form.protocol.data
        return redirect(url_for("email.config_account"))

    panel_html = render_template("email/protocol.html", form=form, user=current_user)
    if _is_spa_request():
        return panel_html
    return render_template("dashboard.html", initial_panel=panel_html)
