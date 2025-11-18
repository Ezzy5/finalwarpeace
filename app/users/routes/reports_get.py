from flask_login import login_required
from flask import jsonify
from sqlalchemy.exc import OperationalError
from app.models import User
from app.permissions import require_permission, USERS_REPORTS
from .. import bp
from .helpers import _today, _fmt, _report_files_for
from dateutil.relativedelta import relativedelta

def _countdown_from(last, months_every: int):
    if not last: return None, None, None
    from datetime import date as _date
    due = last + relativedelta(months=+months_every)
    now = _today()
    if due <= now: return _fmt(due), 0, 0
    rd = relativedelta(due, now)
    months_left = rd.years * 12 + rd.months
    days_left = rd.days
    return _fmt(due), months_left, days_left

@bp.route("/api/reports/<int:user_id>", methods=["GET"])
@login_required
@require_permission(USERS_REPORTS)
def api_reports_get(user_id: int):
    u = User.query.get_or_404(user_id)
    try:
        r = u.report
        sanitary_last = r.sanitary_last if r else None
        system_last   = r.system_last if r else None
    except OperationalError:
        sanitary_last = None
        system_last = None

    sanitary_due, sanitary_m, sanitary_d = _countdown_from(sanitary_last, 6)
    system_due, system_m, system_d = _countdown_from(system_last, 24)

    try:
        sanitary_hist = _report_files_for(u, "sanitary")
        system_hist   = _report_files_for(u, "system")
    except OperationalError:
        sanitary_hist = []
        system_hist = []

    return jsonify({
        "sanitary": {"last": _fmt(sanitary_last), "next_due": sanitary_due, "left_months": sanitary_m, "left_days": sanitary_d},
        "system":   {"last": _fmt(system_last),   "next_due": system_due,   "left_months": system_m,   "left_days": system_d},
        "sanitary_history": sanitary_hist,
        "system_history": system_hist,
    })
