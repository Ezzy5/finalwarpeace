# app/tickets/routes/edit.py
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload

from .. import bp
from ..forms import TicketForm
from ..permissions import enforce_can_edit
from app.extensions import db
from app.models import User, Department
from app.tickets.models import Ticket, TicketChecklist
from .helpers import (
    is_spa_request,
    enforce_can_view,
    is_assignee,
    parse_priority,
    load_users_and_departments,
    user_label,
    dept_label,
    save_checklists_for_ticket_from_request,
)

@bp.route("/<int:ticket_id>/edit", methods=["GET", "POST"])
@login_required
def edit(ticket_id):
    # Load ticket
    t = (
        Ticket.query.options(
            joinedload(Ticket.assignees),
            joinedload(Ticket.departments),
        )
        .filter(Ticket.id == ticket_id)
        .first_or_404()
    )
    enforce_can_view(current_user, t)
    enforce_can_edit(current_user, t)

    form = TicketForm(obj=t)

    # Populate choices safely
    users, departments = load_users_and_departments()
    if hasattr(form, "assignees"):
        form.assignees.choices = [(int(u.id), user_label(u)) for u in users]
        # Preselect existing assignees on GET
        if request.method == "GET":
            form.assignees.data = [int(u.id) for u in getattr(t, "assignees", [])]

    if hasattr(form, "departments"):
        form.departments.choices = [(int(d.id), dept_label(d)) for d in departments]
        # Preselect existing departments on GET
        if request.method == "GET":
            form.departments.data = [int(d.id) for d in getattr(t, "departments", [])]

    if request.method == "POST" and form.validate_on_submit():
        # --- Update scalar fields
        t.title = (form.title.data or "").strip()
        t.description = form.description.data or ""
        if hasattr(form, "priority"):
            t.priority = parse_priority(form.priority.data)
        if hasattr(form, "due_date"):
            t.due_date = form.due_date.data or None

        # --- Update assignees/departments
        if hasattr(form, "assignees"):
            ids = form.assignees.data or []
            t.assignees = list(User.query.filter(User.id.in_(ids)).all())
        if hasattr(form, "departments"):
            ids = form.departments.data or []
            t.departments = list(Department.query.filter(Department.id.in_(ids)).all())

        # --- Replace checklist with the newly submitted one
        # Remove existing rows for this ticket
        TicketChecklist.query.filter_by(ticket_id=t.id).delete(synchronize_session=False)
        # Parse JSON/arrays from request and insert new rows
        save_checklists_for_ticket_from_request(ticket_id=t.id)

        db.session.commit()
        flash("Тикетот е ажуриран.", "success")
        return redirect(url_for("tickets.panel"))

    tpl = "tickets/edit.html"
    ctx = dict(
        form=form,
        t=t,
        is_creator=True,  # you already gated by enforce_can_edit; keep template happy
        am_assignee=is_assignee(current_user, t),
    )
    if is_spa_request():
        return render_template(tpl, **ctx)
    return render_template("dashboard.html", initial_panel=render_template(tpl, **ctx))
