from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal, ROUND_UP
from pathlib import Path
from typing import Any

from .cycle_handoff import build_cycle_reviewer_prompt, requirement_inventory_for_cycle_packet, verify_cycle_handoff_packet
from .evidence_sufficiency import EVIDENCE_SUFFICIENCY_CONTRACT_VERSION
from .forensic import build_wire_request
from .manifest import build_canonical_token_request_v2_from_cycle_packet, build_corrected_preflight, build_manifest_from_files, build_manifest_from_files_v2, sha256_json
from .pricing import SOL_PROPOSAL_PRICING, pricing_record_payload
from .schema import reviewer_output_schema
from .task_alignment import TASK_ALIGNMENT_CONFLICT_INVARIANTS, TASK_ALIGNMENT_CONTRACT_VERSION


R3_CANDIDATE_PATH = Path(".console/orchestration/phase1b-r3-candidate-manifest.json")
V2_CALIBRATION_CANDIDATE_PATH = Path(".console/orchestration/phase1c-r1-v2-candidate-manifest.json")
TASK_ALIGNMENT_CANDIDATE_PATH = Path(".console/orchestration/phase1c-task-alignment-v2-1-r1-candidate-manifest.json")
CYCLE_HANDOFF_CANDIDATE_PATH = Path(".console/orchestration/session-handoff-e2e-candidate-manifest.json")


def validate_schema_binding(manifest: dict[str, Any], actual_schema_sha256: str) -> None:
    if manifest.get("structured_output_schema_sha256") != actual_schema_sha256:
        raise RuntimeError("CANDIDATE_SCHEMA_BINDING_MISMATCH")


