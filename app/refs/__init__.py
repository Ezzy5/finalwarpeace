# app/refs/__init__.py
from flask import Blueprint

bp = Blueprint(
    "refs_api",
    __name__,
    url_prefix="/api/refs",
)

# ❌ Do NOT import .api here.
