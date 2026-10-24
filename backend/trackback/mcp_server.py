"""MCP server exposing Trackback's three read tools (get_document, search_claims, get_claim) over stdio with the official
Python MCP SDK. Every read is pinned to a run (TRACKBACK_RUN_ID) and goes through the Memento service, so provenance is
captured exactly as it is for the in-process agents. Run: backend/.venv/bin/python -m trackback.mcp_server"""
from __future__ import annotations

import json
import os

from mcp.server.mcpserver import MCPServer

from . import config, db, tools

mcp = MCPServer("trackback")
_ctx: tools.ToolContext | None = None


def ctx() -> tools.ToolContext:
    global _ctx
    if _ctx is None:
        run_id = os.environ.get("TRACKBACK_RUN_ID", "mcp_session")
        row = db.q1("SELECT pinned_at, agent FROM runs WHERE run_id=?", (run_id,))
        pin = row["pinned_at"] if row else os.environ.get("TRACKBACK_PIN", config.DEMO_NOW)
        if row is None:
            db.insert("runs", {"run_id": run_id, "agent": "mcp", "task": "mcp session", "pinned_at": db.norm_ts(pin), "mode": "mcp", "status": "running",
                               "started_at": db.norm_ts(pin), "finished_at": None, "turns": 0, "note": None})
            db.commit()
        _ctx = tools.ToolContext(run_id, pin, row["agent"] if row else "mcp")
    return _ctx


@mcp.tool()
def get_document(doc_id: str) -> str:
    """Fetch a source document as of the session's pinned time (Memento). Later versions are refused with the pin and both timestamps."""
    return json.dumps(ctx().get_document(doc_id), default=str)


@mcp.tool()
def search_claims(query: str, entity: str | None = None, line_item: str | None = None, period: str | None = None) -> str:
    """Search claims visible as of the pin."""
    return json.dumps(ctx().search_claims(query, entity, line_item, period), default=str)


@mcp.tool()
def get_claim(claim_id: str) -> str:
    """Fetch one claim (as of the pin) by id."""
    return json.dumps(ctx().get_claim(claim_id), default=str)


if __name__ == "__main__":
    mcp.run()
