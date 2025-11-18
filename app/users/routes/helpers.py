from __future__ import annotations
import os, re, uuid, mimetypes, logging
from typing import Optional, Any
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from flask import current_app, request, abort, send_from_directory
from flask_wtf.csrf import validate_csrf, CSRFError
from werkzeug.utils import secure_filename
from sqlalchemy import func
from app.extensions import db
from app.models import (
    User, Role, Attachment, Department, Agreement, Vacation, SickLeave,
    Report, Uniform, Training, RewardPenalty, Permission
)

# Permissions glue
from app.permissions import (
    USERS_VIEW, USERS_GENERAL, USERS_CREATE_EDIT, USERS_AGREEMENT, USERS_VACATION,
    USERS_SICK, USERS_REPORTS, USERS_UNIFORMS, USERS_TRAINING, USERS_REWARDS,
    USERS_PENALTY, USERS_ATTACHMENTS, require_any, require_permission, has_permission
)

log = logging.getLogger(__name__)
FAR_FUTURE = date(2099, 12, 31)
_RE_REPORT = re.compile(r"(?:^|_)report_(sanitary|system)_(\d{4}-\d{2}-\d{2})_", re.IGNORECASE)

# ---- Role helpers ----
def _ensure_admin_role() -> Role:
    role = Role.query.filter(func.lower(Role.name) == "admin").first()
    if not role:
        role = Role(name="admin")
        db.session.add(role)
        db.session.flush()
    return role

def _assign_role_from_is_admin(user: User, is_admin: bool) -> None:
    if is_admin:
        user.role = _ensure_admin_role()
    else:
        if user.role and (user.role.name or "").lower() == "admin":
            user.role = None

# ---- Serializers / misc ----
def _ser_reward(rp: RewardPenalty):
    try:
        atts = rp.attachments.order_by(Attachment.uploaded_at.desc()).all()
    except Exception:
        atts = []
    return {
        "id": rp.id, "note": rp.note or "", "date": _fmt(rp.date),
        "attachments": [{"id": a.id, "filename": a.filename, "stored_name": a.stored_name} for a in atts],
    }

def _parse_iso_date(s: Optional[str]) -> Optional[date]:
    if not s: return None
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    except Exception:
        return None

def _parse_yyyy_mm_dd(s: str) -> date:
    y, m, d = [int(x) for x in (s or "").split("-")]
    return date(y, m, d)

def _fmt(dt):
    if not dt: return ""
    if hasattr(dt, "strftime") and type(dt).__name__ in ("date", "datetime"):
        if type(dt).__name__ == "datetime":
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return dt.strftime("%Y-%m-%d")
    return str(dt)

def _today() -> date:
    return date.today()

def _digits_only(val: Optional[str]) -> Optional[str]:
    if not val: return None
    s = "".join(ch for ch in str(val) if ch.isdigit())
    return s or None

def _safe_int(val: Any, default: int = 0) -> int:
    try: return int(val)
    except Exception: return int(default)

def _is_indef(a: Agreement) -> bool:
    return (a.months or 0) == 0

def _calc_end_months(start: date, months: int) -> date:
    if months <= 0: months = 1
    return start + relativedelta(months=+months)

def _vacation_days_left(u: User) -> int:
    total = int(u.vacation_days or 0)
    used = 0
    for v in u.vacations.filter(Vacation.status != "cancelled").all():
        used += int(v.days or 0)
    left = total - used
    return left if left >= 0 else 0

def _agreement_json(a: Agreement):
    return {
        "id": a.id, "user_id": a.user_id,
        "start_date": _fmt(a.start_date),
        "months": a.months,
        "end_date": ("неопределено" if _is_indef(a) else _fmt(a.end_date)),
        "status": a.status,
        "kind": ("indefinite" if _is_indef(a) else "finite"),
        "attachments": [
            {"id": at.id, "filename": at.filename, "stored_name": at.stored_name}
            for at in _attachments_sorted(a)
        ],
    }

def _attachments_sorted(agreement: Agreement):
    rel = agreement.attachments
    if hasattr(rel, "order_by"):
        return rel.order_by(Attachment.uploaded_at.desc()).all()
    return sorted(rel or [], key=lambda x: x.uploaded_at or datetime.min, reverse=True)

def _check_csrf():
    token = request.headers.get("X-CSRFToken")
    if not token:
        abort(400, description="Missing CSRF token header")
    try:
        validate_csrf(token)
    except CSRFError as e:
        abort(400, description=str(e))

def _upload_root():
    root = current_app.config.get("UPLOAD_FOLDER", os.path.join(current_app.instance_path, "uploads"))
    os.makedirs(root, exist_ok=True)
    return root

