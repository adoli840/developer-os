from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .candidate import R3_CANDIDATE_PATH
from .fixtures import import_fixture
from .forensic import build_wire_request, sha256_bytes, sha256_json
from .manifest import build_canonical_token_request
from .pricing import SOL_PROPOSAL_PRICING, estimate_usage_cost
from .response_pipeline import capture_response_bytes, parse_response, provider_status_record
from .run import build_manual_comparison_packet


ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATION_DIR = ROOT / ".console" / "orchestration"
APPROVAL_ID = "b19f7822e7b8fb31704c7428357b2aabdf6c4e53492a1fcc86fa742afd4b59a5"
EXPECTED_CANDIDATE_FILE = "0e2258eaa342935c5bba114b5145a9a6207e1a038c2486bb85db75b22595b6ae"
EXPECTED_RUNTIME_PROTOCOL = "dbbdf789455132fd6dc79d806752a0c0ee49538615616ee81c3d96319a5905ba"
EXPECTED_WIRE = "c6eca7a307a8e1bf1513d94dc5dfc802f6c452431dd169a1c75c8b2771944301"
EXPECTED_CANONICAL = "890a36db5e405996478b087207ebcd9a5ce63c2fcbdcb8e85485ad0638948db7"
EXPECTED_PROMPT = "b39c772159258904bfb3fbf9b432640a8dd76cbd59e62ac6cae8e5229662ecee"
EXPECTED_SCHEMA = "b34710ce7c074ba36c489bb3c9be3714bae7d44607221a74a55c8ffc0afc1032"
EXPECTED_PRICING = "82102613215bbfa722ea3cdb5c25cee7edfb7f1e301a5d1f9aa569579695d033"
APPROVAL_PATH = ORCHESTRATION_DIR / f"approval-{APPROVAL_ID}.json"
ATTEMPT_PATH = ORCHESTRATION_DIR / f"attempt-{APPROVAL_ID}.json"
RESULT_PATH = ORCHESTRATION_DIR / f"result-{APPROVAL_ID}.json"
CAPTURE_DIR = ORCHESTRATION_DIR / f"response-{APPROVAL_ID}"


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_key() -> str:
    env_path = ROOT / ".env"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        name, separator, value = line.partition("=")
        if separator and name.strip() == "OPENAI_ORCHESTRATION_API_KEY" and value.strip():
            return value.strip().strip('"').strip("'")
    raise RuntimeError("OPENAI_ORCHESTRATION_API_KEY unavailable")


def usage_cost(usage: dict[str, Any]) -> tuple[dict[str, int], str]:
    tokens, cost = estimate_usage_cost(SOL_PROPOSAL_PRICING, usage)
    return tokens, format(cost, ".6f")


def verify_candidate() -> tuple[dict[str, Any], dict[str, Any]]:
    raw = R3_CANDIDATE_PATH.read_bytes()
    if sha256_bytes(raw) != EXPECTED_CANDIDATE_FILE:
        raise RuntimeError("APPROVAL_MANIFEST_MISMATCH")
    candidate = json.loads(raw.decode("utf-8"))
    manifest = dict(candidate["manifest"])
    supplied = manifest.pop("approval_manifest_sha256", None)
    if supplied != APPROVAL_ID or sha256_json(manifest) != APPROVAL_ID:
        raise RuntimeError("APPROVAL_MANIFEST_MISMATCH")
    manifest["approval_manifest_sha256"] = supplied
    if manifest.get("runtime_protocol_sha256") != EXPECTED_RUNTIME_PROTOCOL or manifest.get("approved_for_external_api") is not False:
        raise RuntimeError("APPROVAL_MANIFEST_MISMATCH")
    if manifest.get("timeout_seconds") != 600.0 or manifest.get("retry_count") != 0 or manifest.get("planned_response_call_count") != 1:
        raise RuntimeError("APPROVAL_MANIFEST_MISMATCH")
    if manifest.get("hard_worst_case_cost_usd") > "0.65":
        raise RuntimeError("BUDGET_BLOCKED")
    fixture = import_fixture(Path(r"X:\01_codex_task.txt"), Path(r"X:\02_codex_report.txt"), Path(r"X:\03_manual_sol_review.txt"), project="bTest", historical_date="2026-08-12")
    canonical = build_canonical_token_request(fixture)
    wire = build_wire_request(canonical)
    checks = {
        "wire": sha256_json(wire), "canonical": sha256_json(canonical),
        "prompt": manifest["serialized_reviewer_prompt_sha256"], "schema": manifest["structured_output_schema_sha256"],
        "pricing": manifest["pricing_record_sha256"],
    }
    if checks != {"wire": EXPECTED_WIRE, "canonical": EXPECTED_CANONICAL, "prompt": EXPECTED_PROMPT, "schema": EXPECTED_SCHEMA, "pricing": EXPECTED_PRICING}:
        raise RuntimeError("APPROVAL_MANIFEST_MISMATCH")
    return manifest, wire


