# app/dashboard/routes.py
from __future__ import annotations

from flask import render_template, url_for
from flask_login import login_required
from . import bp


@bp.route("/")
@login_required
def index():
    """
    Render the dashboard with the Feed panel pre-mounted.
    We build the same fragment that /api/feed/panel returns on AJAX loads,
    avoiding an import of app.feed.api (which no longer exists).
    """
    avatar_url = url_for("static", filename="img/avatar-placeholder.png")
    main_js = url_for("feed_api.static", filename="feed-main.js")

    fragment = f"""
<section id="FeedPanel" data-init="mountFeedPanel">
  <div id="feed-root"
       data-endpoint="/api/feed"
       data-drive-picker="/api/feed/drive-picker"
       data-avatar-fallback="{avatar_url}">
  </div>
  <script type="module" src="{main_js}" data-exec></script>
</section>
""".strip()

    return render_template("dashboard.html", initial_panel=fragment)
