from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from typing import Any


PILOT_POLICY_VERSION = "2c.auto-pilot.1"
MAX_AUTO_CYCLES = 2
FORBIDDEN_CHANGE_CLASSES = {
    "DESTRUCTIVE", "DATABASE", "INFRASTRUCTURE", "AUTHORITY",
    "THRESHOLD", "SCOPE_EXPANSION",
}


class AutoSafeContinueError(ValueError):
    pass


@dataclass(frozen=True)
class AutoAdvanceEvidence:
    gate: str
    resolution_kind: str
    task_transition: str
    next_step_basis: str
    source_refs: tuple[str, ...]
    deterministic_validation: str
    task_alignment: str
    evidence_sufficiency: str
    user_required: bool
    blocker: str | None
    workspace_fingerprint_valid: bool
    approval_input_required: bool
    routing_conflict: bool = False
    task_alignment_conflict: bool = False
    evidence_threshold_conflict: bool = False
    transport_failure: bool = False
    change_classes: tuple[str, ...] = ()


def cumulative_cost_preflight(
    per_call_worst_case_usd: str | Decimal,
    per_call_approved_cap_usd: str | Decimal | None = None,
) -> dict[str, Any]:
    per_call = Decimal(per_call_worst_case_usd)
    if per_call <= 0:
        raise AutoSafeContinueError("INVALID_PER_CALL_WORST_CASE")
    cumulative = per_call * MAX_AUTO_CYCLES
    recommended = cumulative.quantize(Decimal("0.01"), rounding=ROUND_CEILING)
    if per_call_approved_cap_usd is not None:
        per_call_cap = Decimal(per_call_approved_cap_usd)
        if per_call_cap < per_call:
            raise AutoSafeContinueError("PER_CALL_CAP_BELOW_WORST_CASE")
        recommended = max(recommended, per_call_cap * MAX_AUTO_CYCLES)
    return {
        "pricing_basis": "LATEST_SEALED_API_MAINLINE_RETURN_PREFLIGHT",
        "per_call_hard_worst_case_usd": str(per_call),
        "per_call_sealed_cap_usd": (
            None if per_call_approved_cap_usd is None else str(Decimal(per_call_approved_cap_usd))
        ),
        "max_mainline_calls": MAX_AUTO_CYCLES,
        "cumulative_hard_worst_case_usd": str(cumulative),
        "recommended_pilot_cap_usd": str(recommended),
        "approved_pilot_cap_usd": None,
        "status": "CUMULATIVE_COST_CAP_APPROVAL_REQUIRED",
    }


