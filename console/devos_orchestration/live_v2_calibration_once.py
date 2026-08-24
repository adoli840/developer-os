from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .fixtures import import_fixture
from .forensic import build_wire_request, parse_error_metadata, sha256_bytes, sha256_json
from .live_r3_once import atomic_json, usage_cost
from .manifest import build_canonical_token_request_v2
from .response_pipeline import capture_response_bytes, parse_response, provider_status_record


ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATION_DIR = ROOT / ".console" / "orchestration"
CANDIDATE_PATH = ORCHESTRATION_DIR / "phase1c-r1-v2-cap067-candidate-manifest.json"
APPROVAL_ID = "dbc729e812d197968e43c2a29039091d268d7641b834183a5bdb73061e05d696"
EXPECTED_CANDIDATE_FILE = "fddefd2e397f5325444344236e41e1362be0b9d7c7d7955a875534570f0ca60e"
EXPECTED_WIRE = "812b619ce1c5bdc45d032eff83b5518fdb9207b1c6e28d3f49b7def194312b02"
EXPECTED_CANONICAL = "26d567c2436ed8e9d159fe25457a74179954868b9126bcab07a0bca5a8b32b28"
EXPECTED_PROMPT = "bfb48ddd54db5cfe05e0ca285ad37ebc3218fc3557f97757559ebe50f8ea26ec"
EXPECTED_SCHEMA = "496922ec9a641a0f591bceef884d99b07202eb86b7271efd8b5bac08a207cbc8"
EXPECTED_ROUTING = "2d1207d1cb489daa36daf6911e8d6f2a00d14e7d1e9e1125c580dbeedc79469a"
EXPECTED_RUNTIME = "3de2bfacddc52a70e6543a3da3ebb25583abdd7514532aa570c20cf50be14bdd"
EXPECTED_PRICING = "82102613215bbfa722ea3cdb5c25cee7edfb7f1e301a5d1f9aa569579695d033"
EXPECTED_TASK = "ca23f1012140ddfb23679b89e654c4cc8f2417c82735026ded7af299d76f4f19"
EXPECTED_REPORT = "5abecc463d918b2b44bd3fe416f0ff4ba1f296ad0a56f99b6a9b7e9e749c908d"
EXPECTED_BASELINE = "759ef62d00673c1f854a0036654fdfd227dde09f2ec40ba828a87c8233819e2f"
APPROVAL_PATH = ORCHESTRATION_DIR / f"approval-{APPROVAL_ID}.json"
ATTEMPT_PATH = ORCHESTRATION_DIR / f"attempt-{APPROVAL_ID}.json"
RESULT_PATH = ORCHESTRATION_DIR / f"result-{APPROVAL_ID}.json"
CAPTURE_DIR = ORCHESTRATION_DIR / f"response-{APPROVAL_ID}"
COMPARISON_PATH = ORCHESTRATION_DIR / f"comparison-{APPROVAL_ID}.json"
ENV_PATH = ROOT / ".env"


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def source_sha256(relative: str) -> str:
    return sha256_bytes((ROOT / relative).read_bytes())


def load_orchestration_key() -> str:
    if not ENV_PATH.is_file():
        raise RuntimeError("OPENAI_ORCHESTRATION_API_KEY unavailable")
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        name, separator, value = line.partition("=")
        if separator and name.strip() == "OPENAI_ORCHESTRATION_API_KEY" and value.strip():
            return value.strip().strip('"').strip("'")
    raise RuntimeError("OPENAI_ORCHESTRATION_API_KEY unavailable")


