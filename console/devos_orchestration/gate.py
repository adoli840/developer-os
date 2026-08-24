from __future__ import annotations

from typing import Any

from .evidence_sufficiency import MANDATORY_EVIDENCE_BASES
from .routing import RoutingConflict, RoutingDecision, validate_routing
from .schema import SchemaError, reviewer_output_schema, validate_strict


def validate_review_output(
    review: dict[str, Any], *, expected_requirement_ids: set[str] | None = None,
    authorized_next_steps: list[dict[str, str]] | None = None,
) -> None:
    version = str(review.get("schema_version", ""))
    validate_strict(review, reviewer_output_schema(version))
    if version in {"2", "2.1", "2.2", "2.3", "2.4"}:
        _validate_v2(review)
        if version in {"2.1", "2.2", "2.3", "2.4"}:
            _validate_task_alignment(review, expected_requirement_ids)
        if version in {"2.2", "2.3", "2.4"}:
            _validate_next_instruction_priority(review)
        if version == "2.4":
            _validate_next_step_authority(
                review, authorized_next_steps or [],
            )
        if version in {"2.3", "2.4"}:
            _validate_evidence_sufficiency(review)
        return
    gate = review["gate_decision"]
    if gate == "SAFE_CONTINUE" and review["next_instruction"] is None:
        raise SchemaError("SAFE_CONTINUE requires next_instruction")
    if gate != "SAFE_CONTINUE" and review["next_instruction"] is not None:
        raise SchemaError("only SAFE_CONTINUE may contain next_instruction")
    if gate == "USER_REQUIRED" and review["user_decision_packet"] is None:
        raise SchemaError("USER_REQUIRED requires user_decision_packet")
    if gate != "USER_REQUIRED" and review["user_decision_packet"] is not None:
        raise SchemaError("only USER_REQUIRED may contain user_decision_packet")
    if gate == "BLOCKED" and review["blocker_packet"] is None:
        raise SchemaError("BLOCKED requires blocker_packet")
    if gate != "BLOCKED" and review["blocker_packet"] is not None:
        raise SchemaError("only BLOCKED may contain blocker_packet")
    if gate == "STOP" and not any(item["severity"] == "STOP" for item in review["findings"]):
        raise SchemaError("STOP requires a STOP finding")


def _validate_v2(review: dict[str, Any]) -> None:
    gate = review["orchestration_gate"]
    routing = review["routing_assessment"]
    try:
        validate_routing(RoutingDecision(
            review_verdict=review["review_verdict"],
            orchestration_gate=gate,
            resolution_kind=routing["resolution_kind"],
            safe_bounded_next_step_available=routing["safe_bounded_next_step_available"],
            evidence_collection_possible=routing["evidence_collection_possible"],
            user_authority_required=routing["user_authority_required"],
            blocker_class=routing["blocker_class"],
            blocker_detail=routing["blocker_detail"],
        ))
    except RoutingConflict as error:
        raise SchemaError(f"ROUTING_CONFLICT: {error}") from error

    if gate == "SAFE_CONTINUE":
        if review["next_instruction"] is None:
            raise SchemaError("ROUTING_CONFLICT: SAFE_CONTINUE requires next_instruction")
    elif review["next_instruction"] is not None:
        raise SchemaError("ROUTING_CONFLICT: only SAFE_CONTINUE may contain next_instruction")

    if gate == "USER_REQUIRED":
        if review["user_decision_packet"] is None:
            raise SchemaError("ROUTING_CONFLICT: USER_REQUIRED requires user_decision_packet")
    elif review["user_decision_packet"] is not None:
        raise SchemaError("ROUTING_CONFLICT: only USER_REQUIRED may contain user_decision_packet")

    if gate == "BLOCKED":
        if review["blocker_packet"] is None:
            raise SchemaError("ROUTING_CONFLICT: BLOCKED requires blocker_packet")
    elif review["blocker_packet"] is not None:
        raise SchemaError("ROUTING_CONFLICT: only BLOCKED may contain blocker_packet")

    if gate == "STOP" and not any(item["severity"] == "STOP" for item in review["findings"]):
        raise SchemaError("ROUTING_CONFLICT: STOP requires a STOP finding")


