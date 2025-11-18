from flask_login import login_required
from flask import jsonify
from sqlalchemy.exc import OperationalError
from app.models import User, Uniform, Attachment
from app.permissions import require_permission, USERS_UNIFORMS
from .. import bp
from .helpers import _fmt, _today
from datetime import datetime, date

@bp.route("/api/uniforms/<int:user_id>", methods=["GET"])
@login_required
@require_permission(USERS_UNIFORMS)
def api_uniforms_list(user_id: int):
    u = User.query.get_or_404(user_id)
    try:
        rows = u.uniforms.order_by(Uniform.assigned_date.desc()).all()
    except OperationalError:
        return jsonify({"active": [], "history": []})

    def ser(un: Uniform):
        try:
            rel = un.attachments
            if hasattr(rel, "order_by"):
                atts = rel.order_by(Attachment.uploaded_at.desc()).all()
            else:
                atts = sorted(rel or [], key=lambda a: a.uploaded_at or datetime.min, reverse=True)
        except Exception:
            atts = []
        return {
            "id": un.id, "kind": un.kind,
            "assigned_date": _fmt(un.assigned_date),
            "renew_every_months": un.renew_every_months,
            "next_due_date": _fmt(un.next_due_date),
            "attachments": [{"id": a.id, "filename": a.filename, "stored_name": a.stored_name} for a in atts],
        }

    today = _today()
    active, history = [], []
    for un in rows:
        (active if (un.next_due_date and un.next_due_date >= today) else history).append(ser(un))

    return jsonify({"active": active, "history": history})
