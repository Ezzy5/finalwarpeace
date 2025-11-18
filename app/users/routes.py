# app/users/routes.py
from __future__ import annotations
import os
import uuid
import logging
import re
from uuid import uuid4
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from flask_wtf.csrf import validate_csrf, CSRFError
import mimetypes


from flask import (
    render_template, jsonify, request,
    current_app, send_from_directory, abort
)
from flask_login import login_required
from sqlalchemy import select, func, desc
from werkzeug.utils import secure_filename
from sqlalchemy.exc import OperationalError

from . import bp  # single, consistent blueprint import
from ..extensions import db
from ..models import (
    User, Role, Attachment, Department,
    Agreement, Vacation,
    SickLeave, Report, Uniform, Training, RewardPenalty
)

from sqlalchemy.exc import OperationalError
# =========================
# Helpers
# =========================

FAR_FUTURE = date(2099, 12, 31)
_RE_REPORT = re.compile(r"(?:^|_)report_(sanitary|system)_(\d{4}-\d{2}-\d{2})_", re.IGNORECASE)
log = logging.getLogger(__name__)

def _ser_reward(rp: RewardPenalty):
    """Serialize a RewardPenalty row with attachments (if any)."""
    try:
        atts = rp.attachments.order_by(Attachment.uploaded_at.desc()).all()
    except Exception:
        atts = []
    return {
        "id": rp.id,
        "note": rp.note or "",
        "date": _fmt(rp.date),
        "attachments": [
            {"id": a.id, "filename": a.filename, "stored_name": a.stored_name}
            for a in atts
        ],
    }


def _parse_iso_date(s: str | None) -> date | None:
    if not s:
        return None
    # Accept only HTML date input format, guard errors
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    except Exception:
        return None
    
def _rp_row(rp):
    try:
        atts = rp.attachments.order_by(Attachment.uploaded_at.desc()).all()
    except Exception:
        atts = []
    return {
        "id": rp.id,
        "note": rp.note,
        "date": _fmt_date(rp.date),
        "attachments": [
            {"id": a.id, "filename": a.filename, "stored_name": a.stored_name}
            for a in atts
        ],
    }
def _report_files_for(user: "User", kind: str):
    """
    Return grouped files for reports of `kind` ('sanitary' or 'system').
    Files are ownerless (no FK) and tagged in stored_name like:
      REP_sanitary_2025-09-01_<uuid>_<filename>
    """
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

    # group by extracted date from stored_name
    buckets = {}  # date_str -> [files]
    for a in q.all():
        date_str = None
        k, d = _parse_report_meta(a.stored_name or "")
        if k == kind and d:
            date_str = d
        files = buckets.setdefault(date_str, [])
        files.append({
            "id": a.id,
            "filename": a.filename,
            "stored_name": a.stored_name,
            "uploaded_at": a.uploaded_at.strftime("%Y-%m-%d %H:%M:%S") if a.uploaded_at else None,
        })

    # Convert to [{date, files}] sorted by date desc (None last)
    def sort_key(item):
        d = item[0]
        return (0, d) if d else (1, "9999-99-99")
    items = []
    for d, files in sorted(buckets.items(), key=sort_key, reverse=True):
        items.append({"date": d, "files": files})
    return items

def _coerce_date(val) -> date | None:
    """Accept date|str|None and return a datetime.date (or None)."""
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return None
        # accept YYYY-MM-DD
        return datetime.strptime(val, "%Y-%m-%d").date()
    raise ValueError("Unsupported date value")

def _dates_csv_to_set(csv_str: str | None) -> set[date]:
    s = set()
    if not csv_str:
        return s
    for part in csv_str.split(","):
        part = part.strip()
        if part:
            try:
                s.add(datetime.strptime(part, "%Y-%m-%d").date())
            except Exception:
                pass
    return s


def _is_indef(a):
    """Convention: months == 0 means indefinite."""
    return (a.months or 0) == 0


def _check_csrf():
    token = request.headers.get("X-CSRFToken")
    if not token:
        abort(400, description="Missing CSRF token header")
    try:
        validate_csrf(token)
    except CSRFError as e:
        abort(400, description=str(e))


def _today() -> date:
    return date.today()


def _parse_yyyy_mm_dd(s: str) -> date:
    y, m, d = [int(x) for x in (s or "").split("-")]
    return date(y, m, d)


def _fmt(dt):
    if not dt:
        return ""
    # if it's a date
    if hasattr(dt, "strftime") and type(dt).__name__ in ("date", "datetime"):
        if type(dt).__name__ == "datetime":
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return dt.strftime("%Y-%m-%d")
    return str(dt)

def _business_days_between(start: date, end: date, holidays: set[date]) -> int:
    """Inclusive business-day count between start and end, skipping Sat/Sun + holidays."""
    if end < start:
        return 0
    days = 0
    d = start
    while d <= end:
        if d.weekday() < 5 and d not in holidays:
            days += 1
        d += timedelta(days=1)
    return days


def _business_days_add(start: date, days: int, holidays: set[date]) -> tuple[date, date]:
    """
    Add 'days' business days to 'start' (Mon–Fri), excluding holidays.
    Returns (end_date, return_date).
    """
    if days <= 0:
        days = 1
    d = start
    used = 0
    while used < days:
        if d.weekday() < 5 and d not in holidays:
            used += 1
            if used == days:
                end_date = d
                break
        d += timedelta(days=1)
    # first working day after end_date
    r = end_date + timedelta(days=1)
    while r.weekday() >= 5 or r in holidays:
        r += timedelta(days=1)
    return end_date, r


def _vacation_days_left(u: User) -> int:
    total = int(u.vacation_days or 0)
    used = 0
    for v in u.vacations.filter(Vacation.status != "cancelled").all():
        used += int(v.days or 0)
    left = total - used
    return left if left >= 0 else 0


def _calc_end_months(start: date, months: int) -> date:
    if months <= 0:
        months = 1
    return start + relativedelta(months=+months)


def _safe_int(val, default=0):
    try:
        return int(val)
    except Exception:
        return default


def _upload_root():
    root = current_app.config.get(
        "UPLOAD_FOLDER",
        os.path.join(current_app.instance_path, "uploads"),
    )
    os.makedirs(root, exist_ok=True)
    return root
def _uploads_dir():
    base = current_app.config.get("UPLOAD_FOLDER")
    if not base:
        base = os.path.join(current_app.instance_path, "uploads")
    os.makedirs(base, exist_ok=True)
    return base

def _agreements_dir():
    path = os.path.join(_upload_root(), "agreements")
    os.makedirs(path, exist_ok=True)
    return path


