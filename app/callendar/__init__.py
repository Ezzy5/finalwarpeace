# app/callendar/__init__.py
from flask import Blueprint
from datetime import datetime, date
from zoneinfo import ZoneInfo

bp = Blueprint(
    "callendar",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/static/callendar",
    url_prefix="/callendar",
)

# ---------- Robust parsing helpers ----------
def _parse_any_dt(x):
    """Return aware UTC datetime from datetime/str/epoch; None if empty/invalid."""
    if x is None or x == "":
        return None
    # Already a datetime?
    if isinstance(x, datetime):
        d = x
        # If naive, assume UTC
        if d.tzinfo is None:
            d = d.replace(tzinfo=ZoneInfo("UTC"))
        else:
            d = d.astimezone(ZoneInfo("UTC"))
        return d
    # A date (no time): treat as midnight UTC
    if isinstance(x, date):
        return datetime(x.year, x.month, x.day, tzinfo=ZoneInfo("UTC"))
    # Epoch (seconds or ms)
    if isinstance(x, (int, float)):
        # Heuristic: <1e12 => seconds; else ms
        ms = int(x * 1000) if x < 1e12 else int(x)
        return datetime.fromtimestamp(ms / 1000, tz=ZoneInfo("UTC"))
    # Strings: try ISO forms
    if isinstance(x, str):
        s = x.strip()
        if not s:
            return None
        # Replace space between date/time with 'T'
        if len(s) >= 16 and s[10] == " ":
            s = s[:10] + "T" + s[11:]
        # If no TZ suffix, assume UTC
        if not (s.endswith("Z") or s.endswith("z") or
                any(sign in s[-6:] for sign in ("+", "-"))):
            s = s + "Z"
        try:
            # Python's fromisoformat handles +00:00; handle 'Z' by replacing
            iso = s.replace("Z", "+00:00").replace("z", "+00:00")
            d = datetime.fromisoformat(iso)
            if d.tzinfo is None:
                d = d.replace(tzinfo=ZoneInfo("UTC"))
            else:
                d = d.astimezone(ZoneInfo("UTC"))
            return d
        except Exception:
            return None
    # Unknown type
    return None

# ---------- Jinja filters ----------
@bp.app_template_filter("tz")
def tz_filter(x, tzname: str = "Europe/Skopje"):
    """
    Convert various datetime representations to the given timezone for display.
    Accepts datetime/date/ISO string/epoch. Naive datetimes are assumed UTC.
    Returns an aware datetime in the target TZ, or None if invalid.
    """
    d_utc = _parse_any_dt(x)
    if d_utc is None:
        return None
    return d_utc.astimezone(ZoneInfo(tzname))

@bp.app_template_filter("tzfmt")
def tzfmt_filter(x, fmt: str = "%Y-%m-%d %H:%M", tzname: str = "Europe/Skopje") -> str:
    """
    Format a datetime-like value in the given timezone.
    Safe for strings/epochs/naive/aware datetimes.
    """
    d_local = tz_filter(x, tzname)
    return "" if d_local is None else d_local.strftime(fmt)

# Keep imports after blueprint & filters
from .routes import views, api  # noqa: E402, F401
from .routes import ticket_details  # noqa: E402, F401
from .routes import fragment  # noqa: E402, F401
from .routes import cron  # noqa: E402, F401
