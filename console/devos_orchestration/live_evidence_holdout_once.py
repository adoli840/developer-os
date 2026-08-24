from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from decimal import Decimal
from pathlib import Path
from typing import Any

from .evidence_sufficiency import (
    EVIDENCE_SUFFICIENCY_CONTRACT_VERSION,
    EVIDENCE_THRESHOLD_CONFLICT_INVARIANTS,
)
from .fixtures import import_fixture, requirement_inventory_for_fixture
from .forensic import build_wire_request, parse_error_metadata, sha256_json
from .live_r3_once import atomic_json, usage_cost
from .live_v2_calibration_once import now, source_sha256
from .manifest import build_canonical_token_request_v2
from .response_pipeline import (
    _atomic_bytes,
    capture_response_bytes,
    parse_response,
    provider_status_record,
)
from .schema import reviewer_output_schema
from .task_alignment import TASK_ALIGNMENT_CONFLICT_INVARIANTS, TASK_ALIGNMENT_CONTRACT_VERSION


ROOT = Path(__file__).resolve().parents[2]
OD = ROOT / ".console" / "orchestration"
CANDIDATE = OD / "phase1c-evidence-sufficiency-mainline-holdout-candidate-manifest.json"
CANDIDATE_SHA = "abc423ea2a1a0b15689fb958b11c52d3a9ca315faee1232eeaf70cb01fede21d"
APPROVAL = "aec30f960e41ae1725da6189db6c2a70c9d030b27e51c3ca77101f736e710715"
EXPECTED_FIXTURE = {
    "task": "435c62f062188565934748e603afb46aeae30347a5257ca03d5886201ddfb1af",
    "report": "0ad1607c5acd4fa8541d208c96cda9bae62a692008b6e0f06944115f22391be9",
    "baseline": "e5268ff7bacf82da494200f7981c916cd56076ff094fa7d841aa1f3afa9d854a",
}
APPROVAL_PATH = OD / f"approval-{APPROVAL}.json"
ATTEMPT_PATH = OD / f"attempt-{APPROVAL}.json"
RESULT_PATH = OD / f"result-{APPROVAL}.json"
COMPARISON_PATH = OD / f"comparison-{APPROVAL}.json"
CAPTURE_DIR = OD / f"response-{APPROVAL}"
ENV_PATH = ROOT / ".env"


def _key() -> str:
    if not ENV_PATH.is_file():
        raise RuntimeError("OPENAI_ORCHESTRATION_API_KEY unavailable")
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        name, separator, value = line.partition("=")
        if separator and name.strip() == "OPENAI_ORCHESTRATION_API_KEY" and value.strip():
            return value.strip().strip('"').strip("'")
    raise RuntimeError("OPENAI_ORCHESTRATION_API_KEY unavailable")


