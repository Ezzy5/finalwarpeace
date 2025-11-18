from flask_login import login_required
from flask import jsonify, request
from app.models import User
from .. import bp

@bp.get("/api/list")
@login_required
def api_users_list():
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))

    q = User.query.order_by(User.id.asc())
    total = q.count()
    rows = q.offset((page - 1) * per_page).limit(per_page).all()

    def serialize(u):
        return {
            "id": u.id,
            "first_name": getattr(u, "first_name", ""),
            "last_name": getattr(u, "last_name", ""),
            "email": getattr(u, "email", ""),
            "phone_number": getattr(u, "phone_number", ""),
            "id_number": getattr(u, "id_number", ""),
            "embg": getattr(u, "embg", ""),
            "vacation_days": getattr(u, "vacation_days", 0),
            "department": getattr(u, "department", ""),
            "director_of": getattr(u, "director_of", ""),
            "is_suspended": bool(getattr(u, "is_suspended", False)),
        }

    items = [serialize(u) for u in rows]
    total_pages = (total + per_page - 1) // per_page if per_page else 1

    return jsonify({
        "items": items, "page": page, "per_page": per_page,
        "total": total, "total_pages": total_pages
    }), 200
