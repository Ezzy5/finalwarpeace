from flask_login import login_required
from flask import jsonify, request
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models import User
from app.permissions import require_permission, USERS_CREATE_EDIT
from .. import bp
from .helpers import _digits_only, _safe_int, _assign_role_from_is_admin, _user_to_dict

@bp.route("/api/update/<int:user_id>", methods=["POST"])
@login_required
@require_permission(USERS_CREATE_EDIT)
def api_update(user_id: int):
    u = User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}

    first_name     = (data.get("first_name") or "").strip()
    last_name      = (data.get("last_name") or "").strip()
    email          = (data.get("email") or "").strip().lower()
    phone_number   = _digits_only(data.get("phone_number")) or None
    id_number      = (data.get("id_number") or "").strip()
    embg           = _digits_only(data.get("embg")) or None
    vacation_days  = _safe_int(data.get("vacation_days"), u.vacation_days or 0)
    bank_account   = _digits_only(data.get("bank_account")) or None
    city           = (data.get("city") or "").strip() or None
    address        = (data.get("address") or "").strip() or None

    new_password   = (data.get("new_password") or "")
    new_password2  = (data.get("new_password2") or "")

    is_admin       = bool(data.get("is_admin"))

    errors = {}
    if not first_name: errors["first_name"] = "Required."
    if not last_name: errors["last_name"] = "Required."
    if not email: errors["email"] = "Required."
    elif "@" not in email: errors["email"] = "Invalid email."
    if not id_number: errors["id_number"] = "Required."
    if vacation_days < 0: errors["vacation_days"] = "Must be ≥ 0."

    from app.models import User as U
    if email and db.session.query(U.id).filter(U.id != u.id, func.lower(U.email) == email).first():
        errors["email"] = "Email already exists."
    if id_number and db.session.query(U.id).filter(U.id != u.id, U.id_number == id_number).first():
        errors["id_number"] = "ID number already exists."
    if embg and db.session.query(U.id).filter(U.id != u.id, U.embg == embg).first():
        errors["embg"] = "EMBG already exists."

    if new_password or new_password2:
        if not new_password: errors["new_password"] = "Required."
        elif len(new_password) < 8: errors["new_password"] = "Min 8 characters."
        if new_password != new_password2: errors["new_password2"] = "Passwords do not match."

    if errors: return jsonify({"errors": errors}), 400

    u.first_name, u.last_name, u.email = first_name, last_name, email
    u.phone_number, u.id_number, u.embg = phone_number, id_number, embg
    u.vacation_days = vacation_days
    u.bank_account, u.city, u.address = bank_account, city, address

    _assign_role_from_is_admin(u, is_admin)
    if new_password:
        u.set_password(new_password)

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify({"errors": {"__global": f"Update failed: {e.__class__.__name__}"}}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"errors": {"__global": f"Update failed: {e}"}}), 400

    return jsonify({"ok": True, "item": _user_to_dict(u)})
