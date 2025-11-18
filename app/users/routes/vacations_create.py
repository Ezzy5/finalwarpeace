from flask_login import login_required
from flask import jsonify, request
from app.models import User, Vacation
from app.permissions import require_permission, USERS_VACATION
from app.extensions import db
from .. import bp

@bp.route("/api/vacations/<int:user_id>/create", methods=["POST"])
@login_required
@require_permission(USERS_VACATION)
def vacations_create(user_id: int):
    u = User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}

    start_date_str = (data.get("start_date") or "").strip()
    days = data.get("days")
    holidays = data.get("holidays") or []

    errors = {}
    if not start_date_str:
        errors["start_date"] = "Required."
    try:
        days = int(days)
        if days <= 0:
            raise ValueError
    except Exception:
        errors["days"] = "Must be a positive integer."
    if errors:
        return jsonify({"errors": errors}), 400

    from datetime import date, timedelta
    def parse(d): return date.fromisoformat(d)
    def fmt(d):   return d.isoformat()

    holiday_set = set(h for h in holidays if h)
    d = parse(start_date_str)
    remaining = days - 1
    while remaining > 0:
        d = d + timedelta(days=1)
        if d.weekday() < 5 and fmt(d) not in holiday_set:
            remaining -= 1
    end_date = d

    ret = end_date
    while True:
        ret = ret + timedelta(days=1)
        if ret.weekday() < 5 and fmt(ret) not in holiday_set:
            break

    vac = Vacation(
        user_id=u.id, start_date=parse(start_date_str), end_date=end_date,
        days=days, return_date=ret, status="active",
        holidays_csv=",".join(sorted(holiday_set)) if holiday_set else None
    )
    db.session.add(vac)
    db.session.commit()

    return jsonify({"ok": True, "item": {
        "id": vac.id, "start_date": vac.start_date.isoformat(),
        "end_date": vac.end_date.isoformat(), "return_date": vac.return_date.isoformat(),
        "days": vac.days, "status": vac.status, "attachments": [],
    }})
