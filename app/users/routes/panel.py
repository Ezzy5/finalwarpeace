# app/users/routes/panel.py
from flask import render_template, request
from flask_login import login_required

from .. import bp  # import bp from parent package (app.users)

@bp.route("/panel", methods=["GET"], endpoint="panel")
@login_required
def panel():
    # If requested by the SPA loader, return just the panel fragment
    if request.headers.get("X-Requested-With") == "fetch":
        return render_template("panel.html")
    # Fallback: open full dashboard shell if someone browses directly
    return render_template("dashboard.html", initial_panel="users")
