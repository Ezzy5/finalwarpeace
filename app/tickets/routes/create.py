# app/tickets/routes/create.py
import json
from pathlib import Path
from datetime import datetime

from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from .. import bp
from app.extensions import db
from app.models import User, Department
from app.tickets.models import Ticket, TicketStatus, TicketChecklist
from ..forms import TicketForm
from .helpers import (
    is_spa_request,
    load_users_and_departments,
    parse_priority,
    save_comment_file_under_ticket_root,
    save_checklists_for_ticket_from_request,
)

@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    form = TicketForm()
    users, departments = load_users_and_departments()

    selected_assignee_ids = [int(x) for x in request.form.getlist("assignees") if str(x).isdigit()]
    selected_dept_ids     = [int(x) for x in request.form.getlist("departments") if str(x).isdigit()]

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip()
        if not title:
            flash("Title is required.", "danger")
        else:
            priority_val = parse_priority(request.form.get("priority"))

            # Parse due_date (YYYY-MM-DD)
            due_date = None
            due_raw = request.form.get("due_date", "").strip()
            if due_raw:
                try:
                    due_date = datetime.strptime(due_raw, "%Y-%m-%d").date()
                except Exception:
                    flash("Invalid due date format. Use YYYY-MM-DD.", "warning")

            t = Ticket(
                title=title,
                description=description,
                status=TicketStatus.IN_PROGRESS,
                priority=priority_val,
                due_date=due_date,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            t.creator_id = current_user.id

            # Assignees / Departments
            if selected_assignee_ids:
                t.assignees = User.query.filter(User.id.in_(selected_assignee_ids)).all()
            if selected_dept_ids:
                t.departments = Department.query.filter(Department.id.in_(selected_dept_ids)).all()

            db.session.add(t)
            db.session.flush()  # need t.id

            # ✅ Save checklist items from JSON or form arrays
            save_checklists_for_ticket_from_request(ticket_id=t.id)
           

            # 🔎 Sanity check – if nothing was saved, let the user know (helps debugging)
            saved_cnt = TicketChecklist.query.filter_by(ticket_id=t.id).count()
            if saved_cnt == 0:
                flash("No checklist items were received with the form. If you added items, make sure the checklist is serialized into the hidden field before submitting.", "warning")
            # Multiple attachments (optional) -> store as comment entries
            files = request.files.getlist("attachments")
            if files:
                from app.tickets.models import TicketComment  # local import to avoid cycles
                for f in files:
                    if f and getattr(f, "filename", ""):
                        rel_path = save_comment_file_under_ticket_root(f, Path("tickets") / str(t.id))
                        c = TicketComment(ticket_id=t.id, user_id=current_user.id, body=None)
                        if rel_path:
                            c.attachment_path = rel_path
                        db.session.add(c)

            db.session.commit()
            flash("Ticket created.", "success")
            return redirect(url_for("tickets.panel"))

    ctx = dict(
        form=form,
        users=users,
        departments=departments,
        selected_assignee_ids=selected_assignee_ids,
        selected_dept_ids=selected_dept_ids,
    )
    tpl = "tickets/new.html"
    if is_spa_request():
        return render_template(tpl, **ctx)
    return render_template("dashboard.html", initial_panel=render_template(tpl, **ctx))
