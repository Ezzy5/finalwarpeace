# app/callendar/routes/views.py
from __future__ import annotations
from app.utils import tz
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import render_template, request
from flask_login import login_required, current_user



from .. import bp
from ..forms import FilterForm, EventForm
from ..services.invitations_service import list_invitations_for_user
from app.models import User
from app.extensions import db


def _build_forms():
    """Prepare FilterForm + EventForm and populate attendees."""
    filter_form = FilterForm()
    event_form = EventForm()
    users = db.session.query(User.id, User.username).order_by(User.username.asc()).all()
    event_form.attendees.choices = [(u.id, u.username) for u in users]
    return filter_form, event_form


@bp.route("/", methods=["GET"])
@login_required
def index():
    """
    Standalone full-page calendar (with its own head/body).
    Good for direct linking or when you prefer outside the dashboard SPA.
    """
    selected_view = (request.args.get("view") or "month").lower()
    if selected_view not in {"day", "week", "month"}:
        selected_view = "month"

    filter_form, event_form = _build_forms()
    invites_count = len(list_invitations_for_user(current_user.id))

    return render_template(
        "callendar/index.html",
        selected_view=selected_view,
        filter_form=filter_form,
        event_form=event_form,
        invites_count=invites_count,
        now = datetime.now(ZoneInfo("Europe/Skopje")),
    )


@bp.route("/panel", methods=["GET"])
@login_required
def panel():
    """
    SPA-friendly fragment. If requested via the dashboard fetch (header X-Requested-With),
    return only the panel fragment. If the user refreshes or visits this URL directly,
    render the full dashboard shell and inject this panel inside (so UI doesn’t break).
    """
    selected_view = (request.args.get("view") or "month").lower()
    if selected_view not in {"day", "week", "month"}:
        selected_view = "month"

    filter_form, event_form = _build_forms()
    invites_count = len(list_invitations_for_user(current_user.id))

    # Are we inside the SPA fetch?
    xr = (request.headers.get("X-Requested-With") or "").lower()
    is_spa_fetch = xr in {"fetch", "xmlhttprequest"}

    if is_spa_fetch:
        # Return just the panel fragment
        return render_template(
            "callendar/panel.html",
            selected_view=selected_view,
            filter_form=filter_form,
            event_form=event_form,
            invites_count=invites_count,
            now = datetime.now(ZoneInfo("Europe/Skopje")),
        )

    # Fallback for refresh/direct access: render dashboard shell and inject panel
    panel_html = render_template(
        "callendar/panel.html",
        selected_view=selected_view,
        filter_form=filter_form,
        event_form=event_form,
        invites_count=invites_count,
        now = datetime.now(ZoneInfo("Europe/Skopje")),
    )
    # The dashboard template expects `initial_panel` and will execute `data-exec` scripts.
    return render_template("dashboard.html", initial_panel=panel_html)


@bp.route("/invitations", methods=["GET"])
@login_required
def invitations_view():
    """Server-rendered invitations partial for the Invitations panel."""
    invitations = list_invitations_for_user(current_user.id)
    return render_template("callendar/_invites_list.html", invitations=invitations)
