from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from .api_mainline_bootstrap import (
    ApiMainlineBootstrapError,
    api_mainline_bootstrap_schema,
    build_bootstrap_request,
    validate_bootstrap_output,
)
from .evidence_sufficiency import EVIDENCE_SUFFICIENCY_CONTRACT_VERSION
from .gate import validate_review_output
from .manifest import sha256_json
from .schema import reviewer_output_schema
from .task_alignment import (
    TASK_ALIGNMENT_CONTRACT_VERSION,
    canonical_next_step_catalog,
    extract_requirement_inventory,
)
from .token_efficiency import TOKEN_EFFICIENCY_POLICY_VERSION, compact_canonical_context


CONTINUATION_PROMPT_VERSION = "2c.token-efficiency.1"
CONTINUATION_SCHEMA_VERSION = "2c.token-efficiency.1"
CONTINUATION_RUNTIME_VERSION = "2c.token-efficiency.1"
REVIEWER_SCHEMA_VERSION = "2.4"
CONTINUATION_MAX_OUTPUT_TOKENS = 6_144

CONTINUATION_STABLE_PREFIX = "\n".join([
    "You are BTEST_MAINLINE_API, the sole managed Mainline authority for this turn.",
    "Use only the dynamic canonical context, current task, latest Codex report, requirement IDs, and authorized source refs supplied next.",
    "Return exactly one strict structured routing action and auto_advance_review using reviewer schema 2.4.",
    "Evaluate task evidence before routing; never self-declare local validator PASS values.",
    "Unresolved requirements require CONTINUE_CURRENT_TASK.",
    "Completed work may SAFE_CONTINUE only through an exact authorized next-step source_ref.",
    "If no authorized next step applies, route USER_DECISION_REQUIRED with USER_REQUIRED; never invent source_refs.",
    "HANDOFF_CODEX requires CODEX_WORKER; USER_REQUIRED requires a decision packet; BLOCKED and STOP require exact reasons.",
    "Propose only updated_state_delta and never rewrite frozen decisions, authority, or routing.",
    "For Codex handoff_message, provide only the task delta, required checks, changed constraints, and exact authority/source refs.",
    "Do not repeat stable contracts, prior completed-cycle prose, Activity Timeline, manual review, or repository history.",
    "Keep executive summaries, findings, and packets concise; do not repeat the same evidence prose across fields.",
    "No tool use, network side effect, Codex dispatch, or automatic next cycle is permitted.",
])


def _source_hash(module_name: str) -> str:
    path = Path(__file__).with_name(module_name)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validation_provenance() -> dict[str, Any]:
    value = {
        "continuation_schema_version": CONTINUATION_SCHEMA_VERSION,
        "reviewer_schema_version": REVIEWER_SCHEMA_VERSION,
        "routing_controller_sha256": _source_hash("routing.py"),
        "gate_controller_sha256": _source_hash("gate.py"),
        "task_alignment_contract_version": TASK_ALIGNMENT_CONTRACT_VERSION,
        "task_alignment_controller_sha256": _source_hash("task_alignment.py"),
        "evidence_sufficiency_contract_version": EVIDENCE_SUFFICIENCY_CONTRACT_VERSION,
        "evidence_sufficiency_controller_sha256": _source_hash("evidence_sufficiency.py"),
        "token_efficiency_policy_version": TOKEN_EFFICIENCY_POLICY_VERSION,
        "token_efficiency_controller_sha256": _source_hash("token_efficiency.py"),
    }
    return {**value, "provenance_sha256": sha256_json(value)}


def continuation_output_schema() -> dict[str, Any]:
    schema = copy.deepcopy(api_mainline_bootstrap_schema())
    schema["required"].append("auto_advance_review")
    schema["properties"]["auto_advance_review"] = reviewer_output_schema(REVIEWER_SCHEMA_VERSION)
    return schema


def build_continuation_request(
    canonical_state: dict[str, Any],
    task_text: str,
    report_text: str,
) -> tuple[dict[str, Any], str, list[dict[str, Any]]]:
    inventory = extract_requirement_inventory(task_text)
    next_step_catalog = canonical_next_step_catalog(canonical_state)
    dynamic_payload = {
        "canonical_context": compact_canonical_context(canonical_state),
        "current_task": task_text,
        "latest_codex_report": report_text,
        "requirement_ids": [item["requirement_id"] for item in inventory],
        "authorized_next_steps": next_step_catalog,
    }
    request, _ = build_bootstrap_request(canonical_state, report_text)
    request["input"] = [
        {"role": "developer", "content": CONTINUATION_STABLE_PREFIX},
        {
            "role": "user",
            "content": json.dumps(
                dynamic_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            ),
        },
    ]
    request["text"]["verbosity"] = "low"
    request["max_output_tokens"] = CONTINUATION_MAX_OUTPUT_TOKENS
    request["text"]["format"] = {
        "type": "json_schema",
        "name": "developer_os_api_mainline_continuation",
        "strict": True,
        "schema": continuation_output_schema(),
    }
    return request, CONTINUATION_STABLE_PREFIX, inventory


