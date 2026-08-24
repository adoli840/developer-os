from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .gate import validate_review_output
from .preflight import PreflightResult
from .state import validate_state


def build_run_artifact(*, run_id: str, state: dict[str, Any], preflight: PreflightResult, model: str, prompt_schema_version: str = "1", response: dict[str, Any] | None = None) -> dict[str, Any]:
    validate_state(state)
    value = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "input_fixture_hashes": [],
        "orchestration_state_hash": hashlib.sha256(json.dumps(state, sort_keys=True).encode("utf-8")).hexdigest(),
        "prompt_schema_version": prompt_schema_version,
        "model_requested": model,
        "model_returned": None,
        "reasoning_settings": {"effort": "high", "verbosity": "medium"},
        "response_id": None,
        "request_latency_ms": None,
        "input_tokens": preflight.conservative_input_tokens,
        "cached_input_tokens": None,
        "cache_write_tokens": None,
        "output_tokens": None,
        "reasoning_tokens": None,
        "estimated_cost_usd": str(preflight.worst_case_cost_usd),
        "actual_cost_usd": None,
        "actual_cost_status": "NOT_RECONCILED",
        "parsing_success": False,
        "gate": None,
        "generated_next_instruction": None,
        "manual_comparison_status": "PENDING_REVIEW",
        "error_classification": None,
    }
    if response is not None:
        value.update({"model_returned": response.get("model"), "response_id": response.get("response_id"), "request_latency_ms": response.get("latency_ms"), "parsing_success": True, "gate": response.get("gate_decision")})
    return value


def write_artifact(path: Path, artifact: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(artifact, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def build_manual_comparison_packet(*, manual_gate: str, api_gate: str | None, generated_instruction: str | None = None) -> dict[str, Any]:
    return {
        "manual_gate": manual_gate,
        "api_gate": api_gate,
        "major_findings": [],
        "scope_assessment": "PENDING_REVIEW",
        "authority_assessment": "PENDING_REVIEW",
        "user_decision_required": False,
        "generated_next_task_purpose": generated_instruction,
        "generated_next_task_changes": None,
        "evidence_for_difference": [],
        "overreach": [],
        "under_review": [],
        "manual_semantic_comparison_status": "PENDING_REVIEW",
    }
