# app/decorators.py
from functools import wraps
from flask import request, redirect, url_for, flash, jsonify

# ---- helpers ---------------------------------------------------------------

def _wants_json():
    """Treat front-end fetches as JSON requests (avoid redirects during XHR)."""
    return (
        request.is_json
        or request.headers.get("X-Requested-With") == "fetch"
        or (request.accept_mimetypes and request.accept_mimetypes.best == "application/json")
    )

def _safe_redirect_fallback(default_path: str = "/"):
    """Try common endpoints; if none exist, fall back to a literal path."""
    from flask import redirect, url_for
    candidates = ("dashboard.index", "main.dashboard", "main.index", "auth.login", "index")
    for ep in candidates:
        try:
            return redirect(url_for(ep))
        except Exception:
            continue
    return redirect(default_path)

def _str_or_empty(x):
    """Best-effort to get a lowercase string value from x."""
    if isinstance(x, str):
        return x.strip().lower()
    # Role-like object with .name
    name = getattr(x, "name", None)
    if isinstance(name, str):
        return name.strip().lower()
    # Don’t attempt to stringify arbitrary objects (avoid noisy reprs)
    return ""

def _iter_roles(user):
    """
    Yield possible role names from user in a safe, normalized way:
    - user.role  (string or Role object)
    - user.roles (iterable of strings or Role objects)
    """
    # single role
    if hasattr(user, "role"):
        yield _str_or_empty(getattr(user, "role"))
    # multiple roles
    roles = getattr(user, "roles", None)
    if roles:
        try:
            for r in roles:
                yield _str_or_empty(r)
        except TypeError:
            # roles isn’t iterable; ignore
            pass

def _is_admin(user) -> bool:
    """Flexible admin detection to match your app’s schema."""
    if not user:
        return False

    # 1) Boolean flag
    if bool(getattr(user, "is_admin", False)):
        return True

    # 2) Check string/Role in user.role and items in user.roles
    admin_names = {"admin", "administrator", "superadmin", "super_admin"}
    for role_name in _iter_roles(user):
        if role_name in admin_names:
            return True

    # 3) Permission/role API if present
    for meth in ("has_permission", "has_role"):
        fn = getattr(user, meth, None)
        if callable(fn):
            try:
                if fn("admin"):
                    return True
            except Exception:
                pass

    return False

# ---- main decorator --------------------------------------------------------

def admin_only(view_func):
    """
    Require logged-in admin.
    - JSON/fetch -> JSON 401/403
    - Page -> safe redirect (no BuildError)
    """
    from flask_login import current_user

    @wraps(view_func)
    def wrapper(*args, **kwargs):
        # Not logged in
        if not getattr(current_user, "is_authenticated", False):
            if _wants_json():
                return jsonify({"error": "login_required"}), 401
            try:
                return redirect(url_for("auth.login", next=request.full_path or request.path))
            except Exception:
                return _safe_redirect_fallback("/login")

        # Logged in but not admin
        if not _is_admin(current_user):
            if _wants_json():
                return jsonify({"error": "forbidden", "detail": "Admin only"}), 403
            flash("You do not have permission to access this page.", "danger")
            return _safe_redirect_fallback("/")

        return view_func(*args, **kwargs)

    return wrapper
