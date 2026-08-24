from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from console.devos_orchestration.api_mainline import API_MAINLINE_NODE_ID, default_mainline_state
from console.devos_orchestration.api_mainline_run import (
    ApiMainlineRunError,
    ApiMainlineRunStore,
    HttpResult,
)
from console.devos_orchestration.api_mainline_start import ApiMainlineStartStore


class FakeControlPlane:
    def __init__(self) -> None:
        mainline = default_mainline_state()
        mainline["authority"] = API_MAINLINE_NODE_ID
        mainline["canonical_state"]["authority"] = API_MAINLINE_NODE_ID
        self.enabled = True
        self.mainline = mainline
        self.applied: list[dict[str, object]] = []

    def list_projects(self) -> dict[str, object]:
        return {"projects": [{
            "project": "btest", "orchestration_enabled": self.enabled,
            "mainline_state": copy.deepcopy(self.mainline),
        }]}

    def apply_api_mainline_turn(self, project: str, output: dict[str, object], **metadata: object) -> dict[str, object]:
        self.applied.append({"project": project, "output": copy.deepcopy(output), **metadata})
        return {}


class FakeTransport:
    def __init__(self, output: dict[str, object], *, status: int = 200) -> None:
        self.output = output
        self.status = status
        self.calls = 0

    def __call__(self, request: dict[str, object], api_key: str, timeout: float) -> HttpResult:
        self.calls += 1
        self.request = request
        self.timeout = timeout
        response = {
            "id": "resp_test_mainline",
            "model": "gpt-5.6-sol",
            "status": "completed",
            "output": [{"type": "message", "content": [{
                "type": "output_text", "text": json.dumps(self.output),
            }]}],
            "usage": {
                "input_tokens": 100,
                "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                "output_tokens": 50,
                "output_tokens_details": {"reasoning_tokens": 10},
                "total_tokens": 150,
            },
        }
        return HttpResult(self.status, {"x-request-id": "req_test"}, json.dumps(response).encode())


def output(action: str = "HANDOFF_CODEX") -> dict[str, object]:
    base: dict[str, object] = {
        "action": action,
        "assistant_message": "Prepared." if action == "CONTINUE_USER_DIALOGUE" else None,
        "gate": "SAFE_CONTINUE" if action == "HANDOFF_CODEX" else None,
        "destination": "CODEX_WORKER" if action == "HANDOFF_CODEX" else "USER",
        "handoff_message": "Read-only bounded task." if action == "HANDOFF_CODEX" else None,
        "decision_packet": None,
        "blocker": None,
        "updated_state_delta": {
            "current_purpose": "Bounded purpose",
            "scope_append": ["Approved scope"],
            "user_decisions_append": [],
            "current_gate": "SAFE_CONTINUE" if action == "HANDOFF_CODEX" else None,
            "latest_relevant_handoff": None,
        },
    }
    if action == "USER_REQUIRED":
        base.update({"gate": "USER_REQUIRED", "decision_packet": {"question": "Choose?", "options": ["A", "B"]}})
        base["updated_state_delta"]["current_gate"] = "USER_REQUIRED"  # type: ignore[index]
    elif action == "BLOCKED":
        base.update({"destination": None, "gate": "BLOCKED", "blocker": {"reason": "Missing input", "required_action": "Provide it", "stop_reason": None}})
        base["updated_state_delta"]["current_gate"] = "BLOCKED"  # type: ignore[index]
    elif action == "STOP":
        base.update({"destination": None, "gate": "STOP", "blocker": {"reason": None, "required_action": None, "stop_reason": "Unsafe"}})
        base["updated_state_delta"]["current_gate"] = "STOP"  # type: ignore[index]
    return base


class ApiMainlineRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.env_file = self.root / "developer-os.env"
        self.env_file.write_text("OPENAI_ORCHESTRATION_API_KEY=test-only\n", encoding="utf-8")
        self.control = FakeControlPlane()
        self.starts = ApiMainlineStartStore(self.root / "starts", self.control)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def make_store(self, response: dict[str, object]) -> tuple[ApiMainlineRunStore, FakeTransport, dict[str, object]]:
        transport = FakeTransport(response)
        store = ApiMainlineRunStore(
            self.root / "runs", self.starts, self.control,
            env_file=self.env_file, transport=transport,
        )
        candidate = self.starts.prepare("btest", "Exact user request")
        return store, transport, candidate

    def test_exactly_once_capture_parse_validate_and_prepared_handoff(self) -> None:
        store, transport, candidate = self.make_store(output())
        result = store.approve_and_execute(
            "btest", candidate["candidate_file_sha256"], candidate["approval_manifest_sha256"],
        )
        self.assertEqual(transport.calls, 1)
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["parsed_action"], "HANDOFF_CODEX")
        self.assertEqual(result["handoff"]["status"], "PREPARED")
        self.assertEqual(result["dispatch_count"], 0)
        self.assertTrue((store.directory / candidate["approval_manifest_sha256"] / "provider-response.raw.json").is_file())
        self.assertEqual(len(self.control.applied), 1)
        restored = store.status("btest")
        self.assertEqual(restored["parsed_action"], "HANDOFF_CODEX")
        self.assertEqual(restored["destination"], "CODEX_WORKER")
        self.assertEqual(restored["response_id"], result["response_id"])
        self.assertEqual(
            restored["usage_based_estimated_cost_usd"],
            result["usage_based_estimated_cost_usd"],
        )
        prepared = store.prepared_handoff("btest")
        self.assertEqual(prepared["destination_node_id"], "BTEST_CODEX_WORKER")
        self.assertEqual(prepared["exact_message"], "Read-only bounded task.")
        self.assertEqual(
            prepared["exact_message_sha256"],
            result["handoff"]["exact_message_sha256"],
        )
        with self.assertRaisesRegex(ApiMainlineRunError, "NOT_READY|CONSUMED"):
            store.approve_and_execute(
                "btest", candidate["candidate_file_sha256"], candidate["approval_manifest_sha256"],
            )
        self.assertEqual(transport.calls, 1)

    def test_all_structured_actions_validate_without_dispatch(self) -> None:
        for action in ("USER_REQUIRED", "CONTINUE_USER_DIALOGUE", "BLOCKED", "STOP"):
            with self.subTest(action=action):
                self.tearDown()
                self.setUp()
                store, transport, candidate = self.make_store(output(action))
                result = store.approve_and_execute(
                    "btest", candidate["candidate_file_sha256"], candidate["approval_manifest_sha256"],
                )
                self.assertEqual(result["parsed_action"], action)
                self.assertIsNone(result["handoff"])
                self.assertEqual(result["dispatch_count"], 0)
                self.assertEqual(transport.calls, 1)

    def test_invalid_output_is_consumed_without_retry_or_state_apply(self) -> None:
        invalid = output()
        invalid["destination"] = "USER"
        store, transport, candidate = self.make_store(invalid)
        with self.assertRaises(ApiMainlineRunError):
            store.approve_and_execute(
                "btest", candidate["candidate_file_sha256"], candidate["approval_manifest_sha256"],
            )
        self.assertEqual(transport.calls, 1)
        self.assertEqual(self.control.applied, [])
        self.assertEqual(store.status("btest")["status"], "FAILED")
        with self.assertRaises(ApiMainlineRunError):
            store.approve_and_execute(
                "btest", candidate["candidate_file_sha256"], candidate["approval_manifest_sha256"],
            )
        self.assertEqual(transport.calls, 1)

    def test_cancel_is_terminal_and_never_calls_transport(self) -> None:
        store, transport, candidate = self.make_store(output())
        result = store.cancel(
            "btest", candidate["candidate_file_sha256"], candidate["approval_manifest_sha256"],
        )
        self.assertEqual(result["status"], "CANCELLED")
        self.assertEqual(transport.calls, 0)
        with self.assertRaises(ApiMainlineRunError):
            store.approve_and_execute(
                "btest", candidate["candidate_file_sha256"], candidate["approval_manifest_sha256"],
            )


if __name__ == "__main__":
    unittest.main()
