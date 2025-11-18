# app/uploader/__init__.py
from flask import Blueprint

bp = Blueprint(
    "uploader",
    __name__,
    url_prefix="/api/upload",
)

# Do NOT import .api here (avoids circulars). The app factory imports app.uploader.api before registering bp.
