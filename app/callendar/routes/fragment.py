# app/callendar/routes/fragment.py
from __future__ import annotations
from flask import render_template, abort, request
from flask_login import login_required
from app.extensions import db
from app.callendar.models import Event   # adjust if your model import differs
from app.callendar import bp


def _is_fragment_request() -> bool:
    """Check if request is made for a fragment (AJAX/Fetch)."""
    return request.headers.get("X-Requested-With", "").lower() == "fetch"


@bp.route("/fragment/events/<int:eid>", methods=["GET"])
@login_required
def event_fragment(eid: int):
    """Return the event view HTML fragment (for use in Notifications modal)."""
    ev = db.session.get(Event, eid)
    if not ev:
        abort(404)

    # 🔥 Important: replace this with your actual event details template
    return render_template("callendar/event_view.html", event=ev, from_notifications=True)
