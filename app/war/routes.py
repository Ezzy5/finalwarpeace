# app/war/routes.py
from __future__ import annotations

from io import BytesIO
from datetime import datetime
from typing import Optional

from flask import render_template, request, jsonify, abort, send_file
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload

from . import war_bp
from .models_war import db, WarCompany, WarInteraction, WarComment, InteractionKind
from app.models import Department, User
from app.permissions import has_permission, is_admin_like

# Optional PDF deps
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import cm
except Exception:
    A4 = canvas = cm = None


# =========================
# Helpers
# =========================
def _user_dep_id(u: Optional[User] = None) -> Optional[int]:
    u = u or current_user
    return getattr(u, "department_id", None)

def _company_accessible(company: WarCompany, u: Optional[User] = None) -> bool:
    """Company must be linked to the user's department, or user is admin-like."""
    u = u or current_user
    if is_admin_like(u):
        return True
    dep_id = _user_dep_id(u)
    if dep_id is None:
        return False
    return any(d.id == dep_id for d in company.departments)

def _position_for_user(u: Optional[User]) -> str:
    """
    'admin' if admin-like, 'director' if they manage their department, else 'member'.
    """
    if not u:
        return "member"
    if is_admin_like(u):
        return "admin"
    dept = getattr(u, "dept", None)
    if dept and getattr(dept, "manager_id", None) == u.id:
        return "director"
    return "member"

def _parse_dt(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val)
    except Exception:
        return None

def _safe_full_name(u: Optional[User]) -> str:
    if not u:
        return ""
    # Prefer model property if present and non-empty
    val = (getattr(u, "full_name", None) or "").strip()
    if val:
        return val
    first = (getattr(u, "first_name", "") or "").strip()
    last  = (getattr(u, "last_name", "") or "").strip()
    if first or last:
        return f"{first} {last}".strip()
    return (getattr(u, "username", None) or getattr(u, "email", None) or "").strip()

def _comment_to_dict(c: WarComment) -> dict:
    u: Optional[User] = getattr(c, "user", None)
    return {
        "id": c.id,
        "text": c.text,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "user_id": c.user_id,
        "user_name": _safe_full_name(u),
        "user_department": getattr(getattr(u, "dept", None), "name", ""),
        "user_position": _position_for_user(u),
    }

def _interaction_to_dict(it: WarInteraction, with_comments: bool = True) -> dict:
    u: Optional[User] = getattr(it, "user", None)
    payload = {
        "id": it.id,
        "company_id": it.company_id,
        "kind": (it.kind.value if hasattr(it.kind, "value") else str(it.kind)),  # ensure string
        "text": it.text,
        "archived": bool(it.archived),
        "created_at": it.created_at.isoformat() if it.created_at else None,
        "user_id": it.user_id,
        "user_name": _safe_full_name(u),
        "user_department": getattr(getattr(u, "dept", None), "name", ""),
        "user_position": _position_for_user(u),
        "department_id": it.department_id,
    }
    if with_comments:
        comments_rel = getattr(it, "comments", [])
        if hasattr(comments_rel, "order_by"):  # dynamic relationship
            comments = comments_rel.order_by(WarComment.created_at.asc()).all()
        else:
            comments = comments_rel or []
        payload["comments"] = [_comment_to_dict(c) for c in comments]
    return payload


# =========================
# UI
# =========================
@war_bp.route("/panel", strict_slashes=False)
@login_required
def panel():
    # war.view required to open the panel
    if not (is_admin_like(current_user) or has_permission(current_user, "war.view")):
        abort(403)

    # If the request is an AJAX/fragment request, return only the panel HTML.
    is_ajax = (
        request.args.get("ajax") in {"1", "true", "yes"}
        or request.headers.get("X-Requested-With") in ("XMLHttpRequest", "fetch")
    )

    departments = Department.query.order_by(Department.name.asc()).all()

    if is_ajax:
        return render_template("war.html", departments=departments, ajax=True)

    # Server-embed the fragment; SPA loader mounts it on first paint.
    panel_html = render_template("war.html", departments=departments, ajax=False)
    return render_template("dashboard.html", initial_panel=panel_html)


