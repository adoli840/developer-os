from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from console.devos_orchestration.api_mainline_bootstrap import (
    ALLOWED_STATE_DELTA_FIELDS,
    API_MAINLINE_NODE_ID,
    ApiMainlineBootstrapError,
    api_mainline_bootstrap_schema,
    build_bootstrap_candidate,
    load_control_plane_canonical_state,
    read_public_bootstrap_summary,
    verify_bootstrap_candidate,
    validate_bootstrap_output,
    validate_state_delta,
)
from console.devos_orchestration.manifest import sha256_json
from console.devos_orchestration.schema import lint_structured_output_schema


def state_delta(gate: str | None = None) -> dict[str, object]:
    return {
        "current_purpose": None,
        "scope_append": [],
        "user_decisions_append": [],
        "current_gate": gate,
        "latest_relevant_handoff": None,
    }


class ApiMainlineBootstrapTests(unittest.TestCase):
    def test_schema_is_strict_and_state_delta_excludes_frozen_authority_routing(self) -> None:
        schema = api_mainline_bootstrap_schema()
        delta = schema["properties"]["updated_state_delta"]
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["required"]), set(schema["properties"]))
        self.assertEqual(set(delta["required"]), ALLOWED_STATE_DELTA_FIELDS)
        self.assertNotIn("frozen_decisions", delta["properties"])
        self.assertNotIn("authority", delta["properties"])
        self.assertNotIn("routing", delta["properties"])
        self.assertEqual(lint_structured_output_schema(schema)["status"], "PASS")

    def test_handoff_codex_requires_destination_and_message(self) -> None:
        output = {
            "action": "HANDOFF_CODEX",
            "assistant_message": None,
            "gate": "SAFE_CONTINUE",
            "destination": "CODEX_WORKER",
            "handoff_message": "Inspect the approved bounded scope.",
            "decision_packet": None,
            "blocker": None,
            "updated_state_delta": state_delta("SAFE_CONTINUE"),
        }
        self.assertEqual(validate_bootstrap_output(output), output)
        output["handoff_message"] = None
        with self.assertRaisesRegex(ApiMainlineBootstrapError, "BOOTSTRAP_ROUTING_CONFLICT"):
            validate_bootstrap_output(output)

    def test_user_dialogue_cannot_create_codex_handoff(self) -> None:
        output = {
            "action": "CONTINUE_USER_DIALOGUE",
            "assistant_message": "What is the first bTest objective?",
            "gate": None,
            "destination": "USER",
            "handoff_message": None,
            "decision_packet": None,
            "blocker": None,
            "updated_state_delta": state_delta(),
        }
        self.assertEqual(validate_bootstrap_output(output), output)
        output["handoff_message"] = "Do unapproved work"
        with self.assertRaisesRegex(ApiMainlineBootstrapError, "BOOTSTRAP_ROUTING_CONFLICT"):
            validate_bootstrap_output(output)

    def test_user_required_blocked_and_stop_are_fail_closed(self) -> None:
        base = {
            "assistant_message": None,
            "handoff_message": None,
            "updated_state_delta": state_delta(),
        }
        values = [
            dict(base, action="USER_REQUIRED", gate="USER_REQUIRED", destination="USER",
                 updated_state_delta=state_delta("USER_REQUIRED"),
                 decision_packet={"question": "Choose one", "options": ["A", "B"]}, blocker=None),
            dict(base, action="BLOCKED", gate="BLOCKED", destination=None, decision_packet=None,
                 updated_state_delta=state_delta("BLOCKED"),
                 blocker={"reason": "Required artifact is absent", "required_action": None, "stop_reason": None}),
            dict(base, action="STOP", gate="STOP", destination=None, decision_packet=None,
                 updated_state_delta=state_delta("STOP"),
                 blocker={"reason": None, "required_action": None, "stop_reason": "Safety boundary violated"}),
        ]
        for value in values:
            with self.subTest(action=value["action"]):
                self.assertEqual(validate_bootstrap_output(value), value)

    def test_state_delta_rejects_full_state_or_authority_changes(self) -> None:
        delta = state_delta()
        delta["authority"] = API_MAINLINE_NODE_ID
        with self.assertRaisesRegex(ApiMainlineBootstrapError, "CANONICAL_STATE_DELTA_FORBIDDEN"):
            validate_state_delta(delta)

    def test_candidate_seals_request_state_prompt_schema_runtime_and_cost(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "candidate.json"
            candidate = build_bootstrap_candidate(output)
            manifest = candidate["manifest"]
            request = candidate["request"]
            unsigned = dict(manifest)
            supplied = unsigned.pop("approval_manifest_sha256")

            self.assertEqual(supplied, sha256_json(unsigned))
            self.assertEqual(manifest["request_sha256"], hashlib.sha256(
                json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest())
            self.assertEqual(manifest["structured_output_schema_sha256"], sha256_json(
                request["text"]["format"]["schema"]
            ))
            self.assertNotIn("mode", request["reasoning"])
            self.assertEqual(request["tools"], [])
            self.assertFalse(request["store"])
            self.assertFalse(request["background"])
            self.assertFalse(candidate["approved_for_external_api"])
            self.assertEqual(candidate["network_calls"], 0)
            self.assertEqual(candidate["dispatch_count"], 0)
            self.assertGreater(Decimal(manifest["proposed_single_call_cap_usd"]), Decimal("0"))
            self.assertGreaterEqual(
                Decimal(manifest["proposed_single_call_cap_usd"]),
                Decimal(manifest["hard_worst_case_cost_usd"]),
            )
            verify_bootstrap_candidate(candidate)

    def test_candidate_input_excludes_unrelated_history_and_secret_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = build_bootstrap_candidate(Path(directory) / "candidate.json")
            serialized = json.dumps(candidate["request"])
            self.assertNotIn("conversation_id", serialized)
            self.assertNotIn("previous_response_id", serialized)
            self.assertNotIn("FUTURE_DESIGN", serialized)
            self.assertNotIn("OPENAI_ORCHESTRATION_API_KEY", serialized)

    def test_public_summary_verifies_manifest_and_never_exposes_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "candidate.json"
            candidate = build_bootstrap_candidate(output)
            summary = read_public_bootstrap_summary(output)
            self.assertEqual(
                summary["status"],
                "DO_NOT_EXECUTE / SAFE_BOOTSTRAP_FALLBACK",
            )
            self.assertEqual(summary["model"], candidate["manifest"]["model"])
            self.assertEqual(
                set(summary),
                {"status", "model", "proposed_hard_cap_usd", "canonical_state_sha256"},
            )
            candidate["request"]["model"] = "tampered"
            output.write_text(json.dumps(candidate), encoding="utf-8")
            self.assertEqual(read_public_bootstrap_summary(output)["status"], "INVALID")

    def test_public_summary_honors_matching_do_not_execute_disposition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "candidate.json"
            candidate = build_bootstrap_candidate(output)
            approval = candidate["manifest"]["approval_manifest_sha256"]
            disposition = {
                "approval_manifest_sha256": approval,
                "candidate_file_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "decision": "DO_NOT_EXECUTE",
            }
            (output.parent / f"disposition-{approval}.json").write_text(
                json.dumps(disposition), encoding="utf-8",
            )
            self.assertEqual(
                read_public_bootstrap_summary(output)["status"],
                "DO_NOT_EXECUTE / SAFE_BOOTSTRAP_FALLBACK",
            )

    def test_state_delta_gate_must_match_routing_gate(self) -> None:
        output = {
            "action": "USER_REQUIRED",
            "assistant_message": None,
            "gate": "USER_REQUIRED",
            "destination": "USER",
            "handoff_message": None,
            "decision_packet": {"question": "Choose one", "options": ["A", "B"]},
            "blocker": None,
            "updated_state_delta": state_delta("BLOCKED"),
        }
        with self.assertRaisesRegex(ApiMainlineBootstrapError, "BOOTSTRAP_STATE_GATE_CONFLICT"):
            validate_bootstrap_output(output)

    def test_existing_canonical_state_is_loaded_without_conversation_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "control.json"
            path.write_text(json.dumps({
                "projects": {"btest": {"mainline_state": {
                    "canonical_state": {"current_purpose": "existing"},
                    "openai_conversation_state": {"conversation_id": "private"},
                }}},
            }), encoding="utf-8")
            self.assertEqual(
                load_control_plane_canonical_state(path),
                {"current_purpose": "existing"},
            )


if __name__ == "__main__":
    unittest.main()
