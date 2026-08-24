from __future__ import annotations

import hashlib
import json
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from typing import Any

from .api_mainline_bootstrap import MODEL, TIMEOUT_SECONDS, _cost_preflight
from .api_mainline_continuation import (
    CONTINUATION_MAX_OUTPUT_TOKENS,
    CONTINUATION_PROMPT_VERSION,
    REVIEWER_SCHEMA_VERSION,
    CONTINUATION_RUNTIME_VERSION,
    CONTINUATION_SCHEMA_VERSION,
    build_continuation_request,
    validation_provenance,
)
from .fixtures import SECRET_PATTERNS
from .manifest import canonical_json, sha256_json
from .pricing import SOL_PROPOSAL_PRICING, pricing_record_payload
from .task_alignment import canonical_next_step_catalog
from .token_efficiency import (
    TOKEN_EFFICIENCY_POLICY_VERSION,
    evaluation_identity_sha256,
)


RETRY_CANDIDATE_VERSION = "2c.auto-pilot-retry.2"


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_retry_candidate(
    output: Path,
    *,
    source_candidate_path: Path,
    dispatch_artifact_path: Path,
    canonical_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if output.exists():
        raise ValueError("AUTO_SAFE_CONTINUE_RETRY_CANDIDATE_EXISTS")
    source_raw = source_candidate_path.read_bytes()
    source = json.loads(source_raw.decode("utf-8"))
    dispatch_raw = dispatch_artifact_path.read_bytes()
    dispatch = json.loads(dispatch_raw.decode("utf-8"))
    task = (dispatch.get("rendered_message") or {}).get("message")
    report = source.get("exact_result")
    source_state = source.get("canonical_state")
    state = canonical_state if canonical_state is not None else source_state
    if not all((isinstance(task, str), isinstance(report, str), isinstance(state, dict))):
        raise ValueError("AUTO_SAFE_CONTINUE_RETRY_SOURCE_INVALID")
    task_hash = hashlib.sha256(task.encode("utf-8")).hexdigest()
    report_hash = hashlib.sha256(report.encode("utf-8")).hexdigest()
    if (
        task_hash != dispatch.get("task_content_sha256")
        or report_hash != source.get("manifest", {}).get("exact_result_sha256")
        or dispatch.get("handoff_id") != source.get("manifest", {}).get("source_dispatch_id")
    ):
        raise ValueError("AUTO_SAFE_CONTINUE_RETRY_SOURCE_BINDING_MISMATCH")

    request, prompt, inventory = build_continuation_request(state, task, report)
    serialized = canonical_json(request)
    if any(pattern.search(serialized) for pattern in SECRET_PATTERNS):
        raise ValueError("AUTO_SAFE_CONTINUE_RETRY_SECRET_SCAN_FAILED")
    preflight = _cost_preflight(request)
    cumulative = Decimal(preflight["hard_worst_case_cost_usd"]) * Decimal(2)
    proposed_cap = cumulative.quantize(Decimal("0.01"), rounding=ROUND_CEILING)
    provenance = validation_provenance()
    canonical_state_hash = sha256_json(state)
    dynamic_payload_hash = hashlib.sha256(
        request["input"][1]["content"].encode("utf-8"),
    ).hexdigest()
    evaluation_hash = evaluation_identity_sha256(
        canonical_state_sha256=canonical_state_hash,
        task_sha256=task_hash,
        report_sha256=report_hash,
        protocol_version=CONTINUATION_SCHEMA_VERSION,
        reviewer_schema_version=REVIEWER_SCHEMA_VERSION,
    )
    workspace_hash = (
        ((dispatch.get("dispatch_envelope") or {}).get("workspace") or {})
        .get("workspace_fingerprint_sha256")
    )
    runtime = {
        "version": CONTINUATION_RUNTIME_VERSION,
        "timeout_seconds": TIMEOUT_SECONDS,
        "max_auto_cycles": 2,
        "retry_count": 0,
        "fallback_count": 0,
        "dispatch_count": 0,
        "approved_cumulative_cap_usd": None,
        "live_execution": "LOCKED_NEW_APPROVAL_REQUIRED",
    }
    binding = {
        "source_candidate_file_sha256": hashlib.sha256(source_raw).hexdigest(),
        "source_dispatch_file_sha256": hashlib.sha256(dispatch_raw).hexdigest(),
        "task_content_sha256": task_hash,
        "report_content_sha256": report_hash,
        "canonical_state_sha256": canonical_state_hash,
        "next_step_catalog_sha256": sha256_json(canonical_next_step_catalog(state)),
        "requirement_inventory_sha256": sha256_json(inventory),
        "request_sha256": hashlib.sha256(serialized).hexdigest(),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "stable_prefix_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "dynamic_payload_sha256": dynamic_payload_hash,
        "evaluation_identity_sha256": evaluation_hash,
        "workspace_fingerprint_sha256": workspace_hash,
        "structured_output_schema_sha256": sha256_json(request["text"]["format"]["schema"]),
        "validation_provenance_sha256": provenance["provenance_sha256"],
        "runtime_protocol_sha256": sha256_json(runtime),
        "pricing_record_sha256": sha256_json(pricing_record_payload(SOL_PROPOSAL_PRICING)),
        "token_efficiency_policy_version": TOKEN_EFFICIENCY_POLICY_VERSION,
    }
    manifest = {
        "manifest_version": RETRY_CANDIDATE_VERSION,
        "candidate_type": "AUTO_SAFE_CONTINUE_RETRY_PREFLIGHT",
        "model": MODEL,
        "prompt_version": CONTINUATION_PROMPT_VERSION,
        "schema_version": CONTINUATION_SCHEMA_VERSION,
        **binding,
        "max_output_tokens": CONTINUATION_MAX_OUTPUT_TOKENS,
        "timeout_seconds": TIMEOUT_SECONDS,
        "max_auto_cycles": 2,
        "per_call_hard_worst_case_usd": preflight["hard_worst_case_cost_usd"],
        "cumulative_hard_worst_case_usd": str(cumulative),
        "proposed_cumulative_cap_usd": str(proposed_cap),
        "approved_for_external_api": False,
    }
    manifest["approval_manifest_sha256"] = sha256_json(manifest)
    candidate = {
        "candidate_type": "AUTO_SAFE_CONTINUE_RETRY_PREFLIGHT",
        "manifest": manifest,
        "binding": binding,
        "canonical_state": state,
        "request": request,
        "requirement_inventory": inventory,
        "validation_provenance": provenance,
        "runtime_protocol": runtime,
        "preflight": preflight,
        "state": "PREPARED",
        "approved_for_external_api": False,
        "approval_record": False,
        "attempt_record": False,
        "result_record": False,
        "network_calls": 0,
        "codex_turns": 0,
        "dispatch_count": 0,
    }
    candidate["candidate_sha256"] = sha256_json(candidate)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(candidate, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return {
        "candidate_file": str(output),
        "candidate_file_sha256": _file_sha256(output),
        "candidate_sha256": candidate["candidate_sha256"],
        "approval_manifest_sha256": manifest["approval_manifest_sha256"],
        "request_sha256": binding["request_sha256"],
        "prompt_sha256": binding["prompt_sha256"],
        "schema_sha256": binding["structured_output_schema_sha256"],
        "validation_provenance_sha256": binding["validation_provenance_sha256"],
        "runtime_protocol_sha256": binding["runtime_protocol_sha256"],
        "request_bytes": preflight["request_utf8_bytes"],
        "hard_input_bound": preflight["hard_input_token_upper_bound"],
        "per_call_hard_worst_case_usd": preflight["hard_worst_case_cost_usd"],
        "cumulative_hard_worst_case_usd": str(cumulative),
        "proposed_cumulative_cap_usd": str(proposed_cap),
        "approved_for_external_api": False,
        "approval_record": False,
        "attempt_record": False,
        "result_record": False,
        "network_calls": 0,
    }


def verify_retry_candidate(candidate: dict[str, Any]) -> None:
    unsigned = dict(candidate)
    supplied_candidate_sha256 = unsigned.pop("candidate_sha256", None)
    if supplied_candidate_sha256 != sha256_json(unsigned):
        raise ValueError("AUTO_SAFE_CONTINUE_RETRY_CANDIDATE_HASH_MISMATCH")
    manifest = candidate.get("manifest") or {}
    unsigned_manifest = dict(manifest)
    supplied_manifest_sha256 = unsigned_manifest.pop("approval_manifest_sha256", None)
    if supplied_manifest_sha256 != sha256_json(unsigned_manifest):
        raise ValueError("AUTO_SAFE_CONTINUE_RETRY_MANIFEST_HASH_MISMATCH")
    if (
        candidate.get("state") != "PREPARED"
        or candidate.get("approved_for_external_api") is not False
        or candidate.get("approval_record") is not False
        or candidate.get("attempt_record") is not False
        or candidate.get("result_record") is not False
        or candidate.get("network_calls") != 0
        or candidate.get("codex_turns") != 0
        or candidate.get("dispatch_count") != 0
    ):
        raise ValueError("AUTO_SAFE_CONTINUE_RETRY_NOT_PRISTINE")
    request = candidate["request"]
    binding = candidate["binding"]
    inventory = candidate["requirement_inventory"]
    provenance = candidate["validation_provenance"]
    runtime = candidate["runtime_protocol"]
    expected = {
        "request_sha256": hashlib.sha256(canonical_json(request)).hexdigest(),
        "prompt_sha256": hashlib.sha256(request["input"][0]["content"].encode("utf-8")).hexdigest(),
        "stable_prefix_sha256": hashlib.sha256(
            request["input"][0]["content"].encode("utf-8"),
        ).hexdigest(),
        "dynamic_payload_sha256": hashlib.sha256(
            request["input"][1]["content"].encode("utf-8"),
        ).hexdigest(),
        "structured_output_schema_sha256": sha256_json(request["text"]["format"]["schema"]),
        "canonical_state_sha256": sha256_json(candidate.get("canonical_state", {})),
        "next_step_catalog_sha256": sha256_json(
            canonical_next_step_catalog(candidate.get("canonical_state", {})),
        ),
        "requirement_inventory_sha256": sha256_json(inventory),
        "validation_provenance_sha256": provenance["provenance_sha256"],
        "runtime_protocol_sha256": sha256_json(runtime),
        "pricing_record_sha256": sha256_json(pricing_record_payload(SOL_PROPOSAL_PRICING)),
        "token_efficiency_policy_version": TOKEN_EFFICIENCY_POLICY_VERSION,
    }
    expected["evaluation_identity_sha256"] = evaluation_identity_sha256(
        canonical_state_sha256=expected["canonical_state_sha256"],
        task_sha256=binding["task_content_sha256"],
        report_sha256=binding["report_content_sha256"],
        protocol_version=candidate["manifest"]["schema_version"],
        reviewer_schema_version=validation_provenance()["reviewer_schema_version"],
    )
    # Older generated candidates did not duplicate canonical state outside their request.
    if "canonical_state" not in candidate:
        expected.pop("canonical_state_sha256")
        expected.pop("next_step_catalog_sha256")
    if any(binding.get(key) != value for key, value in expected.items()):
        raise ValueError("AUTO_SAFE_CONTINUE_RETRY_BINDING_MISMATCH")
    if provenance != validation_provenance():
        raise ValueError("AUTO_SAFE_CONTINUE_RETRY_PROVENANCE_MISMATCH")
    if candidate["preflight"] != _cost_preflight(request):
        raise ValueError("AUTO_SAFE_CONTINUE_RETRY_COST_MISMATCH")
    cumulative = Decimal(candidate["preflight"]["hard_worst_case_cost_usd"]) * Decimal(2)
    if str(cumulative) != manifest.get("cumulative_hard_worst_case_usd"):
        raise ValueError("AUTO_SAFE_CONTINUE_RETRY_CUMULATIVE_COST_MISMATCH")
    if cumulative > Decimal(manifest["proposed_cumulative_cap_usd"]):
        raise ValueError("AUTO_SAFE_CONTINUE_RETRY_BUDGET_BLOCKED")
