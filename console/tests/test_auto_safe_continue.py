from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from console.devos_orchestration.activity_timeline import project_activity_timeline
from console.devos_orchestration.auto_safe_continue import (
    AutoAdvanceEvidence,
    AutoSafeContinueError,
    cumulative_cost_preflight,
    evaluate_auto_advance,
    pilot_policy,
)
from console.devos_orchestration.auto_safe_continue_pilot import (
    AutoSafeContinuePilotError,
    AutoSafeContinuePilotStore,
)
from console.devos_orchestration.api_mainline_bootstrap import ApiMainlineBootstrapError
from console.devos_orchestration.api_mainline_continuation import (
    build_continuation_request,
    validate_auto_advance_evidence,
    validate_continuation_output,
    validation_provenance,
)
from console.devos_orchestration.task_alignment import extract_requirement_inventory
from console.devos_orchestration.auto_safe_continue_retry import build_retry_candidate
from console.devos_orchestration.manifest import sha256_json
from console.tests.test_orchestration import valid_review_v2_4


def valid_evidence() -> AutoAdvanceEvidence:
    return AutoAdvanceEvidence(
        gate="SAFE_CONTINUE",
        resolution_kind="BOUNDED_TASK",
        task_transition="CONTINUE_CURRENT_TASK",
        next_step_basis="UNRESOLVED_REQUIREMENT",
        source_refs=("task_requirement:REQ-1",),
        deterministic_validation="PASS",
        task_alignment="PASS",
        evidence_sufficiency="PASS",
        user_required=False,
        blocker=None,
        workspace_fingerprint_valid=True,
        approval_input_required=False,
    )


