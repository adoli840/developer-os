from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .fixtures import build_reviewer_prompt, import_fixture
from .forensic import build_wire_request, parse_error_metadata
from .gate import validate_review_output
from .manifest import build_canonical_token_request, canonical_json, sha256_bytes, sha256_json
from .pricing import SOL_PROPOSAL_PRICING, estimate_cost
from .schema import reviewer_output_schema


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / ".console" / "orchestration" / "phase1b-r2-candidate-manifest.json"
APPROVAL_PATH = ROOT / ".console" / "orchestration" / "approval-48ffc98c.json"
ATTEMPT_PATH = ROOT / ".console" / "orchestration" / "attempt-48ffc98c.json"
RESULT_PATH = ROOT / ".console" / "orchestration" / "result-48ffc98c.json"
EXPECTED_APPROVAL = "48ffc98c27cf88fb14c22f9cb8d20421330169928b95a7dfaf9f814a7ae77e82"
EXPECTED_FILE = "571f9eb45dcb078c968f9b76a12d1819411c9e18d4f23ebc6d0599548d92ee62"
EXPECTED_WIRE = "c6eca7a307a8e1bf1513d94dc5dfc802f6c452431dd169a1c75c8b2771944301"
EXPECTED_CANONICAL = "890a36db5e405996478b087207ebcd9a5ce63c2fcbdcb8e85485ad0638948db7"
EXPECTED_PROMPT = "b39c772159258904bfb3fbf9b432640a8dd76cbd59e62ac6cae8e5229662ecee"
EXPECTED_SCHEMA = "b34710ce7c074ba36c489bb3c9be3714bae7d44607221a74a55c8ffc0afc1032"
EXPECTED_PRICING = "82102613215bbfa722ea3cdb5c25cee7edfb7f1e301a5d1f9aa569579695d033"


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_key() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        name, separator, value = line.partition("=")
        if separator and name.strip() == "OPENAI_ORCHESTRATION_API_KEY" and value.strip():
            return value.strip().strip('"').strip("'")
    raise RuntimeError("OPENAI_ORCHESTRATION_API_KEY unavailable")


def verify() -> tuple[dict[str, Any], dict[str, Any]]:
    raw = MANIFEST_PATH.read_bytes()
    if __import__("hashlib").sha256(raw).hexdigest() != EXPECTED_FILE:
        raise RuntimeError("APPROVAL_MANIFEST_MISMATCH")
    envelope = json.loads(raw.decode("utf-8"))
    manifest = envelope["manifest"]
    supplied = manifest.pop("approval_manifest_sha256", None)
    try:
        if supplied != EXPECTED_APPROVAL or sha256_json(manifest) != EXPECTED_APPROVAL:
            raise RuntimeError("APPROVAL_MANIFEST_MISMATCH")
    finally:
        manifest["approval_manifest_sha256"] = supplied
    if manifest["approved_for_external_api"] is not False:
        raise RuntimeError("APPROVAL_MANIFEST_MISMATCH")
    if float(manifest["timeout_seconds"]) != 600.0 or manifest["retry_count"] != 0 or manifest["planned_response_call_count"] != 1:
        raise RuntimeError("APPROVAL_MANIFEST_MISMATCH")
    if manifest["hard_worst_case_cost_usd"] > "0.65":
        raise RuntimeError("BUDGET_BLOCKED")
    fixture = import_fixture(Path(r"X:\01_codex_task.txt"), Path(r"X:\02_codex_report.txt"), Path(r"X:\03_manual_sol_review.txt"), project="bTest", historical_date="2026-08-12")
    canonical = build_canonical_token_request(fixture)
    prompt = build_reviewer_prompt(fixture)
    wire = build_wire_request(canonical)
    checks = {
        "wire": sha256_json(wire), "canonical": sha256_json(canonical), "prompt": sha256_bytes(prompt.encode("utf-8")),
        "schema": sha256_json(reviewer_output_schema()), "pricing": manifest["pricing_record_sha256"],
    }
    if checks != {"wire": EXPECTED_WIRE, "canonical": EXPECTED_CANONICAL, "prompt": EXPECTED_PROMPT, "schema": EXPECTED_SCHEMA, "pricing": EXPECTED_PRICING}:
        raise RuntimeError("APPROVAL_MANIFEST_MISMATCH")
    return manifest, wire


def extract_output(response: dict[str, Any]) -> dict[str, Any]:
    for item in response.get("output", []) if isinstance(response.get("output"), list) else []:
        for content in item.get("content", []) if isinstance(item, dict) else []:
            if content.get("type") in {"output_json", "json"}:
                value = content.get("json", content.get("text"))
                if isinstance(value, dict):
                    return value
                if isinstance(value, str) and isinstance(json.loads(value), dict):
                    return json.loads(value)
    raise ValueError("structured output missing")


