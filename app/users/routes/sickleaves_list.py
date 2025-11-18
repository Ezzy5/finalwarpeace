from flask_login import login_required
from flask import jsonify
from sqlalchemy.exc import OperationalError
from app.extensions import db
from app.models import User, SickLeave, Attachment
from app.permissions import require_permission, USERS_SICK
from .. import bp
from .helpers import _fmt, _today
from datetime import datetime

@bp.route("/api/sickleaves/<int:user_id>", methods=["GET"])
@login_required
@require_permission(USERS_SICK)
def api_sickleaves_list(user_id: int):
    u = User.query.get_or_404(user_id)
    try:
        ls = u.sick_leaves.order_by(SickLeave.start_date.desc()).all()
    except OperationalError:
        return jsonify({"active": [], "history": []})

    today = _today()
    changed = False

    def ser(s: SickLeave):
        try:
            rel = s.attachments
            if hasattr(rel, "order_by"):
                atts = rel.order_by(Attachment.uploaded_at.desc()).all()
            else:
                atts = sorted(rel or [], key=lambda a: a.uploaded_at or datetime.min, reverse=True)
        except Exception:
            atts = []
        return {
            "id": s.id, "start_date": _fmt(s.start_date), "end_date": _fmt(s.end_date),
            "kind": s.kind, "business_days": s.business_days, "status": s.status,
            "comments": s.comments or "",
            "holidays": [h for h in (s.holidays_csv.split(",") if s.holidays_csv else []) if h],
            "attachments": [{"id": a.id, "filename": a.filename, "stored_name": a.stored_name} for a in atts],
        }

    for s in ls:
        if s.status == "active" and s.end_date < today:
            s.status = "history"
            changed = True

    if changed:
        try: db.session.commit()
        except OperationalError: db.session.rollback()

    active = [ser(s) for s in ls if s.status == "active"]
    history = [ser(s) for s in ls if s.status != "active"]
    return jsonify({"active": active, "history": history})
