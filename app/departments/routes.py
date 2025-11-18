# app/departments/routes.py
from flask import jsonify, request, render_template
from flask_login import login_required
from sqlalchemy import (
    func, text, Table, Column, Integer, String, Boolean, MetaData, UniqueConstraint
)
from sqlalchemy.engine import reflection
from sqlalchemy.exc import OperationalError, ProgrammingError

from . import bp  # departments blueprint with url_prefix='/departments'
from ..extensions import db
from ..models import Department, User
from ..decorators import admin_only

# =====================================================================
#                             PANEL
# =====================================================================

@bp.route("/panel", methods=["GET"])
@login_required
@admin_only
def panel():
    if request.headers.get("X-Requested-With") == "fetch":
        return render_template("panel_dep.html")
    return render_template("dashboard.html", initial_panel="departments")


# =====================================================================
#                         CRUD: DEPARTMENTS
# =====================================================================

# List departments (paginated)
@bp.route("/api/list", methods=["GET"])
@login_required
@admin_only
def api_list_departments():
    page = max(int(request.args.get("page", 1) or 1), 1)
    page_size = min(max(int(request.args.get("page_size", 50) or 50), 1), 200)
    q = Department.query.order_by(Department.id.asc())
    pagination = q.paginate(page=page, per_page=page_size, error_out=False)

    def row(dep: Department):
        manager_name = None
        if dep.manager:
            fn = (dep.manager.first_name or "").strip()
            ln = (dep.manager.last_name or "").strip()
            manager_name = (f"{fn} {ln}".strip() or dep.manager.email)
        return {
            "id": dep.id,
            "name": dep.name,
            "manager_id": dep.manager_id,
            "manager_name": manager_name,
        }

    return jsonify({
        "items": [row(d) for d in pagination.items],
        "page": pagination.page,
        "pages": pagination.pages,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "has_prev": pagination.has_prev,
        "has_next": pagination.has_next,
    })


# Create department
@bp.route("/api/create", methods=["POST"])
@login_required
@admin_only
def api_create_department():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    manager_id = data.get("manager_id")

    errors = {}
    if not name:
        errors["name"] = "Required."
    else:
        exists = Department.query.filter(func.lower(Department.name) == name.lower()).first()
        if exists:
            errors["name"] = "Department with this name already exists."

    manager = None
    if manager_id:
        manager = User.query.get(int(manager_id))
        if not manager:
            errors["manager_id"] = "Director not found."
        elif manager.department_id is not None:
            errors["manager_id"] = "User already assigned to a department."

    if errors:
        return jsonify({"errors": errors}), 400

    dep = Department(name=name, manager=manager)
    db.session.add(dep)
    db.session.commit()
    return jsonify({"ok": True, "id": dep.id})


# Update department
@bp.route("/api/update/<int:dep_id>", methods=["POST"])
@login_required
@admin_only
def api_update_department(dep_id: int):
    dep = Department.query.get_or_404(dep_id)
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    manager_id = data.get("manager_id")

    errors = {}
    if not name:
        errors["name"] = "Required."
    else:
        exists = Department.query.filter(
            func.lower(Department.name) == name.lower(),
            Department.id != dep.id
        ).first()
        if exists:
            errors["name"] = "Department with this name already exists."

    manager = None
    if manager_id not in (None, "", "null"):
        manager = User.query.get(int(manager_id))
        if not manager:
            errors["manager_id"] = "Director not found."
        elif manager.department_id is not None and manager.department_id != dep.id:
            errors["manager_id"] = "User is assigned to another department."

    if errors:
        return jsonify({"errors": errors}), 400

    dep.name = name
    dep.manager = manager  # can be None
    db.session.commit()
    return jsonify({"ok": True})


