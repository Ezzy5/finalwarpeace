from flask_login import login_required
from flask import jsonify
from sqlalchemy import desc
from app.models import User, Attachment
from app.permissions import require_permission, USERS_VIEW
from .. import bp

@bp.route("/api/attachments/<int:user_id>", methods=["GET"])
@login_required
@require_permission(USERS_VIEW)
def list_attachments(user_id: int):
    u = User.query.get_or_404(user_id)
    q = u.attachments.order_by(desc(Attachment.uploaded_at))
    items = [{
        "id": a.id, "filename": a.filename, "stored_name": a.stored_name,
        "content_type": a.content_type,
        "uploaded_at": a.uploaded_at.isoformat() if a.uploaded_at else None,
        "agreement_id": a.agreement_id, "sick_leave_id": a.sick_leave_id,
        "vacation_id": a.vacation_id, "uniform_id": a.uniform_id,
        "report_kind": getattr(a, "report_kind", None),
    } for a in q.all()]
    return jsonify({"items": items})
