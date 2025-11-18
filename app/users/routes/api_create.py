from flask_login import login_required
from flask import jsonify, request
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models import User, Role, Department
from .. import bp
from .helpers import _digits_only, _safe_int, _vacation_days_left

@bp.route("/api/create", methods=["POST"])
@login_required
def api_create():
    data = request.get_json(silent=True) or {}

    first_name     = (data.get("first_name") or "").strip()
    last_name      = (data.get("last_name") or "").strip()
    email          = (data.get("email") or "").strip().lower()
    phone_number   = _digits_only(data.get("phone_number")) or None
    id_number      = (data.get("id_number") or "").strip()
    embg           = _digits_only(data.get("embg")) or None
    vacation_days  = _safe_int(data.get("vacation_days"), 0)
    role_id        = data.get("role_id")

    bank_account   = _digits_only(data.get("bank_account")) or None
    city           = (data.get("city") or "").strip() or None
    address        = (data.get("address") or "").strip() or None

    password       = data.get("password") or ""
    password2      = data.get("password2") or ""

    errors = {}
    if not first_name: errors["first_name"] = "Required."
    if not last_name: errors["last_name"] = "Required."
    if not email: errors["email"] = "Required."
    elif "@" not in email: errors["email"] = "Invalid email."
    if not id_number: errors["id_number"] = "Required."
    if vacation_days < 0: errors["vacation_days"] = "Must be ≥ 0."

    if email and db.session.query(User.id).filter(func.lower(User.email) == email).first():
        errors["email"] = "Email already exists."
    if id_number and db.session.query(User.id).filter(User.id_number == id_number).first():
        errors["id_number"] = "ID number already exists."
    if embg and db.session.query(User.id).filter(User.embg == embg).first():
        errors["embg"] = "EMBG already exists."

    role = None
    if role_id not in (None, "", "null"):
        try: role = db.session.get(Role, int(role_id))
        except Exception: role = None
        if not role: errors["role_id"] = "Role not found."

    if not password: errors["password"] = "Required."
    elif len(password) < 8: errors["password"] = "Min 8 characters."
    if password != password2: errors["password2"] = "Passwords do not match."

    if errors: return jsonify({"errors": errors}), 400

    u = User(
        first_name=first_name, last_name=last_name, email=email,
        phone_number=phone_number, id_number=id_number, embg=embg,
        role=role, department=None, vacation_days=vacation_days,
        is_active=True, is_suspended=False,
        bank_account=bank_account, city=city, address=address,
    )
    u.set_password(password)

    db.session.add(u)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"errors": {"email": "Email already exists."}}), 400

    managed = Department.query.filter_by(manager_id=u.id).first()
    return jsonify({
        "ok": True,
        "item": {
            "id": u.id, "first_name": u.first_name, "last_name": u.last_name,
            "department": (u.dept.name if getattr(u, "dept", None) else None),
            "email": u.email, "phone_number": u.phone_number, "id_number": u.id_number,
            "embg": u.embg, "vacation_days": int(u.vacation_days or 0),
            "vacation_days_left": _vacation_days_left(u),
            "role": (u.role.name if u.role else None),
            "director_of": (managed.name if managed else None),
            "is_suspended": bool(getattr(u, "is_suspended", False)),
            "bank_account": u.bank_account or "", "city": u.city or "", "address": u.address or "",
        }
    }), 201
