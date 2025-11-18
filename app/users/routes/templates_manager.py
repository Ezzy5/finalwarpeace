# app/users/routes/templates_manager.py
from __future__ import annotations
from flask import render_template
from flask_login import login_required
from .. import bp
from app.permissions import require_permission, USERS_AGREEMENT

@bp.get("/templates/manager")
@login_required
@require_permission(USERS_AGREEMENT)
def templates_manager():
    # Renders the modal template. The HTML inside is wrapped in {% raw %} so
    # Jinja doesn't try to evaluate example placeholders like {{ first_name }}.
    return render_template("users/templates_manager.html")
