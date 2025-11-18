# app/tickets/routes/complete.py
from flask import redirect, url_for, flash
from flask_login import login_required, current_user

from .. import bp
from app.extensions import db
from app.tickets.models import Ticket, TicketStatus
from .helpers import enforce_can_view, enforce_can_mark_complete

@bp.route("/<int:ticket_id>/complete", methods=["POST"])
@login_required
def mark_completed(ticket_id):
    t = Ticket.query.get_or_404(ticket_id)
    enforce_can_view(current_user, t)
    enforce_can_mark_complete(current_user, t)
    if t.status != TicketStatus.COMPLETED:
        t.status = TicketStatus.COMPLETED
        db.session.commit()
        flash("Тикетот е означен како завршен.", "success")
    return redirect(url_for("tickets.view", ticket_id=t.id))