def _validate_task_alignment(
    review: dict[str, Any], expected_requirement_ids: set[str] | None,
) -> None:
    if expected_requirement_ids is None:
        raise SchemaError("TASK_ALIGNMENT_CONFLICT: expected requirement inventory is required")
    assessments = review["task_requirement_assessment"]
    ids = [item["requirement_id"] for item in assessments]
    if len(ids) != len(set(ids)):
        raise SchemaError("TASK_ALIGNMENT_CONFLICT: duplicate requirement_id")
    if set(ids) != expected_requirement_ids:
        raise SchemaError("TASK_ALIGNMENT_CONFLICT: explicit task requirement omitted or invented")

    unresolved: set[str] = set()
    for item in assessments:
        action = item["unresolved_action"]
        if item["status"] in {"UNRESOLVED", "BLOCKED"}:
            if not isinstance(action, str) or not action.strip():
                raise SchemaError("TASK_ALIGNMENT_CONFLICT: unresolved requirement needs an action")
            unresolved.add(item["requirement_id"])
        elif action is not None:
            raise SchemaError("TASK_ALIGNMENT_CONFLICT: resolved requirement cannot have unresolved_action")

    instruction = review["next_instruction"]
    addressed = set(instruction["addresses_requirement_ids"]) if instruction is not None else set()
    if instruction is not None:
        if len(instruction["addresses_requirement_ids"]) != len(addressed):
            raise SchemaError("TASK_ALIGNMENT_CONFLICT: duplicate addressed requirement")
        authorized_advance = (
            review["schema_version"] == "2.4"
            and not unresolved
            and review["next_step_authority"]["task_transition"] == "ADVANCE_AUTHORIZED_PLAN"
        )
        if authorized_advance:
            if addressed:
                raise SchemaError(
                    "TASK_ALIGNMENT_CONFLICT: authorized plan advance cannot invent unresolved requirements",
                )
        elif not addressed or not addressed <= unresolved:
            raise SchemaError("TASK_ALIGNMENT_CONFLICT: next instruction is unrelated to unresolved task")

    replacements: set[str] = set()
    for item in review["added_scope"]:
        related = set(item["related_requirement_ids"])
        if not item["added_scope"].strip() or not item["prerequisite_justification"].strip():
            raise SchemaError("TASK_ALIGNMENT_CONFLICT: added scope needs justification")
        authorized_advance = (
            review["schema_version"] == "2.4"
            and not unresolved
            and review["next_step_authority"]["task_transition"] == "ADVANCE_AUTHORIZED_PLAN"
        )
        if (not authorized_advance and not related) or not related <= expected_requirement_ids:
            raise SchemaError("TASK_ALIGNMENT_CONFLICT: added scope is unrelated to the original task")
        if item["replaces_original_task"]:
            evidence = item["exact_blocking_evidence"]
            if not isinstance(evidence, str) or not evidence.strip():
                raise SchemaError("TASK_ALIGNMENT_CONFLICT: replacement prerequisite lacks blocking evidence")
            replacements.update(related)

    if (
        review["schema_version"] not in {"2.2", "2.3"}
        and review["orchestration_gate"] == "SAFE_CONTINUE"
        and unresolved - addressed - replacements
    ):
        raise SchemaError("TASK_ALIGNMENT_CONFLICT: unresolved task requirement omitted from next instruction")


def _validate_next_instruction_priority(review: dict[str, Any]) -> None:
    assessments = {
        item["requirement_id"]: item for item in review["task_requirement_assessment"]
    }
    unresolved = {
        requirement_id for requirement_id, item in assessments.items()
        if item["status"] in {"UNRESOLVED", "BLOCKED"}
    }
    instruction = review["next_instruction"]
    primary = set(instruction["primary_requirement_ids"]) if instruction is not None else set()
    addressed = set(instruction["addresses_requirement_ids"]) if instruction is not None else set()

    if instruction is not None:
        if len(instruction["primary_requirement_ids"]) != len(primary):
            raise SchemaError("TASK_ALIGNMENT_CONFLICT: duplicate primary requirement")
        authorized_advance = (
            review["schema_version"] == "2.4"
            and not unresolved
            and review["next_step_authority"]["task_transition"] == "ADVANCE_AUTHORIZED_PLAN"
        )
        if authorized_advance:
            if primary or addressed:
                raise SchemaError(
                    "TASK_ALIGNMENT_CONFLICT: authorized plan advance cannot claim unresolved coverage",
                )
        elif not primary or not primary <= unresolved:
            raise SchemaError("TASK_ALIGNMENT_CONFLICT: primary task must directly address unresolved requirements")
        if not authorized_advance and primary != addressed:
            raise SchemaError("TASK_ALIGNMENT_CONFLICT: next instruction coverage must equal primary requirements")

    deferred = unresolved - primary
    for requirement_id, item in assessments.items():
        reason = item["defer_reason"]
        evidence = item["exact_blocking_evidence"]
        if requirement_id in deferred:
            if not isinstance(reason, str) or not reason.strip():
                raise SchemaError("TASK_ALIGNMENT_CONFLICT: deferred requirement lacks defer_reason")
            if not isinstance(evidence, str) or not evidence.strip():
                raise SchemaError("TASK_ALIGNMENT_CONFLICT: deferred requirement lacks exact blocking evidence")
        elif reason is not None or evidence is not None:
            raise SchemaError("TASK_ALIGNMENT_CONFLICT: non-deferred requirement carries defer metadata")

    for item in review["added_scope"]:
        related = item["related_requirement_ids"]
        authorized_advance = (
            review["schema_version"] == "2.4"
            and not unresolved
            and review["next_step_authority"]["task_transition"] == "ADVANCE_AUTHORIZED_PLAN"
        )
        if not related and not authorized_advance:
            raise SchemaError("TASK_ALIGNMENT_CONFLICT: added scope lacks related original requirements")
        if item["replaces_original_task"] or item["is_prerequisite"]:
            evidence = item["exact_blocking_evidence"]
            if not isinstance(evidence, str) or not evidence.strip():
                raise SchemaError("TASK_ALIGNMENT_CONFLICT: promoted added scope lacks blocker evidence")


