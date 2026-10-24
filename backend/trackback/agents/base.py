"""Tool-use loop over the Messages API through the cache gateway. One run = one pinned_at. Max 25 tool turns."""
from __future__ import annotations

import json
import uuid
from typing import Any, Callable

from .. import config, db, tools
from ..llm import gateway
from . import prose

SEATS = {
    "close_accountant": "Senior Accountant, Close and Reporting at Tidewall Climbing Co. You run the monthly and quarterly close: accruals, true-ups, out-of-period entries, the misstatement log, and correcting entries. You propose; the Controller (Dana Ortiz) approves. You never approve your own entries.",
    "reporting_analyst": "Reporting / FP&A Analyst at Tidewall Climbing Co. You build the board deck (KPI tiles plus commentary), budget-versus-actuals lines, flux commentary and the 13-week cash forecast.",
    "covenant_comp": "Covenant and Compensation analyst at Tidewall Climbing Co. You compute TTM Adjusted EBITDA and net leverage from the credit agreement's definition, draft the quarterly compliance certificate (sent only after the CFO signs), compute GM bonuses and sales commissions (paid only after HR or VP Sales plus the Controller approve), and the quarterly estimated tax payment.",
    # Lyft, Feb 2024 (real-world scenario): the company's own finance team, then the outside world that builds on what it publishes
    "lyft_fpa": "FP&A analyst at Lyft. You own the guidance model: the Adjusted EBITDA margin bridge (as a percentage of Gross Bookings) and the basis points of expansion it implies.",
    "lyft_ir": "Reporting and Investor Relations analyst at Lyft. You draft the earnings release highlights and the CFO's prepared remarks from the close pack and the FP&A model, and propose publication for the CFO's sign-off.",
    "lyft_disclosure": "Disclosure counsel's analyst at Lyft. You prepare the Form 8-K that furnishes the earnings release, resting on the approved release.",
    "street_analyst": "Sell-side analyst outside Lyft. You read what the company publishes, write flash notes with the implied numbers, and route orders to the PM.",
    "newsroom": "Markets newsroom outside Lyft. You write the headline and the story from the company's release and publish them.",
}

RULES = ("Rules. (1) You can only see data through your tools; every read is pinned to this run's date and anything published later is refused. "
         "(2) Numbers are produced ONLY via emit_number: give a formula over inputs you have read (claim ids) or produced (artifact ids). Never type a computed number into prose. "
         "(3) Sentences are produced ONLY via emit_sentence with the claim ids they rest on. "
         "(4) Read the company's policies as claims (materiality memo, credit agreement, comp plan, company policies) rather than assuming them. "
         "(5) When timing or materiality is ambiguous, call route_to_human. (6) Call finish when every required output exists.")


def run_agent(*, run_id: str, agent: str, task: str, pinned_at: str, required_outputs: str, script: list[dict] | None = None,
              on_tool: Callable[[str, dict, dict], None] | None = None) -> dict:
    pinned = db.norm_ts(pinned_at)
    if db.q1("SELECT 1 FROM runs WHERE run_id=?", (run_id,)) is None:
        db.insert("runs", {"run_id": run_id, "agent": agent, "task": task, "pinned_at": pinned, "mode": gateway.mode(), "status": "running",
                           "started_at": pinned, "finished_at": None, "turns": 0, "note": None})
        db.commit()
    ctx = tools.ToolContext(run_id, pinned, agent, prose_writer=prose.write_sentence)
    system = f"Seat: {SEATS[agent]}\n\n{RULES}\n\nToday is {pinned[:10]} (run pinned at {pinned})."
    messages: list[dict] = [{"role": "user", "content": f"Task: {task}\n\nRequired outputs (artifact names are fixed; produce each exactly once):\n{required_outputs}"}]
    scripted = _scripted_provider(script) if script is not None else None
    turns, summary, results = 0, "", []
    while turns < config.MAX_TOOL_TURNS:
        turns += 1
        resp, key, hit = gateway.complete(model=config.AGENT_MODEL, system=system, messages=messages, tools=tools.TOOL_SPECS,
                                          params={"max_tokens": 4096, "effort": "low"}, pinned_at=pinned, scripted=scripted, purpose=f"agent:{run_id}:{turns}")
        content = resp.get("content", [])
        messages.append({"role": "assistant", "content": content})
        tool_uses = [b for b in content if b.get("type") == "tool_use"]
        if not tool_uses or resp.get("stop_reason") == "end_turn":
            break
        tool_results = []
        done = False
        for tu in tool_uses:
            name, args = tu["name"], tu.get("input") or {}
            if isinstance(args, str):
                args = json.loads(args)
            result = ctx.dispatch(name, args, tu.get("id"))
            results.append({"tool": name, "args": args, "result": result})
            if on_tool:
                on_tool(name, args, result)
            tool_results.append({"type": "tool_result", "tool_use_id": tu["id"], "content": db.dumps(result)[:6000], "is_error": "error" in result})
            if name == "finish":
                summary = args.get("summary", ""); done = True
        messages.append({"role": "user", "content": tool_results})
        if done:
            break
    db.get_conn().execute("UPDATE runs SET status=?, finished_at=?, turns=?, note=? WHERE run_id=?", ("done", pinned, turns, summary[:500], run_id))
    db.commit()
    return {"run_id": run_id, "turns": turns, "summary": summary, "produced": dict(ctx.produced), "refusals": ctx.refusals, "results": results}


def _refs(step: dict) -> set[str]:
    a = step["args"]
    out: set[str] = set()
    if step["tool"] == "emit_number":
        out |= set(a["inputs"].values())
    out |= set(a.get("artifact_ids") or []) | set(a.get("supporters") or []) | set(a.get("artifact_ids") or [])
    if step["tool"] == "route_to_human":
        out |= set(a.get("artifact_ids") or [])
    return out


def _scripted_provider(script: list[dict], max_per_turn: int = 12) -> Callable[[dict], dict]:
    """Deterministic provider: emits the work order's tool calls, batching independent steps into one turn (parallel tool use)."""
    state = {"i": 0}

    def provider(request: dict) -> dict:
        i = state["i"]
        if i >= len(script):
            return {"content": [{"type": "text", "text": "Done."}], "stop_reason": "end_turn", "role": "assistant"}
        batch, produced = [], set()
        while i + len(batch) < len(script) and len(batch) < max_per_turn:
            st = script[i + len(batch)]
            if batch and (st["tool"] == "finish" or batch[-1]["tool"] == "finish"):
                break
            if _refs(st) & produced:
                break
            is_read = st["tool"] in ("get_document", "search_claims", "get_claim")
            if batch and is_read != (batch[-1]["tool"] in ("get_document", "search_claims", "get_claim")):
                break
            batch.append(st)
            produced.add(st["args"].get("name", ""))
        state["i"] = i + len(batch)
        blocks = [{"type": "tool_use", "id": f"toolu_{uuid.uuid5(uuid.NAMESPACE_URL, db.dumps(s) + str(i + k)).hex[:12]}", "name": s["tool"], "input": s["args"]} for k, s in enumerate(batch)]
        return {"content": blocks, "stop_reason": "tool_use", "role": "assistant"}

    return provider
