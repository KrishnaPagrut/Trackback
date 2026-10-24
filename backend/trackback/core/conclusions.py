"""Stated conclusions on an artifact (thresholds, signs, tiers, display precision) evaluated for a value. Domain-neutral."""
from __future__ import annotations

from typing import Any


def conclusion_state(value: float | None, conclusions: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None or not conclusions:
        return None
    st: dict[str, Any] = {}
    if "covenant_max" in conclusions:
        st["covenant_compliant"] = value <= float(conclusions["covenant_max"]) + 1e-9
    if "target" in conclusions:
        st["above_target"] = value > float(conclusions["target"])
    if "sign" in conclusions:
        st["sign"] = "up" if value > 0 else ("down" if value < 0 else "flat")
    if "min_buffer" in conclusions:
        st["buffer_ok"] = value >= float(conclusions["min_buffer"])
    if "ratio_min" in conclusions:
        st["ratio_met"] = value >= float(conclusions["ratio_min"])
    if "max" in conclusions:
        st["within_max"] = value <= float(conclusions["max"])
    if "display_rounding" in conclusions:
        r = float(conclusions["display_rounding"])
        st["display"] = round(value / r) if r else value
    if "display_decimals" in conclusions:
        st["display"] = round(value, int(conclusions["display_decimals"]))
    if "tiers" in conclusions:
        st["tier"] = sum(1 for t in conclusions["tiers"] if value >= float(t))
    return st or None


def boolean_part(state: dict | None) -> dict:
    return {k: v for k, v in (state or {}).items() if k != "display"}