def _validate_next_step_authority(
    review: dict[str, Any],
    authorized_next_steps: list[dict[str, str]],
) -> None:
    authority = review["next_step_authority"]
    transition = authority["task_transition"]
    basis = authority["next_step_basis"]
    refs = authority["source_refs"]
    if len(refs) != len(set(refs)):
        raise SchemaError("TASK_ALIGNMENT_CONFLICT: duplicate next-step source reference")

    unresolved = {
        item["requirement_id"] for item in review["task_requirement_assessment"]
        if item["status"] in {"UNRESOLVED", "BLOCKED"}
    }
    gate = review["orchestration_gate"]
    if gate in {"BLOCKED", "STOP"}:
        if basis != "NONE" or refs:
            raise SchemaError("TASK_ALIGNMENT_CONFLICT: terminal routing cannot claim next-step authority")
        return

    if unresolved:
        expected_refs = {f"task_requirement:{item}" for item in unresolved}
        if (
            transition != "CONTINUE_CURRENT_TASK"
            or basis != "UNRESOLVED_REQUIREMENT"
            or not refs
            or not set(refs) <= expected_refs
        ):
            raise SchemaError("TASK_ALIGNMENT_CONFLICT: unresolved task authority was replaced")
        return

    catalog = {item["source_ref"]: item["basis"] for item in authorized_next_steps}
    if transition == "ADVANCE_AUTHORIZED_PLAN":
        if gate != "SAFE_CONTINUE" or basis not in {"FROZEN_NEXT_STEP", "APPROVED_PLAN_ITEM"}:
            raise SchemaError("TASK_ALIGNMENT_CONFLICT: invalid authorized-plan routing")
        if not refs or any(catalog.get(ref) != basis for ref in refs):
            raise SchemaError("TASK_ALIGNMENT_CONFLICT: next-step source reference is not canonical")
        return

    if transition == "USER_DECISION_REQUIRED":
        if gate != "USER_REQUIRED" or basis != "USER_DECISION" or refs:
            raise SchemaError("TASK_ALIGNMENT_CONFLICT: unapproved next step requires user routing")
        return

    raise SchemaError("TASK_ALIGNMENT_CONFLICT: completed task lacks authorized transition")


def _validate_evidence_sufficiency(review: dict[str, Any]) -> None:
    for item in review["task_requirement_assessment"]:
        criterion = item["acceptance_criteria_status"]
        reason = item["unresolved_reason_kind"]
        mandatory = item["mandatory_additional_evidence"]
        basis = item["mandatory_evidence_basis"]
        refs = item["mandatory_evidence_refs"]
        status = item["status"]

        if mandatory:
            if basis not in MANDATORY_EVIDENCE_BASES or not refs:
                raise SchemaError(
                    "EVIDENCE_THRESHOLD_CONFLICT: mandatory evidence lacks an allowed basis or exact evidence",
                )
            if basis == "ACCEPTANCE_CRITERION_UNMET" and criterion != "UNMET":
                raise SchemaError("EVIDENCE_THRESHOLD_CONFLICT: unmet basis contradicts criterion status")
            if basis == "ACTUAL_CONTRADICTION" and criterion != "CONTRADICTED":
                raise SchemaError("EVIDENCE_THRESHOLD_CONFLICT: contradiction basis lacks contradiction status")
            if basis in {"EXPLICIT_PROVENANCE_CONTRACT", "SAFETY_AUTHORITY_REQUIREMENT"} and criterion == "MET":
                raise SchemaError("EVIDENCE_THRESHOLD_CONFLICT: met criterion cannot be strengthened")
        elif basis != "NONE" or refs:
            raise SchemaError("EVIDENCE_THRESHOLD_CONFLICT: optional evidence carries mandatory basis")

        if criterion == "MET" and reason == "EVIDENCE_GAP":
            raise SchemaError("EVIDENCE_THRESHOLD_CONFLICT: met criterion reopened for additional evidence")
        if reason == "EVIDENCE_GAP" and not mandatory:
            raise SchemaError("EVIDENCE_THRESHOLD_CONFLICT: optional evidence cannot keep a requirement unresolved")
        if status in {"SATISFIED", "NOT_APPLICABLE"}:
            if reason != "NONE" or mandatory:
                raise SchemaError("EVIDENCE_THRESHOLD_CONFLICT: resolved requirement carries mandatory evidence work")
        elif reason == "NONE":
            raise SchemaError("EVIDENCE_THRESHOLD_CONFLICT: unresolved requirement lacks a reason kind")
