from flask_login import login_required
from flask import jsonify, request
from sqlalchemy.exc import OperationalError
from app.extensions import db
from app.models import User, SickLeave
from app.permissions import require_permission, USERS_SICK
from .. import bp
from .helpers import _parse_yyyy_mm_dd, _today, _business_days_between, _fmt

@bp.route("/api/sickleaves/<int:user_id>/create", methods=["POST"])
@login_required
@require_permission(USERS_SICK)
def api_sickleaves_create(user_id: int):
    User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}

    start_s  = (data.get("start_date") or "").strip()
    end_s    = (data.get("end_date") or "").strip()
    kind     = (data.get("kind") or "").strip()
    comments = (data.get("comments") or "").strip()
    holidays = data.get("holidays") or []

    errors, start, end = {}, None, None
    try: start = _parse_yyyy_mm_dd(start_s)
    except Exception:
        errors["start_date"] = "Invalid date."
    try: end = _parse_yyyy_mm_dd(end_s)
    except Exception:
        errors["end_date"] = "Invalid date."
    if start and end and end < start:
        errors["end_date"] = "End date must be ≥ start date."
    if not kind:
        errors["kind"] = "Required."
    if errors: return jsonify({"errors": errors}), 400

    hol = set()
    for hs in holidays:
        try: hol.add(_parse_yyyy_mm_dd(hs))
        except Exception: pass

    business_days = _business_days_between(start, end, hol)

    try:
        s = SickLeave(
            user_id=user_id, start_date=start, end_date=end, kind=kind,
            comments=comments or None,
            holidays_csv=",".join(sorted(h.strftime("%Y-%m-%d") for h in hol)) if hol else None,
            business_days=business_days,
            status="active" if (end and end > _today()) else "history",
        )
        db.session.add(s)
        db.session.commit()
    except OperationalError:
        db.session.rollback()
        return jsonify({"error": "sick_leaves table missing; run migrations"}), 503

    return jsonify({"ok": True, "sick_leave": {
        "id": s.id, "start_date": _fmt(s.start_date), "end_date": _fmt(s.end_date),
        "kind": s.kind, "business_days": s.business_days, "status": s.status,
        "comments": s.comments or "",
        "holidays": [h for h in (s.holidays_csv.split(",") if s.holidays_csv else []) if h],
    }})