# =========================
# Current user's WAR abilities (for UI gating)
# =========================
@war_bp.get("/api/abilities")
@login_required
def api_abilities():
    u = current_user
    if is_admin_like(u):
        return jsonify({"war": {"view": True, "edit": True, "export": True, "manage": True}})
    return jsonify({
        "war": {
            "view":   has_permission(u, "war.view"),
            "edit":   has_permission(u, "war.edit"),
            "export": has_permission(u, "war.export"),
            "manage": has_permission(u, "war.manage"),
        }
    })


# =========================
# Departments (for modal multi-select)
# =========================
@war_bp.get("/api/departments")
@login_required
def api_departments():
    # Need at least view to see departments
    if not (is_admin_like(current_user) or has_permission(current_user, "war.view")):
        return jsonify({"error": "Forbidden"}), 403
    q = (request.args.get("q") or "").strip()
    query = Department.query
    if q:
        query = query.filter(Department.name.ilike(f"%{q}%"))
    deps = query.order_by(Department.name.asc()).all()
    return jsonify([{"id": d.id, "name": d.name} for d in deps])


# =========================
# Companies
# =========================
@war_bp.get("/api/companies")
@login_required
def api_companies():
    # Need at least view to list companies
    if not (is_admin_like(current_user) or has_permission(current_user, "war.view")):
        return jsonify({"error": "Forbidden"}), 403

    search = (request.args.get("search") or "").strip()
    q = WarCompany.query.options(joinedload(WarCompany.departments))
    if search:
        like = f"%{search}%"
        q = q.filter((WarCompany.name.ilike(like)) | (WarCompany.external_id.ilike(like)))
    q = q.order_by(WarCompany.created_at.desc())
    rows = q.limit(200).all()

    if not is_admin_like(current_user):
        dep_id = _user_dep_id()
        rows = [c for c in rows if any(d.id == dep_id for d in c.departments)]

    return jsonify([
        {
            "id": c.id,
            "name": c.name,
            "external_id": c.external_id,
            "departments": [{"id": d.id, "name": d.name} for d in c.departments],
            "created_at": c.created_at.isoformat() if c.created_at else None,
        } for c in rows
    ])

@war_bp.post("/api/company")
@login_required
def api_company_create():
    # war.manage required to create
    if not (is_admin_like(current_user) or has_permission(current_user, "war.manage")):
        return jsonify({"error": "Not authorized to create companies"}), 403

    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400
    external_id = (data.get("external_id") or "").strip()
    dep_ids = data.get("department_ids") or []

    company = WarCompany(name=name, external_id=external_id)
    if dep_ids:
        company.departments = Department.query.filter(Department.id.in_(dep_ids)).all()
    db.session.add(company)
    db.session.commit()
    return jsonify({"ok": True, "id": company.id}), 201

@war_bp.get("/api/company/<int:company_id>")
@login_required
def api_company_get(company_id):
    # Need at least view to open
    if not (is_admin_like(current_user) or has_permission(current_user, "war.view")):
        return jsonify({"error": "Forbidden"}), 403

    company = (WarCompany.query
               .options(joinedload(WarCompany.departments))
               .get_or_404(company_id))
    if not _company_accessible(company):
        return jsonify({"error": "Forbidden"}), 403
    return jsonify({
        "id": company.id,
        "name": company.name,
        "external_id": company.external_id,
        "departments": [{"id": d.id, "name": d.name} for d in company.departments],
    })

@war_bp.put("/api/company/<int:company_id>")
@login_required
def api_company_update(company_id):
    # war.manage required to update
    if not (is_admin_like(current_user) or has_permission(current_user, "war.manage")):
        return jsonify({"error": "Not authorized to update companies"}), 403

    company = WarCompany.query.get_or_404(company_id)
    data = request.get_json(force=True)

    name = (data.get("name") or "").strip()
    ext = (data.get("external_id") or "").strip()
    if name:
        company.name = name
    company.external_id = ext

    dep_ids = data.get("department_ids")
    if isinstance(dep_ids, list):
        company.departments = Department.query.filter(Department.id.in_(dep_ids)).all()

    db.session.commit()
    return jsonify({"ok": True})

