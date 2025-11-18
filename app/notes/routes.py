# app/notes/routes.py
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, date, timedelta

from flask import render_template, request, jsonify, abort
from flask_login import login_required, current_user

from ..extensions import db
from ..models import Department, User, WorkLogEntry  # WorkLogEntry added earlier in your models.py
from datetime import timezone as _py_tz
from . import bp

# -------------------------
# Timezone helpers (Windows friendly; uses tzdata if available)
# -------------------------
try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    try:
        TZ = ZoneInfo("Europe/Skopje")
    except ZoneInfoNotFoundError:
        from dateutil.tz import gettz
        TZ = gettz("Europe/Skopje") or ZoneInfo("UTC")
except Exception:
    class _UTC(datetime.tzinfo):
        def utcoffset(self, dt): return timedelta(0)
        def tzname(self, dt): return "UTC"
        def dst(self, dt): return timedelta(0)
    TZ = _UTC()

def now_utc() -> datetime:
    return datetime.utcnow()

def to_utc(dt_local: datetime) -> datetime:
    # expects aware local datetime
    return dt_local.astimezone(ZoneInfo("UTC")) if dt_local.tzinfo else dt_local

def as_aware_utc(dt: datetime | None) -> datetime | None:
    """Normalize DB datetimes to aware UTC."""
    if dt is None: return None
    if dt.tzinfo is None: return dt.replace(tzinfo=_py_tz.utc)
    return dt.astimezone(_py_tz.utc)
    
def from_utc(dt_utc: datetime) -> datetime:
    # returns aware local datetime
    if dt_utc is None:
        return None
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=ZoneInfo("UTC"))
    return dt_utc.astimezone(TZ)

def today_local() -> date:
    return datetime.now(TZ).date()

