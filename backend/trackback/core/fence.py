"""Pre-execution fence (PlanFence idea): before an action executes, every transitive supporter must still be the current version."""
from __future__ import annotations

from .. import config
from . import db, graph


def check(artifact_id: str, version: int | None = None, _seen: set | None = None) -> list[dict]:
    """Return a list of stale supporters (empty = fence passes).

    Direct claim supporters must still carry their recorded value. Artifact supporters must be the current version with a
    live status; their own supporters are covered by propagation (a superseded claim with a different value already produced a
    finding and a status change on that artifact), so the check is one level deep on artifacts and exact on claims."""
    _seen = _seen if _seen is not None else set()
    cur = db.artifact_current(artifact_id) if version is None else db.q1("SELECT * FROM artifacts WHERE artifact_id=? AND version=?", (artifact_id, version))
    if cur is None:
        return [{"kind": "artifact", "id": artifact_id, "problem": "missing"}]
    key = (artifact_id, cur["version"])
    if key in _seen:
        return []
    _seen.add(key)
    stale: list[dict] = []
    for e in graph.supporters_of(artifact_id, cur["version"]):
        if e["dep_kind"] == "control":
            continue  # a compensation points at the stale action it compensates, by design
        if e["supporter_kind"] == "claim":
            cv = db.q1("SELECT * FROM claim_versions WHERE claim_version_id=?", (e["supporter_version"],))
            if cv is None or cv["tx_to"] != config.TX_CURRENT:
                newer = db.claim_version_current(e["supporter_id"])
                if cv is not None and newer is not None and cv["value_num"] is not None and newer["value_num"] is not None and abs(cv["value_num"] - newer["value_num"]) < 1e-9:
                    continue  # re-issued with an identical value: not stale
                stale.append({"kind": "claim", "id": e["supporter_id"], "version": e["supporter_version"], "problem": "superseded",
                              "current": newer["claim_version_id"] if newer else None, "old_value": cv["value_num"] if cv else None, "new_value": newer["value_num"] if newer else None})
        else:
            latest = db.artifact_current(e["supporter_id"])
            if latest is None or str(latest["version"]) != str(e["supporter_version"]) or latest["status"] in ("stale", "superseded", "unprovable"):
                stale.append({"kind": "artifact", "id": e["supporter_id"], "version": e["supporter_version"], "problem": "superseded_or_stale",
                              "current": latest["version"] if latest else None})
            elif latest["kind"] == "sentence":
                fm = figure_mismatch(latest)
                if fm:
                    stale.append({"kind": "artifact", "id": e["supporter_id"], "version": e["supporter_version"], **fm})
            # artifact supporter is current and live: covered by propagation
    return stale


def guard_execute(action_id: str, ts: str) -> tuple[bool, list[dict]]:
    """Run the fence for an action. Blocks (state=blocked) and logs when any supporter is stale."""
    a = db.q1("SELECT * FROM actions WHERE action_id=?", (action_id,))
    stale = check(a["artifact_id"])
    if stale:
        graph.set_action_state(action_id, "blocked", ts)
        db.log_event("fence_block", f"Pre-execution fence blocked {action_id}: {len(stale)} stale supporter(s)", actor="trackback:fence", ts=ts,
                     detail={"action_id": action_id, "stale": stale})
        db.commit()
        return False, stale
    return True, []


def figure_mismatch(sentence_row) -> dict | None:
    """The extra-zero check: a sentence that cites a numeric artifact must show that figure. If the figure is absent and the
    sentence instead shows the same digits at another power of ten (500 for a cited 50), the sentence misstates what it rests on.
    Deliberately narrow (cited |value| >= 10, identical digit string, different magnitude) so rounding and ratios never trip it."""
    import json
    import re
    from .judge import _displays
    fields = json.loads(sentence_row["fields_json"]) if sentence_row["fields_json"] else {}
    content = sentence_row["content"] or ""
    nums = [float(x.replace(",", "")) for x in re.findall(r"(?<![\d.])\d[\d,]*(?:\.\d+)?(?![\d])", content)]
    digits = lambda x: (f"{x:.6f}".replace(".", "").strip("0") or "0")  # noqa: E731
    for aid in fields.get("artifacts") or []:
        cur = db.artifact_current(aid)
        if cur is None or cur["value_num"] is None or abs(cur["value_num"]) < 10:
            continue
        v = cur["value_num"]
        if any(re.search(r"(?<![\d.])" + re.escape(d) + r"(?!\.?\d)", content) for d in _displays(v)):
            continue  # the cited figure is shown
        for n in nums:
            if n != v and digits(n) == digits(v):
                return {"problem": "figure_mismatch", "cited_artifact": aid, "cited_value": v, "stated": n,
                        "message": f"states {n:g} but rests on {aid} = {v:g} (same digits, different magnitude)"}
    return None
