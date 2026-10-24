"""Re-rendering a figure in an agent's line from Trackback's new value (never computed by a model)."""
from __future__ import annotations

import re


def render(item: dict, new) -> str:
    fields = item.get("fields") or {}
    old = item.get("prior_output_excerpt") or ""
    if fields.get("display_unit") == "K":
        return re.sub(r"\$[\d,]+K", f"${new / 1000:,.0f}K", old, count=1)
    if isinstance(new, (int, float)):
        return re.sub(r"\$[\d,]+(\.\d+)?", f"${new:,.0f}", old, count=1) if "$" in old else f"{old} [now {new:,.2f}]"
    return old