def validate_continuation_output(
    output: dict[str, Any],
    expected_requirement_ids: set[str],
    canonical_state: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    expected = set(api_mainline_bootstrap_schema()["required"]) | {"auto_advance_review"}
    if not isinstance(output, dict) or set(output) != expected:
        raise ApiMainlineBootstrapError("INVALID_CONTINUATION_OUTPUT_SHAPE")
    review = output["auto_advance_review"]
    base = {key: value for key, value in output.items() if key != "auto_advance_review"}
    validated = validate_bootstrap_output(base)
    validate_review_output(
        review,
        expected_requirement_ids=expected_requirement_ids,
        authorized_next_steps=canonical_next_step_catalog(canonical_state or {}),
    )
    if validated["gate"] != review["orchestration_gate"]:
        raise ApiMainlineBootstrapError("CONTINUATION_GATE_REVIEW_CONFLICT")
    if validated["action"] == "HANDOFF_CODEX" and (
        review["orchestration_gate"] != "SAFE_CONTINUE"
        or review["routing_assessment"]["resolution_kind"] != "BOUNDED_TASK"
    ):
        raise ApiMainlineBootstrapError("CONTINUATION_AUTO_ROUTE_CONFLICT")

    provenance = validation_provenance()
    evidence = {
        "resolution_kind": review["routing_assessment"]["resolution_kind"],
        "task_transition": review["next_step_authority"]["task_transition"],
        "next_step_basis": review["next_step_authority"]["next_step_basis"],
        "source_refs": copy.deepcopy(review["next_step_authority"]["source_refs"]),
        "deterministic_validation": "PASS",
        "task_alignment": "PASS",
        "evidence_sufficiency": "PASS",
        "source_review_id": review["review_id"],
        "source_review_sha256": sha256_json(review),
        "provenance": provenance,
    }
    return {**validated, "auto_advance_review": copy.deepcopy(review)}, evidence


def validate_auto_advance_evidence(value: Any) -> dict[str, Any]:
    required = {
        "resolution_kind", "task_transition", "next_step_basis", "source_refs",
        "deterministic_validation", "task_alignment",
        "evidence_sufficiency", "source_review_id", "source_review_sha256", "provenance",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ApiMainlineBootstrapError("AUTO_ADVANCE_EVIDENCE_SHAPE_INVALID")
    if value["resolution_kind"] not in {
        "BOUNDED_TASK", "USER_DECISION", "MISSING_DEPENDENCY", "SAFETY_STOP", "NONE",
    }:
        raise ApiMainlineBootstrapError("AUTO_ADVANCE_RESOLUTION_KIND_INVALID")
    if value["task_transition"] not in {
        "CONTINUE_CURRENT_TASK", "ADVANCE_AUTHORIZED_PLAN", "USER_DECISION_REQUIRED",
    }:
        raise ApiMainlineBootstrapError("AUTO_ADVANCE_TASK_TRANSITION_INVALID")
    if value["next_step_basis"] not in {
        "UNRESOLVED_REQUIREMENT", "FROZEN_NEXT_STEP", "APPROVED_PLAN_ITEM",
        "USER_DECISION", "NONE",
    } or not isinstance(value["source_refs"], list):
        raise ApiMainlineBootstrapError("AUTO_ADVANCE_NEXT_STEP_AUTHORITY_INVALID")
    for field in ("deterministic_validation", "task_alignment", "evidence_sufficiency"):
        if value[field] not in {"PASS", "FAIL", "UNKNOWN"}:
            raise ApiMainlineBootstrapError(f"AUTO_ADVANCE_{field.upper()}_INVALID")
    if value["provenance"] != validation_provenance():
        raise ApiMainlineBootstrapError("AUTO_ADVANCE_PROVENANCE_MISMATCH")
    if not isinstance(value["source_review_id"], str) or not value["source_review_id"].strip():
        raise ApiMainlineBootstrapError("AUTO_ADVANCE_SOURCE_REVIEW_MISSING")
    if not isinstance(value["source_review_sha256"], str) or len(value["source_review_sha256"]) != 64:
        raise ApiMainlineBootstrapError("AUTO_ADVANCE_SOURCE_REVIEW_HASH_INVALID")
    return copy.deepcopy(value)


def validation_stage_status(error: Exception) -> dict[str, str]:
    message = str(error)
    if "TASK_ALIGNMENT_CONFLICT" in message:
        return {
            "deterministic_validation": "FAIL",
            "task_alignment": "FAIL",
            "evidence_sufficiency": "NOT_RUN",
        }
    if "EVIDENCE_THRESHOLD_CONFLICT" in message:
        return {
            "deterministic_validation": "FAIL",
            "task_alignment": "PASS",
            "evidence_sufficiency": "FAIL",
        }
    return {
        "deterministic_validation": "FAIL",
        "task_alignment": "NOT_ACCEPTED",
        "evidence_sufficiency": "NOT_RUN",
    }
