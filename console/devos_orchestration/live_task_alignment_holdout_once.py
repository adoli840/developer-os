from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from decimal import Decimal
from pathlib import Path
from typing import Any

from .fixtures import import_fixture, requirement_inventory_for_fixture
from .forensic import build_wire_request, parse_error_metadata, sha256_bytes, sha256_json
from .live_r3_once import atomic_json, usage_cost
from .live_v2_calibration_once import now, source_sha256
from .manifest import build_canonical_token_request_v2
from .response_pipeline import _atomic_bytes, capture_response_bytes, parse_response, provider_status_record
from .schema import reviewer_output_schema
from .task_alignment import TASK_ALIGNMENT_CONFLICT_INVARIANTS, TASK_ALIGNMENT_CONTRACT_VERSION


ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATION_DIR = ROOT / ".console" / "orchestration"
CANDIDATE_PATH = ORCHESTRATION_DIR / "phase1c-task-alignment-v2-2-mainline-holdout-candidate-manifest.json"
CANDIDATE_SHA256 = "8682c5bd682b4bd555fefac26d32ae9df31118d6fc73cfe99525636fb9af54c3"
APPROVAL_ID = "ab82ee093cbd40ba3b59be5745bb6f2e6fb19e8ce1adeef42cb384bd4a5c6325"
EXPECTED_TASK = "ae8ee84e2b63f628fdaa1c1e2b2c3442c76d0587e7aa1b54404cc77b97a80036"
EXPECTED_REPORT = "2b4e0367abe0cda305c0270d5295d837f0642327a4522301245a6a9149e7e220"
EXPECTED_BASELINE = "a2e99f14f5a1573ac05ab7503e2ed08128ca8333288a4343c3025e384186b602"
APPROVAL_PATH = ORCHESTRATION_DIR / f"approval-{APPROVAL_ID}.json"
ATTEMPT_PATH = ORCHESTRATION_DIR / f"attempt-{APPROVAL_ID}.json"
RESULT_PATH = ORCHESTRATION_DIR / f"result-{APPROVAL_ID}.json"
COMPARISON_PATH = ORCHESTRATION_DIR / f"comparison-{APPROVAL_ID}.json"
CAPTURE_DIR = ORCHESTRATION_DIR / f"response-{APPROVAL_ID}"
ENV_PATH = ROOT / ".env"


def load_orchestration_key() -> str:
    if not ENV_PATH.is_file():
        raise RuntimeError("OPENAI_ORCHESTRATION_API_KEY unavailable")
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        name, separator, value = line.partition("=")
        if separator and name.strip() == "OPENAI_ORCHESTRATION_API_KEY" and value.strip():
            return value.strip().strip('"').strip("'")
    raise RuntimeError("OPENAI_ORCHESTRATION_API_KEY unavailable")


