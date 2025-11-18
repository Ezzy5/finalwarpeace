from flask import Blueprint

# Use this folder itself as the template root (since you said no templates/ folder)
bp = Blueprint("dashboard", __name__, template_folder="")

from . import routes  # noqa: E402,F401