def compute_minutes(start_utc: datetime, end_utc: datetime | None) -> int:
    if not start_utc or not end_utc:
        return 0
    delta = end_utc - start_utc
    return max(0, int(delta.total_seconds() // 60))

# -------------------------
# Auth/permissions helpers
# -------------------------

def as_aware_utc(dt: datetime | None) -> datetime | None:
    """Return dt as timezone-aware UTC (or None). Works if dt is naive or already aware."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Treat DB naive timestamps as UTC
        return dt.replace(tzinfo=_py_tz.utc)
    return dt.astimezone(_py_tz.utc)
    
def capture_user_department_id(u: User) -> int:
    dept_id = None
    if getattr(u, "dept", None):
        try: dept_id = u.dept.id
        except Exception: dept_id = None
    if dept_id is None:
        dept_id = getattr(u, "department_id", None)
    if not dept_id:
        abort(400, "User has no department.")
    return int(dept_id)

def require_director_of(dept_id: int) -> Department:
    dep = Department.query.get(dept_id)
    if not dep:
        abort(404, "Department not found.")
    if dep.manager_id != current_user.id:
        abort(403, "Not a director of this department.")
    return dep

# -------------------------
# Panel route (fragment vs full dashboard)
# -------------------------
@bp.route("/panel")
@login_required
def panel():
    is_fetch = request.headers.get("X-Requested-With") == "fetch"
    my_depts = (Department.query
                .filter_by(manager_id=current_user.id)
                .order_by(Department.name.asc())
                .all())
    if is_fetch:
        return render_template("panel_notes.html", my_depts=my_depts)
    # Direct load / reload → return dashboard with initial_panel so SPA opens Notes
    return render_template("dashboard.html", initial_panel="notes")

# -------------------------
# API — My Notes (Today)  GET /notes/api/me/today
# -------------------------
@bp.route("/api/me/today", methods=["GET"])
@login_required
def api_me_today():
    d = today_local()
    rows = (WorkLogEntry.query
            .filter_by(user_id=current_user.id, work_date=d)
            .order_by(WorkLogEntry.start_time_utc.asc())
            .all())

    blocks = []
    total = 0
    for r in rows:
        start_local = from_utc(r.start_time_utc).strftime("%H:%M")
        end_local = from_utc(r.end_time_utc).strftime("%H:%M") if r.end_time_utc else None
        mins = r.minutes or compute_minutes(r.start_time_utc, r.end_time_utc)
        total += mins
        blocks.append({
            "id": r.id,
            "start": start_local,
            "end": end_local,
            "minutes": mins,
            "note": r.note or "",
        })

    return jsonify({
        "today": d.isoformat(),
        "total_minutes": total,
        "blocks": blocks,
    })

# -------------------------
# API — My History  GET /notes/api/me/history?start&end
# -------------------------
@bp.route("/api/me/history", methods=["GET"])
@login_required
def api_me_history():
    start_str = (request.args.get("start") or "").strip()
    end_str   = (request.args.get("end") or "").strip()
    t = today_local()
    try:
        d_from = datetime.strptime(start_str, "%Y-%m-%d").date() if start_str else (t - timedelta(days=7))
        d_to   = datetime.strptime(end_str, "%Y-%m-%d").date()   if end_str   else t
    except Exception:
        abort(400, "Invalid date format. Use YYYY-MM-DD.")
    if d_to < d_from:
        d_from, d_to = d_to, d_from

    rows = (WorkLogEntry.query
            .filter(WorkLogEntry.user_id == current_user.id,
                    WorkLogEntry.work_date >= d_from,
                    WorkLogEntry.work_date <= d_to)
            .order_by(WorkLogEntry.work_date.asc(),
                      WorkLogEntry.start_time_utc.asc())
            .all())

    grouped = defaultdict(list)
    totals = defaultdict(int)
    for r in rows:
        grouped[r.work_date].append(r)
        totals[r.work_date] += (r.minutes or compute_minutes(r.start_time_utc, r.end_time_utc))

    days = []
    for day in sorted(grouped.keys()):
        items = []
        for r in grouped[day]:
            items.append({
                "start": from_utc(r.start_time_utc).strftime("%H:%M"),
                "end":   from_utc(r.end_time_utc).strftime("%H:%M") if r.end_time_utc else None,
                "minutes": r.minutes or compute_minutes(r.start_time_utc, r.end_time_utc),
                "note": r.note or "",
            })
        days.append({
            "date": day.isoformat(),
            "total_minutes": totals[day],
            "blocks": items,
            "corrections": [],
        })

    return jsonify({
        "owner": { "id": current_user.id, "name": current_user.full_name },
        "days": days
    })

# -------------------------
# API — Create fixed entry (overlaps allowed)
# POST /notes/api/me/block/create  {"start":"HH:MM","end":"HH:MM","note": "..."}
# -------------------------
@bp.route("/api/me/block/create", methods=["POST"])
@login_required
def api_me_block_create():
    data = request.get_json(silent=True) or {}
    start_hhmm = (data.get("start") or "").strip()
    end_hhmm   = (data.get("end") or "").strip()
    note       = (data.get("note") or "").strip()

    if not (start_hhmm and end_hhmm):
        abort(400, "Потребни се и почеток и крај (HH:MM).")

    d = today_local()
    def parse(hhmm: str) -> datetime:
        try:
            h, m = map(int, hhmm.split(":"))
            return datetime(d.year, d.month, d.day, h, m, tzinfo=TZ)
        except Exception:
            abort(400, "Невалиден формат за време (HH:MM).")

    start_local = parse(start_hhmm)
    end_local   = parse(end_hhmm)
    dept_id     = capture_user_department_id(current_user)

    if end_local >= start_local:
        s_utc = to_utc(start_local)
        e_utc = to_utc(end_local)
        entry = WorkLogEntry(
            user_id=current_user.id,
            department_id=dept_id,
            work_date=d,
            start_time_utc=s_utc,
            end_time_utc=e_utc,
            task_category_id=None,
            note=note,
            status="draft",
            source="manual",
            minutes=compute_minutes(s_utc, e_utc),
        )
        db.session.add(entry)
        db.session.commit()
        return jsonify({"ok": True, "id": entry.id})
    else:
        # Cross-midnight: split into two rows
        end1_local = datetime(start_local.year, start_local.month, start_local.day, 23, 59, 59, tzinfo=TZ)
        s1_utc = to_utc(start_local)
        e1_utc = to_utc(end1_local)
        if e1_utc <= s1_utc:
            e1_utc = s1_utc + timedelta(minutes=1)

        e1 = WorkLogEntry(
            user_id=current_user.id,
            department_id=dept_id,
            work_date=d,
            start_time_utc=s1_utc,
            end_time_utc=e1_utc,
            task_category_id=None,
            note=note,
            status="draft",
            source="manual",
            minutes=compute_minutes(s1_utc, e1_utc),
        )
        db.session.add(e1)
        db.session.flush()

        next_day = d + timedelta(days=1)
        start2_local = datetime(end_local.year, end_local.month, end_local.day, 0, 0, tzinfo=TZ)
        s2_utc = to_utc(start2_local)
        e2_utc = to_utc(end_local)
        if e2_utc <= s2_utc:
            e2_utc = s2_utc + timedelta(minutes=1)

        e2 = WorkLogEntry(
            user_id=current_user.id,
            department_id=dept_id,
            work_date=next_day,
            start_time_utc=s2_utc,
            end_time_utc=e2_utc,
            task_category_id=None,
            note=note,
            status="draft",
            source="manual",
            minutes=compute_minutes(s2_utc, e2_utc),
        )
        db.session.add(e2)
        db.session.commit()
        return jsonify({"ok": True, "id": e1.id, "split": True, "new_id": e2.id})

# -------------------------
# API — Update (same-day only, overlaps allowed)
# POST /notes/api/me/block/update {"id":..., "start":"HH:MM","end":"HH:MM","note":"..."}
# -------------------------
@bp.route("/api/me/block/update", methods=["POST"])
@login_required
def api_me_block_update():
    data = request.get_json(silent=True) or {}
    block_id   = data.get("id")
    start_hhmm = (data.get("start") or "").strip()
    end_hhmm   = (data.get("end") or "").strip()
    note       = (data.get("note") or "").strip()

    if not block_id:
        abort(400, "Недостасува ID.")
    b = WorkLogEntry.query.filter_by(id=block_id, user_id=current_user.id).first()
    if not b:
        abort(404, "Записот не постои.")

    wd = b.work_date
    def parse_on(day: date, hhmm: str) -> datetime:
        try:
            h, m = map(int, hhmm.split(":"))
            return datetime(day.year, day.month, day.day, h, m, tzinfo=TZ)
        except Exception:
            abort(400, "Невалидно време (HH:MM).")

    if start_hhmm:
        b.start_time_utc = to_utc(parse_on(wd, start_hhmm))
    if end_hhmm:
        b.end_time_utc = to_utc(parse_on(wd, end_hhmm))

    if not b.start_time_utc or not b.end_time_utc:
        abort(400, "Потребни се и почеток и крај.")
    if b.end_time_utc <= b.start_time_utc:
        abort(400, "Крајот мора да е по почетокот (за истиот ден).")

    b.note = note
    b.minutes = compute_minutes(b.start_time_utc, b.end_time_utc)
    db.session.commit()
    return jsonify({"ok": True})

# -------------------------
# API — Delete
# -------------------------
@bp.route("/api/me/block/delete", methods=["POST"])
@login_required
def api_me_block_delete():
    data = request.get_json(silent=True) or {}
    block_id = data.get("id")
    if not block_id:
        abort(400, "Недостасува ID.")
    b = WorkLogEntry.query.filter_by(id=block_id, user_id=current_user.id).first()
    if not b:
        abort(404, "Записот не постои.")
    db.session.delete(b)
    db.session.commit()
    return jsonify({"ok": True})

# -------------------------
# API — Director History (My Dept)
# GET /notes/api/director/history?department_id=..&start=YYYY-MM-DD&end=YYYY-MM-DD
# -------------------------
@bp.route("/api/director/history", methods=["GET"])
@login_required
def api_director_history():
    dept_id = request.args.get("department_id", type=int)
    if not dept_id:
        abort(400, "Missing department_id.")
    dep = require_director_of(dept_id)

    start_str = (request.args.get("start") or "").strip()
    end_str   = (request.args.get("end") or "").strip()
    t = today_local()
    try:
        d_from = datetime.strptime(start_str, "%Y-%m-%d").date() if start_str else (t - timedelta(days=7))
        d_to   = datetime.strptime(end_str, "%Y-%m-%d").date()   if end_str   else t
    except Exception:
        abort(400, "Invalid date format. Use YYYY-MM-DD.")
    if d_to < d_from:
        d_from, d_to = d_to, d_from

    members = dep.members.order_by(User.first_name.asc(), User.last_name.asc()).all()
    member_ids = {u.id for u in members}

    rows = (WorkLogEntry.query
            .filter(WorkLogEntry.department_id == dep.id,
                    WorkLogEntry.user_id.in_(member_ids),
                    WorkLogEntry.work_date >= d_from,
                    WorkLogEntry.work_date <= d_to)
            .order_by(WorkLogEntry.user_id.asc(),
                      WorkLogEntry.work_date.asc(),
                      WorkLogEntry.start_time_utc.asc())
            .all())

    grouped = defaultdict(lambda: defaultdict(list))  # user -> day -> blocks
    total_user = defaultdict(int)
    total_day  = defaultdict(int)

    for r in rows:
        grouped[r.user_id][r.work_date].append(r)
        mins = r.minutes or compute_minutes(r.start_time_utc, r.end_time_utc)
        total_user[r.user_id] += mins
        total_day[(r.user_id, r.work_date)] += mins

    payload = {
        "department": {"id": dep.id, "name": dep.name},
        "date_from": d_from.isoformat(),
        "date_to": d_to.isoformat(),
        "users": []
    }

    for u in members:
        days_out = []
        for dday, lst in sorted(grouped.get(u.id, {}).items(), key=lambda x: x[0]):
            blocks = [{
                "id": b.id,
                "start": from_utc(b.start_time_utc).strftime("%H:%M"),
                "end":   from_utc(b.end_time_utc).strftime("%H:%M") if b.end_time_utc else None,
                "minutes": b.minutes or compute_minutes(b.start_time_utc, b.end_time_utc),
                "note": b.note or "",
            } for b in lst]
            days_out.append({
                "date": dday.isoformat(),
                "total_minutes": total_day[(u.id, dday)],
                "blocks": blocks,
                "corrections": [],
            })
        payload["users"].append({
            "user_id": u.id,
            "name": u.full_name,
            "total_minutes": total_user[u.id],
            "days": days_out,
        })

    return jsonify(payload)


# ... (imports and helpers as in my previous answer)

# Real-Time (My Dept): “active now” if now ∈ [start,end] TODAY (local-tz aware)
# app/notes/routes.py (replace the whole realtime route with this)
@bp.route("/api/director/realtime", methods=["GET"])
@login_required
def api_director_realtime():
    dept_id = request.args.get("department_id", type=int)
    if not dept_id:
        abort(400, "Missing department_id.")
    dep = require_director_of(dept_id)

    # Local “today” and an aware UTC 'now'
    now_local = datetime.now(TZ)
    today = now_local.date()
    now_utc_ts = as_aware_utc(now_local.astimezone(_py_tz.utc))

    # Current roster
    members = dep.members.order_by(User.first_name.asc(), User.last_name.asc()).all()
    member_ids = {u.id for u in members}
    name_by_id = {u.id: u.full_name for u in members}

    # Today’s rows
    rows = (WorkLogEntry.query
            .filter(WorkLogEntry.department_id == dep.id,
                    WorkLogEntry.user_id.in_(member_ids),
                    WorkLogEntry.work_date == today)
            .order_by(WorkLogEntry.user_id.asc(),
                      WorkLogEntry.start_time_utc.asc())
            .all())

    # Group rows per user and normalize datetimes
    per_user = {uid: [] for uid in member_ids}
    for r in rows:
        r.start_time_utc = as_aware_utc(r.start_time_utc)
        r.end_time_utc   = as_aware_utc(r.end_time_utc)
        per_user.setdefault(r.user_id, []).append(r)

    users_out = []
    for u in members:
        lst = per_user.get(u.id, [])
        total_mins = 0
        blocks_out = []
        active_now = False
        latest_end = None

        for r in lst:
            mins = (r.minutes or 0)
            if not mins and r.start_time_utc and r.end_time_utc:
                mins = int((r.end_time_utc - r.start_time_utc).total_seconds() // 60)
            total_mins += mins

            is_now = bool(
                r.start_time_utc and r.end_time_utc and
                r.start_time_utc <= now_utc_ts <= r.end_time_utc
            )
            active_now = active_now or is_now
            if r.end_time_utc and (latest_end is None or r.end_time_utc > latest_end):
                latest_end = r.end_time_utc

            blocks_out.append({
                "id": r.id,
                "start": from_utc(r.start_time_utc).strftime("%H:%M") if r.start_time_utc else None,
                "end":   from_utc(r.end_time_utc).strftime("%H:%M") if r.end_time_utc else None,
                "minutes": mins,
                "note": r.note or "",
                "active_now": is_now,
            })

        status = "offline"
        last_end_hhmm = None
        if lst:
            status = "active" if active_now else "idle"
            if latest_end:
                last_end_hhmm = from_utc(latest_end).strftime("%H:%M")

        users_out.append({
            "user_id": u.id,
            "name": name_by_id.get(u.id, f"User {u.id}"),
            "status": status,                 # active | idle | offline
            "last_end": last_end_hhmm,        # for idle users
            "total_minutes": total_mins,
            "blocks": blocks_out,             # all blocks for today
        })

    # Optional UX sorting: active first, then idle, then offline; then by name
    order_key = {"active": 0, "idle": 1, "offline": 2}
    users_out.sort(key=lambda x: (order_key.get(x["status"], 9), x["name"]))

    return jsonify({
        "department": {"id": dep.id, "name": dep.name},
        "date": today.isoformat(),
        "users": users_out
    })