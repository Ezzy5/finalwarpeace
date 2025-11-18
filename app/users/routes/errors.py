from flask import jsonify, current_app
from werkzeug.exceptions import HTTPException
from .. import bp

@bp.errorhandler(HTTPException)
def _rewards_http_error(e: HTTPException):
    payload = {"error": e.name}
    if getattr(e, "description", None):
        payload["detail"] = e.description
    return jsonify(payload), e.code

@bp.errorhandler(Exception)
def _rewards_unexpected_error(e: Exception):
    current_app.logger.exception("Unexpected error in Users API")
    return jsonify({"error": "Internal Server Error"}), 500
