# app/permissions.py
from __future__ import annotations
from functools import wraps
from typing import Iterable, Set

from flask import abort
from flask_login import current_user
from sqlalchemy import text

from app.extensions import db

# -------------------------------------------------------------------
# Canonical permission codes (use these everywhere for consistency)
# -------------------------------------------------------------------
USERS_VIEW        = "users.view"
USERS_GENERAL     = "users.general"
USERS_CREATE_EDIT = "users.create_edit"     # ← underscore, not slash
USERS_AGREEMENT   = "users.agreement"
USERS_REPORTS     = "users.reports"
USERS_VACATION    = "users.vacation"
USERS_SICK        = "users.sick"
USERS_UNIFORMS    = "users.uniforms"
USERS_REWARDS     = "users.rewards"
USERS_TRAINING    = "users.training"
USERS_PENALTY     = "users.penalty"
USERS_ATTACHMENTS = "users.attachments"

WAR_VIEW          = "war.view"
WAR_EDIT          = "war.edit"
WAR_EXPORT        = "war.export"
WAR_MANAGE        = "war.manage"

# Human names for UI (keep keys exactly matching codes above)
PERMISSION_CATALOG = {
    # USERS
    USERS_VIEW:        "Users: view list",
    USERS_GENERAL:     "Users: general tab",
    USERS_CREATE_EDIT: "Users: create & edit",
    USERS_AGREEMENT:   "Users: agreements",
    USERS_VACATION:    "Users: vacation",
    USERS_SICK:   "Users: sick",
    USERS_REPORTS:     "Users: reports",
    USERS_UNIFORMS:    "Users: uniforms",
    USERS_TRAINING:    "Users: training",
    USERS_REWARDS:     "Users: rewards",
    USERS_PENALTY:     "Users: penalties",
    USERS_ATTACHMENTS: "Users: attachments",

    # WAR
    WAR_VIEW:          "War: view",
    WAR_EDIT:          "War: edit",
    WAR_EXPORT:        "War: export",
    WAR_MANAGE:        "War: manage",
}


# app/permissions.py

# --- add these near the top (with any other permission constants) ---
# Tickets module permission codes (strings are what get stored/checked)
TICKETS_VIEW        = "tickets.view"
TICKETS_CREATE      = "tickets.create"
TICKETS_EDIT        = "tickets.edit"
TICKETS_DELETE      = "tickets.delete"
TICKETS_ASSIGN      = "tickets.assign"     # assign/unassign users
TICKETS_COMMENT     = "tickets.comment"    # add comments
TICKETS_UPLOAD      = "tickets.upload"     # upload attachments
TICKETS_ADMIN       = "tickets.admin"      # optional: manage settings

# Optional: a canonical list/set you can reuse elsewhere
TICKETS_PERMISSIONS = {
    TICKETS_VIEW,
    TICKETS_CREATE,
    TICKETS_EDIT,
    TICKETS_DELETE,
    TICKETS_ASSIGN,
    TICKETS_COMMENT,
    TICKETS_UPLOAD,
    TICKETS_ADMIN,
}

# If you already have __all__ defined, append to it; otherwise define it.
try:
    __all__  # type: ignore
except NameError:
    __all__ = []

__all__ += [
    "TICKETS_VIEW", "TICKETS_CREATE", "TICKETS_EDIT", "TICKETS_DELETE",
    "TICKETS_ASSIGN", "TICKETS_COMMENT", "TICKETS_UPLOAD", "TICKETS_ADMIN",
    "TICKETS_PERMISSIONS",
]

# -------------------------------------------------------------------
# Admin detection
# -------------------------------------------------------------------
def is_admin_like(user) -> bool:
    role = getattr(user, "role", None)
    name = (getattr(role, "name", "") or "").strip().lower()
    return name == "admin"

# -------------------------------------------------------------------
# Role → permissions (M2M) helpers
# -------------------------------------------------------------------
def _role_codes_for(user) -> Set[str]:
    """Collect codes from role.permissions M2M if present."""
    try:
        role = getattr(user, "role", None)
        perms = getattr(role, "permissions", None) or []
        return {p.code for p in perms if getattr(p, "code", None)}
    except Exception:
        return set()

# -------------------------------------------------------------------
# Department → permissions (department_permissions table) helpers
# -------------------------------------------------------------------
def _department_codes_for(user) -> Set[str]:
    """Read department toggles from raw table (allowed=1)."""
    try:
        dep_id = getattr(user, "department_id", None)
        if not dep_id:
            return set()
        rows = db.session.execute(
            text("SELECT code FROM department_permissions WHERE department_id = :d AND allowed = 1"),
            {"d": dep_id},
        ).fetchall()
        out = set()
        for r in rows:
            try:
                out.add(r["code"])
            except Exception:
                out.add(r[0])
        return out
    except Exception:
        return set()

# -------------------------------------------------------------------
# Effective / final codes for a user
# -------------------------------------------------------------------
def effective_codes(user) -> Set[str]:
    """
    Admin → all known codes from the catalog.
    Others → union of role-based codes and department toggles.
    """
    if not user:
        return set()
    if is_admin_like(user):
        # Use keys directly from local CATALOG defined above.
        return set(PERMISSION_CATALOG.keys())
    return _role_codes_for(user) | _department_codes_for(user)

# -------------------------------------------------------------------
# Point-in-time boolean check
# -------------------------------------------------------------------
def has_permission(user, code: str) -> bool:
    if not user:
        return False
    if is_admin_like(user):
        return True
    try:
        return code in effective_codes(user)
    except Exception:
        return False

# -------------------------------------------------------------------
# Route decorators
# -------------------------------------------------------------------
def require_permission(code: str):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **k):
            if has_permission(current_user, code):
                return fn(*a, **k)
            abort(403)
        return wrapper
    return deco

def require_any(*codes: Iterable[str]):
    codes = tuple(codes)
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **k):
            if is_admin_like(current_user):
                return fn(*a, **k)
            for c in codes:
                if has_permission(current_user, c):
                    return fn(*a, **k)
            abort(403)
        return wrapper
    return deco


def require_any_permission(*perms):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **k):
            if any(has_permission(current_user, p) for p in perms):
                return fn(*a, **k)
            return jsonify({"error": "Forbidden"}), 403
        return wrapper
    return deco