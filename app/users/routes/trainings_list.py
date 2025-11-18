from flask_login import login_required
from flask import jsonify
from sqlalchemy.exc import OperationalError
from app.models import User, Training, Attachment
from app.permissions import require_permission, USERS_TRAINING
from .. import bp
from .helpers import _fmt, _today
from datetime import datetime

@bp.route("/api/trainings/<int:user_id>", methods=["GET"])
@login_required
@require_permission(USERS_TRAINING)
def api_trainings_list(user_id: int):
    u = User.query.get_or_404(user_id)
    try:
        ts = u.trainings.order_by(Training.start_date.desc()).all()
    except OperationalError:
        return jsonify({"active": [], "history": []})

    today = _today()
    changed = False

    def ser(t: Training):
        try:
            rel = t.attachments
            if hasattr(rel, "order_by"):
                atts = rel.order_by(Attachment.uploaded_at.desc()).all()
            else:
                atts = sorted(rel or [], key=lambda a: a.uploaded_at or datetime.min, reverse=True)
        except Exception:
            atts = []
        return {
            "id": t.id, "title": t.title,
            "start_date": _fmt(t.start_date),
            "end_date": _fmt(t.end_date),
            "status": t.status,
            "attachments": [{"id": a.id, "filename": a.filename, "stored_name": a.stored_name} for a in atts],
        }

    for t in ts:
        if t.status == "active" and t.end_date < today:
            t.status = "history"
            changed = True

    if changed:
        try: from app.extensions import db; db.session.commit()
        except OperationalError: from app.extensions import db; db.session.rollback()

    active = [ser(t) for t in ts if t.status == "active"]
    history = [ser(t) for t in ts if t.status != "active"]
    return jsonify({"active": active, "history": history})
