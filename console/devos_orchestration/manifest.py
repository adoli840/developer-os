from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from .cycle_handoff import (
    build_cycle_reviewer_prompt,
    requirement_inventory_for_cycle_packet,
    verify_cycle_handoff_packet,
)
from .fixtures import REVIEWER_PROMPT_V2, build_reviewer_prompt, build_reviewer_prompt_v2, import_fixture, requirement_inventory_for_fixture
from .pricing import PricingRecord, SOL_PROPOSAL_PRICING, estimate_cost, pricing_record_payload
from .schema import reviewer_output_schema
from .state import build_initial_state


PROMPT_VERSION = "1"
MANIFEST_SCHEMA_VERSION = "1"
MAX_OUTPUT_TOKENS = 16_384
PROPOSED_HARD_CAP = Decimal("0.65")
TIMEOUT_SECONDS = 30.0
V2_PROMPT_VERSION = "2.3"
V2_SCHEMA_VERSION = "2.3"
V2_TIMEOUT_SECONDS = 600.0


def canonical_json(value: Any) -> bytes:
    normalized = unicodedata.normalize("NFC", value) if isinstance(value, str) else value
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value))


def normalized_file_content(path: Path) -> str:
    return unicodedata.normalize("NFC", path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n"))


def build_canonical_token_request(fixture: dict[str, Any], *, model: str = SOL_PROPOSAL_PRICING.model) -> dict[str, Any]:
    files = {item["source_label"]: item for item in fixture["files"]}
    task = normalized_file_content(Path(files["historical_codex_task"]["source"]))
    report = normalized_file_content(Path(files["historical_codex_report"]["source"]))
    return {
        "messages": [
            {"role": "system", "content": "You are the DeveloperOS GPT/Sol independent reviewer."},
            {"role": "developer", "content": "Evaluate only the frozen orchestration safety contract. Do not dispatch instructions."},
            {"role": "developer", "content": "Frozen decisions: LIVE_OPENAI_CALL=OFF; CODEX_AUTO_EXECUTION=OFF; NO_DISPATCH. Manual comparison is post-response only."},
            {"role": "user", "content": "Historical Codex task:\n" + task + "\n\nHistorical Codex report:\n" + report},
        ],
        "model": model,
        "text": {"format": {"type": "json_schema", "name": "developer_os_reviewer_output", "strict": True, "schema": reviewer_output_schema()}, "verbosity": "medium"},
        "reasoning": {"effort": "high"},
        "store": False,
        "tools": [],
        "background": False,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "prompt_version": PROMPT_VERSION,
        "reviewer_schema_version": "1",
    }


def build_canonical_token_request_v2(
    fixture: dict[str, Any], *, model: str = SOL_PROPOSAL_PRICING.model,
    requirement_inventory: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    inventory = requirement_inventory if requirement_inventory is not None else requirement_inventory_for_fixture(fixture)
    return {
        "messages": [
            {"role": "system", "content": "You are the DeveloperOS GPT/Sol independent reviewer."},
            {"role": "developer", "content": REVIEWER_PROMPT_V2},
            {"role": "developer", "content": "Frozen execution contract: no dispatch, no automatic next cycle, and manual baseline is excluded from reviewer input."},
            {"role": "user", "content": build_reviewer_prompt_v2(fixture, requirement_inventory=inventory)},
        ],
        "model": model,
        "text": {
            "format": {
                "type": "json_schema", "name": "developer_os_reviewer_output_v2",
                "strict": True, "schema": reviewer_output_schema(V2_SCHEMA_VERSION),
            },
            "verbosity": "medium",
        },
        "reasoning": {"effort": "high"},
        "store": False,
        "tools": [],
        "background": False,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "prompt_version": V2_PROMPT_VERSION,
        "reviewer_schema_version": V2_SCHEMA_VERSION,
    }


def build_canonical_token_request_v2_from_cycle_packet(
    packet: dict[str, Any], *, model: str = SOL_PROPOSAL_PRICING.model,
) -> dict[str, Any]:
    """Build the official reviewer input from an immutable Cycle Handoff packet."""
    verify_cycle_handoff_packet(packet)
    inventory = requirement_inventory_for_cycle_packet(packet)
    return {
        "messages": [
            {"role": "system", "content": "You are the DeveloperOS GPT/Sol independent reviewer."},
            {"role": "developer", "content": REVIEWER_PROMPT_V2},
            {"role": "developer", "content": "Frozen execution contract: no dispatch, no automatic next cycle, and manual baseline is excluded from reviewer input."},
            {"role": "user", "content": build_cycle_reviewer_prompt(packet)},
        ],
        "model": model,
        "text": {
            "format": {
                "type": "json_schema", "name": "developer_os_reviewer_output_v2",
                "strict": True, "schema": reviewer_output_schema(V2_SCHEMA_VERSION),
            },
            "verbosity": "medium",
        },
        "reasoning": {"effort": "high"},
        "store": False,
        "tools": [],
        "background": False,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "prompt_version": V2_PROMPT_VERSION,
        "reviewer_schema_version": V2_SCHEMA_VERSION,
        "cycle_handoff_packet_sha256": packet["packet_sha256"],
        "task_requirement_inventory_sha256": sha256_json(inventory),
    }


def build_corrected_preflight(canonical_request: dict[str, Any], pricing: PricingRecord = SOL_PROPOSAL_PRICING) -> dict[str, Any]:
    serialized = canonical_json(canonical_request)
    byte_length = len(serialized)
    hard_tokens = math.ceil(byte_length * 1.10) + 2048
    hard_input_cost = estimate_cost(pricing, uncached_input=0, cached_input=0, cache_write=hard_tokens, output=0)
    hard_output_cost = estimate_cost(pricing, uncached_input=0, cached_input=0, cache_write=0, output=MAX_OUTPUT_TOKENS)
    subtotal = hard_input_cost + hard_output_cost
    safety_margin = max(Decimal("0.02"), subtotal * Decimal("0.10"))
    worst = subtotal + safety_margin
    return {
        "canonical_request_utf8_bytes": byte_length,
        "hard_input_token_upper_bound": hard_tokens,
        "hard_input_cost_usd": hard_input_cost,
        "hard_output_cost_usd": hard_output_cost,
        "subtotal_usd": subtotal,
        "safety_margin_usd": safety_margin,
        "hard_worst_case_cost_usd": worst,
        "proposed_hard_cost_cap_usd": PROPOSED_HARD_CAP,
        "status": "READY" if worst <= PROPOSED_HARD_CAP else "BUDGET_POLICY_REQUIRED",
    }


def build_approval_manifest(*, fixture: dict[str, Any], state: dict[str, Any], canonical_request: dict[str, Any], preflight: dict[str, Any], pricing: PricingRecord = SOL_PROPOSAL_PRICING) -> dict[str, Any]:
    request_bytes = canonical_json(canonical_request)
    prompt = build_reviewer_prompt(fixture)
    pricing_record = pricing_record_payload(pricing)
    files = {item["source_label"]: item for item in fixture["files"]}
    manifest = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "fixture_id": fixture["fixture_id"], "historical_date": fixture["historical_date"],
        "task_original_sha256": files["historical_codex_task"]["original_byte_sha256"], "task_normalized_sha256": files["historical_codex_task"]["normalized_content_sha256"],
        "report_original_sha256": files["historical_codex_report"]["original_byte_sha256"], "report_normalized_sha256": files["historical_codex_report"]["normalized_content_sha256"],
        "baseline_original_sha256": files["manual_review_baseline"]["original_byte_sha256"], "baseline_normalized_sha256": files["manual_review_baseline"]["normalized_content_sha256"],
        "orchestration_state_sha256": sha256_json(state),
        "serialized_reviewer_prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
        "structured_output_schema_sha256": sha256_json(reviewer_output_schema()),
        "canonical_token_bearing_request_sha256": sha256_bytes(request_bytes),
        "prompt_version": PROMPT_VERSION, "reviewer_schema_version": "1", "model": pricing.model,
        "reasoning_effort": "high", "reasoning_mode": None, "text_verbosity": "medium", "store": False, "tools": [], "background": False,
        "max_output_tokens": MAX_OUTPUT_TOKENS, "timeout_seconds": TIMEOUT_SECONDS, "retry_count": 0, "planned_response_call_count": 1,
        "pricing_record_sha256": sha256_json(pricing_record), "pricing_effective_date": pricing.pricing_as_of,
        "hard_input_token_upper_bound": preflight["hard_input_token_upper_bound"], "hard_input_cost_usd": str(preflight["hard_input_cost_usd"]),
        "hard_output_cost_usd": str(preflight["hard_output_cost_usd"]), "safety_margin_usd": str(preflight["safety_margin_usd"]),
        "hard_worst_case_cost_usd": str(preflight["hard_worst_case_cost_usd"]), "proposed_hard_cost_cap_usd": str(PROPOSED_HARD_CAP),
        "approved_for_external_api": False, "credential_variable": "OPENAI_ORCHESTRATION_API_KEY",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    manifest["approval_manifest_sha256"] = sha256_json(manifest)
    return manifest


def build_manifest_from_files(task: Path, report: Path, baseline: Path, *, project: str, historical_date: str, run_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    fixture = import_fixture(task, report, baseline, project=project, historical_date=historical_date)
    if fixture.get("status") != "MATCHED_FIXTURE_REGISTERED":
        raise ValueError(fixture["status"])
    state = build_initial_state(run_id, project, "Phase 1B canonical approval preflight")
    request = build_canonical_token_request(fixture)
    preflight = build_corrected_preflight(request)
    manifest = build_approval_manifest(fixture=fixture, state=state, canonical_request=request, preflight=preflight)
    return manifest, {"fixture": fixture, "state": state, "canonical_request": request}, preflight


def build_manifest_from_files_v2(
    task: Path, report: Path, baseline: Path, *, project: str, historical_date: str,
    run_id: str, pricing: PricingRecord = SOL_PROPOSAL_PRICING,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    fixture = import_fixture(task, report, baseline, project=project, historical_date=historical_date)
    if fixture.get("status") != "MATCHED_FIXTURE_REGISTERED":
        raise ValueError(fixture["status"])
    state = build_initial_state(run_id, project, "Phase 1C-R1 Gate Contract v2 calibration")
    requirement_inventory = requirement_inventory_for_fixture(fixture)
    request = build_canonical_token_request_v2(
        fixture, model=pricing.model, requirement_inventory=requirement_inventory,
    )
    preflight = build_corrected_preflight(request, pricing)
    files = {item["source_label"]: item for item in fixture["files"]}
    pricing_record = pricing_record_payload(pricing)
    manifest = {
        "manifest_schema_version": "2",
        "candidate_purpose": "same-fixture Gate Contract v2 calibration; not holdout validation",
        "fixture_id": fixture["fixture_id"], "historical_date": fixture["historical_date"],
        "task_normalized_sha256": files["historical_codex_task"]["normalized_content_sha256"],
        "report_normalized_sha256": files["historical_codex_report"]["normalized_content_sha256"],
        "baseline_normalized_sha256": files["manual_review_baseline"]["normalized_content_sha256"],
        "orchestration_state_sha256": sha256_json(state),
        "serialized_reviewer_prompt_sha256": sha256_json(request["messages"]),
        "structured_output_schema_sha256": sha256_json(
            request["text"]["format"]["schema"],
        ),
        "canonical_token_bearing_request_sha256": sha256_json(request),
        "prompt_version": V2_PROMPT_VERSION, "reviewer_schema_version": V2_SCHEMA_VERSION,
        "model": pricing.model, "reasoning_effort": "high", "reasoning_mode": None,
        "text_verbosity": "medium", "store": False, "tools": [], "background": False,
        "max_output_tokens": MAX_OUTPUT_TOKENS, "timeout_seconds": V2_TIMEOUT_SECONDS,
        "retry_count": 0, "planned_response_call_count": 1,
        "pricing_record_sha256": sha256_json(pricing_record), "pricing_effective_date": pricing.pricing_as_of,
        "cost_formula_version": "2",
        "task_requirement_inventory_sha256": sha256_json(requirement_inventory),
        "task_requirement_count": len(requirement_inventory),
        "hard_input_token_upper_bound": preflight["hard_input_token_upper_bound"],
        "hard_input_cost_usd": str(preflight["hard_input_cost_usd"]),
        "hard_output_cost_usd": str(preflight["hard_output_cost_usd"]),
        "safety_margin_usd": str(preflight["safety_margin_usd"]),
        "hard_worst_case_cost_usd": str(preflight["hard_worst_case_cost_usd"]),
        "proposed_hard_cost_cap_usd": str(PROPOSED_HARD_CAP),
        "approved_for_external_api": False,
        "credential_variable": "OPENAI_ORCHESTRATION_API_KEY",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    return manifest, {
        "fixture": fixture, "state": state, "canonical_request": request,
        "task_requirement_inventory": requirement_inventory,
    }, preflight


class ApprovalManifestMismatch(RuntimeError):
    pass


class ApprovalManifestGuard:
    def __init__(self, manifest: dict[str, Any]) -> None:
        self.manifest_hash = manifest.get("approval_manifest_sha256")
        self.consumed = False

    def validate(self, supplied_hash: str) -> None:
        if not self.manifest_hash or supplied_hash != self.manifest_hash:
            raise ApprovalManifestMismatch("APPROVAL_MANIFEST_MISMATCH")
        if self.consumed:
            raise ApprovalManifestMismatch("approval manifest already consumed")

    def consume(self, supplied_hash: str) -> None:
        self.validate(supplied_hash)
        self.consumed = True
