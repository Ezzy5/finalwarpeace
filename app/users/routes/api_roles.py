from flask_login import login_required
from flask import jsonify
from app.models import Role
from .. import bp

@bp.get("/api/roles")
@login_required
def api_roles():
    roles = Role.query.order_by(Role.name.asc()).all()
    return jsonify([{"id": r.id, "name": r.name} for r in roles])
