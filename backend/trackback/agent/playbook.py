"""The versioned playbook (SPEC.md Section 7). Behaviour is reproducible because decisions come from these rules, and lessons change them.

v1 deliberately carries four weaknesses real junior accountants have (the planted agent mistakes in the answer key):
1. materiality: only the 5% of annual pretax rule, rollover method only, no qualitative tests, no aggregation
2. classification: any invoice for a closed period's service is an error, without checking when the information arrived
3. posting: correcting entries are dated in the original period
4. routing: lender documents go to the controller instead of the CFO
Approved lessons turn each weakness into a check (playbook v2).
"""
from __future__ import annotations

import copy

V1 = {
    "version": "v1",
    "materiality": {"methods": ["rollover"], "qualitative": False, "aggregate": False, "rule": "five_percent_pretax"},
    "classification": {"by_knowable_at": False, "closed_period_invoice": "error"},
    "posting": {"period": "original"},
    "routing": {"lender_document": "controller", "journal_entry": "controller", "comp_offset": "hr", "tax_offset": "controller", "vendor_credit": "ap", "misstatement_log": "controller"},
    "guidance": [],
}

# the four lessons the agent can learn, as playbook patches (each one is a check, not guidance text)
LESSON_PATCHES = {
    "materiality_framework": {"path": ["materiality"], "value": {"methods": ["rollover", "iron_curtain"], "qualitative": True, "aggregate": True, "rule": "sab108_sab99"},
                              "rule": "Never conclude immaterial without both SAB 108 methods, the qualitative tests (SAB 99) and aggregation with the misstatement log."},
    "classify_by_knowable_at": {"path": ["classification"], "value": {"by_knowable_at": True, "closed_period_invoice": "use_replay"},
                                "rule": "Classify by when the information arrived (Replay), not by the service period: an invoice that arrived after the close is a change in estimate."},
    "post_in_open_period": {"path": ["posting"], "value": {"period": "open_with_orig_period"},
                            "rule": "Post corrections in the open period with orig_period set; never date an entry in a locked period."},
    "lender_documents_to_cfo": {"path": ["routing", "lender_document"], "value": "cfo",
                                "rule": "Lender documents (corrected certificate, lender notice) go to the CFO, the only signatory under the credit agreement."},
    # an over-generalization a person might write after X3; the regression gate should refuse it (it breaks the invoices that arrived before the close)
    "closed_period_invoices_are_estimates": {"path": ["classification"], "value": {"by_knowable_at": False, "closed_period_invoice": "estimate_change"},
                                             "rule": "Never restate for an invoice that covers a closed period: treat it as a change in estimate."},
}
ROLE_PERSON = {"controller": "dana", "cfo": "sam", "hr": "lena", "ap": "marco", "assistant_controller": "priya"}


def apply(base: dict, lesson_keys: list[str], version: str | None = None) -> dict:
    pb = copy.deepcopy(base)
    for k in lesson_keys:
        p = LESSON_PATCHES[k]
        tgt = pb
        for step in p["path"][:-1]:
            tgt = tgt[step]
        tgt[p["path"][-1]] = copy.deepcopy(p["value"])
        pb["guidance"].append(p["rule"])
    pb["version"] = version or (f"{base['version']}+" + "+".join(lesson_keys) if lesson_keys else base["version"])
    pb["lessons"] = list(lesson_keys)
    return pb


def current(lesson_keys: list[str] | None = None) -> dict:
    """The live playbook: v1 plus every approved, gate-passed lesson."""
    if lesson_keys is None:
        from ..core import db
        lesson_keys = [r["mistake_kind"] for r in db.q("SELECT mistake_kind FROM lessons WHERE status='active' AND world='tidewall' ORDER BY decided_at")]
    return apply(V1, lesson_keys, "v2" if set(GOOD) <= set(lesson_keys) else None) if lesson_keys else copy.deepcopy(V1)


GOOD = ["materiality_framework", "classify_by_knowable_at", "post_in_open_period", "lender_documents_to_cfo"]
