from __future__ import annotations

import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .manifest import sha256_json


TOKEN_EFFICIENCY_POLICY_VERSION = "OrchestrationTokenEfficiencyV1"
EVALUATION_REUSE_INDEX_VERSION = "EvaluationReuseIndexV1"


def compact_canonical_context(state: dict[str, Any]) -> dict[str, Any]:
    """Return only current authority-bearing state, never conversation history."""
    required = {
        "current_purpose", "frozen_decisions", "scope", "authority", "routing",
        "user_decisions", "current_gate", "latest_relevant_handoff",
    }
    if not isinstance(state, dict) or not required.issubset(state):
        raise ValueError("TOKEN_EFFICIENCY_CANONICAL_STATE_INVALID")
    value = {
        "current_purpose": state["current_purpose"],
        "frozen_decisions": copy.deepcopy(state["frozen_decisions"]),
        "scope": copy.deepcopy(state["scope"]),
        "authority": state["authority"],
        "routing": copy.deepcopy(state["routing"]),
        "user_decisions": copy.deepcopy(state["user_decisions"]),
        "current_gate": state["current_gate"],
        "latest_relevant_handoff": state["latest_relevant_handoff"],
    }
    return value


def evaluation_identity_sha256(
    *,
    canonical_state_sha256: str,
    task_sha256: str,
    report_sha256: str,
    protocol_version: str,
    reviewer_schema_version: str,
) -> str:
    return sha256_json({
        "canonical_state_sha256": canonical_state_sha256,
        "task_sha256": task_sha256,
        "report_sha256": report_sha256,
        "protocol_version": protocol_version,
        "reviewer_schema_version": reviewer_schema_version,
    })


def deterministic_continuation_precheck(
    candidate: dict[str, Any],
    *,
    current_canonical_state_sha256: str,
    credential_available: bool,
    already_consumed: bool,
    route_binding_valid: bool,
    workspace_binding_valid: bool,
) -> dict[str, Any]:
    """Check only objective execution prerequisites; never choose a semantic Gate."""
    binding = candidate.get("binding") or candidate.get("request_binding") or {}
    manifest = candidate.get("manifest") or {}
    required = {
        "canonical_state_sha256", "task_content_sha256", "report_content_sha256",
        "evaluation_identity_sha256", "stable_prefix_sha256", "dynamic_payload_sha256",
    }
    reasons: list[str] = []
    if not required.issubset(binding):
        reasons.append("MISSING_REQUIRED_EVIDENCE_FIELD")
    if binding.get("canonical_state_sha256") != current_canonical_state_sha256:
        reasons.append("STALE_CANONICAL_STATE")
    if already_consumed:
        reasons.append("CONSUMED_HANDOFF")
    if not credential_available:
        reasons.append("MISSING_CREDENTIAL")
    if not route_binding_valid:
        reasons.append("INVALID_ROUTE_BINDING")
    if not workspace_binding_valid:
        reasons.append("WORKSPACE_MISMATCH")
    if manifest.get("prompt_version") != manifest.get("schema_version"):
        reasons.append("INVALID_PROTOCOL_BINDING")
    return {
        "policy_version": TOKEN_EFFICIENCY_POLICY_VERSION,
        "status": "PASS" if not reasons else "BLOCKED",
        "reasons": reasons,
        "semantic_judgment_performed": False,
    }


class EvaluationReuseStore:
    """Metrics-only identity index for already validated equivalent evaluations."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _read(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"version": EVALUATION_REUSE_INDEX_VERSION, "evaluations": {}}
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if (
            value.get("version") != EVALUATION_REUSE_INDEX_VERSION
            or not isinstance(value.get("evaluations"), dict)
        ):
            raise ValueError("EVALUATION_REUSE_INDEX_INVALID")
        return value

    def lookup(self, identity_sha256: str) -> dict[str, Any] | None:
        value = self._read()["evaluations"].get(identity_sha256)
        if not isinstance(value, dict) or value.get("status") != "VALIDATED":
            return None
        return copy.deepcopy(value)

    def register_validated(
        self,
        identity_sha256: str,
        *,
        result_sha256: str,
        result_artifact: str,
        protocol_version: str,
        reviewer_schema_version: str,
    ) -> dict[str, Any]:
        index = self._read()
        existing = index["evaluations"].get(identity_sha256)
        if existing is not None:
            if existing.get("result_sha256") != result_sha256:
                raise ValueError("EVALUATION_REUSE_IDENTITY_CONFLICT")
            return copy.deepcopy(existing)
        record = {
            "status": "VALIDATED",
            "evaluation_identity_sha256": identity_sha256,
            "result_sha256": result_sha256,
            "result_artifact": result_artifact,
            "protocol_version": protocol_version,
            "reviewer_schema_version": reviewer_schema_version,
            "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        index["evaluations"][identity_sha256] = record
        payload = (json.dumps(index, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.tmp")
        temporary.write_bytes(payload)
        os.replace(temporary, self.path)
        return copy.deepcopy(record)
