from flask_login import login_required
from flask import jsonify
from sqlalchemy.exc import OperationalError
from app.extensions import db
from app.models import User, Vacation, Attachment
from app.permissions import require_permission, USERS_VACATION
from .. import bp
from .helpers import _fmt, _vacation_days_left, _auto_expire_for_user
from datetime import datetime

@bp.route("/api/vacations/<int:user_id>", methods=["GET"])
@login_required
@require_permission(USERS_VACATION)
def vacations_list(user_id: int):
    u = User.query.get_or_404(user_id)
    try:
        _auto_expire_for_user(u)
        rows = u.vacations.order_by(Vacation.start_date.desc()).all()
    except OperationalError:
        return jsonify({"vacation_days_left": 0, "active": [], "history": []})

    def ser(v):
        try:
            rel = v.attachments
            if hasattr(rel, "order_by"):
                atts = rel.order_by(Attachment.uploaded_at.desc()).all()
            else:
                atts = sorted(rel or [], key=lambda a: a.uploaded_at or datetime.min, reverse=True)
        except Exception:
            atts = []
        return {
            "id": v.id, "start_date": _fmt(v.start_date), "end_date": _fmt(v.end_date),
            "days": v.days, "return_date": _fmt(v.return_date), "status": v.status,
            "attachments": [{"id": a.id, "filename": a.filename, "stored_name": a.stored_name} for a in atts],
        }

    active = [ser(v) for v in rows if v.status == "active"]
    history = [ser(v) for v in rows if v.status != "active"]

    return jsonify({
        "vacation_days_left": _vacation_days_left(u),
        "active": active, "history": history,
    })