def _attachments_sorted(agreement):
    rel = agreement.attachments
    if hasattr(rel, "order_by"):
        return rel.order_by(Attachment.uploaded_at.desc()).all()
    return sorted(
        rel or [],
        key=lambda x: x.uploaded_at or datetime.min,
        reverse=True
    )


def _agreement_json(a: Agreement):
    return {
        "id": a.id,
        "user_id": a.user_id,
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


def _allowed_mimetype(mtype: str) -> bool:
    allowed = set(current_app.config.get("ALLOWED_UPLOADS", []))
    if not allowed:
        # If not configured, allow all types
        return True
    return (mtype or "").lower() in allowed


def _ensure_upload_dir() -> str:
    upload_dir = current_app.config.get("UPLOADS_DIR") or current_app.config.get("UPLOAD_FOLDER")
    if not upload_dir:
        # Fallback: instance/uploads
        upload_dir = os.path.join(current_app.instance_path, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def _collect_files_from_request():
    """
    Supports both 'file' (possibly multiple parts with same name)
    and 'files' (array style).
    Returns a list of FileStorage.
    """
    files = []
    # multiple parts named 'file'
    files.extend(request.files.getlist("file"))
    # multiple parts named 'files'
    files.extend(request.files.getlist("files"))
    # de-dup in case a client sent same objects under both keys
    seen = set()
    unique = []
    for f in files:
        if id(f) not in seen and f and f.filename:
            unique.append(f)
            seen.add(id(f))
    return unique


def _agreements_upload_dir() -> str:
    """
    Returns the absolute folder path where agreement files are stored.
    Uses CONFIG if present; otherwise falls back to instance/agreements.
    Ensures the directory exists.
    """
    base = current_app.config.get("AGREEMENTS_UPLOAD_DIR")
    if not base:
        base = os.path.join(current_app.instance_path, "agreements")
    os.makedirs(base, exist_ok=True)
    return base


def _parse_report_meta(stored_name: str):
    """
    Returns (kind, date_str) or (None, None).
    Matches both:
      - report_sanitary_2025-09-01_<...>
      - <uuid>_report_system_2025-09-01_<...>
    """
    if not stored_name:
        return (None, None)
    m = _RE_REPORT.search(stored_name)  # <-- use .search, not .match
    if not m:
        return (None, None)
    return (m.group(1).lower(), m.group(2))
    
from datetime import date
from app.models import db, User, Attachment, Training, Uniform, Vacation, SickLeave

from datetime import date
from app.models import db, User, Attachment, Training, Uniform, Vacation, SickLeave

def _auto_expire_for_user(u: User) -> None:
    """Update statuses in-place. Never throws if tables are mid-migration."""
    try:
        today = date.today()

        # Trainings: active -> history if end_date <= today
        for t in u.trainings.filter(Training.status == "active").all():
            if t.end_date and t.end_date <= today:
                t.status = "history"

        # Uniforms: active/history from next_due_date
        for un in u.uniforms.all():
            if un.next_due_date:
                un.status = "history" if un.next_due_date <= today else "active"

        # Vacations: active -> completed if end_date <= today
        for v in u.vacations.filter(Vacation.status == "active").all():
            if v.end_date and v.end_date <= today:
                v.status = "completed"

        # SickLeaves: active -> history if end_date <= today
        for s in u.sick_leaves.filter(SickLeave.status == "active").all():
            if s.end_date and s.end_date <= today:
                s.status = "history"

        db.session.commit()
    except Exception:
        db.session.rollback()
        # swallow to avoid breaking list routes


# =========================
# Panel
# =========================

@bp.route("/panel", methods=["GET"])
@login_required
def panel():
  if request.headers.get("X-Requested-With") == "fetch":
    return render_template("panel.html")  # the fragment above
  # open directly in a full page? serve the dashboard shell (which includes #MainContent)
  return render_template("dashboard.html", initial_panel="users")
# =========================
# Users: list / create / update / delete
# =========================

@bp.route("/api/list", methods=["GET"])
@login_required
def api_list():
    page = max(int(request.args.get("page", 1) or 1), 1)
    per_page = min(max(int(request.args.get("per_page", 50) or 50), 1), 200)

    q = User.query.order_by(User.id.asc())
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)
    users = pagination.items

    # map user_id -> first department managed (director_of)
    user_ids = [u.id for u in users]
    director_map = {}
    if user_ids:
        rows = db.session.execute(
            select(Department.manager_id, Department.name).where(Department.manager_id.in_(user_ids))
        ).all()
        for mid, dname in rows:
            if mid and dname and mid not in director_map:
                director_map[mid] = dname

    def row(u: User):
        dept_name = u.dept.name if getattr(u, "dept", None) else None
        return {
            "id": u.id,
            "first_name": u.first_name or "",
            "last_name": u.last_name or "",
            "department": dept_name,
            "email": u.email or "",
            "phone_number": u.phone_number or "",
            "id_number": u.id_number or "",
            "embg": u.embg or "",
            "vacation_days": int(u.vacation_days or 0),
            "vacation_days_left": _vacation_days_left(u),
            "role": (u.role.name if getattr(u, "role", None) else None),
            "director_of": director_map.get(u.id),
        }

    return jsonify({
        "items": [row(u) for u in users],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
        "per_page": pagination.per_page,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev,
    })

@bp.route("/api/create", methods=["POST"])
@login_required
def api_create():
    data = request.get_json(silent=True) or {}

    first_name     = (data.get("first_name") or "").strip()
    last_name      = (data.get("last_name") or "").strip()
    email          = (data.get("email") or "").strip().lower()
    phone_number   = (data.get("phone_number") or "").strip() or None
    id_number      = (data.get("id_number") or "").strip()
    embg           = (data.get("embg") or "").strip() or None
    vacation_days  = _safe_int(data.get("vacation_days"), 0)
    role_id        = data.get("role_id")

    # NEW: password fields
    password       = data.get("password") or ""
    password2      = data.get("password2") or ""

    errors = {}

    # ---- validations ----
    if not first_name:
        errors["first_name"] = "Required."
    if not last_name:
        errors["last_name"] = "Required."
    if not email:
        errors["email"] = "Required."
    elif "@" not in email:
        errors["email"] = "Invalid email."
    if not id_number:
        errors["id_number"] = "Required."
    if vacation_days < 0:
        errors["vacation_days"] = "Must be ≥ 0."

    # unique constraints (case-insensitive for email)
    if email and db.session.query(User.id).filter(func.lower(User.email) == email).first():
        errors["email"] = "Email already exists."
    if id_number and db.session.query(User.id).filter(User.id_number == id_number).first():
        errors["id_number"] = "ID number already exists."
    if embg and db.session.query(User.id).filter(User.embg == embg).first():
        errors["embg"] = "EMBG already exists."

    # role check (optional)
    role = None
    if role_id not in (None, "", "null"):
        try:
            role = db.session.get(Role, int(role_id))
        except Exception:
            role = None
        if not role:
            errors["role_id"] = "Role not found."

    # NEW: password requirements
    if not password:
        errors["password"] = "Required."
    elif len(password) < 8:
        errors["password"] = "Min 8 characters."
    if password != password2:
        errors["password2"] = "Passwords do not match."

    if errors:
        return jsonify({"errors": errors}), 400

    # ---- create user ----
    u = User(
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone_number=phone_number,
        id_number=id_number,
        embg=embg,
        role=role,
        department=None,            # set later if needed
        vacation_days=vacation_days,
        is_active=True,             # ensure active
        is_suspended=False,         # new users can log in
    )
    # hash & set password
    u.set_password(password)

    db.session.add(u)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        # In case of race conditions on unique fields
        return jsonify({"errors": {"email": "Email already exists."}}), 400

    managed = Department.query.filter_by(manager_id=u.id).first()

    return jsonify({
        "ok": True,
        "item": {
            "id": u.id,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "department": (u.dept.name if getattr(u, "dept", None) else None),
            "email": u.email,
            "phone_number": u.phone_number,
            "id_number": u.id_number,
            "embg": u.embg,
            "vacation_days": int(u.vacation_days or 0),
            "vacation_days_left": _vacation_days_left(u),
            "role": (u.role.name if u.role else None),
            "director_of": (managed.name if managed else None),
            "is_suspended": bool(getattr(u, "is_suspended", False)),  # expose for UI
        }
    }), 201

@bp.route("/api/update/<int:user_id>", methods=["POST"])
@login_required
def api_update(user_id: int):
    u = User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}

    # ----- incoming fields -----
    first_name     = (data.get("first_name") or "").strip()
    last_name      = (data.get("last_name") or "").strip()
    email          = (data.get("email") or "").strip().lower()
    phone_number   = (data.get("phone_number") or "").strip() or None
    id_number      = (data.get("id_number") or "").strip()
    embg           = (data.get("embg") or "").strip() or None
    vacation_days  = _safe_int(data.get("vacation_days"), u.vacation_days or 0)

    # NEW: optional password change
    new_password   = (data.get("new_password") or "")
    new_password2  = (data.get("new_password2") or "")

    errors = {}

    # ----- validations (profile) -----
    if not first_name:
        errors["first_name"] = "Required."
    if not last_name:
        errors["last_name"] = "Required."
    if not email:
        errors["email"] = "Required."
    elif "@" not in email:
        errors["email"] = "Invalid email."
    if not id_number:
        errors["id_number"] = "Required."
    if vacation_days < 0:
        errors["vacation_days"] = "Must be ≥ 0."

    # unique checks (email case-insensitive)
    if email and db.session.query(User.id).filter(
        func.lower(User.email) == email,
        User.id != u.id
    ).first():
        errors["email"] = "Email already exists."

    if id_number and db.session.query(User.id).filter(
        User.id_number == id_number,
        User.id != u.id
    ).first():
        errors["id_number"] = "ID number already exists."

    if embg and db.session.query(User.id).filter(
        User.embg == embg,
        User.id != u.id
    ).first():
        errors["embg"] = "EMBG already exists."

    # ----- validations (password) -----
    # Only validate if the client is attempting a change
    if new_password or new_password2:
        if not new_password:
            errors["new_password"] = "Required."
        elif len(new_password) < 8:
            errors["new_password"] = "Min 8 characters."
        if new_password != new_password2:
            errors["new_password2"] = "Passwords do not match."

    if errors:
        return jsonify({"errors": errors}), 400

    # ----- apply updates -----
    u.first_name     = first_name
    u.last_name      = last_name
    u.email          = email
    u.phone_number   = phone_number
    u.id_number      = id_number
    u.embg           = embg
    u.vacation_days  = vacation_days

    # set new password if requested
    if new_password:
        u.set_password(new_password)

    db.session.commit()

    managed = Department.query.filter_by(manager_id=u.id).first()

    return jsonify({
        "ok": True,
        "item": {
            "id": u.id,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "department": (u.dept.name if getattr(u, "dept", None) else None),
            "email": u.email,
            "phone_number": u.phone_number,
            "id_number": u.id_number,
            "embg": u.embg,
            "vacation_days": int(u.vacation_days or 0),
            "vacation_days_left": _vacation_days_left(u),
            "role": (u.role.name if u.role else None),
            "director_of": (managed.name if managed else None),
            # you can also include is_suspended here if your UI needs it
        }
    })

