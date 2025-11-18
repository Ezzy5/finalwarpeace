from flask_login import login_required
from flask import jsonify
from app.models import User
from app.permissions import require_permission, USERS_VIEW
from .. import bp
from .helpers import _user_to_dict

@bp.route("/api/show/<int:user_id>", methods=["GET"])
@login_required
@require_permission(USERS_VIEW)
def api_show(user_id):
    u = User.query.get_or_404(user_id)
    return jsonify({"item": _user_to_dict(u)})