class AutoSafeContinuePolicyTests(unittest.TestCase):
    def test_cost_preflight_is_bounded_to_two_calls_and_requires_approval(self) -> None:
        value = cumulative_cost_preflight("0.313524750", "0.32")
        self.assertEqual(value["cumulative_hard_worst_case_usd"], "0.627049500")
        self.assertEqual(value["recommended_pilot_cap_usd"], "0.64")
        self.assertIsNone(value["approved_pilot_cap_usd"])
        self.assertEqual(value["status"], "CUMULATIVE_COST_CAP_APPROVAL_REQUIRED")
        self.assertFalse(pilot_policy(value)["enabled"])

    def test_valid_bounded_safe_continue_can_advance_only_under_approved_cap(self) -> None:
        value = evaluate_auto_advance(
            valid_evidence(), cycles_completed=0, cumulative_cost_usd="0",
            next_call_worst_case_usd="0.313524750", approved_cumulative_cap_usd="0.63",
        )
        self.assertEqual(value["decision"], "ALLOW_AUTO_ADVANCE")
        self.assertEqual(value["next_cycle"], 1)
        self.assertEqual(value["codex_retry_count"], 0)
        self.assertFalse(value["automatic_approval"])

    def test_second_completed_cycle_stops_regardless_of_gate(self) -> None:
        value = evaluate_auto_advance(
            valid_evidence(), cycles_completed=2, cumulative_cost_usd="0.4",
            next_call_worst_case_usd="0.1", approved_cumulative_cap_usd="0.63",
        )
        self.assertEqual(value["stop_reason"], "AUTO_CYCLE_LIMIT_REACHED")

    def test_fail_closed_stop_conditions(self) -> None:
        cases = {
            "user gate": (replace(valid_evidence(), gate="USER_REQUIRED"), "USER_REQUIRED"),
            "user flag": (replace(valid_evidence(), user_required=True), "USER_REQUIRED"),
            "blocked": (replace(valid_evidence(), gate="BLOCKED"), "BLOCKED"),
            "stop": (replace(valid_evidence(), gate="STOP"), "STOP"),
            "approval": (replace(valid_evidence(), approval_input_required=True), "CODEX_APPROVAL_OR_INPUT_REQUIRED"),
            "routing": (replace(valid_evidence(), routing_conflict=True), "ROUTING_CONFLICT"),
            "task": (replace(valid_evidence(), task_alignment_conflict=True), "TASK_ALIGNMENT_CONFLICT"),
            "evidence": (replace(valid_evidence(), evidence_threshold_conflict=True), "EVIDENCE_THRESHOLD_CONFLICT"),
            "workspace": (replace(valid_evidence(), workspace_fingerprint_valid=False), "WORKSPACE_CHANGED_EXTERNALLY"),
            "transport": (replace(valid_evidence(), transport_failure=True), "TRANSPORT_FAILURE"),
            "blocker": (replace(valid_evidence(), blocker="missing artifact"), "BLOCKER_PRESENT"),
        }
        for label, (evidence, reason) in cases.items():
            with self.subTest(label=label):
                value = evaluate_auto_advance(
                    evidence, cycles_completed=0, cumulative_cost_usd="0",
                    next_call_worst_case_usd="0.1", approved_cumulative_cap_usd="0.63",
                )
                self.assertEqual(value["decision"], "STOP_AUTO_ADVANCE")
                self.assertEqual(value["stop_reason"], reason)

    def test_forbidden_change_classes_and_budget_fail_closed(self) -> None:
        for change_class in ("DESTRUCTIVE", "DATABASE", "INFRASTRUCTURE", "AUTHORITY", "THRESHOLD", "SCOPE_EXPANSION"):
            with self.subTest(change_class=change_class):
                value = evaluate_auto_advance(
                    replace(valid_evidence(), change_classes=(change_class,)),
                    cycles_completed=0, cumulative_cost_usd="0",
                    next_call_worst_case_usd="0.1", approved_cumulative_cap_usd="0.63",
                )
                self.assertEqual(value["stop_reason"], "FORBIDDEN_AUTO_CHANGE")
        missing_cap = evaluate_auto_advance(
            valid_evidence(), cycles_completed=0, cumulative_cost_usd="0",
            next_call_worst_case_usd="0.1", approved_cumulative_cap_usd=None,
        )
        self.assertEqual(missing_cap["stop_reason"], "CUMULATIVE_COST_CAP_APPROVAL_REQUIRED")
        exceeded = evaluate_auto_advance(
            valid_evidence(), cycles_completed=1, cumulative_cost_usd="0.4",
            next_call_worst_case_usd="0.3", approved_cumulative_cap_usd="0.63",
        )
        self.assertEqual(exceeded["stop_reason"], "CUMULATIVE_COST_CAP_EXCEEDED")

    def test_invalid_costs_are_rejected(self) -> None:
        with self.assertRaises(AutoSafeContinueError):
            cumulative_cost_preflight("0")
        with self.assertRaises(AutoSafeContinueError):
            evaluate_auto_advance(
                valid_evidence(), cycles_completed=0, cumulative_cost_usd="-1",
                next_call_worst_case_usd="0.1", approved_cumulative_cap_usd="1",
            )


class ActivityTimelineTests(unittest.TestCase):
    def test_timeline_uses_sealed_dispatch_and_return_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dispatch = root / "dispatch"
            returns = root / "returns"
            dispatch.mkdir()
            returns.mkdir()
            handoff = "handoff-1"
            (dispatch / f"{handoff}.json").write_text(json.dumps({
                "source_node_id": "BTEST_MAINLINE_API",
                "destination_node_id": "BTEST_CODEX_WORKER",
                "task_message": "Run the bounded read-only check.",
            }), encoding="utf-8")
            (dispatch / "dispatch-ledger.json").write_text(json.dumps({
                "handoffs": {handoff: {
                    "state": "COMPLETED", "attempt_started_at": "2026-08-16T01:00:00Z",
                    "updated_at": "2026-08-16T01:04:00Z", "task_content_sha256": "a" * 64,
                    "envelope_sha256": "b" * 64,
                }},
            }), encoding="utf-8")
            return_id = "return-1"
            (returns / "ledger.json").write_text(json.dumps({
                "returns": {return_id: {"project": "btest", "state": "COMPLETED"}},
            }), encoding="utf-8")
            (returns / f"{return_id}-result.json").write_text(json.dumps({
                "completed_at": "2026-08-16T01:05:00Z", "gate": "SAFE_CONTINUE",
                "status": "COMPLETED", "destination": "CODEX_WORKER",
                "token_usage": {"total_tokens": 1356},
                "usage_based_estimated_cost_usd": "0.022430",
                "result_sha256": "c" * 64,
                "next_handoff": {"status": "PREPARED", "exact_message": "Next bounded task",
                    "exact_message_sha256": "d" * 64},
            }), encoding="utf-8")

            value = project_activity_timeline("btest", dispatch, returns)

        self.assertEqual([item["event_type"] for item in value["events"]], [
            "TASK_SENT", "REPORT_RECEIVED", "GATE_DECIDED", "NEXT_TASK_PREPARED",
        ])
        self.assertEqual(value["events"][0]["detail"]["message_preview"], "Run the bounded read-only check.")
        self.assertEqual(value["events"][-1]["status"], "USER_APPROVAL_REQUIRED")
        self.assertNotIn("manual", json.dumps(value).lower())