@bp.post("/api/suspend/<int:user_id>")
@login_required
def api_suspend(user_id):
    u = db.session.get(User, user_id)
    if not u:
        return jsonify({"error": "Not found"}), 404
    data = request.get_json(silent=True) or {}
    suspended = bool(data.get("suspended"))
    u.is_suspended = suspended
    db.session.commit()
    return jsonify({"ok": True, "item": {"id": u.id, "is_suspended": u.is_suspended}})


# =========================
# Attachments (user-level & agreement/sick-leave level)
# =========================

# ---------- LIST ----------
@bp.route("/api/attachments/<int:user_id>", methods=["GET"])
@login_required
def list_attachments(user_id: int):
    u = User.query.get_or_404(user_id)
    q = u.attachments.order_by(desc(Attachment.uploaded_at))
    items = [{
        "id": a.id,
        "filename": a.filename,
        "stored_name": a.stored_name,
        "content_type": a.content_type,
        "uploaded_at": a.uploaded_at.isoformat() if a.uploaded_at else None,
        # associations (we include all so clients can reuse this list anywhere)
        "agreement_id": a.agreement_id,
        "sick_leave_id": a.sick_leave_id,
        "vacation_id": a.vacation_id,
        "uniform_id": a.uniform_id,
        "report_kind": a.report_kind,  # e.g., "sanitary" / "system"
    } for a in q.all()]
    return jsonify({"items": items})

# ---------- UPLOAD ----------
# app/users/routes.py
# app/users/routes.py (upload endpoint)
# Attachments upload (works for multiple owners + reports)
def _filesize(fs) -> int:
    """Best-effort size of an uploaded FileStorage without consuming it."""
    # Try content_length first
    size = getattr(fs, "content_length", None)
    if isinstance(size, int) and size >= 0:
        return size
    # Probe stream length
    try:
        pos = fs.stream.tell()
    except Exception:
        pos = None
    try:
        fs.stream.seek(0, os.SEEK_END)
        size = fs.stream.tell()
    except Exception:
        size = -1
    finally:
        try:
            fs.stream.seek(pos or 0, os.SEEK_SET)
        except Exception:
            pass
    return size

