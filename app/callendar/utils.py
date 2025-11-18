# app/callendar/utils.py
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Tuple


__all__ = ["calc_period_bounds"]


def calc_period_bounds(
    period: Optional[str],
    now: datetime,
    next_n_days: Optional[int] = None,
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Returns (start, end) datetime bounds for a given period key.
    If a bound is None, it means open-ended.

    Supported period keys (case-insensitive):
      - "ANY"
      - "YESTERDAY"
      - "TODAY"
      - "TOMORROW"
      - "THIS_WEEK"      (Mon–Sun)
      - "THIS_MONTH"
      - "THIS_QUARTER"   (Q1: Jan–Mar, Q2: Apr–Jun, ...)
      - "NEXT_N"         (uses next_n_days, default 7 if invalid)
      - "THIS_YEAR"
    """
    key = (period or "ANY").upper()

    def start_of_week(d: datetime) -> datetime:
        # Monday = 0
        w = (d.weekday())  # 0..6
        return (d - timedelta(days=w)).replace(hour=0, minute=0, second=0, microsecond=0)

    def start_of_month(d: datetime) -> datetime:
        return d.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def start_of_quarter(d: datetime) -> datetime:
        q_month = ((d.month - 1) // 3) * 3 + 1
        return d.replace(month=q_month, day=1, hour=0, minute=0, second=0, microsecond=0)

    def start_of_year(d: datetime) -> datetime:
        return d.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    if key == "ANY":
        return None, None

    if key == "YESTERDAY":
        y = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return y, y + timedelta(days=1)

    if key == "TODAY":
        t0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return t0, t0 + timedelta(days=1)

    if key == "TOMORROW":
        tm = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return tm, tm + timedelta(days=1)

    if key == "THIS_WEEK":
        s = start_of_week(now)
        return s, s + timedelta(days=7)

    if key == "THIS_MONTH":
        s = start_of_month(now)
        # Move to first of next month safely
        if s.month == 12:
            e = s.replace(year=s.year + 1, month=1)
        else:
            e = s.replace(month=s.month + 1)
        return s, e

    if key == "THIS_QUARTER":
        s = start_of_quarter(now)
        # Advance by 3 months (safe across year boundary)
        m = s.month + 3
        y = s.year + (m - 1) // 12
        m = ((m - 1) % 12) + 1
        e = s.replace(year=y, month=m)
        return s, e

    if key == "NEXT_N":
        n = int(next_n_days or 0)
        if n < 1:
            n = 7
        s = now
        e = now + timedelta(days=n)
        return s, e

    if key == "THIS_YEAR":
        s = start_of_year(now)
        e = s.replace(year=s.year + 1)
        return s, e

    # Unknown key -> open
    return None, None
