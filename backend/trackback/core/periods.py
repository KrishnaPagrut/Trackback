"""Period helpers shared by the core and packs (fiscal periods are a generic notion: month, quarter, half, year, day, week)."""
from __future__ import annotations

from . import claims as CL


def period_end(period: str | None) -> str | None:
    if not period or period[5:6] == "W":
        return None
    return CL.period_bounds(period)[1] or None


def overlaps(period: str | None, month: str) -> bool:
    if not period or not month or period[5:6] == "W":
        return False
    ps, pe = CL.period_bounds(period)
    return ps[:7] <= month <= pe[:7]