# Delete department
@bp.route("/api/delete/<int:dep_id>", methods=["POST"])
@login_required
@admin_only
def api_delete_department(dep_id: int):
    dep = Department.query.get_or_404(dep_id)
    # Detach users
    User.query.filter(User.department_id == dep.id).update({User.department_id: None})
    db.session.flush()
    # Detach manager and delete
    dep.manager = None
    db.session.delete(dep)
    db.session.commit()
    return jsonify({"ok": True})


# =====================================================================
#                         MEMBERSHIP HELPERS
# =====================================================================

# All users (for selects)
@bp.route("/api/users", methods=["GET"])
@login_required
@admin_only
def api_dep_users():
    users = User.query.order_by(User.id.asc()).all()
    items = []
    for u in users:
        fn = (u.first_name or "").strip()
        ln = (u.last_name or "").strip()
        items.append({
            "id": u.id,
            "name": (f"{fn} {ln}".strip() or u.email),
            "email": u.email,
            "department_id": u.department_id,
        })
    return jsonify({"items": items})


# Department members list
@bp.route("/api/members/<int:dep_id>", methods=["GET"])
@login_required
@admin_only
def api_dep_members(dep_id: int):
    dep = Department.query.get_or_404(dep_id)
    members_q = User.query.filter(User.department_id == dep.id).order_by(User.id.asc())
    items = []
    for m in members_q:
        fn = (m.first_name or "").strip()
        ln = (m.last_name or "").strip()
        items.append({
            "id": m.id,
            "name": (f"{fn} {ln}".strip() or m.email),
            "email": m.email,
        })
    return jsonify({"items": items})


# Add member to department
@bp.route("/api/members/<int:dep_id>", methods=["POST"])
@login_required
@admin_only
def api_dep_add_member(dep_id: int):
    Department.query.get_or_404(dep_id)
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"errors": {"user_id": "Required."}}), 400

    u = User.query.get(int(user_id))
    if not u:
        return jsonify({"errors": {"user_id": "User not found."}}), 404

    u.department_id = dep_id
    db.session.commit()
    return jsonify({"ok": True})


# Remove member from department
@bp.route("/api/members/<int:dep_id>/remove", methods=["POST"])
@login_required
@admin_only
def api_dep_remove_member(dep_id: int):
    Department.query.get_or_404(dep_id)
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"errors": {"user_id": "Required."}}), 400

    u = User.query.get(int(user_id))
    if not u:
        return jsonify({"errors": {"user_id": "User not found."}}), 404

    if u.department_id == dep_id:
        u.department_id = None
        db.session.commit()
    return jsonify({"ok": True})


# =====================================================================
#                      PERMISSIONS (War & Peace)
# =====================================================================

# NOTE:
# This endpoint family manages a low-level table (department_permissions)
# and is self-healing across SQLite/Postgres/MySQL. It exposes:
#   GET  /api/perms/<dep_id>  -> list of known codes and allowed flags
#   POST /api/perms/<dep_id>  -> upsert provided items = [{code, allowed}, ...]

# Which codes the panel shows
PERMISSION_CODES = [
    # USERS
    "users.view",
    "users.general",
    "users.create_edit",
    "users.agreement",
    "users.vacation",
    "users.sick",          # note: use the same key you defined in PERMISSION_CATALOG
    "users.reports",
    "users.uniforms",
    "users.training",
    "users.rewards",
    "users.penalty",
    "users.attachments",

    # WAR
    "war.view",
    "war.edit",
    "war.export",
    "war.manage",
]


TABLE_NAME = "department_permissions"


def _insp():
    return reflection.Inspector.from_engine(db.engine)


