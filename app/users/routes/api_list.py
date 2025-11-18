# app/users/routes/api_list.py
from flask import jsonify, request
from flask_login import login_required
from sqlalchemy import select, or_

from .. import bp
from ...extensions import db
from ...models import User, Department
from .helpers import vacation_days_left  # <-- import helper


@bp.route("/api/list", methods=["GET"])
@login_required
def api_list():
    """
    Users API list

    Used by:
      - Users table (pagination)
      - Feed permissions picker (with ?search=)

    Query params:
      - page: int (default 1)
      - per_page: int (default 50, max 200)
      - search: optional text to filter by name / email
    """
    page = max(int(request.args.get("page", 1) or 1), 1)
    per_page = min(max(int(request.args.get("per_page", 50) or 50), 1), 200)
    search = (request.args.get("search") or "").strip()

    q = User.query

    # Optional: only active users if you have such a column
    if hasattr(User, "is_active"):
        q = q.filter(User.is_active.is_(True))

    # NEW: search filter (for feed picker)
    if search:
        # 🔑 "starts with" instead of "contains":
        #   - 'M'  -> matches "Martin", "Mila", "Marko", but not "Aleksandar"
        like = f"{search}%"
        conditions = []
        if hasattr(User, "first_name"):
            conditions.append(User.first_name.ilike(like))  # type: ignore[attr-defined]
        if hasattr(User, "last_name"):
            conditions.append(User.last_name.ilike(like))   # type: ignore[attr-defined]
        if hasattr(User, "email"):
            conditions.append(User.email.ilike(like))       # type: ignore[attr-defined]

        if conditions:
            q = q.filter(or_(*conditions))

    # You can switch this ordering if you prefer name sorting:
    # q = q.order_by(User.first_name.asc(), User.last_name.asc())
    q = q.order_by(User.id.asc())

    pagination = q.paginate(page=page, per_page=per_page, error_out=False)
    users = pagination.items

    # director map
    user_ids = [u.id for u in users]
    director_map = {}
    if user_ids:
        rows = db.session.execute(
            select(Department.manager_id, Department.name).where(
                Department.manager_id.in_(user_ids)
            )
        ).all()
        for mid, dname in rows:
            if mid and dname and mid not in director_map:
                director_map[mid] = dname

    def row(u: User):
        dept_name = getattr(getattr(u, "dept", None), "name", None)
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
            "vacation_days_left": vacation_days_left(u),
            "role": (getattr(getattr(u, "role", None), "name", None)),
            "director_of": director_map.get(u.id),
            "bank_account": u.bank_account or "",
            "city": u.city or "",
            "address": u.address or "",
            "is_suspended": bool(getattr(u, "is_suspended", False)),
        }

    return jsonify(
        {
            "items": [row(u) for u in users],
            "total": pagination.total,
            "page": pagination.page,
            "pages": pagination.pages,
            "per_page": pagination.per_page,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
        }
    )
