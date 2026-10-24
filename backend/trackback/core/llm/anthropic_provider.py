"""Anthropic Messages API provider (record mode only). Responses are converted to plain dicts for the cache."""
from __future__ import annotations

from typing import Any


def _client():
    import os
    import anthropic
    headers = {}
    ws = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    if ws:  # an organization-level key must name the workspace; a workspace-scoped key needs nothing
        headers["anthropic-workspace-id"] = ws
    return anthropic.Anthropic(default_headers=headers or None)


def call(*, model: str, system: str, messages: list, tools: list | None, params: dict) -> dict:
    client = _client()
    kwargs: dict[str, Any] = {"model": model, "max_tokens": int(params.get("max_tokens", 4096)), "system": system, "messages": messages}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = {"type": "auto"}
    effort = params.get("effort", "low")
    output_config: dict[str, Any] = {"effort": effort}
    if params.get("json_schema"):
        output_config["format"] = {"type": "json_schema", "schema": params["json_schema"]}
    kwargs["output_config"] = output_config
    resp = client.messages.create(**kwargs)
    return resp.model_dump(mode="json")


def call_citations(*, model: str, system: str, blocks: list[dict], instruction: str, params: dict) -> dict:
    """Citations API: each claim is one block of a custom-content document, so content_block_location maps to a claim."""
    client = _client()
    document = {"type": "document", "source": {"type": "content", "content": [{"type": "text", "text": b["text"]} for b in blocks]},
                "title": "claims", "citations": {"enabled": True}}
    resp = client.messages.create(model=model, max_tokens=int(params.get("max_tokens", 1024)), system=system,
                                  messages=[{"role": "user", "content": [document, {"type": "text", "text": instruction}]}],
                                  output_config={"effort": params.get("effort", "low")})
    return resp.model_dump(mode="json")
