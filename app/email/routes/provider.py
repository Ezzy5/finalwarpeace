# app/email/routes/provider.py
from flask import render_template, redirect, url_for, session, request
from flask_login import login_required, current_user

from app.email import bp
from app.email.forms.provider_form import ProviderForm


def _is_spa_request() -> bool:
    """Detects SPA fetch requests so we can return just the panel."""
    return (
        request.headers.get("X-Requested-With") in {"fetch", "XMLHttpRequest"}
        or request.headers.get("HX-Request") == "true"
    )


@bp.route("/", methods=["GET", "POST"])
@login_required
def provider_select():
    """
    Step 1: choose an email provider (Gmail, Outlook, Yahoo, or Custom).
    If NOT an SPA request, wrap panel inside dashboard.html so refresh keeps the UI.
    """
    form = ProviderForm()

    if form.validate_on_submit():
        session["email_provider"] = form.provider.data
        return redirect(url_for("email.protocol_select"))

    panel_html = render_template("email/provider.html", form=form, user=current_user)
    if _is_spa_request():
        return panel_html
    # Full page load → return dashboard shell with the panel injected
    return render_template("dashboard.html", initial_panel=panel_html)