def _ensure_perm_schema():
    """
    Permanent self-healing:
    - Create table if missing.
    - Ensure columns: code (str, NOT NULL DEFAULT ''), allowed (int/bool, NOT NULL DEFAULT 0).
    - If legacy column 'permission' exists (possibly NOT NULL), keep it populated == code.
    - Create UNIQUE index on (department_id, code).
    """
    insp = _insp()
    tables = set(insp.get_table_names())
    dialect = db.engine.dialect.name

    # 1) Create table if missing
    if TABLE_NAME not in tables:
        metadata = MetaData()
        Table(
            TABLE_NAME,
            metadata,
            Column("id", Integer, primary_key=True),
            Column("department_id", Integer, nullable=False, index=True),
            Column("code", String(64), nullable=False, index=True, default=""),
            Column("allowed", Boolean, nullable=False, default=False),
            UniqueConstraint("department_id", "code", name=f"uq_{TABLE_NAME}_dept_code"),
        )
        metadata.create_all(db.engine)
        try:
            db.session.execute(text(
                f"CREATE UNIQUE INDEX IF NOT EXISTS ux_dept_perm_dept_code ON {TABLE_NAME} (department_id, code)"
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
        return

    # 2) Ensure columns
    cols = {c["name"] for c in insp.get_columns(TABLE_NAME)}

    # 2a) allowed
    if "allowed" not in cols:
        try:
            if dialect == "sqlite":
                db.session.execute(text(f"ALTER TABLE {TABLE_NAME} ADD COLUMN allowed INTEGER NOT NULL DEFAULT 0"))
            elif dialect in ("postgresql", "postgres"):
                db.session.execute(text(f"ALTER TABLE {TABLE_NAME} ADD COLUMN IF NOT EXISTS allowed boolean NOT NULL DEFAULT false"))
            elif dialect in ("mysql", "mariadb"):
                db.session.execute(text(f"ALTER TABLE {TABLE_NAME} ADD COLUMN IF NOT EXISTS allowed TINYINT(1) NOT NULL DEFAULT 0"))
            else:
                db.session.execute(text(f"ALTER TABLE {TABLE_NAME} ADD COLUMN allowed BOOLEAN NOT NULL DEFAULT 0"))
            db.session.commit()
        except Exception:
            db.session.rollback()
            if dialect == "sqlite":
                db.session.execute(text(f"ALTER TABLE {TABLE_NAME} ADD COLUMN allowed INTEGER NOT NULL DEFAULT 0"))
                db.session.commit()

    # 2b) code
    insp = _insp()
    cols = {c["name"] for c in insp.get_columns(TABLE_NAME)}
    if "code" not in cols:
        try:
            if dialect == "sqlite":
                db.session.execute(text(f"ALTER TABLE {TABLE_NAME} ADD COLUMN code VARCHAR(64) NOT NULL DEFAULT ''"))
            elif dialect in ("postgresql", "postgres", "mysql", "mariadb"):
                db.session.execute(text(f"ALTER TABLE {TABLE_NAME} ADD COLUMN IF NOT EXISTS code VARCHAR(64) NOT NULL DEFAULT ''"))
            else:
                db.session.execute(text(f"ALTER TABLE {TABLE_NAME} ADD COLUMN code VARCHAR(64) NOT NULL DEFAULT ''"))
            db.session.commit()
        except Exception:
            db.session.rollback()
            if dialect == "sqlite":
                db.session.execute(text(f"ALTER TABLE {TABLE_NAME} ADD COLUMN code VARCHAR(64) NOT NULL DEFAULT ''"))
                db.session.commit()

    # 2c) If legacy 'permission' column exists, keep it populated (may be NOT NULL)
    insp = _insp()
    cols = {c["name"] for c in insp.get_columns(TABLE_NAME)}
    if "permission" in cols:
        try:
            db.session.execute(text(
                f"UPDATE {TABLE_NAME} SET permission = code "
                f"WHERE (permission IS NULL OR permission = '') AND code <> ''"
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()

    # 3) Unique index
    try:
        db.session.execute(text(
            f"CREATE UNIQUE INDEX IF NOT EXISTS ux_dept_perm_dept_code ON {TABLE_NAME} (department_id, code)"
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()


def _perm_table_columns():
    insp = _insp()
    return {c["name"] for c in insp.get_columns(TABLE_NAME)}


def _fetch_perm_rows(dep_id: int):
    try:
        res = db.session.execute(
            text(f"SELECT code, allowed FROM {TABLE_NAME} WHERE department_id = :d"),
            {"d": dep_id},
        )
        rows = res.fetchall()
    except (OperationalError, ProgrammingError):
        _ensure_perm_schema()
        res = db.session.execute(
            text(f"SELECT code, allowed FROM {TABLE_NAME} WHERE department_id = :d"),
            {"d": dep_id},
        )
        rows = res.fetchall()

    out = {}
    for row in rows:
        try:
            code = row["code"]; allowed = row["allowed"]
        except Exception:
            code = row[0]; allowed = row[1]
        out[str(code)] = bool(allowed)
    return out


# GET permissions
@bp.route("/api/perms/<int:dep_id>", methods=["GET"])
@login_required
@admin_only
def api_dep_perms_get(dep_id: int):
    Department.query.get_or_404(dep_id)
    _ensure_perm_schema()
    current = _fetch_perm_rows(dep_id)
    items = [{"code": c, "allowed": bool(current.get(c, False))} for c in PERMISSION_CODES]
    return jsonify({"items": items})


# SET permissions (upsert)
@bp.route("/api/perms/<int:dep_id>", methods=["POST"])
@login_required
@admin_only
def api_dep_perms_set(dep_id: int):
    Department.query.get_or_404(dep_id)
    _ensure_perm_schema()

    data = request.get_json(silent=True) or {}
    items = data.get("items")
    if not isinstance(items, list):
        return jsonify({"error": "Invalid payload"}), 400

    desired = {}
    for entry in items:
        if not isinstance(entry, dict):
            continue
        code = (entry.get("code") or "").strip()
        if not code:
            continue
        desired[code] = bool(entry.get("allowed", False))

    cols = _perm_table_columns()
    has_legacy_permission_col = "permission" in cols

    for code, allowed in desired.items():
        # UPDATE first (and keep legacy 'permission' in sync if it exists)
        if has_legacy_permission_col:
            try:
                res = db.session.execute(
                    text(f"""
                        UPDATE {TABLE_NAME}
                        SET allowed = :a, permission = :c
                        WHERE department_id = :d AND code = :c
                    """),
                    {"a": int(allowed), "d": dep_id, "c": code},
                )
            except (OperationalError, ProgrammingError):
                _ensure_perm_schema()
                res = db.session.execute(
                    text(f"""
                        UPDATE {TABLE_NAME}
                        SET allowed = :a, permission = :c
                        WHERE department_id = :d AND code = :c
                    """),
                    {"a": int(allowed), "d": dep_id, "c": code},
                )
        else:
            try:
                res = db.session.execute(
                    text(f"""
                        UPDATE {TABLE_NAME}
                        SET allowed = :a
                        WHERE department_id = :d AND code = :c
                    """),
                    {"a": int(allowed), "d": dep_id, "c": code},
                )
            except (OperationalError, ProgrammingError):
                _ensure_perm_schema()
                res = db.session.execute(
                    text(f"""
                        UPDATE {TABLE_NAME}
                        SET allowed = :a
                        WHERE department_id = :d AND code = :c
                    """),
                    {"a": int(allowed), "d": dep_id, "c": code},
                )

        # INSERT if nothing was updated (and populate legacy 'permission' if required)
        if res.rowcount == 0:
            if has_legacy_permission_col:
                db.session.execute(
                    text(f"""
                        INSERT INTO {TABLE_NAME} (department_id, code, allowed, permission)
                        VALUES (:d, :c, :a, :c)
                    """),
                    {"d": dep_id, "c": code, "a": int(allowed)},
                )
            else:
                db.session.execute(
                    text(f"""
                        INSERT INTO {TABLE_NAME} (department_id, code, allowed)
                        VALUES (:d, :c, :a)
                    """),
                    {"d": dep_id, "c": code, "a": int(allowed)},
                )

    db.session.commit()
    return jsonify({"ok": True})
