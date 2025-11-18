from flask_login import login_required, current_user
from flask import jsonify, request, abort
from sqlalchemy.exc import OperationalError
from app.models import Training
from app.permissions import require_permission, has_permission, USERS_TRAINING, USERS_CREATE_EDIT
from app.extensions import db
from .. import bp
from .helpers import _parse_yyyy_mm_dd, _fmt, _today

@bp.route("/api/trainings/<int:user_id>/<int:training_id>/update", methods=["POST"])
@login_required
@require_permission(USERS_TRAINING)   # <- ADD
def api_trainings_update(user_id: int, training_id: int):
    if not has_permission(current_user, USERS_CREATE_EDIT):  # <- ADD
        abort(403)
    try:
        tr = Training.query.filter_by(id=training_id, user_id=user_id).first_or_404()
    except OperationalError:
        return jsonify({"error": "trainings table missing; run migrations"}), 503

    data = request.get_json(silent=True) or {}
    title   = (data.get("title") or tr.title or "").strip()
    start_s = (data.get("start_date") or _fmt(tr.start_date) or "").strip()
    end_s   = (data.get("end_date") or _fmt(tr.end_date) or "").strip()

    errors = {}
    if not title:
        errors["title"] = "Required."
    try:
        start = _parse_yyyy_mm_dd(start_s)
    except Exception:
        errors["start_date"] = "Invalid date."
        start = None
    try:
        end = _parse_yyyy_mm_dd(end_s)
    except Exception:
        errors["end_date"] = "Invalid date."
        end = None
    if start and end and end < start:
        errors["end_date"] = "End date must be ≥ start date."
    if errors:
        return jsonify({"errors": errors}), 400

    tr.title = title
    tr.start_date = start
    tr.end_date = end
    tr.status = "active" if (end and end >= _today()) else "history"

    try:
        db.session.commit()
    except OperationalError:
        db.session.rollback()
        return jsonify({"error": "trainings table missing; run migrations"}), 503

    return jsonify({"ok": True, "item": {
        "id": tr.id,
        "title": tr.title,
        "start_date": _fmt(tr.start_date),
        "end_date": _fmt(tr.end_date),
        "status": tr.status,
    }})