@bp.route("/api/attachments/<int:user_id>", methods=["POST"])
@login_required
def upload_attachment(user_id: int):
    """
    Multipart form-data:
      files=<File,File,...> OR file=<File> (older clients)
    Optional single owner id (agreement_id/sick_leave_id/vacation_id/uniform_id/training_id/reward_penalty_id)
    Optional report context for ownerless uploads:
      report_kind|kind|context: 'sanitary' | 'system'
      last_date|date: 'YYYY-MM-DD' (optional; defaults to today)
    """
    u = User.query.get_or_404(user_id)

    # ---- gather files (and dedupe) ----
    incoming = _collect_files_from_request()  # supports both 'file' and 'files'
    if not incoming:
        return jsonify({"errors": {"file": "Please choose a file."}}), 400

    # Per-request dedupe by (sanitized filename, filesize)
    unique_files = []
    seen = set()
    for f in incoming:
        if not f or not f.filename:
            continue
        safe = secure_filename(f.filename)
        key = (safe, _filesize(f))
        if key in seen:
            continue
        seen.add(key)
        unique_files.append((f, safe))

    if not unique_files:
        return jsonify({"errors": {"file": "No new files to upload."}}), 400

    # ---- detect owner (at most one) ----
    owners = {
        "agreement_id":      request.form.get("agreement_id"),
        "sick_leave_id":     request.form.get("sick_leave_id"),
        "vacation_id":       request.form.get("vacation_id"),
        "uniform_id":        request.form.get("uniform_id"),
        "training_id":       request.form.get("training_id"),
        "reward_penalty_id": request.form.get("reward_penalty_id"),
    }
    non_null = [(k, v) for k, v in owners.items() if v not in (None, "", "null")]
    if len(non_null) > 1:
        return jsonify({"errors": {"owner": "Provide only one owner id."}}), 400
    owner_kwargs = {}
    if non_null:
        k, v = non_null[0]
        try:
            owner_kwargs[k] = int(v)
        except ValueError:
            return jsonify({"errors": {"owner": f"{k} must be an integer"}}), 400

    # ---- report context (ownerless) ----
    rep_kind = (request.form.get("report_kind")
                or request.form.get("kind")
                or request.form.get("context") or "").strip().lower()
    if rep_kind not in ("sanitary", "system"):
        rep_kind = None

    raw_date = (request.form.get("last_date") or request.form.get("date") or "").strip()
    rep_date = None
    if raw_date:
        try:
            rep_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except Exception:
            rep_date = None
    if rep_kind and not rep_date:
        rep_date = date.today()

    # ---- storage ----
    allowed = set(current_app.config.get("ALLOWED_UPLOADS", []))
    upload_dir = _ensure_upload_dir()
    os.makedirs(upload_dir, exist_ok=True)

    saved = []
    for f, safe in unique_files:
        ct = (f.mimetype or "").lower()
        if allowed and ct not in allowed:
            return jsonify({"errors": {"file": f"Unsupported file type: {ct}"}}), 400

        if rep_kind and not owner_kwargs:
            date_str = rep_date.strftime("%Y-%m-%d")
            stored = f"REP_{rep_kind}_{date_str}_{uuid.uuid4().hex}_{safe}"
        else:
            stored = f"{uuid.uuid4().hex}_{safe}"

        f.save(os.path.join(upload_dir, stored))

        kwargs = dict(owner_kwargs)
        if hasattr(Attachment, "report_kind") and rep_kind and not owner_kwargs:
            kwargs["report_kind"] = rep_kind

        att = Attachment(
            user_id=u.id,
            filename=safe,
            stored_name=stored,
            content_type=ct,
            **kwargs,
        )
        db.session.add(att)
        saved.append(att)

    try:
        db.session.commit()
    except Exception as ex:
        db.session.rollback()
        return jsonify({"errors": {"_": f"Failed to save attachments: {type(ex).__name__}"}}), 400

    return jsonify({
        "ok": True,
        "items": [{
            "id": a.id,
            "filename": a.filename,
            "stored_name": a.stored_name,
            "content_type": a.content_type,
            "uploaded_at": a.uploaded_at.isoformat() if getattr(a, "uploaded_at", None) else None,
        } for a in saved]
    })




# ---------- SERVE ----------
@bp.route("/attachments/<path:stored_name>", methods=["GET"])
@login_required
def serve_attachment(stored_name: str):
    upload_dir = _ensure_upload_dir()
    file_path = os.path.join(upload_dir, stored_name)
    if not os.path.isfile(file_path):
        # Optional: log for troubleshooting
        current_app.logger.warning("Attachment not found: %s (looked in %s)", stored_name, upload_dir)
        abort(404)
    # Let Flask detect mimetype; browsers can preview PDFs inline, etc.
    return send_from_directory(upload_dir, stored_name, as_attachment=False)


# =========================
# Agreements
# =========================
# ---------- list ----------
@bp.route("/api/agreements/<int:user_id>", methods=["GET"])
@login_required
def api_agreements_list(user_id: int):
    User.query.get_or_404(user_id)

    ags = (
        Agreement.query
        .filter_by(user_id=user_id)
        .order_by(Agreement.start_date.desc())
        .all()
    )

    active, history = [], []
    today = _today()
    changed = False

    for a in ags:
        # auto-expire ONLY finite agreements (months > 0)
        if a.status == "active" and (a.months or 0) > 0 and a.end_date and a.end_date < today:
            a.status = "expired"
            changed = True

        (active if a.status == "active" else history).append(_agreement_json(a))

    if changed:
        db.session.commit()

    return jsonify({"active": active, "history": history})


# ---------- create (finite) ----------

@bp.route("/api/agreements/<int:user_id>/create", methods=["POST"])
@login_required
def api_agreements_create(user_id: int):
  _check_csrf()
  User.query.get_or_404(user_id)
  data = request.get_json(silent=True) or {}
  start_s = (data.get("start_date") or "").strip()
  months = _safe_int(data.get("months"), 0)
  errors = {}
  try:
    start = _parse_yyyy_mm_dd(start_s)
  except Exception:
    start = None
    errors["start_date"] = "Invalid date (YYYY-MM-DD)."
  if months <= 0:
    errors["months"] = "Months must be positive."
  if errors:
    return jsonify({"errors": errors}), 400
  end = _calc_end_months(start, months)
  a = Agreement(user_id=user_id, start_date=start, months=months, end_date=end, status="active")
  # OPTIONAL: persist kind in db if you add a column; otherwise derived in JSON
  # a.kind = "finite"
  db.session.add(a)
  db.session.commit()
  return jsonify({"ok": True, "agreement": _agreement_json(a)})