@war_bp.delete("/api/company/<int:company_id>")
@login_required
def api_company_delete(company_id):
    # war.manage required to delete
    if not (is_admin_like(current_user) or has_permission(current_user, "war.manage")):
        return jsonify({"error": "Not authorized to delete companies"}), 403
    company = WarCompany.query.get_or_404(company_id)
    db.session.delete(company)
    db.session.commit()
    return jsonify({"ok": True})


# =========================
# Interactions
# =========================
@war_bp.get("/api/company/<int:company_id>/interactions")
@login_required
def api_interactions_list(company_id):
    # Need war.view to list interactions
    if not (is_admin_like(current_user) or has_permission(current_user, "war.view")):
        return jsonify({"error": "Forbidden"}), 403

    company = WarCompany.query.get_or_404(company_id)
    if not _company_accessible(company):
        return jsonify({"error": "Forbidden"}), 403

    date_from = _parse_dt(request.args.get("from"))
    date_to = _parse_dt(request.args.get("to"))
    kind = (request.args.get("kind") or "").strip().lower()
    archived = (request.args.get("archived") or "active").strip().lower()

    qry = (
        WarInteraction.query
        .options(
            joinedload(WarInteraction.user).joinedload(User.dept),
            # DO NOT eager-load .comments (dynamic relationship).
        )
        .filter(WarInteraction.company_id == company.id)
        .order_by(WarInteraction.created_at.desc())
    )

    if not is_admin_like(current_user):
        qry = qry.filter(WarInteraction.department_id == _user_dep_id())

    if kind in {"meeting", "email", "phone"}:
        qry = qry.filter(WarInteraction.kind == kind)

    if archived == "active":
        qry = qry.filter(WarInteraction.archived.is_(False))
    elif archived == "archived":
        qry = qry.filter(WarInteraction.archived.is_(True))
    # 'all' → no archived filter

    if date_from:
        qry = qry.filter(WarInteraction.created_at >= date_from)
    if date_to:
        qry = qry.filter(WarInteraction.created_at <= date_to)

    rows = qry.limit(500).all()
    return jsonify([_interaction_to_dict(it) for it in rows])

@war_bp.post("/api/company/<int:company_id>/interactions")
@login_required
def api_interactions_create(company_id):
    # war.edit required to create interaction
    if not (is_admin_like(current_user) or has_permission(current_user, "war.edit")):
        return jsonify({"error": "Not authorized to create interactions"}), 403

    company = WarCompany.query.get_or_404(company_id)
    if not _company_accessible(company):
        return jsonify({"error": "Forbidden"}), 403

    dep_id = _user_dep_id()
    if dep_id is None:
        return jsonify({"error": "User has no department"}), 400

    data = request.get_json(force=True)
    kind = (data.get("kind") or "meeting").strip().lower()
    text = (data.get("text") or "").strip()

    if kind not in {"meeting", "email", "phone"}:
        return jsonify({"error": "Invalid kind"}), 400
    if not text:
        return jsonify({"error": "Text is required"}), 400

    it = WarInteraction(
        company_id=company.id,
        user_id=getattr(current_user, "id", 0),
        department_id=dep_id,
        kind=InteractionKind(kind),
        text=text,
        archived=False,
        created_at=datetime.utcnow(),
    )
    db.session.add(it)
    db.session.commit()

    # Reload with author join to return enriched payload
    it = (
        WarInteraction.query
        .options(
            joinedload(WarInteraction.user).joinedload(User.dept),
        )
        .get(it.id)
    )

    return jsonify(_interaction_to_dict(it)), 201

@war_bp.post("/api/interaction/<int:interaction_id>/archive")
@login_required
def api_interaction_archive(interaction_id):
    # war.edit required to archive/unarchive
    if not (is_admin_like(current_user) or has_permission(current_user, "war.edit")):
        return jsonify({"error": "Not authorized to archive interactions"}), 403

    it = (
        WarInteraction.query
        .options(joinedload(WarInteraction.company))
        .get_or_404(interaction_id)
    )
    if not _company_accessible(it.company):
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json(silent=True) or {}
    it.archived = bool(data.get("archived", True))
    db.session.commit()
    return jsonify({"ok": True, "archived": bool(it.archived)})

