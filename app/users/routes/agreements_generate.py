# app/users/routes/agreements_generate.py
from __future__ import annotations
import os
import uuid
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict

from flask import jsonify, request, abort, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from .. import bp
from ...extensions import db
from ...models import User, Agreement, Attachment, Department
from app.permissions import require_permission, has_permission, USERS_AGREEMENT, USERS_CREATE_EDIT
from .templates_store import get_template_by_id as _get_tpl

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

def _agreements_dir() -> str:
    base = current_app.config.get("AGREEMENTS_UPLOAD_DIR")
    if not base:
        base = os.path.join(current_app.instance_path, "agreements")
    os.makedirs(base, exist_ok=True)
    return base

def _parse_yyyy_mm_dd(s: str) -> date:
    y, m, d = [int(x) for x in (s or "").split("-")]
    return date(y, m, d)

def _calc_end_months(start: date, months: int) -> date:
    from dateutil.relativedelta import relativedelta
    months = max(1, int(months or 0))
    return start + relativedelta(months=+months)

def _next_business_day(d: date) -> date:
    r = d + timedelta(days=1)
    while r.weekday() >= 5:
        r += timedelta(days=1)
    return r

# {{ name|upper }} and {{ start_date|date('%d.%m.%Y') }} filters (for HTML only)
_re_var = re.compile(r"{{\s*([a-zA-Z0-9_]+)(?:\|([a-zA-Z]+)(?:\((.*?)\))?)?\s*}}")

def _apply_filter(val: Any, fname: str | None, farg: str | None) -> str:
    s = "" if val is None else str(val)
    f = (fname or "").lower()
    if f == "upper": return s.upper()
    if f == "lower": return s.lower()
    if f == "title": return s.title()
    if f == "date":
        fmt = "%Y-%m-%d"
        if farg:
            a = farg.strip()
            if (a.startswith("'") and a.endswith("'")) or (a.startswith('"') and a.endswith('"')): a = a[1:-1]
            fmt = a or fmt
        try:
            return datetime.strptime(s, "%Y-%m-%d").strftime(fmt)
        except Exception:
            return s
    return s

def _render_html(content: str, ctx: Dict[str, Any]) -> str:
    def repl(m: re.Match):
        name, fname, farg = m.group(1), m.group(2), m.group(3)
        val = ctx.get(name, "")
        return _apply_filter(val, fname, farg) if fname else ("" if val is None else str(val))
    return _re_var.sub(repl, content or "")

