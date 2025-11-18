from flask import jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import asc
from app.extensions import db
from app.models import User, Department  # If your sector model is named differently, adjust import.
from . import bp 


PAGE_SIZE = 100  # sane upper bound

def _q():
    # optional search query
    return (request.args.get("q") or "").strip().lower()

def _page_size():
    try:
        p = int(request.args.get("limit", PAGE_SIZE))
        return max(1, min(p, PAGE_SIZE))
    except Exception:
        return PAGE_SIZE

def _cursor_arg():
    try:
        return int(request.args.get("after_id") or 0)
    except Exception:
        return 0

def _user_can_view_sector(sid: int) -> bool:
    role = getattr(current_user, "role", "user")
    if role == "admin":
        return True
    # Directors: only their own sector(s)
    user_sid = getattr(current_user, "sector_id", None)
    if role == "director":
        if user_sid and sid == int(user_sid):
            return True
        # also support many-to-many style sector_ids
        many = getattr(current_user, "sector_ids", []) or []
        for s in many:
            s_id = getattr(s, "id", s)
            if int(s_id) == int(sid):
                return True
        return False
    # Normal users: cannot browse sectors (but we still allow listing their sector for convenience)
    if user_sid and sid == int(user_sid):
        return True
    many = getattr(current_user, "sector_ids", []) or []
    return any(int(getattr(s, "id", s)) == int(sid) for s in many)

def _user_can_view_user(u: User) -> bool:
    role = getattr(current_user, "role", "user")
    if role == "admin":
        return True
    if role == "director":
        # same-sector visibility
        cs = getattr(u, "sector_id", None)
        return cs is not None and _user_can_view_sector(int(cs))
    # normal user: only self and same-sector users
    if u.id == current_user.id:
        return True
    cs = getattr(u, "sector_id", None)
    my = getattr(current_user, "sector_id", None)
    if cs is not None and my is not None and int(cs) == int(my):
        return True
    # also support sector_ids list on current_user
    many = getattr(current_user, "sector_ids", []) or []
    for s in many:
        if int(getattr(s, "id", s)) == int(cs or -1):
            return True
    return False

def _user_public(u: User):
    return {
        "id": u.id,
        "name": getattr(u, "full_name", None) or getattr(u, "username", f"user:{u.id}"),
        "avatar": getattr(u, "avatar_url", None),
        "sector_id": getattr(u, "sector_id", None),
        "role": getattr(u, "role", None),
    }

@login_required
@bp.get("/sectors")
def sectors():
    """
    GET /api/refs/sectors?q=term&after_id=123&limit=50
    Role rules:
      - admin: all sectors
      - director: only their own sector(s)
      - user: only their sector (if any)
    """
    q = Department.query.order_by(asc(Department.name))
    # simple pagination by id cursor
    after_id = _cursor_arg()
    if after_id:
        q = q.filter(Department.id > after_id)

    # role-based filter in Python to respect custom relationships
    items = []
    limit = _page_size()
    s = _q()
    for dep in q.limit(limit * 3):  # fetch extra to compensate filtering
        if not _user_can_view_sector(dep.id):
            continue
        if s and s not in (dep.name or "").lower():
            continue
        items.append({"id": dep.id, "name": dep.name})
        if len(items) >= limit:
            break

    next_after = items[-1]["id"] if items else None
    return jsonify({"ok": True, "items": items, "next_after_id": next_after})

@login_required
@bp.get("/users")
def users():
    """
    GET /api/refs/users?q=term&after_id=123&limit=50
    Role rules:
      - admin: all users
      - director: users in their sector(s)
      - user: self + users in same sector(s)
    """
    q = User.query.order_by(asc(User.id))
    after_id = _cursor_arg()
    if after_id:
        q = q.filter(User.id > after_id)

    s = _q()
    limit = _page_size()
    items = []
    for u in q.limit(limit * 4):  # fetch extra to compensate filtering + search
        if not _user_can_view_user(u):
            continue
        # basic search across username/full_name
        name = getattr(u, "full_name", None) or getattr(u, "username", "")
        if s and s not in (name or "").lower():
            continue
        items.append(_user_public(u))
        if len(items) >= limit:
            break

    next_after = items[-1]["id"] if items else None
    return jsonify({"ok": True, "items": items, "next_after_id": next_after})
