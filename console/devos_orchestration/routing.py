from __future__ import annotations

from dataclasses import dataclass


class RoutingConflict(ValueError):
    """A review verdict and orchestration route contradict the local contract."""


@dataclass(frozen=True)
class RoutingDecision:
    review_verdict: str
    orchestration_gate: str
    resolution_kind: str
    safe_bounded_next_step_available: bool
    evidence_collection_possible: bool
    user_authority_required: bool
    blocker_class: str
    blocker_detail: str | None = None


def validate_routing(decision: RoutingDecision) -> None:
    if decision.review_verdict not in {"PASS", "FAIL", "INCOMPLETE", "UNKNOWN"}:
        raise RoutingConflict("invalid review verdict")
    if decision.orchestration_gate not in {"SAFE_CONTINUE", "USER_REQUIRED", "BLOCKED", "STOP"}:
        raise RoutingConflict("invalid orchestration Gate")
    if decision.resolution_kind not in {"BOUNDED_TASK", "USER_DECISION", "MISSING_DEPENDENCY", "SAFETY_STOP", "NONE"}:
        raise RoutingConflict("invalid resolution kind")
    if decision.blocker_class not in {"NONE", "ENVIRONMENT", "PERMISSION", "MISSING_ARTIFACT", "EXTERNAL_DEPENDENCY", "CREDENTIAL", "OTHER"}:
        raise RoutingConflict("invalid blocker class")
    gate = decision.orchestration_gate
    if gate == "SAFE_CONTINUE" and not (
        decision.resolution_kind == "BOUNDED_TASK"
        and decision.safe_bounded_next_step_available
        and not decision.user_authority_required
    ):
        raise RoutingConflict("SAFE_CONTINUE requires a bounded safe task without user authority")
    if gate == "USER_REQUIRED" and not (
        decision.resolution_kind == "USER_DECISION" and decision.user_authority_required
    ):
        raise RoutingConflict("USER_REQUIRED requires a user decision")
    if gate == "BLOCKED" and not (
        decision.resolution_kind == "MISSING_DEPENDENCY"
        and not decision.safe_bounded_next_step_available
        and not decision.evidence_collection_possible
        and not decision.user_authority_required
        and decision.blocker_class != "NONE"
        and bool(decision.blocker_detail and decision.blocker_detail.strip())
    ):
        raise RoutingConflict("BLOCKED requires an exact unavailable dependency and no bounded route")
    if gate == "STOP" and decision.resolution_kind != "SAFETY_STOP":
        raise RoutingConflict("STOP requires SAFETY_STOP")


def route_from_facts(
    *, review_verdict: str, resolution_kind: str,
    safe_bounded_next_step_available: bool, evidence_collection_possible: bool,
    user_authority_required: bool, blocker_class: str = "NONE",
    blocker_detail: str | None = None,
) -> RoutingDecision:
    if resolution_kind == "SAFETY_STOP":
        gate = "STOP"
    elif user_authority_required or resolution_kind == "USER_DECISION":
        gate = "USER_REQUIRED"
    elif resolution_kind == "BOUNDED_TASK" and safe_bounded_next_step_available:
        gate = "SAFE_CONTINUE"
    elif resolution_kind == "MISSING_DEPENDENCY":
        gate = "BLOCKED"
    else:
        raise RoutingConflict("facts do not resolve to an orchestration Gate")
    decision = RoutingDecision(
        review_verdict, gate, resolution_kind, safe_bounded_next_step_available,
        evidence_collection_possible, user_authority_required, blocker_class,
        blocker_detail,
    )
    validate_routing(decision)
    return decision
