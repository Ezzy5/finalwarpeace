# app/tickets/routes/comments.py
from pathlib import Path

from flask import redirect, url_for, flash
from flask_login import login_required, current_user

from .. import bp
from ..forms import CommentForm
from app.extensions import db
from app.tickets.models import Ticket, TicketComment, TicketStatus
from .helpers import enforce_can_comment, save_comment_file_under_ticket_root

@bp.route("/<int:ticket_id>/comment", methods=["POST"])
@login_required
def add_comment(ticket_id):
    t = Ticket.query.get_or_404(ticket_id)
    enforce_can_comment(current_user, t)

    form = CommentForm()
    if not form.validate_on_submit():
        flash("Невалидни податоци за коментар.", "danger")
        return redirect(url_for("tickets.view", ticket_id=ticket_id))

    c = TicketComment(ticket_id=t.id, user_id=current_user.id, body=(form.body.data or "").strip() or None)

    if hasattr(form, "status_change_to") and form.status_change_to.data:
        try:
            new_status = TicketStatus(form.status_change_to.data)
        except Exception:
            new_status = None
        if new_status:
            c.status_change_to = new_status
            t.status = new_status

    f = getattr(form, "attachment", None)
    f = f.data if f else None
    if f and getattr(f, "filename", ""):
        rel_dir = Path("tickets") / str(t.id)
        rel_path = save_comment_file_under_ticket_root(f, rel_dir)
        if rel_path:
            c.attachment_path = rel_path

    db.session.add(c)
    db.session.commit()

    flash("Коментарот е додаден.", "success")
    return redirect(url_for("tickets.view", ticket_id=t.id))
