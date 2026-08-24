from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from .fixtures import build_reviewer_prompt, import_fixture
from .forensic import parse_error_metadata
from .gate import validate_review_output
from .manifest import build_canonical_token_request, canonical_json, sha256_bytes, sha256_json
from .pricing import SOL_PROPOSAL_PRICING, estimate_cost
from .schema import reviewer_output_schema
from .state import build_initial_state


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / ".console" / "orchestration" / "phase1b-approval-manifest.json"
ATTEMPT_PATH = ROOT / ".console" / "orchestration" / "attempt-5efd79b9.json"
APPROVAL_PATH = ROOT / ".console" / "orchestration" / "approval-5efd79b9.json"
RESULT_PATH = ROOT / ".console" / "orchestration" / "result-5efd79b9.json"
EXPECTED_MANIFEST = "5efd79b9fe8460714779d8753d9f8ec4734bfe47f12ac49e3a99fcffde71b06f"
EXPECTED_CANONICAL = "8cd1f430c755778a399dee469b077b8db84322120a408894ee119230bde0223e"
EXPECTED_PROMPT = "b39c772159258904bfb3fbf9b432640a8dd76cbd59e62ac6cae8e5229662ecee"
EXPECTED_SCHEMA = "cd7d30fe792a5cf6eb7123cebb4f2e6b378f1e5cbc3a19dcf5b21cbe04a6fe8c"
EXPECTED_PRICING = "82102613215bbfa722ea3cdb5c25cee7edfb7f1e301a5d1f9aa569579695d033"


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_key() -> str:
    env_path = ROOT / ".env"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        name, separator, value = line.partition("=")
        if separator and name.strip() == "OPENAI_ORCHESTRATION_API_KEY":
            value = value.strip().strip('"').strip("'")
            if value:
                return value
    raise RuntimeError("OPENAI_ORCHESTRATION_API_KEY is unavailable")


def load_and_verify() -> tuple[dict[str, Any], dict[str, Any], str, str]:
    envelope = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest = envelope["manifest"]
    supplied_hash = manifest.pop("approval_manifest_sha256", None)
    if supplied_hash != EXPECTED_MANIFEST or sha256_json(manifest) != EXPECTED_MANIFEST:
        raise RuntimeError("APPROVAL_MANIFEST_MISMATCH")
    manifest["approval_manifest_sha256"] = supplied_hash
    if manifest["approved_for_external_api"] is not False:
        raise RuntimeError("manifest approval flag must remain false")
    fixture = import_fixture(Path(r"X:\01_codex_task.txt"), Path(r"X:\02_codex_report.txt"), Path(r"X:\03_manual_sol_review.txt"), project="bTest", historical_date="2026-08-12")
    if fixture.get("status") != "MATCHED_FIXTURE_REGISTERED":
        raise RuntimeError(fixture.get("status", "FIXTURE_INVALID"))
    state = build_initial_state("historical-btest-2026-08-12", "bTest", "Phase 1B live reviewer request")
    request = build_canonical_token_request(fixture)
    prompt = build_reviewer_prompt(fixture)
    checks = {
        "canonical": sha256_json(request),
        "prompt": sha256_bytes(prompt.encode("utf-8")),
        "schema": sha256_json(reviewer_output_schema()),
        "pricing": manifest["pricing_record_sha256"],
    }
    if checks["canonical"] != EXPECTED_CANONICAL or checks["prompt"] != EXPECTED_PROMPT or checks["schema"] != EXPECTED_SCHEMA or checks["pricing"] != EXPECTED_PRICING:
        raise RuntimeError("APPROVAL_MANIFEST_MISMATCH")
    if manifest["hard_worst_case_cost_usd"] > "0.65":
        raise RuntimeError("BUDGET_POLICY_REQUIRED")
    return manifest, fixture, prompt, json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def extract_output(response: dict[str, Any]) -> dict[str, Any]:
    output = response.get("output", [])
    for item in output if isinstance(output, list) else []:
        for content in item.get("content", []) if isinstance(item, dict) else []:
            if content.get("type") in {"output_json", "json"}:
                value = content.get("json", content.get("text"))
                if isinstance(value, dict):
                    return value
                if isinstance(value, str):
                    parsed = json.loads(value)
                    if isinstance(parsed, dict):
                        return parsed
    raise ValueError("structured output missing")


