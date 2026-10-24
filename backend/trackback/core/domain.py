"""The one interface a pack implements. The core never imports a pack; packs register themselves by name, and the module path comes from config."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DomainPack(Protocol):
    name: str

    def is_material(self, node: dict, old_value: float | None, new_value: float | None, conclusions: dict | None) -> tuple[bool, str]:
        """(material, reason). reason in: early_cutoff, below_materiality, conclusion_unchanged, conclusion_flipped, value_changed, supporter_retracted."""
        ...

    def classify_correction(self, correction: dict, knowable_at: str, original_artifact_time: str | None) -> str:
        """estimate | error | fact_update, from 'when did this fact first exist?' versus when the original artifact was made."""
        ...

    def unaffected_reason(self, node: dict, change: dict) -> str | None:
        """A structural or policy reason the node is untouched by this change (different_period, different_line_item, estimate_change, ...), or None."""
        ...

    def compensation_for(self, action: dict) -> dict:
        """From a fixed catalog: {kind, approver, description}."""
        ...

    def approver_for(self, action_or_compensation: dict) -> str:
        ...

    def can_post(self, entry: dict) -> tuple[bool, str]:
        """Period lock check for a ledger-style effect."""
        ...

    def tie_out_checks(self, artifact_versions: list[dict]) -> list[dict]:
        """Cross-agent consistency checks on reworked outputs: [{name, ok, detail}]."""
        ...

    def correction_verdict(self, correction: dict, impact: float, flips: bool, prior_period: bool) -> str:
        """Domain-level classification of a whole correction (finance: log | book_oop | little_r | big_r | escalate)."""
        ...

    def execute_effect(self, action: dict, params: dict, ts: str, approval_id: str | None) -> dict:
        """Apply an approved action's effect in the domain's system of record; returns {effect_spec, observed_effect}."""
        ...


_REGISTRY: dict[str, Any] = {}
_ACTIVE: str = "finance"


def register(pack: Any) -> None:
    _REGISTRY[pack.name] = pack


def set_active(name: str) -> None:
    global _ACTIVE
    _ACTIVE = name


def get_domain(name: str | None = None) -> Any:
    key = name or _ACTIVE
    if key not in _REGISTRY:
        import importlib
        from .. import config
        importlib.import_module(config.PACK_MODULES[key])  # packs register on import; the core only knows the name
    return _REGISTRY[key]
