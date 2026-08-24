from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from .schema import SchemaError, validate_strict


STATE_SCHEMA: dict[str, Any] = {
    "type": "object", "additionalProperties": False,
    "required": ["schema_version", "orchestration_run_id", "project", "current_purpose", "current_gates", "frozen_decisions", "routing_contract", "scope_freeze", "latest_codex_task", "latest_codex_report", "user_decisions", "unresolved_items", "branches"],
    "properties": {
        "schema_version": {"type": "string", "enum": ["1"]},
        "orchestration_run_id": {"type": "string", "maxLength": 200},
        "project": {"type": "string", "maxLength": 200},
        "current_purpose": {"type": "string", "maxLength": 12_000},
        "current_gates": {"type": "array", "items": {"type": "string", "maxLength": 200}},
        "frozen_decisions": {"type": "array", "items": {"type": "string", "maxLength": 12_000}},
        "routing_contract": {"type": "object", "additionalProperties": True},
        "scope_freeze": {"type": "object", "additionalProperties": True},
        "latest_codex_task": {"type": "object", "additionalProperties": True},
        "latest_codex_report": {"type": "object", "additionalProperties": True},
        "user_decisions": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        "unresolved_items": {"type": "array", "items": {"type": "string", "maxLength": 12_000}},
        "branches": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
    },
}


def build_initial_state(run_id: str, project: str, purpose: str, *, scope_freeze: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema_version": "1", "orchestration_run_id": run_id, "project": project,
        "current_purpose": purpose, "current_gates": ["HISTORICAL_FIXTURE_REQUIRED"],
        "frozen_decisions": ["LIVE_OPENAI_CALL=OFF", "CODEX_AUTO_EXECUTION=OFF", "NO_DISPATCH"],
        "routing_contract": {"reviewer": "GPT/Sol", "model_call": "OPENAI_ORCHESTRATION_API_KEY_ONLY"},
        "scope_freeze": scope_freeze or {"local_only": True, "btest_write": False, "deployment": False},
        "latest_codex_task": {}, "latest_codex_report": {}, "user_decisions": [],
        "unresolved_items": ["Approved historical Codex report and manual baseline pair"], "branches": [],
    }


def validate_state(state: dict[str, Any]) -> None:
    validate_strict(state, STATE_SCHEMA)


def line_numbered_content(content: str) -> str:
    return "\n".join(f"{index}: {line}" for index, line in enumerate(content.splitlines(), 1))


def evidence_record(source: str, content: str) -> dict[str, str]:
    return {
        "source": source,
        "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "line_numbered_content": line_numbered_content(content),
    }