def main() -> int:
    if any(path.exists() for path in (APPROVAL_PATH, ATTEMPT_PATH, RESULT_PATH)):
        print(json.dumps({"status": "ALREADY_CONSUMED"}))
        return 4
    try:
        manifest, wire = verify_candidate()
        key = load_key()
    except Exception as error:
        print(json.dumps({"status": str(error)}))
        return 2

    atomic_json(APPROVAL_PATH, {"record_type": "one_time_user_live_approval", "approval_manifest_sha256": APPROVAL_ID, "approved_external_transmission": True, "approved_local_response_capture": True, "approved_cost_cap_usd": "0.65", "approved_attempt_count": 1, "approved_model": "gpt-5.6-sol", "timeout_seconds": 600, "approval_source": "explicit_user_instruction", "approved_at": now()})
    atomic_json(ATTEMPT_PATH, {"record_type": "ATTEMPT_STARTED", "approval_manifest_sha256": APPROVAL_ID, "started_at": now(), "attempt_count": 1, "network_call_count": 0, "retry_count": 0, "fallback_count": 0, "dispatch_count": 0, "baseline_transmission_count": 0})

    started = time.perf_counter()
    response: dict[str, Any] = {}
    body: bytes | None = None
    status = "NETWORK_ERROR"
    http_status: int | None = None
    error_metadata: dict[str, Any] | None = None
    try:
        request = urllib.request.Request("https://api.openai.com/v1/responses", data=json.dumps(wire, ensure_ascii=False).encode("utf-8"), headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=600.0) as stream:
            body = stream.read()
        response = json.loads(body.decode("utf-8"))
        status = response.get("status", "completed")
        http_status = 200
    except urllib.error.HTTPError as error:
        body = error.read(1_000_000)
        http_status = error.code
        error_metadata = {"http_status": error.code, "response_body_bytes": len(body), "error_body_parse_status": "RETAINED_SEPARATELY"}
        status = "HTTP_ERROR"
    except Exception as error:
        status = type(error).__name__.upper()
    latency_ms = round((time.perf_counter() - started) * 1000, 2)

    capture = None
    pipeline = None
    if body is not None and http_status == 200:
        capture = capture_response_bytes(body, CAPTURE_DIR)
        pipeline = parse_response(response)
    result: dict[str, Any] = {"status": status, "approval_manifest_sha256": APPROVAL_ID, "request_attempts": 1, "http_status": http_status, "response_id": response.get("id"), "returned_model": response.get("model"), "latency_ms": latency_ms, "retry_count": 0, "fallback_count": 0, "dispatch_count": 0, "baseline_transmission_count": 0, "error_metadata": error_metadata, "response_capture": capture, "provider_status": provider_status_record(response, pipeline) if pipeline else "NOT_RUN", "manual_comparison_packet": build_manual_comparison_packet(manual_gate="PENDING", api_gate=None)}
    if response:
        tokens, cost = usage_cost(response.get("usage", {}))
        result.update({"tokens": tokens, "usage_based_estimated_cost_usd": cost, "provider_billed_actual_cost_usd": None, "actual_cost_status": "NOT_RECONCILED"})
    if pipeline:
        result.update({"processing_stages": pipeline.stages, "structured_parsing": "PASS" if pipeline.parsed_output is not None else "FAIL", "parse_error": pipeline.error})
        if pipeline.parsed_output is not None:
            result["reviewer_gate"] = pipeline.parsed_output.get("gate_decision")
            result["findings"] = pipeline.parsed_output.get("findings", [])
            result["executive_summary"] = pipeline.parsed_output.get("executive_summary")
            result["manual_comparison_packet"] = build_manual_comparison_packet(manual_gate="PENDING", api_gate=pipeline.parsed_output.get("gate_decision"))
    atomic_json(RESULT_PATH, result)
    atomic_json(ATTEMPT_PATH, {"record_type": "ATTEMPT_COMPLETED", "approval_manifest_sha256": APPROVAL_ID, "attempt_count": 1, "network_call_count": 1 if body is not None else 0, "retry_count": 0, "fallback_count": 0, "dispatch_count": 0, "baseline_transmission_count": 0, "completed_at": now(), "status": status, "http_status": http_status, "latency_ms": latency_ms})
    print(json.dumps({key: value for key, value in result.items() if key not in {"error_metadata", "response_capture"}}, ensure_ascii=True, indent=2))
    return 0 if body is not None else 5


if __name__ == "__main__":
    raise SystemExit(main())
