from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from console.devos_console.audit import AuditLog
from console.devos_orchestration.control_plane import (
    ControlPlaneError,
    OrchestrationControlStore,
    transport_adapter,
    transport_capabilities,
)
from console.devos_orchestration.api_mainline import api_mainline_output_schema


def node(
    node_id: str,
    role: str,
    transport_kind: str = "MOCK",
    *,
    enabled: bool = True,
    allowed_sources: list[str] | None = None,
    allowed_destinations: list[str] | None = None,
) -> dict[str, object]:
    return {
        "node_id": node_id,
        "display_name": node_id.replace("-", " ").title(),
        "role": role,
        "transport_kind": transport_kind,
        "transport_ref": f"private:{node_id}",
        "enabled": enabled,
        "allowed_sources": allowed_sources or [],
        "allowed_destinations": allowed_destinations or [],
    }


class ControlPlaneStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.audit_path = root / "audit.jsonl"
        self.store = OrchestrationControlStore(
            root / "orchestration-control.json",
            ["developer-os", "btest"],
            AuditLog(self.audit_path),
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_default_project_model_is_disabled_and_execution_locked(self) -> None:
        value = self.store.list_projects()
        project = value["projects"][0]

        self.assertEqual(project["mode"], "OFF")
        self.assertEqual(project["status"], "DISABLED")
        self.assertFalse(project["orchestration_enabled"])
        self.assertFalse(value["background_execution"])
        self.assertFalse(value["dispatch_enabled"])
        self.assertEqual(value["reserved_modes"][0]["status"], "PILOT_LOCKED_CAP_APPROVAL_REQUIRED")
        self.assertEqual(value["reserved_modes"][0]["max_auto_cycles"], 2)
        self.assertFalse(value["reserved_modes"][0]["background_execution"])
        self.assertIn("SESSION_HANDOFF", value["phase_1_contracts"])

    def test_node_crud_persists_but_public_state_hides_transport_reference(self) -> None:
        created = self.store.add_node("developer-os", node("mainline", "MAINLINE"))
        public_node = created["nodes"][0]
        self.assertNotIn("transport_ref", public_node)
        self.assertTrue(public_node["transport_configured"])

        updated = self.store.update_node(
            "developer-os", "mainline", {"display_name": "Mainline GPT", "role": "REVIEWER"},
        )
        self.assertEqual(updated["nodes"][0]["display_name"], "Mainline GPT")
        self.assertEqual(updated["nodes"][0]["role"], "REVIEWER")

        reloaded = OrchestrationControlStore(
            self.store.path,
            ["developer-os", "btest"],
            AuditLog(self.audit_path),
        )
        self.assertEqual(reloaded.list_projects()["projects"][0]["nodes"][0]["node_id"], "mainline")
        self.assertEqual(self.store.delete_node("developer-os", "mainline")["nodes"], [])

    def test_route_graph_supports_user_destination_and_crud(self) -> None:
        self.store.add_node(
            "developer-os",
            node("mainline", "MAINLINE", allowed_destinations=["user"]),
        )
        self.store.add_node(
            "developer-os",
            node("user", "USER", "USER_ASSISTED", allowed_sources=["mainline"]),
        )
        created = self.store.add_route(
            "developer-os",
            {
                "route_id": "mainline-to-user",
                "source_node_id": "mainline",
                "destination_node_id": "user",
                "enabled": True,
                "handoff_type": "DECISION",
            },
        )
        self.assertEqual(created["routes"][0]["destination_node_id"], "user")
        self.assertFalse(
            self.store.update_route(
                "developer-os", "mainline-to-user", {"enabled": False},
            )["routes"][0]["enabled"]
        )
        self.assertEqual(
            self.store.delete_route("developer-os", "mainline-to-user")["routes"],
            [],
        )

    def test_invalid_missing_self_and_disallowed_destinations_are_rejected(self) -> None:
        self.store.add_node(
            "developer-os",
            node("mainline", "MAINLINE", allowed_destinations=["worker"]),
        )
        self.store.add_node("developer-os", node("worker", "CODEX_WORKER"))
        self.store.add_node("developer-os", node("user", "USER"))

        cases = [
            ("missing", "mainline", "missing", "ROUTE_NODE_NOT_FOUND"),
            ("self", "mainline", "mainline", "SELF_ROUTE_FORBIDDEN"),
            ("forbidden", "mainline", "user", "DESTINATION_NOT_ALLOWED"),
        ]
        for route_id, source, destination, expected in cases:
            with self.subTest(route_id=route_id), self.assertRaisesRegex(ControlPlaneError, expected):
                self.store.add_route(
                    "developer-os",
                    {
                        "route_id": route_id,
                        "source_node_id": source,
                        "destination_node_id": destination,
                        "enabled": True,
                        "handoff_type": "HANDOFF",
                    },
                )

    def test_enabled_route_blocks_disabling_a_node(self) -> None:
        self.store.add_node("developer-os", node("mainline", "MAINLINE"))
        self.store.add_node("developer-os", node("worker", "CODEX_WORKER"))
        self.store.add_route(
            "developer-os",
            {
                "route_id": "work",
                "source_node_id": "mainline",
                "destination_node_id": "worker",
                "enabled": True,
                "handoff_type": "TASK",
            },
        )
        with self.assertRaisesRegex(ControlPlaneError, "DISABLED_NODE_ROUTE_FORBIDDEN"):
            self.store.update_node("developer-os", "worker", {"enabled": False})

    def test_mode_and_pause_resume_stop_transitions(self) -> None:
        state = self.store.set_mode("developer-os", "SHADOW_REVIEW")
        self.assertEqual((state["mode"], state["status"]), ("SHADOW_REVIEW", "IDLE"))
        state = self.store.set_mode("developer-os", "SEMI_AUTO")
        self.assertEqual((state["mode"], state["status"]), ("SEMI_AUTO", "IDLE"))
        self.assertEqual(self.store.control("developer-os", "PAUSE")["status"], "PAUSED")
        self.assertEqual(self.store.control("developer-os", "RESUME")["status"], "IDLE")
        stopped = self.store.control("developer-os", "STOP")
        self.assertEqual(stopped["status"], "STOPPED")
        self.assertFalse(stopped["orchestration_enabled"])
        off = self.store.set_mode("developer-os", "OFF")
        self.assertEqual((off["mode"], off["status"]), ("OFF", "DISABLED"))

    def test_auto_safe_continue_is_not_selectable(self) -> None:
        with self.assertRaisesRegex(ControlPlaneError, "AUTO_SAFE_CONTINUE_LOCKED"):
            self.store.set_mode("developer-os", "AUTO_SAFE_CONTINUE")

    def test_audit_records_user_actions_without_transport_refs_or_content(self) -> None:
        self.store.add_node("developer-os", node("mainline", "MAINLINE"))
        self.store.set_mode("developer-os", "SHADOW_REVIEW")
        records = [json.loads(line) for line in self.audit_path.read_text(encoding="utf-8").splitlines()]
        serialized = json.dumps(records)

        self.assertEqual([record["action_type"] for record in records], ["NODE_ADDED", "MODE_CHANGED"])
        self.assertTrue(all(record["project"] == "developer-os" for record in records))
        self.assertTrue(all("old_state" in record and "new_state" in record for record in records))
        self.assertTrue(records[0]["new_state"]["nodes"][0]["enabled"])
        self.assertNotIn("private:mainline", serialized)
        self.assertNotIn("transport_ref", serialized)

    def test_btest_api_mainline_state_is_separate_and_private_transport_ids_stay_hidden(self) -> None:
        private = self.store._load()
        conversation = private["projects"]["btest"]["mainline_state"]["openai_conversation_state"]
        conversation["conversation_id"] = "conv-private"
        conversation["previous_response_id"] = "resp-private"
        conversation["model_interaction_history"] = [{"response_id": "resp-private"}]
        self.store._write(private)
        project = next(
            item for item in self.store.list_projects()["projects"] if item["project"] == "btest"
        )
        api_node = next(item for item in project["nodes"] if item["node_id"] == "BTEST_MAINLINE_API")

        self.assertEqual(project["mainline_state"]["authority"], "NATIVE_MAINLINE")
        native_node = next(item for item in project["nodes"] if item["node_id"] == "BTEST_MAINLINE")
        self.assertEqual(native_node["authority_status"], "ACTIVE")
        self.assertEqual(api_node["transport_kind"], "OPENAI_RESPONSES")
        self.assertEqual(api_node["authority_status"], "INACTIVE")
        self.assertTrue(project["mainline_state"]["api_mainline"]["conversation_initialized"])
        self.assertEqual(project["mainline_state"]["api_mainline"]["interaction_count"], 1)
        self.assertEqual(
            set(project["mainline_state"]["api_mainline"]["capabilities"]),
            {"READ", "WRITE", "RESUME"},
        )
        serialized = json.dumps(project)
        self.assertNotIn("conversation_id", serialized)
        self.assertNotIn("previous_response_id", serialized)
        self.assertNotIn("model_interaction_history", serialized)
        self.store.set_mode("btest", "SHADOW_REVIEW")
        self.assertNotIn("conv-private", self.audit_path.read_text(encoding="utf-8"))
        self.assertNotIn("resp-private", self.audit_path.read_text(encoding="utf-8"))

    def test_btest_authority_switches_without_dual_canonical_authority(self) -> None:
        enabled = self.store.set_mode("btest", "SHADOW_REVIEW")
        self.assertEqual(enabled["mainline_state"]["authority"], "BTEST_MAINLINE_API")
        authorities = {
            node["node_id"]: node.get("authority_status")
            for node in enabled["nodes"] if node["role"] == "MAINLINE"
        }
        self.assertEqual(authorities["BTEST_MAINLINE_API"], "ACTIVE")

        stopped = self.store.control("btest", "STOP")
        self.assertEqual(stopped["mainline_state"]["authority"], "NATIVE_MAINLINE")
        records = [json.loads(line) for line in self.audit_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(records[0]["old_state"]["mainline"]["authority"], "NATIVE_MAINLINE")
        self.assertEqual(records[0]["new_state"]["mainline"]["authority"], "BTEST_MAINLINE_API")
        self.assertNotIn("conversation_id", json.dumps(records))

    def test_inactive_native_mainline_route_is_blocked_when_orchestration_is_on(self) -> None:
        self.store.add_node(
            "btest",
            node(
                "BTEST_CODEX_WORKER", "CODEX_WORKER", "CODEX_THREAD",
                allowed_sources=["BTEST_MAINLINE", "BTEST_MAINLINE_API"],
                allowed_destinations=["BTEST_MAINLINE", "BTEST_MAINLINE_API"],
            ),
        )
        self.store.add_route("btest", {
            "route_id": "native-to-worker",
            "source_node_id": "BTEST_MAINLINE",
            "destination_node_id": "BTEST_CODEX_WORKER",
            "enabled": True,
            "handoff_type": "TASK",
        })
        self.store.set_mode("btest", "SHADOW_REVIEW")

        with self.assertRaisesRegex(ControlPlaneError, "INACTIVE_MAINLINE_AUTHORITY"):
            self.store.resolve_route("btest", "native-to-worker")
        resolved = self.store.resolve_route("btest", "BTEST_MAINLINE_API_TO_CODEX")
        self.assertEqual(resolved["source"]["node_id"], "BTEST_MAINLINE_API")

    def test_structured_mainline_routing_validates_action_and_destination(self) -> None:
        self.store.add_node(
            "btest",
            node(
                "BTEST_CODEX_WORKER", "CODEX_WORKER", "CODEX_THREAD",
                allowed_sources=["BTEST_MAINLINE_API"],
                allowed_destinations=["BTEST_MAINLINE_API"],
            ),
        )
        self.store.set_mode("btest", "SEMI_AUTO")
        output = {
            "action": "HANDOFF_CODEX",
            "destination_node_id": "BTEST_CODEX_WORKER",
            "exact_message": "Perform the approved bounded task.",
            "user_decision_packet": None,
            "blocker_packet": None,
            "stop_reason": None,
        }
        recorded = self.store.record_mainline_output("btest", "BTEST_MAINLINE_API", output)
        self.assertEqual(
            recorded["mainline_state"]["canonical_state"]["routing"],
            {"latest_action": "HANDOFF_CODEX", "current_destination": "BTEST_CODEX_WORKER"},
        )

        invalid = dict(output, destination_node_id="missing-worker")
        with self.assertRaisesRegex(ControlPlaneError, "INVALID_CODEX_HANDOFF_ACTION"):
            self.store.record_mainline_output("btest", "BTEST_MAINLINE_API", invalid)
        with self.assertRaisesRegex(ControlPlaneError, "NON_CANONICAL_MAINLINE_SOURCE"):
            self.store.record_mainline_output("btest", "BTEST_MAINLINE", output)

    def test_structured_mainline_actions_are_fail_closed(self) -> None:
        self.store.set_mode("btest", "SHADOW_REVIEW")
        valid = [
            {
                "action": "USER_REQUIRED", "destination_node_id": "USER",
                "exact_message": None,
                "user_decision_packet": {"question": "Choose a threshold", "options": ["0.8", "0.9"]},
                "blocker_packet": None, "stop_reason": None,
            },
            {
                "action": "CONTINUE_USER_DIALOGUE", "destination_node_id": "USER",
                "exact_message": "Please clarify the intended scope.",
                "user_decision_packet": None, "blocker_packet": None, "stop_reason": None,
            },
            {
                "action": "BLOCKED", "destination_node_id": None, "exact_message": None,
                "user_decision_packet": None,
                "blocker_packet": {"blocker": "Required fixture is unavailable", "required_action": None},
                "stop_reason": None,
            },
            {
                "action": "STOP", "destination_node_id": None, "exact_message": None,
                "user_decision_packet": None, "blocker_packet": None,
                "stop_reason": "Safety contract violation",
            },
        ]
        for output in valid:
            with self.subTest(action=output["action"]):
                state = self.store.record_mainline_output("btest", "BTEST_MAINLINE_API", output)
                self.assertEqual(
                    state["mainline_state"]["canonical_state"]["routing"]["latest_action"],
                    output["action"],
                )

        conflict = dict(valid[0], destination_node_id="BTEST_CODEX_WORKER")
        with self.assertRaisesRegex(ControlPlaneError, "INVALID_USER_REQUIRED_ACTION"):
            self.store.record_mainline_output("btest", "BTEST_MAINLINE_API", conflict)

    def test_api_mainline_output_schema_is_strict_and_network_stays_disabled(self) -> None:
        schema = api_mainline_output_schema()
        value = self.store.list_projects()
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["required"]), set(schema["properties"]))
        self.assertFalse(value["api_mainline_network_enabled"])

    def test_api_mainline_turn_applies_only_allowlisted_delta_and_safe_linkage(self) -> None:
        self.store.set_mode("btest", "SHADOW_REVIEW")
        before = next(
            item for item in self.store.list_projects()["projects"] if item["project"] == "btest"
        )["mainline_state"]["canonical_state"]
        output = {
            "action": "HANDOFF_CODEX", "destination": "CODEX_WORKER",
            "updated_state_delta": {
                "current_purpose": "Implement the bounded request",
                "scope_append": ["First user turn"],
                "user_decisions_append": ["Use API Mainline while orchestration is on"],
                "current_gate": "SAFE_CONTINUE",
                "latest_relevant_handoff": "handoff-sha256",
            },
        }
        value = self.store.apply_api_mainline_turn(
            "btest", output, response_id="resp-safe", model="gpt-5.6-sol",
            user_input_sha256="a" * 64, result_sha256="b" * 64,
        )
        canonical = value["mainline_state"]["canonical_state"]
        self.assertEqual(canonical["current_purpose"], "Implement the bounded request")
        self.assertEqual(canonical["routing"], {
            "latest_action": "HANDOFF_CODEX", "current_destination": "CODEX_WORKER",
        })
        self.assertEqual(canonical["authority"], before["authority"])
        self.assertEqual(canonical["frozen_decisions"], before["frozen_decisions"])
        self.assertTrue(value["mainline_state"]["api_mainline"]["conversation_initialized"])
        private = self.store._load()["projects"]["btest"]["mainline_state"]
        self.assertEqual(private["openai_conversation_state"]["previous_response_id"], "resp-safe")

    def test_bootstrap_candidate_summary_is_public_without_request_content(self) -> None:
        self.store.bootstrap_candidate_provider = lambda project: {
            "status": "READY",
            "model": "gpt-5.6-sol",
            "proposed_hard_cap_usd": "0.32",
            "canonical_state_sha256": "a" * 64,
        }
        project = next(
            item for item in self.store.list_projects()["projects"]
            if item["project"] == "btest"
        )
        summary = project["mainline_state"]["api_mainline"]["bootstrap_candidate"]
        self.assertEqual(summary["status"], "READY")
        self.assertNotIn("request", json.dumps(summary))


class TransportBoundaryTests(unittest.TestCase):
    def test_mock_adapter_is_local_only_and_supports_contract_methods(self) -> None:
        adapter = transport_adapter("MOCK")
        captured = adapter.capture_message("fixture")
        sent = adapter.send_message("fixture", "bounded test")

        self.assertTrue(adapter.capabilities.can_read)
        self.assertTrue(adapter.capabilities.can_write)
        self.assertFalse(captured["network"])
        self.assertFalse(sent["network"])

    def test_chatgpt_transport_is_not_reported_ready(self) -> None:
        capabilities = transport_capabilities("CHATGPT_SESSION")
        self.assertEqual(capabilities.health, "DEGRADED")
        self.assertEqual(capabilities.status, "REMOTE_READ_UNRELIABLE")
        self.assertFalse(capabilities.can_read)
        self.assertFalse(capabilities.can_write)
        with self.assertRaisesRegex(ControlPlaneError, "TRANSPORT_SEND_DISABLED"):
            transport_adapter("CHATGPT_SESSION").send_message("session", "message")


if __name__ == "__main__":
    unittest.main()
