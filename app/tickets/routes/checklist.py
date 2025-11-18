# app/tickets/routes/checklist.py
from flask import redirect, url_for, request
from flask_login import login_required, current_user

from .. import bp
from app.extensions import db
from app.tickets.models import Ticket, TicketChecklist
from .helpers import enforce_can_comment

@bp.route("/<int:ticket_id>/checklist/<int:chk_id>/toggle", methods=["POST"])
@login_required
def toggle_checklist(ticket_id, chk_id):
    t = Ticket.query.get_or_404(ticket_id)
    enforce_can_comment(current_user, t)

    ch = TicketChecklist.query.filter_by(id=chk_id, ticket_id=t.id).first_or_404()
    # Treat presence of the field as checked; absence as unchecked
    want_done = bool(request.form.get("completed"))
    ch.completed = want_done
    db.session.commit()
    return redirect(url_for("tickets.view", ticket_id=t.id))