def verify_candidate() -> tuple[dict[str, Any], dict[str, Any], set[str], dict[str, str]]:
    if hashlib.sha256(CANDIDATE_PATH.read_bytes()).hexdigest() != CANDIDATE_SHA256:
        raise RuntimeError("CANDIDATE_FILE_HASH_MISMATCH")
    candidate = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8-sig"))
    manifest = dict(candidate["manifest"])
    supplied = manifest.pop("approval_manifest_sha256", None)
    if supplied != APPROVAL_ID or sha256_json(manifest) != APPROVAL_ID:
        raise RuntimeError("APPROVAL_MANIFEST_MISMATCH")
    manifest["approval_manifest_sha256"] = supplied

    evidence_paths = (APPROVAL_PATH, ATTEMPT_PATH, RESULT_PATH, COMPARISON_PATH, CAPTURE_DIR)
    if any(path.exists() for path in evidence_paths):
        raise RuntimeError("MANIFEST_ALREADY_CONSUMED")
    if candidate.get("approved_for_external_api") is not False or manifest.get("approved_for_external_api") is not False:
        raise RuntimeError("CANDIDATE_APPROVAL_STATE_MISMATCH")
    if candidate.get("candidate_type") != "INDEPENDENT_MAINLINE_HOLDOUT_TASK_ALIGNMENT_2_2":
        raise RuntimeError("CANDIDATE_TYPE_MISMATCH")
    if candidate.get("independent_from_prior_fixtures") is not True:
        raise RuntimeError("FIXTURE_INDEPENDENCE_MISMATCH")
    if candidate.get("baseline_contamination_test") != "PASS" or candidate.get("baseline_is_reviewer_input") is not False:
        raise RuntimeError("BASELINE_CONTAMINATION")
    if manifest.get("model") != "gpt-5.6-sol" or manifest.get("max_output_tokens") != 16_384:
        raise RuntimeError("REQUEST_CONTRACT_MISMATCH")
    if manifest.get("timeout_seconds") != 600.0 or manifest.get("retry_count") != 0:
        raise RuntimeError("TRANSPORT_CONTRACT_MISMATCH")
    if manifest.get("planned_response_call_count") != 1:
        raise RuntimeError("ATTEMPT_CONTRACT_MISMATCH")
    if manifest.get("proposed_hard_cost_cap_usd") != "0.79":
        raise RuntimeError("COST_CAP_MISMATCH")
    if Decimal(manifest.get("hard_worst_case_cost_usd", "Infinity")) > Decimal("0.79"):
        raise RuntimeError("BUDGET_BLOCKED")

    fixture = import_fixture(
        Path(r"X:\01_codex_task.txt"), Path(r"X:\02_codex_report.txt"),
        Path(r"X:\03_manual_mainline_review.txt"), project="bTest", historical_date="2026-08-13",
    )
    if fixture.get("status") != "MATCHED_FIXTURE_REGISTERED":
        raise RuntimeError(fixture.get("status", "FIXTURE_SCAN_FAILED"))
    files = {item["source_label"]: item for item in fixture["files"]}
    fixture_hashes = {
        "task": files["historical_codex_task"]["normalized_content_sha256"],
        "report": files["historical_codex_report"]["normalized_content_sha256"],
        "baseline": files["manual_review_baseline"]["normalized_content_sha256"],
    }
    if fixture_hashes != {"task": EXPECTED_TASK, "report": EXPECTED_REPORT, "baseline": EXPECTED_BASELINE}:
        raise RuntimeError("FIXTURE_HASH_MISMATCH")

    inventory = requirement_inventory_for_fixture(fixture)
    requirement_ids = {item["requirement_id"] for item in inventory}
    if len(requirement_ids) != manifest.get("task_requirement_count"):
        raise RuntimeError("TASK_REQUIREMENT_COUNT_MISMATCH")
    if sha256_json(inventory) != manifest.get("task_requirement_inventory_sha256"):
        raise RuntimeError("TASK_REQUIREMENT_INVENTORY_MISMATCH")

    canonical = build_canonical_token_request_v2(fixture, requirement_inventory=inventory)
    wire = build_wire_request(canonical)
    actual_schema_hash = sha256_json(canonical["text"]["format"]["schema"])
    if actual_schema_hash != sha256_json(reviewer_output_schema("2.2")):
        raise RuntimeError("ACTUAL_SCHEMA_SOURCE_MISMATCH")
    recalculated = {
        "actual_wire_request_body_sha256": sha256_json(wire),
        "canonical_token_bearing_request_sha256": sha256_json(canonical),
        "serialized_reviewer_prompt_sha256": sha256_json(canonical["messages"]),
        "structured_output_schema_sha256": actual_schema_hash,
        "pricing_record_sha256": manifest["pricing_record_sha256"],
        "routing_controller_sha256": manifest["routing_controller_sha256"],
        "task_alignment_controller_sha256": manifest["task_alignment_controller_sha256"],
        "runtime_protocol_sha256": manifest["runtime_protocol_sha256"],
    }
    if recalculated != candidate.get("request_binding"):
        raise RuntimeError("REQUEST_BINDING_MISMATCH")
    if manifest.get("structured_output_schema_sha256") != actual_schema_hash:
        raise RuntimeError("CANDIDATE_SCHEMA_BINDING_MISMATCH")

    source_paths = {
        "response_pipeline": "console/devos_orchestration/response_pipeline.py",
        "adapter": "console/devos_orchestration/adapter.py",
        "schema": "console/devos_orchestration/schema.py",
        "gate_controller": "console/devos_orchestration/gate.py",
        "routing_controller": "console/devos_orchestration/routing.py",
        "task_alignment": "console/devos_orchestration/task_alignment.py",
        "manifest_builder": "console/devos_orchestration/manifest.py",
        "cost_estimator": "console/devos_orchestration/pricing.py",
    }
    fingerprints = {name: source_sha256(path) for name, path in source_paths.items()}
    if fingerprints != manifest.get("source_fingerprints"):
        raise RuntimeError("RUNTIME_SOURCE_MISMATCH")
    task_contract = {
        "version": TASK_ALIGNMENT_CONTRACT_VERSION,
        "controller_source_sha256": fingerprints["gate_controller"],
        "inventory_source_sha256": fingerprints["task_alignment"],
        "invariants": list(TASK_ALIGNMENT_CONFLICT_INVARIANTS),
    }
    if sha256_json(task_contract) != manifest.get("task_alignment_controller_sha256"):
        raise RuntimeError("TASK_ALIGNMENT_CONTROLLER_MISMATCH")
    protocol = {
        "response_capture_version": "1", "response_parser_version": "2.1",
        "reviewer_internal_model_version": "2.1", "deterministic_gate_controller_version": "2",
        "task_alignment_contract_version": TASK_ALIGNMENT_CONTRACT_VERSION,
        "cost_formula_version": "2", "source_fingerprints": fingerprints,
    }
    if sha256_json(protocol) != manifest.get("runtime_protocol_sha256"):
        raise RuntimeError("RUNTIME_PROTOCOL_MISMATCH")

    baseline_text = Path(r"X:\03_manual_mainline_review.txt").read_text(encoding="utf-8")
    wire_text = json.dumps(wire, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if baseline_text and baseline_text in wire_text:
        raise RuntimeError("BASELINE_CONTAMINATION")
    return candidate, wire, requirement_ids, fixture_hashes


def main() -> int:
    try:
        _candidate, wire, requirement_ids, fixture_hashes = verify_candidate()
        key = load_orchestration_key()
    except Exception as error:
        print(json.dumps({"status": str(error), "network_calls": 0}, ensure_ascii=True))
        return 2

    atomic_json(APPROVAL_PATH, {
        "record_type": "one_time_user_live_approval", "approval_manifest_sha256": APPROVAL_ID,
        "candidate_file_sha256": CANDIDATE_SHA256, "approved_external_transmission": True,
        "approved_local_response_capture": True, "approved_cost_cap_usd": "0.79",
        "approved_attempt_count": 1, "approved_model": "gpt-5.6-sol", "timeout_seconds": 600,
        "approval_source": "explicit_user_instruction", "approved_at": now(),
    })
    atomic_json(ATTEMPT_PATH, {
        "record_type": "ATTEMPT_STARTED", "approval_manifest_sha256": APPROVAL_ID,
        "started_at": now(), "attempt_count": 1, "network_call_count": 0, "retry_count": 0,
        "fallback_count": 0, "dispatch_count": 0, "baseline_transmission_count": 0,
        "fixture_hashes": fixture_hashes,
    })

    started = time.perf_counter()
    response: dict[str, Any] = {}
    body: bytes | None = None
    status = "NETWORK_ERROR"
    http_status: int | None = None
    response_headers: dict[str, str] = {}
    error_metadata: dict[str, Any] | None = None
    try:
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(wire, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=600.0) as stream:
            body = stream.read()
            http_status = stream.status
            response_headers = dict(stream.headers.items())
        _atomic_bytes(CAPTURE_DIR / "provider-response.raw.json", body)
        response = json.loads(body.decode("utf-8"))
        status = str(response.get("status", "completed"))
    except urllib.error.HTTPError as error:
        body = error.read(1_000_000)
        http_status = error.code
        response_headers = dict(error.headers.items()) if error.headers else {}
        _atomic_bytes(CAPTURE_DIR / "provider-error.raw.bin", body)
        error_metadata = parse_error_metadata(http_status=error.code, headers=response_headers, body=body)
        status = "HTTP_ERROR"
    except Exception as error:
        status = type(error).__name__.upper()
        error_metadata = {"error_type": type(error).__name__, "message": "request failed; details intentionally withheld"}
    latency_ms = round((time.perf_counter() - started) * 1000, 2)

    capture = None
    pipeline = None
    if body is not None and http_status == 200:
        capture = capture_response_bytes(body, CAPTURE_DIR, request_id=response_headers.get("x-request-id"))
        pipeline = parse_response(response, expected_requirement_ids=requirement_ids)

    result: dict[str, Any] = {
        "status": status, "approval_manifest_sha256": APPROVAL_ID, "request_attempts": 1,
        "http_status": http_status, "response_id": response.get("id"), "returned_model": response.get("model"),
        "latency_ms": latency_ms, "retry_count": 0, "fallback_count": 0, "dispatch_count": 0,
        "baseline_transmission_count": 0, "error_metadata": error_metadata, "response_capture": capture,
        "provider_status": provider_status_record(response, pipeline) if pipeline else "NOT_RUN",
        "provider_billed_actual_cost_usd": None, "actual_cost_status": "NOT_RECONCILED",
    }
    if response.get("usage"):
        tokens, cost = usage_cost(response["usage"])
        result.update({"tokens": tokens, "usage_based_estimated_cost_usd": cost})
    if pipeline:
        result.update({
            "processing_stages": pipeline.stages,
            "structured_parsing": "PASS" if pipeline.error is None else "FAIL",
            "parse_error": pipeline.error,
        })
        if pipeline.parsed_output is not None:
            parsed = pipeline.parsed_output
            result.update({
                "review_verdict": parsed.get("review_verdict"),
                "orchestration_gate": parsed.get("orchestration_gate"),
                "routing_assessment": parsed.get("routing_assessment"),
                "task_requirement_assessment": parsed.get("task_requirement_assessment", []),
                "added_scope": parsed.get("added_scope", []),
                "findings": parsed.get("findings", []),
                "generated_next_instruction": parsed.get("next_instruction"),
                "user_decision_packet": parsed.get("user_decision_packet"),
                "blocker_packet": parsed.get("blocker_packet"),
            })
    atomic_json(RESULT_PATH, result)
    atomic_json(ATTEMPT_PATH, {
        "record_type": "ATTEMPT_COMPLETED", "approval_manifest_sha256": APPROVAL_ID,
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
        "added_scope": result.get("added_scope", []), "generated_next_instruction": result.get("generated_next_instruction"),
        "tokens": result.get("tokens"), "usage_based_estimated_cost_usd": result.get("usage_based_estimated_cost_usd"),
        "request_attempts": 1, "retry_count": 0, "fallback_count": 0, "dispatch_count": 0,
        "baseline_transmission_count": 0,
    }
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    return 0 if http_status == 200 and pipeline and pipeline.error is None else 5


if __name__ == "__main__":
    raise SystemExit(main())