@bp.post("/api/agreements/<int:user_id>/generate")
@login_required
@require_permission(USERS_AGREEMENT)
def api_agreements_generate(user_id: int):
    if not has_permission(current_user, USERS_CREATE_EDIT):
        abort(403)

    data = request.get_json(silent=True) or {}
    template_id = data.get("template_id")
    start_s     = (data.get("start_date") or "").strip()
    months      = int(data.get("months") or 0)
    filename_in = (data.get("filename") or "").strip()

    if not template_id:
        return jsonify({"error": "template_id is required"}), 400
    if not start_s:
        return jsonify({"error": "start_date is required (YYYY-MM-DD)"}), 400

    u = User.query.get_or_404(user_id)
    tpl = _get_tpl(int(template_id))
    if not tpl:
        return jsonify({"error": "Template not found"}), 404

    try:
        start_date = _parse_yyyy_mm_dd(start_s)
    except Exception:
        return jsonify({"error": "Invalid start_date"}), 400

    if months > 0:
        end_date = _calc_end_months(start_date, months)
    else:
        end_date = date(2099, 12, 31)

    return_date = _next_business_day(end_date)

    managed = Department.query.filter_by(manager_id=u.id).first()
    indefinite = (months == 0)
    end_date_str = end_date.strftime("%Y-%m-%d") if end_date else ""

    ctx = {
        "first_name": u.first_name or "",
        "last_name": u.last_name or "",
        "full_name": f"{u.first_name or ''} {u.last_name or ''}".strip(),
        "email": u.email or "",
        "phone_number": u.phone_number or "",
        "id_number": u.id_number or "",
        "embg": u.embg or "",
        "city": u.city or "",
        "address": u.address or "",
        "bank_account": u.bank_account or "",
        "department": getattr(getattr(u, "dept", None), "name", "") or "",
        "role": getattr(getattr(u, "role", None), "name", "") or "",
        "director_of": managed.name if managed else "",

        "today": date.today().strftime("%Y-%m-%d"),
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date_str,
        "return_date": return_date.strftime("%Y-%m-%d"),

        "months": months,
        "months_display": ("неопределено" if indefinite else str(months)),
        "end_date_display": ("неопределено" if indefinite else end_date_str),
        "is_indefinite": "да" if indefinite else "не",
        "kind": ("неопределен" if indefinite else "определено"),
    }

    dest_dir = _agreements_dir()
    ttype = (tpl.get("type") or "html").lower()

    if ttype == "docx":
        try:
            from docxtpl import DocxTemplate
        except Exception:
            return jsonify({"error": "docxtpl is not installed. Run: pip install docxtpl"}), 500

        base_title = (filename_in or tpl.get("name") or "agreement").strip() or "agreement"
        if not base_title.lower().endswith(".docx"):
            base_title += ".docx"
        safe_out = secure_filename(base_title) or "agreement.docx"
        stored_name = f"{uuid.uuid4().hex}_{safe_out}"
        out_path = os.path.join(dest_dir, stored_name)

        tpl_base_dir = current_app.config.get("AGREEMENT_TEMPLATES_DIR")
        tpl_file = tpl.get("file_stored_name")
        if not tpl_file:
            return jsonify({"error": "DOCX template has no file uploaded"}), 400
        tpl_path = os.path.join(tpl_base_dir, tpl_file)
        if not os.path.exists(tpl_path):
            return jsonify({"error": f"Template file not found: {tpl_file}"}), 404

        doc = DocxTemplate(tpl_path)
        doc.render(ctx)   # ← keeps Word formatting
        doc.save(out_path)
        content_type = DOCX_MIME

    elif ttype == "html":
        base_title = (filename_in or tpl.get("name") or "agreement").strip() or "agreement"
        if not base_title.lower().endswith(".html"):
            base_title += ".html"
        safe_out = secure_filename(base_title) or "agreement.html"
        stored_name = f"{uuid.uuid4().hex}_{safe_out}"
        out_path = os.path.join(dest_dir, stored_name)
        rendered = _render_html(str(tpl.get("content") or ""), ctx)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(rendered)
        content_type = "text/html"

    else:
        base_title = (filename_in or tpl.get("name") or "agreement").strip() or "agreement"
        if not base_title.lower().endswith(".txt"):
            base_title += ".txt"
        safe_out = secure_filename(base_title) or "agreement.txt"
        stored_name = f"{uuid.uuid4().hex}_{safe_out}"
        out_path = os.path.join(dest_dir, stored_name)
        rendered = _render_html(str(tpl.get("content") or ""), ctx)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(rendered)
        content_type = "text/plain"

    a = Agreement(
        user_id=u.id,
        start_date=start_date,
        months=(months if months > 0 else 0),
        end_date=end_date,
        status="active",
    )
    db.session.add(a)
    db.session.flush()

    att = Attachment(
        user_id=u.id,
        agreement_id=a.id,
        filename=safe_out,
        stored_name=stored_name,
        content_type=content_type,
    )
    db.session.add(att)
    db.session.commit()

    return jsonify({
        "ok": True,
        "agreement": {
            "id": a.id,
            "start_date": a.start_date.strftime("%Y-%m-%d"),
            "months": a.months,
            "end_date": a.end_date.strftime("%Y-%m-%d") if a.end_date else None,
            "status": a.status,
        },
        "attachment": {
            "id": att.id,
            "filename": att.filename,
            "stored_name": att.stored_name,
            "content_type": att.content_type,
        }
    })
