# app/tickets/routes/status.py
from flask import request, jsonify
from flask_login import login_required, current_user

from .. import bp
from app.extensions import db
from app.tickets.models import Ticket, TicketComment, TicketStatus
from ..permissions import enforce_can_edit
from .helpers import enforce_can_view

@bp.route("/<int:ticket_id>/api/status", methods=["POST"])
@login_required
def api_status(ticket_id):
    t = Ticket.query.get_or_404(ticket_id)
    enforce_can_view(current_user, t)
    enforce_can_edit(current_user, t)

    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    if new_status not in (TicketStatus.IN_PROGRESS.value, TicketStatus.COMPLETED.value):
        return jsonify({"ok": False, "error": "invalid"}), 400
    t.status = TicketStatus(new_status)
    db.session.add(TicketComment(ticket_id=t.id, user_id=current_user.id, body=None, status_change_to=t.status))
    db.session.commit()
    return jsonify({"ok": True, "status": t.status.value})
