# app/tickets/routes/panel.py
from datetime import date

from flask import render_template, request
from flask_login import login_required, current_user
from sqlalchemy import case

from .. import bp
from app.tickets.models import Ticket, TicketStatus, TicketPriority
from .helpers import is_spa_request
from ..permissions import visibility_filter  # existing project helper

def _render_panel_fragment(tickets, pagination, q, status, priority, sort, compact):
    return render_template(
        "tickets/panel.html",
        tickets=tickets,
        pagination=pagination,
        q=q,
        status=status,
        priority=priority,
        sort=sort,
        compact=compact,
        today=date.today(),
    )

@bp.route("/panel")
@login_required
def panel():
    q = request.args.get("q", "")
    status = request.args.get("status")
    priority = request.args.get("priority")
    sort = request.args.get("sort", "created_desc")
    compact = request.args.get("compact") == "1"

    qry = visibility_filter(Ticket.query, current_user)

    if q:
        term = f"%{q}%"
        qry = qry.filter((Ticket.title.ilike(term)) | (Ticket.description.ilike(term)))

    if status in (TicketStatus.IN_PROGRESS.value, TicketStatus.COMPLETED.value):
        qry = qry.filter(Ticket.status == TicketStatus(status))
    else:
        status = None

    if priority in [p.value for p in TicketPriority]:
        qry = qry.filter(Ticket.priority == TicketPriority(priority))
    else:
        priority = None

    if sort == "created_asc":
        qry = qry.order_by(Ticket.created_at.asc())
    elif sort == "priority":
        order = case(
            (Ticket.priority == TicketPriority.URGENT, 1),
            (Ticket.priority == TicketPriority.HIGH, 2),
            (Ticket.priority == TicketPriority.MEDIUM, 3),
            else_=4,
        )
        qry = qry.order_by(order.asc(), Ticket.created_at.desc())
    elif sort == "status":
        qry = qry.order_by(Ticket.status.asc(), Ticket.created_at.desc())
    else:
        qry = qry.order_by(Ticket.created_at.desc())

    page = request.args.get("page", 1, type=int)
    pagination = qry.paginate(page=page, per_page=15)

    if is_spa_request():
        return _render_panel_fragment(
            pagination.items, pagination, q, status, priority, sort, compact
        )

    initial_panel = _render_panel_fragment(
        pagination.items, pagination, q, status, priority, sort, compact
    )
    return render_template("dashboard.html", initial_panel=initial_panel)
