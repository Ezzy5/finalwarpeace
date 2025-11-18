# app/users/routes/templates_view.py
from flask import render_template
from flask_login import login_required
from .. import bp
from app.permissions import require_permission, USERS_AGREEMENT

@bp.get("/templates/manager")
@login_required
@require_permission(USERS_AGREEMENT)
def templates_manager_fragment():
    return render_template("template.html")  # looks in app/users/templates/