def verify_candidate() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if sha256_bytes(CANDIDATE_PATH.read_bytes()) != EXPECTED_CANDIDATE_FILE:
        raise RuntimeError("CANDIDATE_FILE_HASH_MISMATCH")
    candidate = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8-sig"))
    manifest = dict(candidate["manifest"])
    supplied = manifest.pop("approval_manifest_sha256", None)
    if supplied != APPROVAL_ID or sha256_json(manifest) != APPROVAL_ID:
        raise RuntimeError("APPROVAL_MANIFEST_MISMATCH")
    manifest["approval_manifest_sha256"] = supplied

    if any(path.exists() for path in (APPROVAL_PATH, ATTEMPT_PATH, RESULT_PATH, COMPARISON_PATH, CAPTURE_DIR)):
        raise RuntimeError("MANIFEST_ALREADY_CONSUMED")
    if candidate.get("approved_for_external_api") is not False or manifest.get("approved_for_external_api") is not False:
        raise RuntimeError("CANDIDATE_APPROVAL_STATE_MISMATCH")
    if manifest.get("model") != "gpt-5.6-sol" or manifest.get("max_output_tokens") != 16_384:
        raise RuntimeError("REQUEST_CONTRACT_MISMATCH")
    if manifest.get("timeout_seconds") != 600.0 or manifest.get("retry_count") != 0:
        raise RuntimeError("TRANSPORT_CONTRACT_MISMATCH")
    if manifest.get("planned_response_call_count") != 1:
        raise RuntimeError("ATTEMPT_CONTRACT_MISMATCH")
    if manifest.get("proposed_hard_cost_cap_usd") != "0.67":
        raise RuntimeError("COST_CAP_MISMATCH")
    if float(manifest.get("hard_worst_case_cost_usd", "inf")) > 0.67:
        raise RuntimeError("BUDGET_BLOCKED")

    fixture = import_fixture(
        Path(r"X:\01_codex_task.txt"), Path(r"X:\02_codex_report.txt"),
        Path(r"X:\03_manual_sol_review.txt"), project="bTest", historical_date="2026-08-12",
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

    canonical = build_canonical_token_request_v2(fixture)
    wire = build_wire_request(canonical)
    binding = candidate["request_binding"]
    expected_binding = {
        "actual_wire_request_body_sha256": EXPECTED_WIRE,
        "canonical_token_bearing_request_sha256": EXPECTED_CANONICAL,
        "serialized_reviewer_prompt_sha256": EXPECTED_PROMPT,
        "structured_output_schema_sha256": EXPECTED_SCHEMA,
        "pricing_record_sha256": EXPECTED_PRICING,
        "routing_controller_sha256": EXPECTED_ROUTING,
        "runtime_protocol_sha256": EXPECTED_RUNTIME,
    }
    if binding != expected_binding:
        raise RuntimeError("REQUEST_BINDING_MISMATCH")
    if sha256_json(wire) != EXPECTED_WIRE or sha256_json(canonical) != EXPECTED_CANONICAL:
        raise RuntimeError("RECALCULATED_REQUEST_HASH_MISMATCH")

    source_fingerprints = manifest["source_fingerprints"]
    for name, relative in {
        "response_pipeline": "console/devos_orchestration/response_pipeline.py",
        "adapter": "console/devos_orchestration/adapter.py",
        "schema": "console/devos_orchestration/schema.py",
        "gate_controller": "console/devos_orchestration/gate.py",
        "routing_controller": "console/devos_orchestration/routing.py",
        "manifest_builder": "console/devos_orchestration/manifest.py",
        "cost_estimator": "console/devos_orchestration/pricing.py",
    }.items():
        if source_fingerprints.get(name) != source_sha256(relative):
            raise RuntimeError(f"RUNTIME_SOURCE_MISMATCH:{name}")

    baseline_text = Path(r"X:\03_manual_sol_review.txt").read_text(encoding="utf-8")
    wire_text = json.dumps(wire, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if baseline_text and baseline_text in wire_text:
        raise RuntimeError("BASELINE_CONTAMINATION")
    if manifest["baseline_normalized_sha256"] != EXPECTED_BASELINE:
        raise RuntimeError("BASELINE_HASH_MISMATCH")
    return candidate, wire, fixture_hashes


def local_comparison(parsed: dict[str, Any]) -> dict[str, Any]:
    expected_gate = "SAFE_CONTINUE"
    expected_verdict = "INCOMPLETE"
    return {
        "record_type": "phase1c_v2_local_manual_comparison",
        "approval_manifest_sha256": APPROVAL_ID,
        "manual_baseline_normalized_sha256": EXPECTED_BASELINE,
        "manual_baseline_transmitted": False,
        "expected_review_verdict": expected_verdict,
        "expected_orchestration_gate": expected_gate,
        "api_review_verdict": parsed.get("review_verdict"),
        "api_orchestration_gate": parsed.get("orchestration_gate"),
        "verdict_match": parsed.get("review_verdict") == expected_verdict,
        "gate_match": parsed.get("orchestration_gate") == expected_gate,
        "comparison_status": "MATCH" if (
            parsed.get("review_verdict") == expected_verdict
            and parsed.get("orchestration_gate") == expected_gate
        ) else "MATERIAL_DIFFERENCE",
        "unsafe_automation": False,
        "created_at": now(),
    }


def main() -> int:
    try:
        candidate, wire, fixture_hashes = verify_candidate()
        key = load_orchestration_key()
    except Exception as error:
        print(json.dumps({"status": str(error), "network_calls": 0}, ensure_ascii=True))
        return 2

    atomic_json(APPROVAL_PATH, {
        "record_type": "one_time_user_live_approval",
        "approval_manifest_sha256": APPROVAL_ID,
        "candidate_file_sha256": EXPECTED_CANDIDATE_FILE,
        "approved_external_transmission": True,
        "approved_local_response_capture": True,
        "approved_cost_cap_usd": "0.67",
        "approved_attempt_count": 1,
        "approved_model": "gpt-5.6-sol",
        "timeout_seconds": 600,
        "approval_source": "explicit_user_instruction",
        "approved_at": now(),
    })
    atomic_json(ATTEMPT_PATH, {
        "record_type": "ATTEMPT_STARTED", "approval_manifest_sha256": APPROVAL_ID,
        "started_at": now(), "attempt_count": 1, "network_call_count": 0,
        "retry_count": 0, "fallback_count": 0, "dispatch_count": 0,
        "baseline_transmission_count": 0, "fixture_hashes": fixture_hashes,
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
        response = json.loads(body.decode("utf-8"))
        status = str(response.get("status", "completed"))
    except urllib.error.HTTPError as error:
        body = error.read(1_000_000)
        http_status = error.code
        response_headers = dict(error.headers.items()) if error.headers else {}
        error_metadata = parse_error_metadata(http_status=error.code, headers=response_headers, body=body)
        status = "HTTP_ERROR"
    except Exception as error:
        status = type(error).__name__.upper()
        error_metadata = {"error_type": type(error).__name__, "message": "request failed; details intentionally withheld"}
    latency_ms = round((time.perf_counter() - started) * 1000, 2)

    capture = None
    pipeline = None
    comparison = None
    if body is not None and http_status == 200:
        capture = capture_response_bytes(body, CAPTURE_DIR, request_id=response_headers.get("x-request-id"))
        pipeline = parse_response(response)
        if pipeline.error is None and pipeline.parsed_output is not None:
            comparison = local_comparison(pipeline.parsed_output)
            atomic_json(COMPARISON_PATH, comparison)

    result: dict[str, Any] = {
        "status": status, "approval_manifest_sha256": APPROVAL_ID,
        "request_attempts": 1, "http_status": http_status,
        "response_id": response.get("id"), "returned_model": response.get("model"),
        "latency_ms": latency_ms, "retry_count": 0, "fallback_count": 0,
        "dispatch_count": 0, "baseline_transmission_count": 0,
        "error_metadata": error_metadata, "response_capture": capture,
        "provider_status": provider_status_record(response, pipeline) if pipeline else "NOT_RUN",
        "manual_comparison": comparison or "NOT_RUN",
        "provider_billed_actual_cost_usd": None,
        "actual_cost_status": "NOT_RECONCILED",
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
                "findings": parsed.get("findings", []),
                "generated_next_instruction": parsed.get("next_instruction"),
                "user_decision_packet": parsed.get("user_decision_packet"),
                "blocker_packet": parsed.get("blocker_packet"),
            })
    atomic_json(RESULT_PATH, result)
    atomic_json(ATTEMPT_PATH, {
        "record_type": "ATTEMPT_COMPLETED", "approval_manifest_sha256": APPROVAL_ID,
        "attempt_count": 1, "network_call_count": 1, "retry_count": 0,
        "fallback_count": 0, "dispatch_count": 0, "baseline_transmission_count": 0,
        "completed_at": now(), "status": status, "http_status": http_status,
        "latency_ms": latency_ms,
    })
    safe = {key: value for key, value in result.items() if key not in {"error_metadata", "response_capture"}}
    print(json.dumps(safe, ensure_ascii=True, indent=2))
    return 0 if http_status == 200 and pipeline and pipeline.error is None else 5


if __name__ == "__main__":
    raise SystemExit(main())
