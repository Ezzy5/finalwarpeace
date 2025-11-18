# app/utils/tz.py
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
try:
    # Py3.9+
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo  # type: ignore

from flask import current_app


# -------------------------------------------------
# Core timezone helpers
# -------------------------------------------------

def app_tz_name() -> str:
    """
    Returns the application timezone name. Defaults to Europe/Skopje.
    """
    try:
        return current_app.config.get("APP_TIMEZONE", "Europe/Skopje")
    except Exception:
        return "Europe/Skopje"


def app_tz() -> ZoneInfo:
    """ZoneInfo instance for the app timezone."""
    return ZoneInfo(app_tz_name())


def now_local() -> datetime:
    """Aware datetime in the app's local timezone."""
    return datetime.now(app_tz())


def now_utc_naive() -> datetime:
    """UTC time as naive datetime (used for DB storage / comparisons)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# -------------------------------------------------
# Conversions
# -------------------------------------------------

def to_utc_naive(dt: datetime) -> datetime:
    """
    Convert any datetime to UTC-naive, with the rule:
      - If dt is naive: treat it as LOCAL (Europe/Skopje),
                        convert to UTC, then drop tzinfo
      - If dt is aware: convert to UTC, then drop tzinfo
    """
    if dt.tzinfo is None:
        # interpret naive as local
        dt = dt.replace(tzinfo=app_tz())
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def from_utc_naive_to_local(dt_utc_naive: datetime) -> datetime:
    """
    Given a UTC-naive datetime (as stored in DB),
    return an AWARE datetime in local timezone.
    """
    if dt_utc_naive.tzinfo is not None:
        # normalize, just in case
        dt_utc_naive = dt_utc_naive.astimezone(timezone.utc).replace(tzinfo=None)
    dt_aware_utc = dt_utc_naive.replace(tzinfo=timezone.utc)
    return dt_aware_utc.astimezone(app_tz())


def iso_utc_z(dt: datetime) -> str:
    """
    Return ISO 8601 string in UTC with 'Z'.
    - If dt is naive ⇒ ASSUME it is UTC (common for stored datetimes)
      and attach UTC tz before serializing.
    - If dt is aware ⇒ convert to UTC then serialize.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    s = dt.isoformat()
    # Normalize +00:00 to Z
    if s.endswith("+00:00"):
        s = s[:-6] + "Z"
    return s


# -------------------------------------------------
# Debug helpers (optional)
# -------------------------------------------------

def debug_pack_now() -> dict:
    """
    Quick snapshot you can jsonify to confirm your app timezone plumbing.
    """
    local = now_local()
    utc_naive = now_utc_naive()
    utc_aware = utc_naive.replace(tzinfo=timezone.utc)
    return {
        "app_tz": app_tz_name(),
        "now_local": local.isoformat(),            # e.g. 2025-10-15T14:05:00+02:00
        "now_utc_naive": utc_naive.isoformat(),    # e.g. 2025-10-15T12:05:00
        "now_utc_Z": iso_utc_z(utc_aware),         # e.g. 2025-10-15T12:05:00Z
    }
