# app/tickets/permissions.py
from flask import abort
from sqlalchemy import or_
from app.tickets.models import Ticket

def is_admin(user):
    return getattr(user, "role", None) == "admin"

# 🔁 Department managers (update attribute names if needed)
def department_managers_for(ticket: Ticket):
    managers = set()
    for d in ticket.departments:
        # If your Department has .manager_id and .manager relationship:
        if getattr(d, "manager", None):
            # Support out-of-office delegate if you have these fields on User
            if getattr(d.manager, "out_of_office", False) and getattr(d.manager, "delegate_id", None):
                managers.add(d.manager.delegate_id)
            managers.add(d.manager_id)
    return managers

def can_view_ticket(user, ticket: Ticket):
    if is_admin(user): return True
    if ticket.creator_id == user.id: return True
    if user.id in [u.id for u in ticket.assignees]: return True
    if user.id in department_managers_for(ticket): return True
    return False

def enforce_can_view(user, ticket: Ticket):
    if not can_view_ticket(user, ticket):
        abort(403)

def can_edit_ticket(user, ticket: Ticket):
    return is_admin(user) or ticket.creator_id == user.id or user.id in department_managers_for(ticket)

def enforce_can_edit(user, ticket: Ticket):
    if not can_edit_ticket(user, ticket):
        abort(403)

def visibility_filter(query, user):
    from app.models import Department  # global Department model
    if is_admin(user):
        return query
    return query.filter(
        or_(
            Ticket.creator_id == user.id,
            Ticket.assignees.any(id=user.id),
            # visible to department managers
            Ticket.departments.any(Department.manager_id == user.id),
        )
    )
