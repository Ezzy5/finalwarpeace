# app/email/permissions.py
"""
Permission helpers for the Email feature.

Usage:
- @require_email_manage
- @require_admin_or_email_manage
- can_manage_email(user)
"""
from functools import wraps
from flask import abort
from flask_login import current_user


# --- Core checks -------------------------------------------------------------

def _has_attr_permission(user, perm: str) -> bool:
    """
    Try common patterns for permission/role checks without coupling to your app.
    - user.has_permission("perm")
    - user.has_perm("perm")
    - "perm" in user.permissions (set/list)
    - user.role in {...}
    """
    if not user:
        return False

    # Method patterns
    if hasattr(user, "has_permission") and callable(user.has_permission):
        try:
            if user.has_permission(perm):
                return True
        except Exception:
            pass

    if hasattr(user, "has_perm") and callable(user.has_perm):
        try:
            if user.has_perm(perm):
                return True
        except Exception:
            pass

    # Collection patterns
    if hasattr(user, "permissions"):
        try:
            if perm in getattr(user, "permissions"):
                return True
        except Exception:
            pass

    return False


def _is_admin_like(user) -> bool:
    """
    Consider common admin roles. Adjust as needed to match your app.
    """
    role = getattr(user, "role", None)
    if not role:
        return False
    role_val = str(role).lower()
    return role_val in {"admin", "superadmin", "super_user", "superuser", "owner"}


# --- Public API --------------------------------------------------------------

def can_manage_email(user) -> bool:
    """
    Returns True if the user can manage email connections (self or org-wide).
    """
    return _is_admin_like(user) or _has_attr_permission(user, "email.manage")


def require_email_manage(fn):
    """
    Decorator: require 'email.manage' capability (or admin-like).
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not can_manage_email(current_user):
            return abort(403)
        return fn(*args, **kwargs)
    return wrapper


def require_admin_or_email_manage(fn):
    """
    Alias for require_email_manage (kept for clarity/semantics).
    """
    return require_email_manage(fn)