def usage_cost(usage: dict[str, Any]) -> tuple[dict[str, Any], str | None, str]:
    input_tokens = int(usage.get("input_tokens", 0) or 0)
    cached = int((usage.get("input_tokens_details") or {}).get("cached_tokens", usage.get("cached_input_tokens", 0)) or 0)
    output_tokens = int(usage.get("output_tokens", 0) or 0)
    reasoning = int((usage.get("output_tokens_details") or {}).get("reasoning_tokens", usage.get("reasoning_tokens", 0)) or 0)
    uncached = max(0, input_tokens - cached)
    cost = estimate_cost(SOL_PROPOSAL_PRICING, uncached_input=uncached, cached_input=cached, cache_write=0, output=output_tokens)
    fields = {"input_tokens": input_tokens, "cached_input_tokens": cached, "cache_write_tokens": 0, "uncached_input_tokens": uncached, "output_tokens": output_tokens, "reasoning_tokens": reasoning, "total_tokens": int(usage.get("total_tokens", input_tokens + output_tokens) or 0)}
    return fields, str(cost), "RECONCILED" if "input_tokens" in usage and "output_tokens" in usage else "PARTIAL_USAGE"


def main() -> int:
    if ATTEMPT_PATH.exists():
        print(json.dumps({"status": "ATTEMPT_ALREADY_RECORDED", "network_calls": "unknown_from_current_process"}))
        return 4
    try:
        manifest, fixture, prompt, canonical_text = load_and_verify()
        key = read_key()
    except Exception as error:
        print(json.dumps({"status": str(error)}))
        return 2
    approval = {"record_type": "one_time_user_live_approval", "manifest_hash": EXPECTED_MANIFEST, "approved_at": now(), "network_call_limit": 1, "retry_count": 0, "fallback": False, "dispatch": False}
    atomic_json(APPROVAL_PATH, approval)
    attempt = {"record_type": "ATTEMPT_STARTED", "manifest_hash": EXPECTED_MANIFEST, "started_at": now(), "request_attempt": 1, "network_calls": 0, "retry_count": 0, "dispatch_count": 0, "baseline_transmissions": 0}
    atomic_json(ATTEMPT_PATH, attempt)
    payload = {
        "model": manifest["model"], "input": json.loads(canonical_text)["messages"],
        "reasoning": {"effort": manifest["reasoning_effort"]}, "text": json.loads(canonical_text)["text"],
        "store": False, "tools": [], "background": False, "max_output_tokens": manifest["max_output_tokens"],
    }
    started = time.perf_counter()
    try:
        request = urllib.request.Request("https://api.openai.com/v1/responses", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=float(manifest["timeout_seconds"])) as response_stream:
            response = json.loads(response_stream.read().decode("utf-8"))
        response_status = response.get("status")
        http_status = 200
        error_class = None
    except urllib.error.HTTPError as error:
        body = error.read(1_000_000)
        response = {"error_metadata": parse_error_metadata(http_status=error.code, headers=dict(error.headers.items()), body=body)}
        response_status = "http_error"
        http_status = error.code
        error_class = "HTTP_ERROR"
    except Exception as error:
        response = {}
        response_status = "transport_error"
        http_status = None
        error_class = type(error).__name__
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    attempt.update({"completed_at": now(), "network_calls": 1, "response_status": response_status, "http_status": http_status, "latency_ms": latency_ms, "retry_count": 0})
    result: dict[str, Any] = {"manifest_hash": EXPECTED_MANIFEST, "request_attempts": 1, "response_status": response_status, "response_id": response.get("id"), "returned_model": response.get("model"), "latency_ms": latency_ms, "error_classification": error_class, "error_metadata": response.get("error_metadata"), "retry_count": 0, "fallback_count": 0, "dispatch_count": 0, "baseline_transmissions": 0}
    if response:
        usage = response.get("usage", {})
        tokens, actual_cost, reconciliation = usage_cost(usage)
        result.update({"tokens": tokens, "usage_based_estimated_cost_usd": actual_cost, "actual_cost_usd": actual_cost, "actual_cost_status": reconciliation})
        try:
            parsed = extract_output(response)
            validate_review_output(parsed)
            result.update({"structured_parsing": "PASS", "deterministic_gate_validation": "PASS", "reviewer_gate": parsed.get("gate_decision"), "findings": parsed.get("findings", []), "next_instruction": parsed.get("next_instruction"), "user_decision_packet": parsed.get("user_decision_packet"), "blocker_packet": parsed.get("blocker_packet")})
        except Exception as error:
            result.update({"structured_parsing": "FAIL", "deterministic_gate_validation": "FAIL", "parse_error": type(error).__name__})
    else:
        result.update({"structured_parsing": "NOT_RUN", "deterministic_gate_validation": "NOT_RUN", "actual_cost_usd": None, "actual_cost_status": "NOT_RECONCILED"})
    baseline = Path(r"X:\03_manual_sol_review.txt").read_text(encoding="utf-8")
    manual_gates = re.findall(r"\b(?:SAFE_CONTINUE|USER_REQUIRED|BLOCKED|STOP)\b", baseline)
    result["manual_comparison_packet"] = {"manual_baseline_transmitted": False, "manual_gate_candidates_count": len(manual_gates), "comparison_status": "PENDING_USER_REVIEW"}
    atomic_json(RESULT_PATH, result)
    atomic_json(ATTEMPT_PATH, attempt)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if response else 5


if __name__ == "__main__":
    raise SystemExit(main())