# ---------- create (indefinite) ----------
@bp.route("/api/agreements/<int:user_id>/create_indefinite", methods=["POST"])
@login_required
def api_agreements_create_indef(user_id: int):
    _check_csrf()
    User.query.get_or_404(user_id)

    data = request.get_json(silent=True) or {}
    start_s = (data.get("start_date") or "").strip()

    try:
      start = _parse_yyyy_mm_dd(start_s) if start_s else _today()
    except Exception:
      return jsonify({"errors": {"start_date": "Invalid date (YYYY-MM-DD)."}}), 400

    # Indefinite: months=0, end_date far future (never auto-expire)
    a = Agreement(
        user_id=user_id,
        start_date=start,
        months=0,
        end_date=FAR_FUTURE,
        status="active",
    )
    db.session.add(a)
    db.session.commit()
    return jsonify({"ok": True, "agreement": _agreement_json(a)})

@bp.route("/api/agreements/<int:user_id>/<int:agreement_id>/extend", methods=["POST"])
@login_required
def api_agreements_extend(user_id: int, agreement_id: int):
    _check_csrf()
    a = Agreement.query.filter_by(id=agreement_id, user_id=user_id).first_or_404()

    data = request.get_json(silent=True) or {}
    add_months = _safe_int(data.get("months"), 0)
    if add_months <= 0:
        return jsonify({"errors": {"months": "Months must be positive."}}), 400

    # Your business rule: extend from current end_date.
    # If end_date is in the past, this still works (keeps the gap). If you
    # prefer renewing from "today" when expired, switch base to max(today, end).
    a.end_date = _calc_end_months(a.end_date, add_months)
    a.months = (a.months or 0) + add_months
    a.status = "active"
    db.session.commit()

    return jsonify({
        "ok": True,
        "agreement": {
            "id": a.id,
            "start_date": _fmt(a.start_date),
            "months": a.months,
            "end_date": _fmt(a.end_date),
            "status": a.status
        }
    })

# ---------- delete ----------
@bp.route("/api/agreements/<int:user_id>/<int:agreement_id>/delete", methods=["POST"])
@login_required
def api_agreements_delete(user_id: int, agreement_id: int):
  _check_csrf()
  a = Agreement.query.filter_by(id=agreement_id, user_id=user_id).first_or_404()
  # optionally delete attachments too
  for att in _attachments_sorted(a):
    try:
      os.remove(os.path.join(_agreements_dir(), att.stored_name))
    except Exception:
      pass
    db.session.delete(att)
  db.session.delete(a)
  db.session.commit()
  return jsonify({"ok": True})
  
# ---------- cancel (moves to history) ----------
@bp.route("/api/agreements/<int:user_id>/<int:agreement_id>/cancel", methods=["POST"])
@login_required
def api_agreements_cancel(user_id: int, agreement_id: int):
  _check_csrf()
  a = Agreement.query.filter_by(id=agreement_id, user_id=user_id).first_or_404()
  a.status = "cancelled"   # matches your model spelling
  db.session.commit()
  return jsonify({"ok": True, "agreement": _agreement_json(a)})


# ---------- attach file ----------
@bp.route("/api/agreements/<int:user_id>/attach", methods=["POST"])
@login_required
def api_agreements_attach(user_id: int):
  _check_csrf()
  user = User.query.get_or_404(user_id)
  agreement_id = request.form.get("agreement_id", type=int)
  if not agreement_id:
    return jsonify({"error": "agreement_id is required"}), 400
  a = Agreement.query.filter_by(id=agreement_id, user_id=user.id).first_or_404()
  f = request.files.get("file")
  if not f or f.filename == "":
    return jsonify({"error": "No file uploaded"}), 400

  dest = _agreements_dir()
  orig = secure_filename(f.filename)
  stored = f"{uuid4().hex}_{orig}"
  save_path = os.path.join(dest, stored)
  current_app.logger.info("Saving agreement attachment to %s", save_path)
  f.save(save_path)

  att = Attachment(
    user_id=user.id,
    agreement_id=a.id,
    filename=orig,
    stored_name=stored,
    content_type=f.mimetype or None,
  )
  db.session.add(att)
  db.session.commit()
  return jsonify({"ok": True, "attachment": {"id": att.id, "filename": att.filename, "stored_name": att.stored_name}})

# ---------- serve attachments (agreements) ----------
@bp.route("/attachments/<path:stored_name>", methods=["GET"], endpoint="attachments_get")
@login_required
def attachments_get(stored_name: str):
    """
    Legacy/alias route. Serves files from the same agreements directory.
    """
    base = _agreements_dir()
    safe_name = os.path.basename(stored_name)
    full = os.path.join(base, safe_name)
    if not os.path.isfile(full):
        current_app.logger.warning("Attachment not found: %s (looked in %s)", safe_name, base)
        abort(404)
    guessed_mime = mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
    current_app.logger.info("Serving attachment %s from %s", safe_name, base)
    return send_from_directory(base, safe_name, as_attachment=False, mimetype=guessed_mime)


@bp.route("/agreements/file/<path:stored_name>", methods=["GET"], endpoint="agreements_file")
@login_required
def agreements_file(stored_name: str):
    """
    Primary route used by the UI:
      /users/agreements/file/<stored_name>
    """
    base = _agreements_dir()  # ✅ use your existing helper
    safe_name = os.path.basename(stored_name)  # prevent traversal
    full = os.path.join(base, safe_name)

    if not os.path.isfile(full):
        current_app.logger.warning("Agreement file not found: %s (looked in %s)", safe_name, base)
        abort(404)

    guessed_mime = mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
    return send_from_directory(base, safe_name, as_attachment=False, mimetype=guessed_mime)
    
# =========================
# Vacations
# =========================

@bp.route("/api/vacations/<int:user_id>", methods=["GET"])
@login_required
def vacations_list(user_id: int):
    u = User.query.get_or_404(user_id)
    try:
        _auto_expire_for_user(u)
        rows = u.vacations.order_by(Vacation.start_date.desc()).all()
    except OperationalError:
        return jsonify({"vacation_days_left": 0, "active": [], "history": []})

    # --- put the fixed ser() here ---
    def ser(v):
        # Works for both lazy="dynamic" and list-like relationships
        try:
            rel = v.attachments
            if hasattr(rel, "order_by"):  # lazy="dynamic"
                atts = rel.order_by(Attachment.uploaded_at.desc()).all()
            else:  # list-like (lazy="selectin")
                atts = sorted(
                    rel or [],
                    key=lambda a: a.uploaded_at or datetime.min,
                    reverse=True
                )
        except Exception:
            atts = []

        return {
            "id": v.id,
            "start_date": _fmt(v.start_date),
            "end_date": _fmt(v.end_date),
            "days": v.days,
            "return_date": _fmt(v.return_date),
            "status": v.status,
            "attachments": [
                {"id": a.id, "filename": a.filename, "stored_name": a.stored_name}
                for a in atts
            ],
        }
    # --------------------------------

    active = [ser(v) for v in rows if v.status == "active"]
    history = [ser(v) for v in rows if v.status != "active"]

    return jsonify({
        "vacation_days_left": _vacation_days_left(u),
        "active": active,
        "history": history,
    })