def verify() -> tuple[dict[str, Any], dict[str, Any], set[str], dict[str, str]]:
    if hashlib.sha256(CANDIDATE.read_bytes()).hexdigest() != CANDIDATE_SHA:
        raise RuntimeError("CANDIDATE_FILE_HASH_MISMATCH")
    candidate = json.loads(CANDIDATE.read_text(encoding="utf-8-sig"))
    manifest = dict(candidate["manifest"])
    supplied = manifest.pop("approval_manifest_sha256", None)
    if supplied != APPROVAL or sha256_json(manifest) != APPROVAL:
        raise RuntimeError("APPROVAL_MANIFEST_MISMATCH")
    manifest["approval_manifest_sha256"] = supplied
    if any(path.exists() for path in (APPROVAL_PATH, ATTEMPT_PATH, RESULT_PATH, COMPARISON_PATH, CAPTURE_DIR)):
        raise RuntimeError("MANIFEST_ALREADY_CONSUMED")
    if candidate.get("approved_for_external_api") is not False or manifest.get("approved_for_external_api") is not False:
        raise RuntimeError("CANDIDATE_APPROVAL_STATE_MISMATCH")
    if candidate.get("candidate_type") != "INDEPENDENT_MAINLINE_HOLDOUT_EVIDENCE_SUFFICIENCY":
        raise RuntimeError("CANDIDATE_TYPE_MISMATCH")
    if candidate.get("independent_from_prior_fixtures") is not True:
        raise RuntimeError("FIXTURE_INDEPENDENCE_MISMATCH")
    if candidate.get("baseline_contamination_test") != "PASS" or candidate.get("baseline_is_reviewer_input") is not False:
        raise RuntimeError("BASELINE_CONTAMINATION")
    expected_contract = {
        "model": "gpt-5.6-sol", "max_output_tokens": 16_384,
        "timeout_seconds": 600.0, "retry_count": 0,
        "planned_response_call_count": 1, "proposed_hard_cost_cap_usd": "0.77",
    }
    if any(manifest.get(name) != value for name, value in expected_contract.items()):
        raise RuntimeError("REQUEST_CONTRACT_MISMATCH")
    if Decimal(manifest.get("hard_worst_case_cost_usd", "Infinity")) > Decimal("0.77"):
        raise RuntimeError("BUDGET_BLOCKED")

    fixture = import_fixture(
        Path(r"X:\01_codex_task.txt"), Path(r"X:\02_codex_report.txt"),
        Path(r"X:\03_manual_mainline_review.txt"), project="bTest", historical_date="2026-08-14",
    )
    if fixture.get("status") != "MATCHED_FIXTURE_REGISTERED":
        raise RuntimeError(fixture.get("status", "FIXTURE_SCAN_FAILED"))
    files = {item["source_label"]: item for item in fixture["files"]}
    hashes = {
        "task": files["historical_codex_task"]["normalized_content_sha256"],
        "report": files["historical_codex_report"]["normalized_content_sha256"],
        "baseline": files["manual_review_baseline"]["normalized_content_sha256"],
    }
    if hashes != EXPECTED_FIXTURE:
        raise RuntimeError("FIXTURE_HASH_MISMATCH")
    inventory = requirement_inventory_for_fixture(fixture)
    requirement_ids = {item["requirement_id"] for item in inventory}
    if len(requirement_ids) != manifest.get("task_requirement_count") or sha256_json(inventory) != manifest.get("task_requirement_inventory_sha256"):
        raise RuntimeError("TASK_REQUIREMENT_INVENTORY_MISMATCH")

    canonical = build_canonical_token_request_v2(fixture, requirement_inventory=inventory)
    wire = build_wire_request(canonical)
    schema_hash = sha256_json(canonical["text"]["format"]["schema"])
    if schema_hash != sha256_json(reviewer_output_schema("2.3")):
        raise RuntimeError("ACTUAL_SCHEMA_SOURCE_MISMATCH")
    binding = {
        "actual_wire_request_body_sha256": sha256_json(wire),
        "canonical_token_bearing_request_sha256": sha256_json(canonical),
        "serialized_reviewer_prompt_sha256": sha256_json(canonical["messages"]),
        "structured_output_schema_sha256": schema_hash,
        "pricing_record_sha256": manifest["pricing_record_sha256"],
        "routing_controller_sha256": manifest["routing_controller_sha256"],
        "task_alignment_controller_sha256": manifest["task_alignment_controller_sha256"],
        "evidence_sufficiency_controller_sha256": manifest["evidence_sufficiency_controller_sha256"],
        "runtime_protocol_sha256": manifest["runtime_protocol_sha256"],
    }
    if binding != candidate.get("request_binding") or manifest.get("structured_output_schema_sha256") != schema_hash:
        raise RuntimeError("REQUEST_BINDING_MISMATCH")

    paths = {
        "response_pipeline": "console/devos_orchestration/response_pipeline.py",
        "adapter": "console/devos_orchestration/adapter.py", "schema": "console/devos_orchestration/schema.py",
        "gate_controller": "console/devos_orchestration/gate.py", "routing_controller": "console/devos_orchestration/routing.py",
        "task_alignment": "console/devos_orchestration/task_alignment.py",
        "evidence_sufficiency": "console/devos_orchestration/evidence_sufficiency.py",
        "manifest_builder": "console/devos_orchestration/manifest.py", "cost_estimator": "console/devos_orchestration/pricing.py",
    }
    fingerprints = {name: source_sha256(path) for name, path in paths.items()}
    if fingerprints != manifest.get("source_fingerprints"):
        raise RuntimeError("RUNTIME_SOURCE_MISMATCH")
    task_contract = {
        "version": TASK_ALIGNMENT_CONTRACT_VERSION,
        "controller_source_sha256": fingerprints["gate_controller"],
        "inventory_source_sha256": fingerprints["task_alignment"],
        "invariants": list(TASK_ALIGNMENT_CONFLICT_INVARIANTS),
    }
    evidence_contract = {
        "version": EVIDENCE_SUFFICIENCY_CONTRACT_VERSION,
        "controller_source_sha256": fingerprints["gate_controller"],
        "policy_source_sha256": fingerprints["evidence_sufficiency"],
        "invariants": list(EVIDENCE_THRESHOLD_CONFLICT_INVARIANTS),
    }
    protocol = {
        "response_capture_version": "1", "response_parser_version": "2.3",
        "reviewer_internal_model_version": "2.3", "deterministic_gate_controller_version": "2",
        "task_alignment_contract_version": TASK_ALIGNMENT_CONTRACT_VERSION,
        "evidence_sufficiency_contract_version": EVIDENCE_SUFFICIENCY_CONTRACT_VERSION,
        "cost_formula_version": "2", "source_fingerprints": fingerprints,
    }
    if sha256_json(task_contract) != manifest.get("task_alignment_controller_sha256"):
        raise RuntimeError("TASK_ALIGNMENT_CONTROLLER_MISMATCH")
    if sha256_json(evidence_contract) != manifest.get("evidence_sufficiency_controller_sha256"):
        raise RuntimeError("EVIDENCE_SUFFICIENCY_CONTROLLER_MISMATCH")
    if sha256_json(protocol) != manifest.get("runtime_protocol_sha256"):
        raise RuntimeError("RUNTIME_PROTOCOL_MISMATCH")
    baseline = Path(r"X:\03_manual_mainline_review.txt").read_text(encoding="utf-8")
    if baseline and baseline in json.dumps(wire, ensure_ascii=False, sort_keys=True, separators=(",", ":")):
        raise RuntimeError("BASELINE_CONTAMINATION")
    return candidate, wire, requirement_ids, hashes


