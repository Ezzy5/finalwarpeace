# app/tickets/routes/view.py
from datetime import date
from flask import render_template
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload

from .. import bp
from ..forms import CommentForm
from app.tickets.models import Ticket, TicketComment, TicketStatus, TicketChecklist
from .helpers import (
    is_spa_request,
    enforce_can_view,
    creator_id,
    is_assignee,
)

@bp.route("/<int:ticket_id>")
@login_required
def view(ticket_id: int):
    # Load ticket and related info
    eager_opts = [
        joinedload(Ticket.assignees),
        joinedload(Ticket.departments),
        joinedload(Ticket.comments),
    ]
    if hasattr(TicketComment, "user"):
        eager_opts.append(joinedload(Ticket.comments).joinedload(TicketComment.user))

    t = Ticket.query.options(*eager_opts).get_or_404(ticket_id)
    enforce_can_view(current_user, t)

    is_creator = (current_user.id == creator_id(t))
    am_assignee = is_assignee(current_user, t)

    status_val = getattr(t, "status", None)
    try:
        is_completed = (status_val == TicketStatus.COMPLETED)
    except Exception:
        is_completed = (str(status_val).upper() == "COMPLETED")

    # ✅ Explicitly load checklist rows (works regardless of relationship config)
    items = (
        TicketChecklist.query
        .filter(TicketChecklist.ticket_id == t.id)
        .order_by(TicketChecklist.section_index.asc(), TicketChecklist.position.asc())
        .all()
    )

    # Group into sections
    sections_map: dict[int, dict] = {}
    for ch in items:
        sidx = getattr(ch, "section_index", 0) or 0
        entry = sections_map.setdefault(sidx, {
            "index": sidx,
            "title": getattr(ch, "section_title", None),
            "items": []
        })
        entry["items"].append(ch)
        if not entry["title"] and getattr(ch, "section_title", None):
            entry["title"] = ch.section_title
    sections = [sections_map[k] for k in sorted(sections_map.keys())]

    # Simplest flag for the template: show card if any rows exist
    has_checklists = len(items) > 0

    comments = list(getattr(t, "comments", []))
    comments.sort(key=lambda c: getattr(c, "created_at", date.min) or date.min)

    ctx = dict(
        t=t,
        comments=comments,
        checklists=items,      # flat list if you need it
        sections=sections,     # grouped for UI
        has_checklists=has_checklists,
        comment_form=CommentForm(),
        can_comment=(not is_completed) and (is_creator or am_assignee or any(
            getattr(d, "id", None) in {getattr(x, "id", None) for x in getattr(current_user, "departments", [])}
            for d in getattr(t, "departments", [])
        )),
        can_edit=is_creator,
        is_creator=is_creator,
        is_assignee=am_assignee,
        today=date.today(),
    )

    if is_spa_request():
        return render_template("tickets/view.html", **ctx)
    return render_template("dashboard.html", initial_panel=render_template("tickets/view.html", **ctx))
