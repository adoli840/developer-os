from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .gate import validate_review_output
from .routing import route_from_facts


SYNTHETIC_EVIDENCE = "SYNTHETIC_ROUTING_EVIDENCE"
REAL_WORLD_EVIDENCE = "REAL_WORLD_EVIDENCE"
USER_REQUIRED_TYPES = {
    "THRESHOLD_SELECTION",
    "AUTHORITY_CHANGE",
    "ARCHITECTURE_SELECTION",
    "SCOPE_EXPANSION",
    "DESTRUCTIVE_DB_MIGRATION",
}


class SyntheticSuiteError(RuntimeError):
    pass


def _instruction_packet(case: dict[str, Any]) -> dict[str, str]:
    return {
        "title": "Run bounded synthetic control",
        "purpose": case["description"],
        "frozen_decisions": "Synthetic evidence only; no network or dispatch.",
        "scope": "Execute only the bounded control.",
        "prohibited_actions": "No production change or dispatch.",
        "tasks": "Collect the bounded evidence.",
        "required_tests": "Validate the deterministic route.",
        "required_evidence": "Synthetic case result.",
        "result_report_format": "Report the selected Gate.",
        "stop_conditions": "Stop on contract conflict.",
    }


def _decision_packet(case: dict[str, Any]) -> dict[str, str]:
    return {
        "decision_id": f"synthetic-{case['case_id']}",
        "question": case["decision_question"],
        "why_user_authority_is_required": case["description"],
        "known_facts": "The repository does not contain an approved user choice.",
        "options": "At least two reasonable choices exist, including no change.",
        "tradeoffs": "Each option changes semantics, authority, architecture, scope, or data risk.",
        "reviewer_recommendation": "Ask the user; do not choose automatically.",
        "consequences_of_no_decision": "No irreversible or authority-changing work proceeds.",
    }


def _blocker_packet(case: dict[str, Any]) -> dict[str, str]:
    return {
        "blocker": case["blocker_detail"],
        "evidence": case["description"],
        "attempted_or_available_checks": "Synthetic availability check exhausted.",
        "exact_unblocking_requirement": "Restore the exact unavailable dependency.",
    }


def _review_output(case: dict[str, Any], gate: str) -> dict[str, Any]:
    review = {
        "schema_version": "2",
        "review_id": f"synthetic-review-{case['case_id']}",
        "review_verdict": case["review_verdict"],
        "orchestration_gate": gate,
        "routing_assessment": {
            key: case[key]
            for key in (
                "resolution_kind", "safe_bounded_next_step_available",
                "evidence_collection_possible", "user_authority_required",
                "blocker_class", "blocker_detail",
            )
        },
        "executive_summary": case["description"],
        "contract_assessment": {
            name: "PASS"
            for name in (
                "purpose", "scope", "frozen_decisions", "semantic_contract",
                "authority", "routing", "safety", "test_evidence",
                "provenance", "report_completeness",
            )
        },
        "findings": [],
        "evidence_refs": [f"synthetic_fixture:{case['case_id']}"],
        "next_instruction": None,
        "user_decision_packet": None,
        "blocker_packet": None,
        "branch_assessment": [],
    }
    if gate == "SAFE_CONTINUE":
        review["next_instruction"] = _instruction_packet(case)
    elif gate == "USER_REQUIRED":
        review["user_decision_packet"] = _decision_packet(case)
    elif gate == "BLOCKED":
        review["blocker_packet"] = _blocker_packet(case)
    elif gate == "STOP":
        review["findings"] = [{
            "finding_id": f"synthetic-stop-{case['case_id']}",
            "severity": "STOP",
            "category": "safety",
            "description": case["description"],
            "evidence_refs": [f"synthetic_fixture:{case['case_id']}"],
            "consequence": "The prohibited operation could violate the safety contract.",
            "required_action": "Stop without dispatch.",
            "user_decision_required": False,
        }]
    return review


def run_synthetic_suite(path: Path) -> dict[str, Any]:
    suite = json.loads(path.read_text(encoding="utf-8"))
    if set(suite) != {"suite_version", "suite_id", "evidence_classification", "historical_fixture", "cases"}:
        raise SyntheticSuiteError("INVALID_SYNTHETIC_SUITE_SHAPE")
    if suite["evidence_classification"] != SYNTHETIC_EVIDENCE or suite["historical_fixture"] is not False:
        raise SyntheticSuiteError("SYNTHETIC_EVIDENCE_MISCLASSIFIED")
    if not isinstance(suite["cases"], list) or not suite["cases"]:
        raise SyntheticSuiteError("SYNTHETIC_CASES_REQUIRED")

    results = []
    seen = set()
    for case in suite["cases"]:
        if case["case_id"] in seen:
            raise SyntheticSuiteError("DUPLICATE_SYNTHETIC_CASE")
        seen.add(case["case_id"])
        decision = route_from_facts(
            review_verdict=case["review_verdict"],
            resolution_kind=case["resolution_kind"],
            safe_bounded_next_step_available=case["safe_bounded_next_step_available"],
            evidence_collection_possible=case["evidence_collection_possible"],
            user_authority_required=case["user_authority_required"],
            blocker_class=case["blocker_class"],
            blocker_detail=case["blocker_detail"],
        )
        review = _review_output(case, decision.orchestration_gate)
        validate_review_output(review)
        expected = case["expected_gate"]
        passed = decision.orchestration_gate == expected
        if case["case_type"] in USER_REQUIRED_TYPES:
            passed = passed and all((
                decision.user_authority_required,
                decision.resolution_kind == "USER_DECISION",
                review["user_decision_packet"] is not None,
                review["next_instruction"] is None,
                decision.orchestration_gate != "BLOCKED",
            ))
        results.append({
            "case_id": case["case_id"],
            "case_type": case["case_type"],
            "expected_gate": expected,
            "actual_gate": decision.orchestration_gate,
            "user_authority_required": decision.user_authority_required,
            "resolution_kind": decision.resolution_kind,
            "user_decision_packet_present": review["user_decision_packet"] is not None,
            "next_instruction_present": review["next_instruction"] is not None,
            "dispatch_count": 0,
            "status": "PASS" if passed else "FAIL",
        })
    if any(item["status"] != "PASS" for item in results):
        raise SyntheticSuiteError("SYNTHETIC_ROUTING_CASE_FAILED")
    gates = {item["actual_gate"] for item in results}
    if not {"SAFE_CONTINUE", "USER_REQUIRED", "BLOCKED", "STOP"}.issubset(gates):
        raise SyntheticSuiteError("NEGATIVE_CONTROL_COVERAGE_MISSING")
    return {
        "status": "SYNTHETIC_USER_REQUIRED_SUITE_COMPLETE",
        "suite_id": suite["suite_id"],
        "evidence_classification": SYNTHETIC_EVIDENCE,
        "historical_validation_claimed": False,
        "case_count": len(results),
        "user_required_case_count": sum(item["actual_gate"] == "USER_REQUIRED" for item in results),
        "negative_control_count": sum(item["case_type"].startswith("NEGATIVE_") for item in results),
        "network_calls": 0,
        "dispatch_count": 0,
        "results": results,
    }