@war_bp.post("/api/interaction/<int:interaction_id>/comments")
@login_required
def api_interaction_comment(interaction_id):
    # war.edit required to comment
    if not (is_admin_like(current_user) or has_permission(current_user, "war.edit")):
        return jsonify({"error": "Not authorized to comment"}), 403

    it = (
        WarInteraction.query
        .options(joinedload(WarInteraction.company))
        .get_or_404(interaction_id)
    )
    if not _company_accessible(it.company):
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json(force=True)
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Text is required"}), 400

    c = WarComment(
        interaction_id=interaction_id,
        user_id=getattr(current_user, "id", 0),
        text=text,
        created_at=datetime.utcnow(),
    )
    db.session.add(c)
    db.session.commit()

    c = (
        WarComment.query
        .options(joinedload(WarComment.user).joinedload(User.dept))
        .get(c.id)
    )
    return jsonify(_comment_to_dict(c)), 201


# =========================
# Export PDF
# =========================
@war_bp.post("/export")
@login_required
def export_pdf():
    # war.export permission required
    if not (is_admin_like(current_user) or has_permission(current_user, "war.export")):
        return jsonify({"error": "Not authorized to export"}), 403

    data = request.get_json(force=True)
    company = WarCompany.query.get_or_404(data.get("company_id"))
    if not _company_accessible(company):
        return jsonify({"error": "Forbidden"}), 403
    if not (A4 and canvas and cm):
        return jsonify({"error": "Missing 'reportlab'. pip install reportlab"}), 500

    date_from = _parse_dt(data.get("from"))
    date_to = _parse_dt(data.get("to"))
    kind = (data.get("kind") or "").strip().lower()
    archived = (data.get("archived") or "active").strip().lower()

    q = (
        WarInteraction.query
        .options(joinedload(WarInteraction.department))
        .filter(WarInteraction.company_id == company.id)
        .order_by(WarInteraction.created_at.asc())
    )

    if not is_admin_like(current_user):
        q = q.filter(WarInteraction.department_id == _user_dep_id())

    if date_from:
        q = q.filter(WarInteraction.created_at >= date_from)
    if date_to:
        q = q.filter(WarInteraction.created_at <= date_to)
    if kind in {"meeting", "email", "phone"}:
        q = q.filter(WarInteraction.kind == kind)
    if archived == "active":
        q = q.filter(WarInteraction.archived.is_(False))
    elif archived == "archived":
        q = q.filter(WarInteraction.archived.is_(True))

    rows = q.all()

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    def line(y, text):
        c.drawString(2 * cm, y, (text or "")[:110])

    c.setFont("Helvetica-Bold", 14)
    c.drawString(2 * cm, height - 2 * cm, f"Company: {company.name} ({company.external_id or '-'})")
    c.setFont("Helvetica", 10)

    y = height - 3 * cm
    for it in rows:
        if y < 3 * cm:
            c.showPage()
            y = height - 2 * cm
        c.setFont("Helvetica-Bold", 11)
        dep_name = (it.department.name if it.department else "")
        kind_str = it.kind.value if hasattr(it.kind, "value") else str(it.kind)
        line(y, f"{it.created_at:%Y-%m-%d %H:%M} | {dep_name} | {kind_str}{' | ARCHIVED' if it.archived else ''}")
        y -= 14
        c.setFont("Helvetica", 10)
        txt = it.text or ""
        for i in range(0, len(txt), 100):
            line(y, txt[i:i+100])
            y -= 12
        for co in it.comments.order_by(WarComment.created_at.asc()).all():
            if y < 3 * cm:
                c.showPage()
                y = height - 2 * cm
            line(y, f"  ↳ {co.created_at:%Y-%m-%d %H:%M} | user {co.user_id}: {co.text}")
            y -= 11
        y -= 8

    c.showPage()
    c.save()
    buf.seek(0)
    filename = f"war_export_{company.id}_{datetime.utcnow():%Y%m%d_%H%M%S}.pdf"
    return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name=filename)
