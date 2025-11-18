# app/email/routes/dnd_move.py
from flask import request, jsonify, abort
from flask_login import login_required, current_user

from app.email import bp
from app.email.models.connection import EmailConnection
from app.email.services.move.move_flow import move_message


@bp.route("/mail/move", methods=["POST"])
@login_required
def dnd_move():
    """
    JSON body: { acc: <id>, uid: "<uid>", from_folder: "<name>", to_folder: "<name>" }
    Returns JSON { ok: bool, method: str, error?: str }
    """
    data = request.get_json(silent=True) or {}
    acc_id = data.get("acc")
    uid = str(data.get("uid") or "").strip()
    from_folder = data.get("from_folder") or "INBOX"
    to_folder = data.get("to_folder")

    if not (acc_id and uid and to_folder):
        abort(400, description="Missing acc/uid/to_folder")

    conn = EmailConnection.query.filter_by(user_id=current_user.id, id=int(acc_id)).first()
    if not conn:
        abort(404, description="Account not found")

    result = move_message(conn, from_folder, uid, to_folder)
    status = 200 if result.get("ok") else 500
    return jsonify(result), status