@bp.route("/api/vacations/<int:user_id>/create", methods=["POST"])
@login_required
def vacations_create(user_id: int):
    u = User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}

    start_date_str = (data.get("start_date") or "").strip()
    days = data.get("days")
    holidays = data.get("holidays") or []  # list of 'YYYY-MM-DD' strings (optional)

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

    # add N business days (Mon–Fri), skipping holidays
    d = parse(start_date_str)
    remaining = days - 1  # inclusive start
    while remaining > 0:
        d = d + timedelta(days=1)
        if d.weekday() < 5 and fmt(d) not in holiday_set:
            remaining -= 1
    end_date = d

    # return date = next business day after end_date
    ret = end_date
    while True:
        ret = ret + timedelta(days=1)
        if ret.weekday() < 5 and fmt(ret) not in holiday_set:
            break

    vac = Vacation(
        user_id=u.id,
        start_date=parse(start_date_str),
        end_date=end_date,
        days=days,
        return_date=ret,
        status="active",
        holidays_csv=",".join(sorted(holiday_set)) if holiday_set else None
    )
    db.session.add(vac)
    db.session.commit()

    # Return clean JSON: only YYYY-MM-DD strings
    return jsonify({
        "ok": True,
        "item": {
            "id": vac.id,
            "start_date": vac.start_date.isoformat(),
            "end_date": vac.end_date.isoformat(),
            "return_date": vac.return_date.isoformat(),
            "days": vac.days,
            "status": vac.status,
            "attachments": [],  # initially empty
        }
    })


# ========================
# Sick Leaves (Боледувања)
# =========================

from sqlalchemy.exc import OperationalError
from flask import jsonify, request
from flask_login import login_required
from ..extensions import db
from ..models import User, SickLeave, Attachment

# =========================
# Sick Leaves: LIST
# =========================
@bp.route("/api/sickleaves/<int:user_id>", methods=["GET"])
@login_required
def api_sickleaves_list(user_id: int):
    u = User.query.get_or_404(user_id)
    try:
        ls = u.sick_leaves.order_by(SickLeave.start_date.desc()).all()
    except OperationalError:
        return jsonify({"active": [], "history": []})

    today = _today()
    changed = False

    def ser(s: SickLeave):
        # attachments: works for dynamic and list-like
        try:
            rel = s.attachments
            if hasattr(rel, "order_by"):
                atts = rel.order_by(Attachment.uploaded_at.desc()).all()
            else:
                atts = sorted(rel or [], key=lambda a: a.uploaded_at or datetime.min, reverse=True)
        except Exception:
            atts = []

        return {
            "id": s.id,
            "start_date": _fmt(s.start_date),
            "end_date": _fmt(s.end_date),
            "kind": s.kind,
            "business_days": s.business_days,
            "status": s.status,
            "comments": s.comments or "",
            "holidays": [h for h in (s.holidays_csv.split(",") if s.holidays_csv else []) if h],
            "attachments": [
                {"id": a.id, "filename": a.filename, "stored_name": a.stored_name}
                for a in atts
            ],
        }

    # auto-expire to history when past end_date
    for s in ls:
        if s.status == "active" and s.end_date < today:
            s.status = "history"
            changed = True

    if changed:
        try:
            db.session.commit()
        except OperationalError:
            db.session.rollback()

    active = [ser(s) for s in ls if s.status == "active"]
    history = [ser(s) for s in ls if s.status != "active"]
    return jsonify({"active": active, "history": history})





# =========================
# Sick Leaves: CREATE
# =========================
@bp.route("/api/sickleaves/<int:user_id>/create", methods=["POST"])
@login_required
def api_sickleaves_create(user_id: int):
    User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}

    start_s  = (data.get("start_date") or "").strip()
    end_s    = (data.get("end_date") or "").strip()
    kind     = (data.get("kind") or "").strip()
    comments = (data.get("comments") or "").strip()
    holidays = data.get("holidays") or []

    errors = {}

    try:
        start = _parse_yyyy_mm_dd(start_s)
    except Exception:
        start = None
        errors["start_date"] = "Invalid date."

    try:
        end = _parse_yyyy_mm_dd(end_s)
    except Exception:
        end = None
        errors["end_date"] = "Invalid date."

    if start and end and end < start:
        errors["end_date"] = "End date must be ≥ start date."

    if not kind:
        errors["kind"] = "Required."

    if errors:
        return jsonify({"errors": errors}), 400

    # Normalize holidays -> set of dates
    hol = set()
    for hs in holidays:
        try:
            hol.add(_parse_yyyy_mm_dd(hs))
        except Exception:
            pass

    business_days = _business_days_between(start, end, hol)

    try:
        s = SickLeave(
            user_id=user_id,
            start_date=start,
            end_date=end,
            kind=kind,
            comments=comments or None,
            holidays_csv=",".join(sorted(h.strftime("%Y-%m-%d") for h in hol)) if hol else None,
            business_days=business_days,
            # >>> change: if end_date is today, this should already be history
            status="active" if (end and end > _today()) else "history",
        )
        db.session.add(s)
        db.session.commit()
    except OperationalError:
        db.session.rollback()
        return jsonify({"error": "sick_leaves table missing; run migrations"}), 503

    return jsonify({
        "ok": True,
        "sick_leave": {
            "id": s.id,
            "start_date": _fmt(s.start_date),  # YYYY-MM-DD
            "end_date": _fmt(s.end_date),      # YYYY-MM-DD
            "kind": s.kind,
            "business_days": s.business_days,
            "status": s.status,                # 'active' or 'history'
            "comments": s.comments or "",
            "holidays": [h for h in (s.holidays_csv.split(",") if s.holidays_csv else []) if h],
        }
    })


# =========================
# Reports (Извештај)
# =========================

def _countdown_from(last, months_every: int):
    """Return (next_due_fmt, months_left, days_left) from today to due date."""
    if not last:
        return None, None, None
    from dateutil.relativedelta import relativedelta  # ensure available
    due = last + relativedelta(months=+months_every)
    now = _today()
    if due <= now:
        return _fmt(due), 0, 0
    rd = relativedelta(due, now)
    months_left = rd.years * 12 + rd.months
    days_left = rd.days
    return _fmt(due), months_left, days_left



