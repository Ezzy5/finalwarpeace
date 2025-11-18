# app/email/routes/_helpers.py
from flask import request

def _is_spa_request() -> bool:
    return request.headers.get("X-Requested-With") == "fetch"