def usage_details(usage: dict[str, Any]) -> tuple[dict[str, int], str | None, str]:
    input_tokens = int(usage.get("input_tokens", 0) or 0)
    cached = int((usage.get("input_tokens_details") or {}).get("cached_tokens", 0) or 0)
    output_tokens = int(usage.get("output_tokens", 0) or 0)
    reasoning = int((usage.get("output_tokens_details") or {}).get("reasoning_tokens", 0) or 0)
    uncached = max(0, input_tokens - cached)
    cost = estimate_cost(SOL_PROPOSAL_PRICING, uncached_input=uncached, cached_input=cached, cache_write=0, output=output_tokens)
    tokens = {"input_tokens": input_tokens, "cached_input_tokens": cached, "cache_write_tokens": 0, "output_tokens": output_tokens, "reasoning_tokens": reasoning, "total_tokens": int(usage.get("total_tokens", input_tokens + output_tokens) or 0)}
    # Usage can estimate this request; it does not prove provider-billed cost.
    return tokens, str(cost), "NOT_RECONCILED"


def main() -> int:
    if any(path.exists() for path in (APPROVAL_PATH, ATTEMPT_PATH, RESULT_PATH)):
        print(json.dumps({"status": "ALREADY_CONSUMED"}))
        return 4
    try:
        manifest, wire = verify()
        key = load_key()
    except Exception as error:
        print(json.dumps({"status": str(error)}))
        return 2
    atomic_json(APPROVAL_PATH, {"record_type": "one_time_user_live_approval", "approval_manifest_sha256": EXPECTED_APPROVAL, "approved_external_transmission": True, "approved_cost_cap_usd": "0.65", "approved_attempt_count": 1, "approved_model": "gpt-5.6-sol", "timeout_seconds": 600, "approval_source": "explicit_user_instruction", "approved_at": now()})
    atomic_json(ATTEMPT_PATH, {"record_type": "ATTEMPT_STARTED", "approval_manifest_sha256": EXPECTED_APPROVAL, "started_at": now(), "attempt_count": 1, "network_call_count": 0, "retry_count": 0, "fallback_count": 0, "dispatch_count": 0, "baseline_transmission_count": 0})
    started = time.perf_counter()
    response: dict[str, Any] = {}
    status = "NETWORK_ERROR"
    http_status: int | None = None
    error_metadata: dict[str, Any] | None = None
    try:
        request = urllib.request.Request("https://api.openai.com/v1/responses", data=json.dumps(wire, ensure_ascii=False).encode("utf-8"), headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=600.0) as stream:
            response = json.loads(stream.read().decode("utf-8"))
        status = response.get("status", "COMPLETED")
        http_status = 200
    except urllib.error.HTTPError as error:
        body = error.read(1_000_000)
        http_status = error.code
        error_metadata = parse_error_metadata(http_status=error.code, headers=dict(error.headers.items()), body=body)
        status = "HTTP_ERROR"
    except TimeoutError:
        status = "TIMEOUT"
    except Exception as error:
        status = type(error).__name__.upper()
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    result: dict[str, Any] = {"status": status, "approval_manifest_sha256": EXPECTED_APPROVAL, "request_attempts": 1, "http_status": http_status, "response_id": response.get("id"), "returned_model": response.get("model"), "latency_ms": latency_ms, "retry_count": 0, "fallback_count": 0, "dispatch_count": 0, "baseline_transmission_count": 0, "error_metadata": error_metadata, "actual_cost_usd": None, "actual_cost_status": "NOT_RECONCILED", "manual_comparison_packet": {"manual_semantic_comparison_status": "PENDING_REVIEW", "baseline_transmission_count": 0}}
    if response:
        tokens, cost, reconciliation = usage_details(response.get("usage", {}))
        result.update({"tokens": tokens, "usage_based_estimated_cost_usd": cost, "actual_cost_usd": None, "actual_cost_status": reconciliation})
        try:
            parsed = extract_output(response)
            validate_review_output(parsed)
            result.update({"structured_parsing": "PASS", "deterministic_gate_validation": "PASS", "reviewer_gate": parsed["gate_decision"], "executive_summary": parsed["executive_summary"], "contract_assessment": parsed["contract_assessment"], "findings": parsed["findings"], "evidence_refs": parsed["evidence_refs"], "next_instruction": parsed["next_instruction"], "user_decision_packet": parsed["user_decision_packet"], "blocker_packet": parsed["blocker_packet"]})
        except Exception as error:
            result.update({"structured_parsing": "FAIL", "deterministic_gate_validation": "FAIL", "parse_error": type(error).__name__})
    else:
        result.update({"structured_parsing": "NOT_RUN", "deterministic_gate_validation": "NOT_RUN"})
    atomic_json(RESULT_PATH, result)
    atomic_json(ATTEMPT_PATH, {"record_type": "ATTEMPT_COMPLETED", "approval_manifest_sha256": EXPECTED_APPROVAL, "attempt_count": 1, "network_call_count": 1, "retry_count": 0, "fallback_count": 0, "dispatch_count": 0, "baseline_transmission_count": 0, "completed_at": now(), "status": status, "http_status": http_status, "latency_ms": latency_ms})
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if response else 5


if __name__ == "__main__":
    raise SystemExit(main())