class AutoSafeContinuePilotStoreTests(unittest.TestCase):
    def test_missing_validation_evidence_stops_before_any_transport(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source-result.json"
            source.write_text(json.dumps({
                "status": "COMPLETED",
                "gate": "SAFE_CONTINUE",
                "parsed_action": "HANDOFF_CODEX",
                "next_handoff": {"status": "PREPARED"},
            }), encoding="utf-8")
            store = AutoSafeContinuePilotStore(root / "pilot")
            result = store.execute_preflight(
                project="btest",
                source_result_path=source,
                approved_cumulative_cap_usd="0.64",
                next_call_worst_case_usd="0.313524750",
                workspace_fingerprint_valid=True,
            )

            self.assertEqual(result["status"], "STOPPED")
            self.assertEqual(
                result["decision"]["stop_reason"],
                "AUTO_ADVANCE_VALIDATION_EVIDENCE_MISSING",
            )
            self.assertEqual(result["mainline_api_calls"], 0)
            self.assertEqual(result["codex_turns"], 0)
            self.assertEqual(result["dispatch_count"], 0)
            self.assertEqual(result["cumulative_usage_based_cost_usd"], "0")
            with self.assertRaises(AutoSafeContinuePilotError):
                store.execute_preflight(
                    project="btest",
                    source_result_path=source,
                    approved_cumulative_cap_usd="0.64",
                    next_call_worst_case_usd="0.313524750",
                    workspace_fingerprint_valid=True,
                )

    def test_pilot_stop_is_visible_in_activity_timeline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dispatch, returns, pilot = root / "dispatch", root / "returns", root / "pilot"
            dispatch.mkdir(); returns.mkdir(); pilot.mkdir()
            (dispatch / "dispatch-ledger.json").write_text('{"handoffs":{}}', encoding="utf-8")
            (returns / "ledger.json").write_text('{"returns":{}}', encoding="utf-8")
            (pilot / "ledger.json").write_text(json.dumps({"runs": {"pilot-1": {
                "project": "btest", "status": "STOPPED",
                "stop_reason": "AUTO_ADVANCE_VALIDATION_EVIDENCE_MISSING",
                "result_file_sha256": "a" * 64,
                "completed_at": "2026-08-16T01:00:00Z",
            }}}), encoding="utf-8")

            value = project_activity_timeline("btest", dispatch, returns, pilot)

        self.assertEqual(len(value["events"]), 1)
        self.assertEqual(value["events"][0]["event_type"], "AUTO_PILOT_STOPPED")


class AutoAdvanceEvidencePropagationTests(unittest.TestCase):
    @staticmethod
    def canonical_state(**updates: object) -> dict[str, object]:
        value: dict[str, object] = {
            "current_purpose": "Perform the bounded audit.",
            "frozen_decisions": ["Do not expand scope."],
            "scope": ["read-only audit"],
            "authority": "BTEST_MAINLINE_API",
            "routing": {"latest_action": None, "current_destination": None},
            "user_decisions": [],
            "current_gate": "SAFE_CONTINUE",
            "latest_relevant_handoff": None,
        }
        value.update(updates)
        return value

    @staticmethod
    def output() -> tuple[dict[str, object], set[str]]:
        task = "1. Inspect\nPerform the bounded audit."
        requirement_id = extract_requirement_inventory(task)[0]["requirement_id"]
        review = valid_review_v2_4((requirement_id,))
        value: dict[str, object] = {
            "action": "HANDOFF_CODEX",
            "assistant_message": None,
            "gate": "SAFE_CONTINUE",
            "destination": "CODEX_WORKER",
            "handoff_message": "Perform the next bounded audit.",
            "decision_packet": None,
            "blocker": None,
            "updated_state_delta": {
                "current_purpose": None, "scope_append": [], "user_decisions_append": [],
                "current_gate": "SAFE_CONTINUE", "latest_relevant_handoff": None,
            },
            "auto_advance_review": review,
        }
        return value, {requirement_id}

    def test_all_four_authoritative_values_propagate_after_validation(self) -> None:
        output, ids = self.output()
        _validated, evidence = validate_continuation_output(output, ids)
        self.assertEqual(evidence["resolution_kind"], "BOUNDED_TASK")
        self.assertEqual(evidence["deterministic_validation"], "PASS")
        self.assertEqual(evidence["task_alignment"], "PASS")
        self.assertEqual(evidence["evidence_sufficiency"], "PASS")
        self.assertEqual(validate_auto_advance_evidence(evidence), evidence)

    def test_each_missing_value_fails_closed(self) -> None:
        output, ids = self.output()
        _validated, evidence = validate_continuation_output(output, ids)
        for field in (
            "resolution_kind", "task_transition", "next_step_basis", "source_refs",
            "deterministic_validation", "task_alignment", "evidence_sufficiency",
        ):
            with self.subTest(field=field):
                changed = dict(evidence)
                changed.pop(field)
                with self.assertRaisesRegex(ApiMainlineBootstrapError, "SHAPE_INVALID"):
                    validate_auto_advance_evidence(changed)

    def test_stale_provenance_fails_closed(self) -> None:
        output, ids = self.output()
        _validated, evidence = validate_continuation_output(output, ids)
        changed = json.loads(json.dumps(evidence))
        changed["provenance"]["continuation_schema_version"] = "stale"
        with self.assertRaisesRegex(ApiMainlineBootstrapError, "PROVENANCE_MISMATCH"):
            validate_auto_advance_evidence(changed)

    def test_safe_continue_with_failed_alignment_or_evidence_is_blocked(self) -> None:
        output, ids = self.output()
        _validated, evidence = validate_continuation_output(output, ids)
        for field in ("task_alignment", "evidence_sufficiency"):
            with self.subTest(field=field):
                changed = {**evidence, field: "FAIL"}
                validated = validate_auto_advance_evidence(changed)
                value = evaluate_auto_advance(
                    AutoAdvanceEvidence(
                        gate="SAFE_CONTINUE",
                        resolution_kind=validated["resolution_kind"],
                        task_transition=validated["task_transition"],
                        next_step_basis=validated["next_step_basis"],
                        source_refs=tuple(validated["source_refs"]),
                        deterministic_validation=validated["deterministic_validation"],
                        task_alignment=validated["task_alignment"],
                        evidence_sufficiency=validated["evidence_sufficiency"],
                        user_required=False, blocker=None,
                        workspace_fingerprint_valid=True, approval_input_required=False,
                    ),
                    cycles_completed=0, cumulative_cost_usd="0",
                    next_call_worst_case_usd="0.1", approved_cumulative_cap_usd="0.64",
                )
                self.assertEqual(value["stop_reason"], "AUTO_ADVANCE_CONTRACT_NOT_SATISFIED")

    def test_continuation_request_binds_task_report_and_schema(self) -> None:
        state = self.canonical_state(
            conversation_history=["must not be transmitted"],
            manual_review="baseline sentinel",
            activity_timeline=["completed cycle"],
        )
        request, prompt, inventory = build_continuation_request(
            state,
            "1. Inspect\nPerform the bounded audit.",
            "Codex report body sentinel",
        )
        dynamic = json.loads(request["input"][1]["content"])
        self.assertEqual(dynamic["latest_codex_report"], "Codex report body sentinel")
        self.assertEqual(dynamic["current_task"], "1. Inspect\nPerform the bounded audit.")
        self.assertEqual(dynamic["requirement_ids"], [inventory[0]["requirement_id"]])
        self.assertEqual(dynamic["canonical_context"]["frozen_decisions"], ["Do not expand scope."])
        self.assertNotIn("conversation_history", dynamic["canonical_context"])
        self.assertNotIn("manual_review", request["input"][1]["content"])
        self.assertNotIn("baseline sentinel", request["input"][1]["content"])
        self.assertNotIn("completed cycle", request["input"][1]["content"])
        self.assertEqual(request["input"][0]["content"], prompt)
        self.assertNotIn("Codex report body sentinel", prompt)
        self.assertEqual(request["text"]["verbosity"], "low")
        self.assertEqual(request["max_output_tokens"], 6144)
        self.assertTrue(inventory)
        self.assertIn("auto_advance_review", request["text"]["format"]["schema"]["properties"])
        self.assertEqual(validation_provenance()["reviewer_schema_version"], "2.4")

    def test_retry_candidate_is_pristine_local_only_and_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = "1. Inspect\nPerform the bounded audit."
            report = "Codex report"
            dispatch = root / "dispatch.json"
            source = root / "source.json"
            output = root / "candidate.json"
            import hashlib
            task_hash = hashlib.sha256(task.encode()).hexdigest()
            report_hash = hashlib.sha256(report.encode()).hexdigest()
            dispatch.write_text(json.dumps({
                "handoff_id": "handoff-1", "task_content_sha256": task_hash,
                "rendered_message": {"message": task},
            }), encoding="utf-8")
            source.write_text(json.dumps({
                "exact_result": report, "canonical_state": self.canonical_state(),
                "manifest": {
                    "exact_result_sha256": report_hash, "source_dispatch_id": "handoff-1",
                },
            }), encoding="utf-8")

            result = build_retry_candidate(
                output, source_candidate_path=source, dispatch_artifact_path=dispatch,
            )

            self.assertFalse(result["approved_for_external_api"])
            self.assertFalse(result["approval_record"])
            self.assertFalse(result["attempt_record"])
            self.assertFalse(result["result_record"])
            self.assertEqual(result["network_calls"], 0)
            with self.assertRaisesRegex(ValueError, "CANDIDATE_EXISTS"):
                build_retry_candidate(
                    output, source_candidate_path=source, dispatch_artifact_path=dispatch,
                )

    def test_retry_candidate_can_rebind_to_current_canonical_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = "1. Inspect\nPerform the bounded audit."
            report = "Codex report"
            dispatch = root / "dispatch.json"
            source = root / "source.json"
            output = root / "candidate.json"
            import hashlib
            task_hash = hashlib.sha256(task.encode()).hexdigest()
            report_hash = hashlib.sha256(report.encode()).hexdigest()
            dispatch.write_text(json.dumps({
                "handoff_id": "handoff-1", "task_content_sha256": task_hash,
                "rendered_message": {"message": task},
            }), encoding="utf-8")
            source.write_text(json.dumps({
                "exact_result": report,
                "canonical_state": self.canonical_state(current_gate="OLD"),
                "manifest": {
                    "exact_result_sha256": report_hash, "source_dispatch_id": "handoff-1",
                },
            }), encoding="utf-8")
            current_state = self.canonical_state()

            result = build_retry_candidate(
                output,
                source_candidate_path=source,
                dispatch_artifact_path=dispatch,
                canonical_state=current_state,
            )
            candidate = json.loads(output.read_text(encoding="utf-8"))

            self.assertEqual(result["network_calls"], 0)
            self.assertEqual(
                candidate["binding"]["canonical_state_sha256"], sha256_json(current_state),
            )
            self.assertNotEqual(
                candidate["binding"]["canonical_state_sha256"],
                sha256_json(self.canonical_state(current_gate="OLD")),
            )
