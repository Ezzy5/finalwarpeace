# app/feed/routes/route_panel.py
from __future__ import annotations
from flask import url_for, current_app, make_response, render_template, jsonify
from flask_login import login_required
from app.feed import bp
from app.feed.routes.util_is_ajax import _is_ajax

@bp.get("/panel")
@login_required
def panel():
    """
    Returns the Feed SPA panel fragment.
    This version removes the 'Фид' header row.
    """
    try:
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

        if _is_ajax():
            return make_response(fragment, 200, {"Content-Type": "text/html; charset=utf-8"})
        return render_template("dashboard.html", initial_panel=fragment)

    except Exception as e:
        current_app.logger.exception("Feed panel failed to render")
        fallback = f"""
<section id="FeedPanel">
  <div class="alert alert-danger m-3">
    <div class="fw-semibold mb-1">Feed panel error</div>
    <div class="small">Exception while rendering /api/feed/panel:</div>
    <pre class="small mt-2" style="white-space:pre-wrap">{e}</pre>
  </div>
</section>
""".strip()
        if _is_ajax():
            return make_response(fallback, 200, {"Content-Type": "text/html; charset=utf-8"})
        return render_template("dashboard.html", initial_panel=fallback)