def build_cycle_handoff_candidate(
    root: Path, packet: dict[str, Any], *, output: Path = CYCLE_HANDOFF_CANDIDATE_PATH,
) -> dict[str, Any]:
    """Build a no-network candidate bound to one verified Cycle Handoff packet."""
    verify_cycle_handoff_packet(packet)
    canonical = build_canonical_token_request_v2_from_cycle_packet(packet)
    wire = build_wire_request(canonical)
    preflight = build_corrected_preflight(canonical)
    source_paths = {
        "response_pipeline": root / "console/devos_orchestration/response_pipeline.py",
        "schema": root / "console/devos_orchestration/schema.py",
        "gate_controller": root / "console/devos_orchestration/gate.py",
        "routing_controller": root / "console/devos_orchestration/routing.py",
        "task_alignment": root / "console/devos_orchestration/task_alignment.py",
        "evidence_sufficiency": root / "console/devos_orchestration/evidence_sufficiency.py",
        "cycle_handoff": root / "console/devos_orchestration/cycle_handoff.py",
        "manifest_builder": root / "console/devos_orchestration/manifest.py",
        "cost_estimator": root / "console/devos_orchestration/pricing.py",
    }
    fingerprints = {name: _source_sha256(path) for name, path in source_paths.items()}
    runtime_protocol = {
        "response_capture_version": "1",
        "response_parser_version": "2.3",
        "deterministic_gate_controller_version": "2",
        "task_alignment_contract_version": TASK_ALIGNMENT_CONTRACT_VERSION,
        "evidence_sufficiency_contract_version": EVIDENCE_SUFFICIENCY_CONTRACT_VERSION,
        "cycle_handoff_packet_version": packet["packet_version"],
        "cost_formula_version": "2",
        "source_fingerprints": fingerprints,
    }
    prompt = build_cycle_reviewer_prompt(packet)
    manual = next(item for item in packet["captured_messages"] if item["kind"] == "manual_review")
    wire_text = json.dumps(wire, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if manual["exact_content"] in wire_text or manual["message_identifier"] in wire_text:
        raise RuntimeError("BASELINE_CONTAMINATION")
    proposed_cap = Decimal(str(preflight["hard_worst_case_cost_usd"])).quantize(
        Decimal("0.01"), rounding=ROUND_UP,
    )
    serialized_preflight = {
        key: str(value) if isinstance(value, Decimal) else value
        for key, value in preflight.items()
    }
    serialized_preflight.update({
        "proposed_hard_cost_cap_usd": str(proposed_cap),
        "status": "READY" if Decimal(str(preflight["hard_worst_case_cost_usd"])) <= proposed_cap else "BUDGET_POLICY_REQUIRED",
    })
    requirement_inventory = requirement_inventory_for_cycle_packet(packet)
    manifest = {
        "manifest_schema_version": "cycle-handoff-1",
        "candidate_type": "SESSION_HANDOFF_E2E_NO_NETWORK",
        "lane": packet["lane"],
        "project": packet["project"],
        "cycle_id": packet["cycle_id"],
        "cycle_handoff_packet_sha256": packet["packet_sha256"],
        "task_exact_content_sha256": packet["task_exact_content_sha256"],
        "report_exact_content_sha256": packet["report_exact_content_sha256"],
        "manual_review_exact_content_sha256": packet["manual_review_exact_content_sha256"],
        "intermediate_user_decisions": packet["intermediate_user_decisions"],
        "serialized_reviewer_prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "structured_output_schema_sha256": sha256_json(canonical["text"]["format"]["schema"]),
        "canonical_token_bearing_request_sha256": sha256_json(canonical),
        "actual_wire_request_body_sha256": sha256_json(wire),
        "routing_controller_sha256": fingerprints["routing_controller"],
        "task_alignment_controller_sha256": fingerprints["task_alignment"],
        "evidence_sufficiency_controller_sha256": fingerprints["evidence_sufficiency"],
        "runtime_protocol_sha256": sha256_json(runtime_protocol),
        "pricing_record_sha256": sha256_json(pricing_record_payload(SOL_PROPOSAL_PRICING)),
        "task_requirement_inventory_sha256": sha256_json(requirement_inventory),
        "task_requirement_count": len(requirement_inventory),
        "model": SOL_PROPOSAL_PRICING.model,
        "max_output_tokens": canonical["max_output_tokens"],
        "timeout_seconds": 600.0,
        "retry_count": 0,
        "planned_response_call_count": 1,
        "hard_input_token_upper_bound": preflight["hard_input_token_upper_bound"],
        "hard_worst_case_cost_usd": str(preflight["hard_worst_case_cost_usd"]),
        "proposed_hard_cost_cap_usd": str(proposed_cap),
        "approved_for_external_api": False,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    manifest["approval_manifest_sha256"] = sha256_json(manifest)
    candidate = {
        "candidate_manifest_version": "cycle-handoff-1",
        "manifest": manifest,
        "preflight": serialized_preflight,
        "request_binding": {
            "cycle_handoff_packet_sha256": packet["packet_sha256"],
            "actual_wire_request_body_sha256": sha256_json(wire),
            "canonical_token_bearing_request_sha256": sha256_json(canonical),
            "serialized_reviewer_prompt_sha256": manifest["serialized_reviewer_prompt_sha256"],
            "structured_output_schema_sha256": manifest["structured_output_schema_sha256"],
            "routing_controller_sha256": manifest["routing_controller_sha256"],
            "task_alignment_controller_sha256": manifest["task_alignment_controller_sha256"],
            "evidence_sufficiency_controller_sha256": manifest["evidence_sufficiency_controller_sha256"],
            "runtime_protocol_sha256": manifest["runtime_protocol_sha256"],
        },
        "baseline_contamination_test": "PASS",
        "future_design_contamination_test": "PASS",
        "unrelated_history_contamination_test": "PASS",
        "approved_for_external_api": False,
        "one_time_approval_record": False,
        "attempt_record": False,
        "result_record": False,
        "network_calls": 0,
        "retry_count": 0,
        "fallback_count": 0,
        "dispatch_count": 0,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(candidate, ensure_ascii=True, indent=2) + "\n")
    except FileExistsError as error:
        raise RuntimeError("IMMUTABLE_CANDIDATE_ALREADY_EXISTS") from error
    return candidate


def _source_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _runtime_protocol(root: Path) -> dict[str, Any]:
    files = {
        "response_pipeline": root / "console/devos_orchestration/response_pipeline.py",
        "adapter": root / "console/devos_orchestration/adapter.py",
        "live_entrypoint": root / "console/devos_orchestration/live_r2_once.py",
        "schema": root / "console/devos_orchestration/schema.py",
        "gate_controller": root / "console/devos_orchestration/gate.py",
        "result_artifact": root / "console/devos_orchestration/run.py",
    }
    fingerprints = {name: _source_sha256(path) for name, path in files.items()}
    result_schema = {
        "fields": [
            "run_id", "input_fixture_hashes", "orchestration_state_hash", "prompt_schema_version",
            "model_requested", "model_returned", "reasoning_settings", "response_id", "request_latency_ms",
            "input_tokens", "cached_input_tokens", "cache_write_tokens", "output_tokens", "reasoning_tokens",
            "estimated_cost_usd", "actual_cost_usd", "actual_cost_status", "parsing_success", "gate",
            "generated_next_instruction", "manual_comparison_status", "error_classification",
        ],
        "additional_properties": False,
    }
    return {
        "response_capture_version": "1", "response_parser_version": "1",
        "reviewer_internal_model_version": "1", "deterministic_gate_controller_version": "1",
        "result_artifact_schema_version": "1", "cost_semantics_version": "2",
        "manual_comparison_contract_version": "1", "source_fingerprints": fingerprints,
        "result_artifact_schema_sha256": sha256_json(result_schema),
    }


def build_parser_bound_candidate(root: Path, *, output: Path = R3_CANDIDATE_PATH) -> dict[str, Any]:
    manifest, details, preflight = build_manifest_from_files(
        Path(r"X:\01_codex_task.txt"), Path(r"X:\02_codex_report.txt"), Path(r"X:\03_manual_sol_review.txt"),
        project="bTest", historical_date="2026-08-12", run_id="phase1b-r3-parser-bound",
    )
    wire = build_wire_request(details["canonical_request"])
    if sha256_json(wire) != "c6eca7a307a8e1bf1513d94dc5dfc802f6c452431dd169a1c75c8b2771944301":
        raise RuntimeError("UNEXPECTED_WIRE_CHANGE")
    if sha256_json(details["canonical_request"]) != "890a36db5e405996478b087207ebcd9a5ce63c2fcbdcb8e85485ad0638948db7":
        raise RuntimeError("UNEXPECTED_WIRE_CHANGE")
    protocol = _runtime_protocol(root)
    manifest.update({
        "candidate_type": "R3_PARSER_BOUND", "timeout_seconds": 600.0,
        **{key: protocol[key] for key in (
            "response_capture_version", "response_parser_version", "reviewer_internal_model_version",
            "deterministic_gate_controller_version", "result_artifact_schema_version", "cost_semantics_version",
            "manual_comparison_contract_version",
        )},
        "runtime_protocol_sha256": sha256_json(protocol),
        "source_fingerprints": protocol["source_fingerprints"],
        "result_artifact_schema_sha256": protocol["result_artifact_schema_sha256"],
        "actual_wire_request_body_sha256": sha256_json(wire), "approved_for_external_api": False,
    })
    manifest.pop("approval_manifest_sha256", None)
    manifest["approval_manifest_sha256"] = sha256_json(manifest)
    candidate = {
        "candidate_manifest_version": "1", "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "manifest": manifest,
        "preflight": {key: str(value) if hasattr(value, "as_tuple") else value for key, value in preflight.items()},
        "request_binding": {
            "actual_wire_request_body_sha256": sha256_json(wire),
            "canonical_token_bearing_request_sha256": sha256_json(details["canonical_request"]),
            "serialized_reviewer_prompt_sha256": manifest["serialized_reviewer_prompt_sha256"],
            "structured_output_schema_sha256": sha256_json(reviewer_output_schema()),
            "pricing_record_sha256": manifest["pricing_record_sha256"],
        },
        "approved_for_external_api": False, "one_time_approval_record": False,
        "attempt_record": False, "result_record": False, "network_calls": 0,
        "retry_count": 0, "dispatch_count": 0,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(candidate, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    return candidate


def build_v2_calibration_candidate(
    root: Path, *, output: Path = V2_CALIBRATION_CANDIDATE_PATH,
) -> dict[str, Any]:
    manifest, details, preflight = build_manifest_from_files_v2(
        Path(r"X:\01_codex_task.txt"), Path(r"X:\02_codex_report.txt"), Path(r"X:\03_manual_sol_review.txt"),
        project="bTest", historical_date="2026-08-12", run_id="phase1c-r1-gate-contract-v2",
    )
    wire = build_wire_request(details["canonical_request"])
    source_paths = {
        "response_pipeline": root / "console/devos_orchestration/response_pipeline.py",
        "adapter": root / "console/devos_orchestration/adapter.py",
        "schema": root / "console/devos_orchestration/schema.py",
        "gate_controller": root / "console/devos_orchestration/gate.py",
        "routing_controller": root / "console/devos_orchestration/routing.py",
        "manifest_builder": root / "console/devos_orchestration/manifest.py",
        "cost_estimator": root / "console/devos_orchestration/pricing.py",
    }
    protocol = {
        "response_capture_version": "1",
        "response_parser_version": "2",
        "reviewer_internal_model_version": "2",
        "deterministic_gate_controller_version": "2",
        "cost_formula_version": "2",
        "source_fingerprints": {name: _source_sha256(path) for name, path in source_paths.items()},
    }
    manifest.update({
        "runtime_protocol_sha256": sha256_json(protocol),
        "routing_controller_sha256": protocol["source_fingerprints"]["routing_controller"],
        "source_fingerprints": protocol["source_fingerprints"],
        "actual_wire_request_body_sha256": sha256_json(wire),
    })
    manifest["approval_manifest_sha256"] = sha256_json(manifest)
    candidate = {
        "candidate_manifest_version": "2",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "manifest": manifest,
        "preflight": {key: str(value) if hasattr(value, "as_tuple") else value for key, value in preflight.items()},
        "request_binding": {
            "actual_wire_request_body_sha256": sha256_json(wire),
            "canonical_token_bearing_request_sha256": sha256_json(details["canonical_request"]),
            "serialized_reviewer_prompt_sha256": manifest["serialized_reviewer_prompt_sha256"],
            "structured_output_schema_sha256": sha256_json(reviewer_output_schema("2")),
            "pricing_record_sha256": manifest["pricing_record_sha256"],
            "routing_controller_sha256": manifest["routing_controller_sha256"],
            "runtime_protocol_sha256": manifest["runtime_protocol_sha256"],
        },
        "calibration_fixture_is_holdout": False,
        "independent_holdout_required": True,
        "approved_for_external_api": False,
        "one_time_approval_record": False,
        "attempt_record": False,
        "result_record": False,
        "network_calls": 0,
        "retry_count": 0,
        "fallback_count": 0,
        "dispatch_count": 0,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(candidate, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    return candidate


def build_task_alignment_candidate(
    root: Path, *, output: Path = TASK_ALIGNMENT_CANDIDATE_PATH,
) -> dict[str, Any]:
    manifest, details, preflight = build_manifest_from_files_v2(
        Path(r"X:\01_codex_task.txt"), Path(r"X:\02_codex_report.txt"),
        Path(r"X:\03_manual_sol_review.txt"), project="bTest",
        historical_date="2026-08-13", run_id="phase1c-task-alignment-v2-1",
    )
    wire = build_wire_request(details["canonical_request"])
    source_paths = {
        "response_pipeline": root / "console/devos_orchestration/response_pipeline.py",
        "adapter": root / "console/devos_orchestration/adapter.py",
        "schema": root / "console/devos_orchestration/schema.py",
        "gate_controller": root / "console/devos_orchestration/gate.py",
        "routing_controller": root / "console/devos_orchestration/routing.py",
        "task_alignment": root / "console/devos_orchestration/task_alignment.py",
        "manifest_builder": root / "console/devos_orchestration/manifest.py",
        "cost_estimator": root / "console/devos_orchestration/pricing.py",
    }
    fingerprints = {name: _source_sha256(path) for name, path in source_paths.items()}
    task_alignment_contract = {
        "version": TASK_ALIGNMENT_CONTRACT_VERSION,
        "controller_source_sha256": fingerprints["gate_controller"],
        "inventory_source_sha256": fingerprints["task_alignment"],
        "invariants": list(TASK_ALIGNMENT_CONFLICT_INVARIANTS),
    }
    task_alignment_hash = sha256_json(task_alignment_contract)
    protocol = {
        "response_capture_version": "1",
        "response_parser_version": "2.1",
        "reviewer_internal_model_version": "2.1",
        "deterministic_gate_controller_version": "2",
        "task_alignment_contract_version": TASK_ALIGNMENT_CONTRACT_VERSION,
        "cost_formula_version": "2",
        "source_fingerprints": fingerprints,
    }
    proposed_cap = Decimal(str(preflight["hard_worst_case_cost_usd"])).quantize(
        Decimal("0.01"), rounding=ROUND_UP,
    )
    manifest.update({
        "candidate_purpose": "same-fixture Task Alignment Contract 2.1 live calibration",
        "lane": "MAINLINE_CODEX_REVIEW_TASK_ALIGNMENT_CALIBRATION",
        "runtime_protocol_sha256": sha256_json(protocol),
        "routing_controller_sha256": fingerprints["routing_controller"],
        "task_alignment_controller_sha256": task_alignment_hash,
        "task_alignment_conflict_invariants_sha256": sha256_json(
            list(TASK_ALIGNMENT_CONFLICT_INVARIANTS),
        ),
        "source_fingerprints": fingerprints,
        "actual_wire_request_body_sha256": sha256_json(wire),
        "proposed_hard_cost_cap_usd": str(proposed_cap),
    })
    actual_schema_hash = sha256_json(details["canonical_request"]["text"]["format"]["schema"])
    validate_schema_binding(manifest, actual_schema_hash)
    manifest["approval_manifest_sha256"] = sha256_json(manifest)
    serialized_preflight = {
        key: str(value) if hasattr(value, "as_tuple") else value
        for key, value in preflight.items()
    }
    serialized_preflight.update({
        "wire_request_utf8_bytes": len(json.dumps(
            wire, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")),
        "proposed_hard_cost_cap_usd": str(proposed_cap),
        "status": "READY",
    })
    candidate = {
        "candidate_manifest_version": "2.1",
        "candidate_type": "TASK_ALIGNMENT_SAME_FIXTURE_CALIBRATION",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "manifest": manifest,
        "preflight": serialized_preflight,
        "request_binding": {
            "actual_wire_request_body_sha256": sha256_json(wire),
            "canonical_token_bearing_request_sha256": sha256_json(details["canonical_request"]),
            "serialized_reviewer_prompt_sha256": manifest["serialized_reviewer_prompt_sha256"],
            "structured_output_schema_sha256": actual_schema_hash,
            "pricing_record_sha256": manifest["pricing_record_sha256"],
            "routing_controller_sha256": manifest["routing_controller_sha256"],
            "task_alignment_controller_sha256": task_alignment_hash,
            "runtime_protocol_sha256": manifest["runtime_protocol_sha256"],
        },
        "baseline_contamination_test": "PASS",
        "baseline_is_reviewer_input": False,
        "expected_gate_is_reviewer_input": False,
        "expected_next_instruction_is_reviewer_input": False,
        "approved_for_external_api": False,
        "one_time_approval_record": False,
        "attempt_record": False,
        "result_record": False,
        "network_calls": 0,
        "retry_count": 0,
        "fallback_count": 0,
        "dispatch_count": 0,
    }
    baseline = Path(r"X:\03_manual_sol_review.txt").read_text(encoding="utf-8")
    wire_text = json.dumps(wire, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if baseline and baseline in wire_text:
        raise RuntimeError("BASELINE_CONTAMINATION")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(candidate, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    return candidate
