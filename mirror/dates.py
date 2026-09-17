from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

_ISO = re.compile(r"^(\d{4})-(\d{2})(?:-(\d{2}))?")


def parse_date(value: Any) -> date | None:
    """Best-effort date parsing across the formats providers actually emit."""
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        try:
            return datetime.utcfromtimestamp(ts).date()
        except (OverflowError, OSError, ValueError):
            return None
    s = str(value).strip()
    m = _ISO.match(s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3) or 1)
        try:
            return date(y, mo, d)
        except ValueError:
            return None
    for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%b %Y", "%B %Y", "%b %d, %Y", "%B %d, %Y", "%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, 1)


def months_between(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month)


def month_range(end: date, count: int) -> list[str]:
    """`count` month keys ending at `end`'s month, oldest first."""
    start = add_months(date(end.year, end.month, 1), -(count - 1))
    return [month_key(add_months(start, i)) for i in range(count)]