def evaluate_auto_advance(
    evidence: AutoAdvanceEvidence,
    *,
    cycles_completed: int,
    cumulative_cost_usd: str | Decimal,
    next_call_worst_case_usd: str | Decimal,
    approved_cumulative_cap_usd: str | Decimal | None,
) -> dict[str, Any]:
    if not 0 <= cycles_completed <= MAX_AUTO_CYCLES:
        raise AutoSafeContinueError("INVALID_AUTO_CYCLE_COUNT")
    if cycles_completed >= MAX_AUTO_CYCLES:
        return _stop("AUTO_CYCLE_LIMIT_REACHED", "WAITING_FOR_USER")
    if evidence.gate == "STOP":
        return _stop("STOP", "STOPPED")
    if evidence.gate == "BLOCKED":
        return _stop("BLOCKED", "BLOCKED")
    if evidence.gate == "USER_REQUIRED" or evidence.user_required:
        return _stop("USER_REQUIRED", "WAITING_FOR_USER")
    if evidence.approval_input_required:
        return _stop("CODEX_APPROVAL_OR_INPUT_REQUIRED", "WAITING_FOR_USER")
    if evidence.routing_conflict:
        return _stop("ROUTING_CONFLICT", "WAITING_FOR_USER")
    if evidence.task_alignment_conflict:
        return _stop("TASK_ALIGNMENT_CONFLICT", "WAITING_FOR_USER")
    if evidence.evidence_threshold_conflict:
        return _stop("EVIDENCE_THRESHOLD_CONFLICT", "WAITING_FOR_USER")
    if not evidence.workspace_fingerprint_valid:
        return _stop("WORKSPACE_CHANGED_EXTERNALLY", "WAITING_FOR_USER")
    if evidence.transport_failure:
        return _stop("TRANSPORT_FAILURE", "WAITING_FOR_USER")
    forbidden = sorted(FORBIDDEN_CHANGE_CLASSES.intersection(evidence.change_classes))
    if forbidden:
        return {
            **_stop("FORBIDDEN_AUTO_CHANGE", "WAITING_FOR_USER"),
            "forbidden_change_classes": forbidden,
        }
    if evidence.blocker:
        return _stop("BLOCKER_PRESENT", "WAITING_FOR_USER")
    if (
        evidence.gate != "SAFE_CONTINUE"
        or evidence.resolution_kind != "BOUNDED_TASK"
        or evidence.task_transition not in {
            "CONTINUE_CURRENT_TASK", "ADVANCE_AUTHORIZED_PLAN",
        }
        or not evidence.source_refs
        or (
            evidence.task_transition == "CONTINUE_CURRENT_TASK"
            and evidence.next_step_basis != "UNRESOLVED_REQUIREMENT"
        )
        or (
            evidence.task_transition == "ADVANCE_AUTHORIZED_PLAN"
            and evidence.next_step_basis not in {"FROZEN_NEXT_STEP", "APPROVED_PLAN_ITEM"}
        )
        or evidence.deterministic_validation != "PASS"
        or evidence.task_alignment != "PASS"
        or evidence.evidence_sufficiency != "PASS"
    ):
        return _stop("AUTO_ADVANCE_CONTRACT_NOT_SATISFIED", "WAITING_FOR_USER")
    if approved_cumulative_cap_usd is None:
        return _stop("CUMULATIVE_COST_CAP_APPROVAL_REQUIRED", "WAITING_FOR_USER")
    cumulative = Decimal(cumulative_cost_usd)
    next_call = Decimal(next_call_worst_case_usd)
    if cumulative < 0 or next_call <= 0:
        raise AutoSafeContinueError("INVALID_CUMULATIVE_COST_INPUT")
    projected = cumulative + next_call
    cap = Decimal(approved_cumulative_cap_usd)
    if projected > cap:
        return {
            **_stop("CUMULATIVE_COST_CAP_EXCEEDED", "WAITING_FOR_USER"),
            "projected_cost_usd": str(projected),
            "approved_cap_usd": str(cap),
        }
    return {
        "decision": "ALLOW_AUTO_ADVANCE",
        "project_status": "RUNNING",
        "stop_reason": None,
        "next_cycle": cycles_completed + 1,
        "projected_cost_usd": str(projected),
        "codex_retry_count": 0,
        "mainline_retry_count": 0,
        "model_fallback_count": 0,
        "automatic_approval": False,
    }


def pilot_policy(preflight: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": PILOT_POLICY_VERSION,
        "mode": "AUTO_SAFE_CONTINUE",
        "selectable": False,
        "enabled": False,
        "live_auto_run": "LOCKED_USER_APPROVAL_REQUIRED",
        "max_auto_cycles": MAX_AUTO_CYCLES,
        "codex_retry_count": 0,
        "mainline_retry_count": 0,
        "model_fallback_count": 0,
        "automatic_approval": False,
        "allowed_gate": "SAFE_CONTINUE",
        "required_resolution_kind": "BOUNDED_TASK",
        "required_validations": [
            "DETERMINISTIC_VALIDATION", "TASK_ALIGNMENT", "EVIDENCE_SUFFICIENCY",
        ],
        "forbidden_change_classes": sorted(FORBIDDEN_CHANGE_CLASSES),
        "stop_conditions": [
            "USER_REQUIRED", "CODEX_APPROVAL_OR_INPUT_REQUIRED", "BLOCKED", "STOP",
            "ROUTING_CONFLICT", "TASK_ALIGNMENT_CONFLICT", "EVIDENCE_THRESHOLD_CONFLICT",
            "WORKSPACE_CHANGED_EXTERNALLY", "TRANSPORT_FAILURE",
            "CUMULATIVE_COST_CAP_EXCEEDED", "AUTO_CYCLE_LIMIT_REACHED",
        ],
        "cost_preflight": preflight,
    }


def _stop(reason: str, status: str) -> dict[str, Any]:
    return {
        "decision": "STOP_AUTO_ADVANCE",
        "project_status": status,
        "stop_reason": reason,
        "next_cycle": None,
        "codex_retry_count": 0,
        "mainline_retry_count": 0,
        "model_fallback_count": 0,
        "automatic_approval": False,
    }
