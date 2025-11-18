# app/feed/routes/util_static_root.py
from __future__ import annotations
import os
from flask import current_app

def _static_root() -> str:
    return current_app.static_folder or os.path.join(current_app.root_path, "static")