# GET -------------------------------------------------------------------------
# Reports API (GET) – robust attachments in histories
@bp.route("/api/reports/<int:user_id>", methods=["GET"])
@login_required
def api_reports_get(user_id: int):
    u = User.query.get_or_404(user_id)
    try:
        r = u.report  # one-to-one
        sanitary_last = r.sanitary_last if r else None
        system_last   = r.system_last if r else None
    except OperationalError:
        # DB not ready yet
        sanitary_last = None
        system_last = None

    sanitary_due, sanitary_m, sanitary_d = _countdown_from(sanitary_last, 6)
    system_due, system_m, system_d = _countdown_from(system_last, 24)

    # Attachments: ownerless, tagged by stored_name prefix
    try:
        sanitary_hist = _report_files_for(u, "sanitary")
        system_hist   = _report_files_for(u, "system")
    except OperationalError:
        sanitary_hist = []
        system_hist = []

    return jsonify({
        "sanitary": {
            "last": _fmt(sanitary_last),
            "next_due": sanitary_due,
            "left_months": sanitary_m,
            "left_days": sanitary_d
        },
        "system": {
            "last": _fmt(system_last),
            "next_due": system_due,
            "left_months": system_m,
            "left_days": system_d
        },
        "sanitary_history": sanitary_hist,
        "system_history": system_hist,
    })



# SET / UPSERT ----------------------------------------------------------------
@bp.route("/api/reports/<int:user_id>/set", methods=["POST"])
@login_required
def api_reports_set(user_id: int):
    u = User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}

    sanitary_last_s = data.get("sanitary_last", None)
    system_last_s   = data.get("system_last", None)

    # Parse only provided fields
    errors = {}
    sanitary_last = None
    system_last   = None

    if sanitary_last_s is not None and sanitary_last_s != "":
        try:
            sanitary_last = _parse_yyyy_mm_dd(sanitary_last_s.strip())
        except Exception:
            errors["sanitary_last"] = "Invalid date."

    if system_last_s is not None and system_last_s != "":
        try:
            system_last = _parse_yyyy_mm_dd(system_last_s.strip())
        except Exception:
            errors["system_last"] = "Invalid date."

    if errors:
        return jsonify({"errors": errors}), 400

    # Ensure row exists
    try:
        if not u.report:
            u.report = Report(user_id=u.id)
        # Update only the fields explicitly present in JSON
        if sanitary_last_s is not None:
            u.report.sanitary_last = sanitary_last
        if system_last_s is not None:
            u.report.system_last = system_last

        db.session.add(u.report)
        db.session.commit()
    except OperationalError:
        db.session.rollback()
        return jsonify({"error": "reports table missing; run migrations"}), 503

    # Return the canonical GET payload (also includes histories)
    return api_reports_get(user_id)


# =========================
# Uniforms (Униформи)
# =========================

@bp.route("/api/uniforms/<int:user_id>", methods=["GET"])
@login_required
def api_uniforms_list(user_id: int):
    u = User.query.get_or_404(user_id)
    try:
        rows = u.uniforms.order_by(Uniform.assigned_date.desc()).all()
    except OperationalError:
        return jsonify({"active": [], "history": []})

    today = _today()

    def ser(un: Uniform):
        # attachments: works for dynamic and list-like
        try:
            rel = un.attachments
            if hasattr(rel, "order_by"):  # lazy="dynamic"
                atts = rel.order_by(Attachment.uploaded_at.desc()).all()
            else:
                atts = sorted(rel or [], key=lambda a: a.uploaded_at or datetime.min, reverse=True)
        except Exception:
            atts = []

        return {
            "id": un.id,
            "kind": un.kind,
            "assigned_date": _fmt(un.assigned_date),
            "renew_every_months": un.renew_every_months,
            "next_due_date": _fmt(un.next_due_date),
            "attachments": [
                {"id": a.id, "filename": a.filename, "stored_name": a.stored_name}
                for a in atts
            ],
        }

    active = []
    history = []
    for un in rows:
        (active if (un.next_due_date and un.next_due_date >= today) else history).append(ser(un))

    return jsonify({"active": active, "history": history})




@bp.route("/api/uniforms/<int:user_id>/create", methods=["POST"])
@login_required
def api_uniforms_create(user_id: int):
    User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}
    kind = (data.get("kind") or "").strip()
    assigned_s = (data.get("assigned_date") or "").strip()
    renew_m = _safe_int(data.get("renew_every_months"), 0)

    errors = {}
    if not kind:
        errors["kind"] = "Required."
    try:
        assigned = _parse_yyyy_mm_dd(assigned_s)
    except Exception:
        errors["assigned_date"] = "Invalid date."
        assigned = None
    if renew_m <= 0:
        errors["renew_every_months"] = "Must be positive."

    if errors:
        return jsonify({"errors": errors}), 400

    next_due = _calc_end_months(assigned, renew_m)

    try:
        un = Uniform(user_id=user_id, kind=kind, assigned_date=assigned,
                     renew_every_months=renew_m, next_due_date=next_due)
        db.session.add(un)
        db.session.commit()
    except OperationalError:
        db.session.rollback()
        return jsonify({"error": "uniforms table missing; run migrations"}), 503

    return jsonify({"ok": True, "item": {
        "id": un.id,
        "kind": un.kind,
        "assigned_date": _fmt(un.assigned_date),
        "renew_every_months": un.renew_every_months,
        "next_due_date": _fmt(un.next_due_date),
    }})


# =========================
# Trainings (Обука)
# =========================

@bp.route("/api/trainings/<int:user_id>", methods=["GET"])
@login_required
def api_trainings_list(user_id: int):
    u = User.query.get_or_404(user_id)
    try:
        ts = u.trainings.order_by(Training.start_date.desc()).all()
    except OperationalError:
        return jsonify({"active": [], "history": []})

    today = _today()
    changed = False

    # robust attachments serializer for dynamic / list relationships
    def ser(t: Training):
        try:
            rel = t.attachments
            if hasattr(rel, "order_by"):  # lazy="dynamic"
                atts = rel.order_by(Attachment.uploaded_at.desc()).all()
            else:  # list-like
                atts = sorted(rel or [], key=lambda a: a.uploaded_at or datetime.min, reverse=True)
        except Exception:
            atts = []

        return {
            "id": t.id,
            "title": t.title,
            "start_date": _fmt(t.start_date),
            "end_date": _fmt(t.end_date),
            "status": t.status,
            "attachments": [
                {"id": a.id, "filename": a.filename, "stored_name": a.stored_name}
                for a in atts
            ],
        }

    # auto-expire to history when past end_date
    for t in ts:
        if t.status == "active" and t.end_date < today:
            t.status = "history"
            changed = True

    if changed:
        try:
            db.session.commit()
        except OperationalError:
            db.session.rollback()

    active = [ser(t) for t in ts if t.status == "active"]
    history = [ser(t) for t in ts if t.status != "active"]
    return jsonify({"active": active, "history": history})