def main() -> int:
    try:
        _candidate, wire, requirement_ids, fixture_hashes = verify()
        key = _key()
    except Exception as error:
        print(json.dumps({"status": str(error), "network_calls": 0}, ensure_ascii=True))
        return 2

    atomic_json(APPROVAL_PATH, {
        "record_type": "one_time_user_live_approval", "approval_manifest_sha256": APPROVAL,
        "candidate_file_sha256": CANDIDATE_SHA, "approved_external_transmission": True,
        "approved_local_response_capture": True, "approved_cost_cap_usd": "0.77",
        "approved_attempt_count": 1, "approved_model": "gpt-5.6-sol",
        "timeout_seconds": 600, "approval_source": "explicit_user_instruction", "approved_at": now(),
    })
    atomic_json(ATTEMPT_PATH, {
        "record_type": "ATTEMPT_STARTED", "approval_manifest_sha256": APPROVAL,
        "started_at": now(), "attempt_count": 1, "network_call_count": 0,
        "retry_count": 0, "fallback_count": 0, "dispatch_count": 0,
        "baseline_transmission_count": 0, "fixture_hashes": fixture_hashes,
    })

    started = time.perf_counter()
    response: dict[str, Any] = {}
    body: bytes | None = None
    status = "NETWORK_ERROR"
    http_status: int | None = None
    headers: dict[str, str] = {}
    error_metadata: dict[str, Any] | None = None
    try:
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(wire, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(request, timeout=600.0) as stream:
            body = stream.read(); http_status = stream.status; headers = dict(stream.headers.items())
        _atomic_bytes(CAPTURE_DIR / "provider-response.raw.json", body)
        response = json.loads(body.decode("utf-8")); status = str(response.get("status", "completed"))
    except urllib.error.HTTPError as error:
        body = error.read(1_000_000); http_status = error.code
        headers = dict(error.headers.items()) if error.headers else {}
        _atomic_bytes(CAPTURE_DIR / "provider-error.raw.bin", body)
        error_metadata = parse_error_metadata(http_status=error.code, headers=headers, body=body)
        status = "HTTP_ERROR"
    except Exception as error:
        status = type(error).__name__.upper()
        error_metadata = {"error_type": type(error).__name__, "message": "request failed; details intentionally withheld"}
    latency_ms = round((time.perf_counter() - started) * 1000, 2)

    capture = pipeline = None
    if body is not None and http_status == 200:
        capture = capture_response_bytes(body, CAPTURE_DIR, request_id=headers.get("x-request-id"))
        pipeline = parse_response(response, expected_requirement_ids=requirement_ids)
    result: dict[str, Any] = {
        "status": status, "approval_manifest_sha256": APPROVAL, "request_attempts": 1,
        "http_status": http_status, "response_id": response.get("id"), "returned_model": response.get("model"),
        "latency_ms": latency_ms, "retry_count": 0, "fallback_count": 0, "dispatch_count": 0,
        "baseline_transmission_count": 0, "error_metadata": error_metadata, "response_capture": capture,
        "provider_status": provider_status_record(response, pipeline) if pipeline else "NOT_RUN",
        "provider_billed_actual_cost_usd": None, "actual_cost_status": "NOT_RECONCILED",
    }
    if response.get("usage"):
        tokens, cost = usage_cost(response["usage"]); result.update({"tokens": tokens, "usage_based_estimated_cost_usd": cost})
    if pipeline:
        result.update({"processing_stages": pipeline.stages, "structured_parsing": "PASS" if pipeline.error is None else "FAIL", "parse_error": pipeline.error})
        if pipeline.parsed_output is not None:
            parsed = pipeline.parsed_output
            result.update({
                "review_verdict": parsed.get("review_verdict"), "orchestration_gate": parsed.get("orchestration_gate"),
                "routing_assessment": parsed.get("routing_assessment"),
                "task_requirement_assessment": parsed.get("task_requirement_assessment", []),
                "added_scope": parsed.get("added_scope", []), "findings": parsed.get("findings", []),
                "generated_next_instruction": parsed.get("next_instruction"),
                "user_decision_packet": parsed.get("user_decision_packet"), "blocker_packet": parsed.get("blocker_packet"),
            })
    atomic_json(RESULT_PATH, result)
    atomic_json(ATTEMPT_PATH, {
        "record_type": "ATTEMPT_COMPLETED", "approval_manifest_sha256": APPROVAL,
        "attempt_count": 1, "network_call_count": 1, "retry_count": 0, "fallback_count": 0,
        "dispatch_count": 0, "baseline_transmission_count": 0, "completed_at": now(),
        "status": status, "http_status": http_status, "latency_ms": latency_ms,
    })
    assessments = result.get("task_requirement_assessment", [])
    primary = (result.get("generated_next_instruction") or {}).get("primary_requirement_ids", [])
    summary = {
        "status": status, "http_status": http_status, "response_id": result.get("response_id"),
        "returned_model": result.get("returned_model"), "latency_ms": latency_ms,
        "structured_parsing": result.get("structured_parsing", "NOT_RUN"),
        "processing_stages": result.get("processing_stages", {}), "parse_error": result.get("parse_error"),
        "review_verdict": result.get("review_verdict"), "orchestration_gate": result.get("orchestration_gate"),
        "routing_assessment": result.get("routing_assessment"),
        "requirement_status_counts": {name: sum(1 for item in assessments if item.get("status") == name) for name in ("SATISFIED", "UNRESOLVED", "BLOCKED", "NOT_APPLICABLE")},
        "primary_requirement_ids": primary,
        "deferred_requirement_ids": [item.get("requirement_id") for item in assessments if item.get("status") in {"UNRESOLVED", "BLOCKED"} and item.get("requirement_id") not in primary],
        "evidence_sufficiency": [{key: item.get(key) for key in ("requirement_id", "acceptance_criteria_status", "unresolved_reason_kind", "mandatory_additional_evidence", "mandatory_evidence_basis", "mandatory_evidence_refs", "optional_evidence_note")} for item in assessments],
        "added_scope": result.get("added_scope", []), "generated_next_instruction": result.get("generated_next_instruction"),
        "tokens": result.get("tokens"), "usage_based_estimated_cost_usd": result.get("usage_based_estimated_cost_usd"),
        "request_attempts": 1, "retry_count": 0, "fallback_count": 0, "dispatch_count": 0, "baseline_transmission_count": 0,
    }
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    return 0 if http_status == 200 and pipeline and pipeline.error is None else 5


if __name__ == "__main__":
    raise SystemExit(main())
