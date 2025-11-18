# app/__init__.py
import os
from pathlib import Path

from flask import Flask, redirect, url_for
from flask_login import current_user
from sqlalchemy import inspect

from .extensions import db, migrate, csrf, login_manager
from app.permissions import has_permission, is_admin_like
from app.departments.routes import _ensure_perm_schema
from app.email import init_app as init_email

# --- Optional scheduler (for reminders) --------------------------------------
try:
    from apscheduler.schedulers.background import BackgroundScheduler  # pip install APScheduler
except Exception:  # pragma: no cover
    BackgroundScheduler = None  # type: ignore


def _ensure_all_tables(app):
    """Dev-only SQLite safety net: make sure base tables exist once."""
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if not uri.startswith("sqlite:"):
        return
    with app.app_context():
        try:
            from app import models  # noqa: F401
        except Exception:
            pass
        insp = inspect(db.engine)
        existing = set(insp.get_table_names())
        if not existing:
            print(">>> Dev create_all (fresh SQLite DB)")
            db.create_all()


def create_app():
    app = Flask(__name__)

    # ---------- Base Config ----------
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///dev.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config.setdefault("TEMPLATES_AUTO_RELOAD", True)
    app.config.setdefault("APP_TIMEZONE", "Europe/Skopje")

    # Reminders scheduler config (sane defaults)
    app.config.setdefault("REMINDERS_SCHED_ENABLED", True)
    app.config.setdefault("REMINDERS_INTERVAL_MINUTES", 1)
    app.config.setdefault("REMINDERS_SCAN_HORIZON_MIN", 120)
    app.config.setdefault("REMINDERS_SKEW_SECONDS", 90)
    app.config.setdefault("REMINDERS_CATCHUP_SECONDS", 300)

    # Ensure instance folder exists
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    # Upload roots
    uploads_dir = os.getenv("UPLOADS_DIR") or os.path.join(app.instance_path, "uploads")
    Path(uploads_dir).mkdir(parents=True, exist_ok=True)
    app.config.setdefault("UPLOADS_DIR", uploads_dir)
    app.config.setdefault("UPLOAD_FOLDER", uploads_dir)

    # Map to feed uploader config
    app.config.setdefault("UPLOAD_ROOT", app.config["UPLOADS_DIR"])
    app.config.setdefault("UPLOAD_URL_PREFIX", "/u")

    # Tickets uploads
    tickets_upload_dir = os.path.join(uploads_dir, "tickets")
    Path(tickets_upload_dir).mkdir(parents=True, exist_ok=True)
    app.config.setdefault("TICKETS_UPLOAD_FOLDER", tickets_upload_dir)

    app.config.setdefault("ALLOWED_UPLOADS", {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/plain",
        "image/jpeg", "image/png", "image/gif",
    })
    app.config.setdefault("MAX_CONTENT_LENGTH", 100 * 1024 * 1024)

    # Drive
    drive_upload_root = os.getenv("DRIVE_UPLOAD_FOLDER") or os.path.join(app.instance_path, "drive_uploads")
    drive_preview_root = os.getenv("DRIVE_PREVIEW_FOLDER") or os.path.join(app.instance_path, "drive_previews")
    app.config.setdefault("DRIVE_UPLOAD_FOLDER", drive_upload_root)
    app.config.setdefault("DRIVE_PREVIEW_FOLDER", drive_preview_root)
    Path(app.config["DRIVE_UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["DRIVE_PREVIEW_FOLDER"]).mkdir(parents=True, exist_ok=True)
    app.config.setdefault(
        "DRIVE_SOFFICE_PATH",
        r"C:\Program Files\LibreOffice\program\soffice.exe" if os.name == "nt" else "soffice"
    )

    # Agreements
    app.config.setdefault("AGREEMENTS_UPLOAD_DIR", os.path.join(app.instance_path, "agreements"))
    app.config.setdefault("AGREEMENT_TEMPLATES_DIR", os.path.join(app.instance_path, "templates", "agreements"))
    os.makedirs(app.config["AGREEMENTS_UPLOAD_DIR"], exist_ok=True)
    os.makedirs(app.config["AGREEMENT_TEMPLATES_DIR"], exist_ok=True)

    # Callendar uploads
    callendar_upload_root = os.getenv("CALLENDAR_UPLOAD_FOLDER") or os.path.join(app.instance_path, "callendar_uploads")
    app.config.setdefault("CALLENDAR_UPLOAD_FOLDER", callendar_upload_root)
    Path(app.config["CALLENDAR_UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    # ---------- Extensions ----------
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    # Dev tables autoboot (sqlite only, once)
    app._schema_checked = False

    @app.before_request
    def _dev_schema_once():
        if app._schema_checked:
            return
        _ensure_all_tables(app)

        if app.config.get("SQLALCHEMY_DATABASE_URI", "").startswith("sqlite:"):
            try:
                from app.dev_schema import ensure_sqlite_schema
                ensure_sqlite_schema(db.metadata)
                print(">>> SQLite dev schema ensured")
            except Exception as e:
                app.logger.error("SQLite auto-migrate failed: %s", e)

        app._schema_checked = True

    # ---------- Jinja helpers ----------
    @app.context_processor
    def inject_permissions():
        def j_can(perm: str, user=None) -> bool:
            try:
                u = user or current_user
                return bool(has_permission(u, perm))
            except Exception:
                return False

        def j_is_admin_like(user=None) -> bool:
            try:
                u = user or current_user
                return bool(is_admin_like(u))
            except Exception:
                return False

        def j_has_permission(user, perm: str) -> bool:
            try:
                return bool(has_permission(user, perm))
            except Exception:
                return False

        return {
            "can": j_can,
            "is_admin_like": j_is_admin_like,
            "has_permission": j_has_permission
        }

    # Optional: Skopje time filter
    from datetime import timezone as _tzmod
    from zoneinfo import ZoneInfo as _ZoneInfo

    def _app_tz():
        try:
            return _ZoneInfo(app.config.get("APP_TIMEZONE", "Europe/Skopje"))
        except Exception:
            return _ZoneInfo("Europe/Skopje")

    def _local_dt(dt):
        if dt is None:
            return ""
        if getattr(dt, "tzinfo", None) is None:
            dt = dt.replace(tzinfo=_tzmod.utc)
        return dt.astimezone(_app_tz())

    app.jinja_env.filters["local_dt"] = _local_dt

    # ---------- Login loader ----------
    from .models import User  # after db.init_app

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            return db.session.get(User, int(user_id))
        except Exception:
            return None

    app.config.setdefault("ATTACHMENTS_DIR", os.path.join(app.root_path, "attachments"))

    # ---------- Core Blueprints ----------
    from .auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix="/auth")

    from .dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")

    from .users import bp as users_bp
    app.register_blueprint(users_bp)

    from .departments import bp as departments_bp
    app.register_blueprint(departments_bp, url_prefix="/departments")

    from .drive import bp as drive_bp
    app.register_blueprint(drive_bp)

    from .notes import bp as notes_bp
    app.register_blueprint(notes_bp, url_prefix="/notes")

    from .plan import bp as plan_bp
    app.register_blueprint(plan_bp)

    from .attachments import bp as attachments_bp
    app.register_blueprint(attachments_bp)

    from app.war import war_bp
    app.register_blueprint(war_bp)

    from .tickets import bp as tickets_bp
    app.register_blueprint(tickets_bp, url_prefix="/tickets")

    # Email feature
    init_email(app)

    # Callendar
    from .callendar import bp as callendar_bp
    app.register_blueprint(callendar_bp)

    # Notifications
    from app.notifications import bp as notifications_bp
    app.register_blueprint(notifications_bp, url_prefix="/notifications")

    # ---------- FEED STACK (order-safe) ----------
    try:
        # Import routes package so all route_*.py attach to the shared bp
        from app.feed import bp as feed_api_bp
        from app.feed import routes as _feed_routes  # noqa: F401  (imports all modules)
        app.register_blueprint(feed_api_bp)
        print(">>> Feed blueprint registered successfully.")
    except Exception as e:
        app.logger.exception("❌ Failed to register Feed blueprint: %s", e)

    # Feed notifications API (DB-triggered)
    try:
        from app.notifications.feed_notifications import bp as feed_notify_api_bp
        app.register_blueprint(feed_notify_api_bp)
    except Exception as e:
        app.logger.warning("Feed notify API not loaded: %s", e)

    # Static notifications widget
    try:
        from app.notifications.feed_widget import bp as feed_notify_widget_bp
        app.register_blueprint(feed_notify_widget_bp)
    except Exception as e:
        app.logger.warning("Feed widget not loaded: %s", e)

    # Refs (sectors & users)
    from app.refs import api as _refs_api      # loads routes onto its bp
    from app.refs import bp as refs_api_bp
    app.register_blueprint(refs_api_bp)

    # ---------- Uploader API + public file serving (ORDER MATTERS) ----------
    # Import the module FIRST so all @bp.* decorators execute before registration.
    import app.uploader.api as _uploader_api  # noqa: F401

    from app.uploader import bp as uploader_bp
    from app.uploader.api import public_bp as uploads_public_bp

    app.register_blueprint(uploader_bp)
    app.register_blueprint(uploads_public_bp)

    # Realtime SSE
    from app.realtime import api as _realtime_api
    from app.realtime import bp as realtime_bp
    app.register_blueprint(realtime_bp)

    # Analytics API
    from app.analytics_feed import api as _feed_analytics_api
    from app.analytics_feed import bp as feed_analytics_bp
    app.register_blueprint(feed_analytics_bp)

    # Static analytics dashboard
    from app.analytics_dashboard import bp as analytics_dashboard_bp
    app.register_blueprint(analytics_dashboard_bp)

    # Static post drawer
    from app.feed_post_drawer import bp as feed_post_drawer_bp
    app.register_blueprint(feed_post_drawer_bp)

    # Feed Search (API + static)
    from app.feed_search import api as _feed_search_api
    from app.feed_search import bp as feed_search_bp
    app.register_blueprint(feed_search_bp)

    from app.users.api_avatar import bp as account_api_bp
    app.register_blueprint(account_api_bp)

    # ---------- Root ----------
    @app.route("/")
    def _root():
        return redirect(
            url_for("dashboard.index")
            if current_user.is_authenticated
            else url_for("auth.login")
        )

    # ---------- Runtime dirs + schema ensure ----------
    with app.app_context():
        _ensure_perm_schema()
        Path(app.config["TICKETS_UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
        Path(app.config["CALLENDAR_UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
        Path(app.config["UPLOAD_ROOT"]).mkdir(parents=True, exist_ok=True)

        if db.engine.dialect.name == "sqlite":
            try:
                from app.dev_schema import ensure_sqlite_schema
                ensure_sqlite_schema(db.metadata)
            except Exception as e:
                app.logger.error("SQLite auto-migrate (startup) failed: %s", e)

    # ---------- Reminders: start background scheduler ----------
    def _start_reminder_scheduler():
        if not app.config.get("REMINDERS_SCHED_ENABLED", True):
            app.logger.info("Reminders scheduler disabled via config.")
            return
        if BackgroundScheduler is None:
            app.logger.warning("APScheduler not installed; reminders scheduler disabled. Run: pip install APScheduler")
            return
        if app.extensions.get("reminder_scheduler"):
            return  # already started

        sched = BackgroundScheduler(daemon=True, timezone="UTC")
        interval = int(app.config.get("REMINDERS_INTERVAL_MINUTES", 1))

        def _run_reminders_job():
            with app.app_context():
                try:
                    from app.callendar.reminders import enqueue_due_reminders
                    sent = enqueue_due_reminders(
                        scan_horizon_minutes=int(app.config.get("REMINDERS_SCAN_HORIZON_MIN", 120)),
                        skew_seconds=int(app.config.get("REMINDERS_SKEW_SECONDS", 90)),
                        catchup_seconds=int(app.config.get("REMINDERS_CATCHUP_SECONDS", 300)),
                    )
                    app.logger.info("[reminders] sent=%s", sent)
                except Exception:
                    app.logger.exception("[reminders] job failed")
                finally:
                    try:
                        db.session.remove()
                    except Exception:
                        pass

        sched.add_job(
            _run_reminders_job,
            "interval",
            minutes=interval,
            id="reminders-job",
            replace_existing=True,
        )
        sched.start()
        app.extensions["reminder_scheduler"] = sched
        app.logger.info("Reminders scheduler started (every %s minute(s))", interval)

    @app.before_request
    def _kick_scheduler_once():
        try:
            _start_reminder_scheduler()
        except Exception:
            app.logger.exception("Failed to start reminders scheduler")

    return app