@bp.route("/api/trainings/<int:user_id>/create", methods=["POST"])
@login_required
def api_trainings_create(user_id: int):
    User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}
    title   = (data.get("title") or "").strip()
    start_s = (data.get("start_date") or "").strip()
    end_s   = (data.get("end_date") or "").strip()

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

    try:
        tr = Training(
            user_id=user_id, title=title, start_date=start, end_date=end,
            status="active" if (end and end >= _today()) else "history"
        )
        db.session.add(tr)
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


@bp.route("/api/trainings/<int:user_id>/<int:training_id>/update", methods=["POST"])
@login_required
def api_trainings_update(user_id: int, training_id: int):
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


@bp.route("/api/trainings/<int:user_id>/<int:training_id>/delete", methods=["POST"])
@login_required
def api_trainings_delete(user_id: int, training_id: int):
    try:
        tr = Training.query.filter_by(id=training_id, user_id=user_id).first_or_404()
        db.session.delete(tr)
        db.session.commit()
    except OperationalError:
        db.session.rollback()
        return jsonify({"error": "trainings table missing; run migrations"}), 503
    return jsonify({"ok": True})

# =========================
# Rewards & Penalties (Казни и Награди)
# =========================
@bp.route("/api/rewards/<int:user_id>", methods=["GET"])
@login_required
def api_rewards_list(user_id: int):
    u = User.query.get_or_404(user_id)

    # Fetch entries (be defensive about schema differences)
    rows = (
        RewardPenalty.query
        .filter_by(user_id=u.id)
        .order_by(RewardPenalty.date.desc(), RewardPenalty.id.desc())
        .all()
    )

    # Helper: serialize attachments regardless of relationship availability
    def serialize_attachments(rp_id: int):
        try:
            # If relationship exists and is configured with selectin/lazy, use it
            rp = next((r for r in rows if r.id == rp_id), None)
            if rp is not None and hasattr(rp, "attachments") and rp.attachments is not None:
                # rp.attachments may be list-like or query-like
                items = rp.attachments if isinstance(rp.attachments, list) else rp.attachments.all()
            else:
                raise AttributeError
        except Exception:
            # Fallback: direct query
            items = (
                Attachment.query
                .filter_by(reward_penalty_id=rp_id)
                .order_by(Attachment.uploaded_at.desc())
                .all()
            )
        return [
            {
                "id": a.id,
                "filename": a.filename,
                "stored_name": a.stored_name,
                "content_type": a.content_type,
                "uploaded_at": a.uploaded_at.isoformat() if getattr(a, "uploaded_at", None) else None,
            }
            for a in items
        ]

    def serialize_row(rp):
        # Be resilient if the 'type' column is missing during migration
        rp_type = getattr(rp, "type", None)
        if not rp_type:
            # Fallback: treat as reward to avoid 500s; your UI will still render
            rp_type = "reward"

        # Normalize to 'reward' | 'penalty'
        t = str(rp_type).strip().lower()
        if t not in ("reward", "penalty"):
            t = "reward"

        date_iso = None
        d = getattr(rp, "date", None)
        try:
            date_iso = d.isoformat() if d else None
        except Exception:
            date_iso = None

        return {
            "id": rp.id,
            "type": t,
            "date": date_iso,
            "note": getattr(rp, "note", "") or "",
            "attachments": serialize_attachments(rp.id),
        }

    rewards, penalties = [], []
    for rp in rows:
        item = serialize_row(rp)
        (penalties if item["type"] == "penalty" else rewards).append(item)

    return jsonify({"rewards": rewards, "penalties": penalties})


# app/users/routes.py (excerpt)
@bp.route("/api/rewards/<int:user_id>/create", methods=["POST"])
@login_required
def api_rewards_create(user_id: int):
    """
    JSON body:
      { "type": "reward" | "penalty", "date": "YYYY-MM-DD", "note": "..." }
    Returns 200 { ok: true, item: {...} } or 400 { errors: {...} }.
    Never 500 on bad input.
    """
    user = User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}

    rtype = (data.get("type") or "").strip().lower()
    rdate = _parse_iso_date(data.get("date"))
    note  = (data.get("note") or "").strip()

    errors = {}
    if rtype not in {"reward", "penalty"}:
        errors["type"] = "Must be 'reward' or 'penalty'."
    if not rdate:
        errors["date"] = "Invalid or missing date (YYYY-MM-DD)."

    # QUICK SCHEMA HEALTH CHECKS (avoid AttributeError → 500)
    # If you recently added 'type' to RewardPenalty, but haven't migrated yet,
    # accessing rp.type would crash. Check column exists before proceeding.
    if not hasattr(RewardPenalty, "type"):
        log.exception("RewardPenalty.type column missing. Run your migrations.")
        return jsonify({"errors": {
            "_": "Server not migrated. Please run database migrations (missing column 'type' on reward_penalties)."
        }}), 400

    if errors:
        return jsonify({"errors": errors}), 400

    try:
        rp = RewardPenalty(user_id=user.id, type=rtype, date=rdate, note=note or None)
        db.session.add(rp)
        db.session.commit()
    except Exception as ex:
        db.session.rollback()
        log.exception("Failed to create reward/penalty for user_id=%s", user.id)
        # Return 400 with a short reason so UI shows a nice message
        return jsonify({"errors": {"_": f"Failed to create: {type(ex).__name__}"}}), 400

    return jsonify({
        "ok": True,
        "item": {
            "id": rp.id,
            "type": rp.type,
            "date": rp.date.isoformat() if rp.date else None,
            "note": rp.note or "",
            "attachments": [],
        }
    })


@bp.route("/api/rewards/<int:user_id>/<int:rp_id>/delete", methods=["POST"])
@login_required
def api_rewards_delete(user_id: int, rp_id: int):
    """Delete a reward/penalty item (and cascade its attachments if configured)."""
    try:
        rp = RewardPenalty.query.filter_by(id=rp_id, user_id=user_id).first_or_404()
        db.session.delete(rp)
        db.session.commit()
    except OperationalError:
        db.session.rollback()
        return jsonify({"error": "reward_penalties table missing; run migrations"}), 503
    return jsonify({"ok": True})