def _ensure_upload_dir() -> str:
    upload_dir = current_app.config.get("UPLOADS_DIR") or current_app.config.get("UPLOAD_FOLDER")
    if not upload_dir:
        upload_dir = os.path.join(current_app.instance_path, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir

def _agreements_dir():
    base = current_app.config.get("AGREEMENTS_UPLOAD_DIR") or os.path.join(current_app.instance_path, "agreements")
    os.makedirs(base, exist_ok=True)
    return base


def _collect_files_from_request():
    files = []
    files.extend(request.files.getlist("file"))
    files.extend(request.files.getlist("files"))
    seen, unique = set(), []
    for f in files:
        if id(f) not in seen and f and f.filename:
            unique.append(f)
            seen.add(id(f))
    return unique

def _report_files_for(user: User, kind: str):
    q = Attachment.query.filter(
        Attachment.user_id == user.id,
        Attachment.agreement_id.is_(None),
        Attachment.sick_leave_id.is_(None),
        Attachment.vacation_id.is_(None),
        Attachment.uniform_id.is_(None),
        Attachment.training_id.is_(None),
        Attachment.reward_penalty_id.is_(None),
        Attachment.stored_name.like(f"REP_{kind}_%"),
    ).order_by(Attachment.uploaded_at.desc())

    buckets = {}
    for a in q.all():
        date_str = None
        k, d = _parse_report_meta(a.stored_name or "")
        if k == kind and d:
            date_str = d
        buckets.setdefault(date_str, []).append({
            "id": a.id, "filename": a.filename, "stored_name": a.stored_name,
            "uploaded_at": a.uploaded_at.strftime("%Y-%m-%d %H:%M:%S") if a.uploaded_at else None,
        })

    def sort_key(item):
        d = item[0]
        return (0, d) if d else (1, "9999-99-99")
    items = []
    for d, files in sorted(buckets.items(), key=sort_key, reverse=True):
        items.append({"date": d, "files": files})
    return items

def _parse_report_meta(stored_name: str):
    if not stored_name: return (None, None)
    m = _RE_REPORT.search(stored_name)
    if not m: return (None, None)
    return (m.group(1).lower(), m.group(2))

def _business_days_between(start: date, end: date, holidays: set[date]) -> int:
    if end < start: return 0
    days, d = 0, start
    while d <= end:
        if d.weekday() < 5 and d not in holidays:
            days += 1
        d += timedelta(days=1)
    return days

def _business_days_add(start: date, days: int, holidays: set[date]) -> tuple[date, date]:
    if days <= 0: days = 1
    d, used = start, 0
    while used < days:
        if d.weekday() < 5 and d not in holidays:
            used += 1
            if used == days:
                end_date = d
                break
        d += timedelta(days=1)
    r = end_date + timedelta(days=1)
    while r.weekday() >= 5 or r in holidays:
        r += timedelta(days=1)
    return end_date, r

def _user_to_dict(u: User) -> dict:
    managed = Department.query.filter_by(manager_id=u.id).first()
    return {
        "id": u.id,
        "first_name": u.first_name,
        "last_name": u.last_name,
        "department": (u.dept.name if getattr(u, "dept", None) else None),
        "email": u.email,
        "phone_number": u.phone_number,
        "id_number": u.id_number,
        "embg": u.embg,
        "city": u.city,
        "address": u.address,
        "bank_account": u.bank_account,
        "vacation_days": int(u.vacation_days or 0),
        "vacation_days_left": _vacation_days_left(u),
        "role": (u.role.name if u.role else None),
        "is_admin": bool(u.role and (u.role.name or "").lower() == "admin"),
        "director_of": (managed.name if managed else None),
        "is_suspended": bool(getattr(u, "is_suspended", False)),
    }

def _filesize(fs) -> int:
    size = getattr(fs, "content_length", None)
    if isinstance(size, int) and size >= 0:
        return size
    try: pos = fs.stream.tell()
    except Exception: pos = None
    try:
        fs.stream.seek(0, os.SEEK_END)
        size = fs.stream.tell()
    except Exception:
        size = -1
    finally:
        try: fs.stream.seek(pos or 0, os.SEEK_SET)
        except Exception: pass
    return size

def serve_file_from(base_dir: str, stored_name: str, require_exists: bool = True):
    safe_name = os.path.basename(stored_name)
    full = os.path.join(base_dir, safe_name)
    if require_exists and not os.path.isfile(full):
        log.warning("File not found: %s (dir=%s)", safe_name, base_dir)
        abort(404)
    guessed_mime = mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
    return send_from_directory(base_dir, safe_name, as_attachment=False, mimetype=guessed_mime)

def _auto_expire_for_user(u: User) -> None:
    try:
        today = date.today()
        for t in u.trainings.filter(Training.status == "active").all():
            if t.end_date and t.end_date <= today:
                t.status = "history"
        for un in u.uniforms.all():
            if un.next_due_date:
                un.status = "history" if un.next_due_date <= today else "active"
        for v in u.vacations.filter(Vacation.status == "active").all():
            if v.end_date and v.end_date <= today:
                v.status = "completed"
        for s in u.sick_leaves.filter(SickLeave.status == "active").all():
            if s.end_date and s.end_date <= today:
                s.status = "history"
        db.session.commit()
    except Exception:
        db.session.rollback()


# app/users/routes/helpers.py
def vacation_days_left(u):
    total = int(u.vacation_days or 0)
    used = 0
    try:
        for v in u.vacations.filter_by().all():
            if getattr(v, "status", None) != "cancelled":
                used += int(getattr(v, "days", 0) or 0)
    except Exception:
        pass
    left = total - used
    return left if left >= 0 else 0
