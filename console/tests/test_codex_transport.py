from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch
from subprocess import CompletedProcess
from pathlib import Path

from console.devos_console.audit import AuditLog
from console.devos_orchestration.codex_transport import (
    APPROVAL_METHODS,
    CodexAppServerAdapter,
    CodexApprovalRequired,
    CodexProtocolProfile,
    CodexProtocolRequestError,
    CodexRuntimeLauncher,
    CodexRuntimeUnavailable,
    CodexThreadBinding,
    CodexWorkspaceBinding,
    CodexTransportError,
    CodexTransportTimeout,
    WslCodexRuntimeLauncher,
    locked_capability_status,
)
from console.devos_orchestration.control_plane import ControlPlaneError, OrchestrationControlStore
from console.devos_orchestration.dispatch_preview import DispatchPreviewStore
from console.devos_orchestration.semi_auto_dispatch import SemiAutoCodexDispatcher
from console.devos_orchestration.return_handoff import ReturnHandoffStore
from console.devos_orchestration.exact_delivery import ExactDeliveryStore
from console.devos_orchestration.api_mainline_return import ApiMainlineReturnStore
from console.devos_orchestration.task_alignment import extract_requirement_inventory
from console.tests.test_orchestration import decision_packet, valid_review_v2_4
from console.devos_orchestration.api_mainline_run import HttpResult
from console.devos_orchestration.workspace_guard import WorkspaceBindingSeal, WorkspaceGuardError


class FakeChannel:
    def __init__(self, messages: list[object]) -> None:
        self.messages = list(messages)
        self.sent: list[dict[str, object]] = []
        self.closed = False

    def send(self, message: dict[str, object]) -> None:
        self.sent.append(message)

    def receive(self, timeout_seconds: float) -> dict[str, object]:
        if not self.messages:
            raise CodexTransportTimeout("CODEX_APP_SERVER_TIMEOUT")
        value = self.messages.pop(0)
        if isinstance(value, Exception):
            raise value
        return value  # type: ignore[return-value]

    def close(self) -> None:
        self.closed = True


def profile() -> CodexProtocolProfile:
    return CodexProtocolProfile(
        cli_version="codex-cli 0.147.0-alpha.6.6",
        schema_bundle_sha256="a" * 64,
        client_methods=frozenset({
            "initialize", "thread/read", "thread/start", "thread/resume",
            "turn/start", "turn/interrupt",
        }),
        server_notifications=frozenset({"turn/started", "turn/completed"}),
        server_requests=frozenset(APPROVAL_METHODS),
        discovered_at="2026-08-14T00:00:00Z",
    )


class CodexAdapterTests(unittest.TestCase):
    def test_wsl_launcher_uses_linux_native_runtime_and_stdio(self) -> None:
        launcher = WslCodexRuntimeLauncher("Ubuntu", "/home/devops/.local/bin/codex")
        self.assertEqual(launcher.app_server_command(), [
            "wsl.exe", "-d", "Ubuntu", "--", "/home/devops/.local/bin/codex",
            "app-server", "--listen", "stdio://",
        ])
        self.assertNotIn("WindowsApps", " ".join(launcher.app_server_command()))

    def test_wsl_login_status_accepts_cli_stderr_status(self) -> None:
        launcher = WslCodexRuntimeLauncher("Ubuntu", "/home/devops/.local/bin/codex")
        with patch.object(
            launcher.discovery,
            "_run",
            return_value=CompletedProcess([], 0, stdout="", stderr="Logged in using ChatGPT\n"),
        ):
            self.assertTrue(launcher.discovery.login_ready())

    def test_wsl_absolute_thread_binding_is_supported(self) -> None:
        binding = CodexThreadBinding.parse(json.dumps({
            "thread_id": "thread-wsl-123",
            "workspace": "/home/devops/.developer-os/orchestration-smoke/smoke-1",
        }))
        self.assertEqual(binding.workspace, "/home/devops/.developer-os/orchestration-smoke/smoke-1")

    def test_runtime_launcher_resolves_path_entrypoint_without_copy(self) -> None:
        with patch("console.devos_orchestration.codex_transport.shutil.which", return_value="C:/Program Files/Codex/codex.exe"):
            source, path = CodexRuntimeLauncher("codex").resolve()
        self.assertEqual(source, "PATH")
        self.assertEqual(Path(path), Path("C:/Program Files/Codex/codex.exe"))

    def test_runtime_launcher_fails_closed_when_cli_is_missing(self) -> None:
        with patch("console.devos_orchestration.codex_transport.shutil.which", return_value=None):
            with self.assertRaises(CodexRuntimeUnavailable) as caught:
                CodexRuntimeLauncher("codex").resolve()
        self.assertEqual(caught.exception.stage, "resolution")

    def test_initialize_handshake_uses_discovered_protocol_shape(self) -> None:
        channel = FakeChannel([{
            "id": 1,
            "result": {"userAgent": "codex", "codexHome": "C:/Codex", "platformFamily": "windows", "platformOs": "windows"},
        }])
        adapter = CodexAppServerAdapter(channel)

        result = adapter.initialize()

        self.assertEqual(result["userAgent"], "codex")
        self.assertEqual(channel.sent[0]["method"], "initialize")
        self.assertEqual(
            channel.sent[0]["params"]["capabilities"],  # type: ignore[index]
            {"experimentalApi": True},
        )
        self.assertEqual(channel.sent[1], {"method": "initialized"})
        self.assertTrue(adapter.initialized)

    def test_read_and_resume_thread_use_binding_without_prompt_injection(self) -> None:
        channel = FakeChannel([{"id": 1, "result": {"thread": {"id": "thread-123"}}}])
        adapter = CodexAppServerAdapter(channel)
        binding = CodexThreadBinding.parse(json.dumps({"thread_id": "thread-123", "workspace": "X:/Projects/bTest"}))

        adapter.resume_thread(binding)

        params = channel.sent[0]["params"]
        self.assertEqual(params["threadId"], "thread-123")  # type: ignore[index]
        self.assertEqual(params["cwd"], "X:/Projects/bTest")  # type: ignore[index]
        self.assertNotIn("message", params)  # type: ignore[operator]

    def test_thread_and_turn_start_are_locked(self) -> None:
        adapter = CodexAppServerAdapter(FakeChannel([]))
        binding = CodexThreadBinding("thread-123", "X:/Projects/bTest")
        with self.assertRaisesRegex(CodexTransportError, "CODEX_THREAD_START_LOCKED"):
            adapter.start_thread(binding.workspace)
        with self.assertRaisesRegex(CodexTransportError, "CODEX_TURN_START_LOCKED"):
            adapter.start_turn(binding, "do work")

    def test_mock_thread_and_turn_lifecycle_use_discovered_methods(self) -> None:
        channel = FakeChannel([
            {"id": 1, "result": {"thread": {"id": "thread-new"}}},
            {"id": 2, "result": {"turn": {"id": "turn-new", "status": "inProgress"}}},
            {"id": 3, "result": {}},
        ])
        adapter = CodexAppServerAdapter(channel, allow_turn_start=True)
        binding = CodexThreadBinding("thread-new", "X:/Projects/bTest")

        adapter.start_thread(binding.workspace)
        adapter.start_turn(binding, "bounded task")
        adapter.interrupt_turn(binding.thread_id, "turn-new")

        self.assertEqual(
            [message["method"] for message in channel.sent],
            ["thread/start", "turn/start", "turn/interrupt"],
        )
        turn_input = channel.sent[1]["params"]["input"][0]  # type: ignore[index]
        self.assertEqual(turn_input, {"type": "text", "text": "bounded task", "text_elements": []})

    def test_thread_start_accepts_read_only_dispatch_instructions(self) -> None:
        channel = FakeChannel([{"id": 1, "result": {"thread": {"id": "thread-new"}}}])
        adapter = CodexAppServerAdapter(channel, allow_turn_start=True)

        adapter.start_thread(
            "/mnt/x/Projects/bTest",
            developer_instructions="Read only and stop after one turn.",
        )

        params = channel.sent[0]["params"]
        self.assertEqual(params["sandbox"], "read-only")  # type: ignore[index]
        self.assertEqual(params["developerInstructions"], "Read only and stop after one turn.")  # type: ignore[index]

    def test_turn_started_before_start_response_is_preserved(self) -> None:
        channel = FakeChannel([
            {"method": "turn/started", "params": {"threadId": "thread-new", "turn": {"id": "turn-new"}}},
            {"id": 1, "result": {"turn": {"id": "turn-new", "status": "inProgress"}}},
            {"method": "turn/completed", "params": {"threadId": "thread-new", "turn": {"id": "turn-new", "status": "completed", "items": []}}},
        ])
        adapter = CodexAppServerAdapter(channel, allow_turn_start=True)
        binding = CodexThreadBinding("thread-new", "X:/Projects/bTest")
        started = adapter.start_turn(binding, "bounded task")
        result = adapter.receive_turn(binding.thread_id, started["turn"]["id"])
        self.assertEqual([event["method"] for event in result["events"]], ["turn/started", "turn/completed"])

    def test_item_completion_is_added_to_terminal_turn_capture(self) -> None:
        channel = FakeChannel([
            {"method": "item/completed", "params": {"item": {"type": "agentMessage", "text": "received"}}},
            {"method": "turn/completed", "params": {"threadId": "thread-new", "turn": {"id": "turn-new", "status": "completed", "items": []}}},
        ])
        result = CodexAppServerAdapter(channel).receive_turn("thread-new", "turn-new")
        self.assertEqual(result["turn"]["items"][0]["text"], "received")

    def test_streaming_preserves_order_and_terminal_states(self) -> None:
        for status in ("completed", "failed", "interrupted"):
            with self.subTest(status=status):
                messages = [
                    {"method": "turn/started", "params": {"threadId": "thread-123", "turn": {"id": "turn-1"}}},
                    {"method": "item/started", "params": {"threadId": "thread-123"}},
                    {"method": "turn/completed", "params": {"threadId": "thread-123", "turn": {"id": "turn-1", "status": status}}},
                ]
                result = CodexAppServerAdapter(FakeChannel(messages)).receive_turn("thread-123", "turn-1")
                self.assertEqual(result["status"], status)
                self.assertEqual([item["method"] for item in result["events"]], ["turn/started", "item/started", "turn/completed"])

    def test_approval_request_is_detected_and_never_answered(self) -> None:
        channel = FakeChannel([{"method": "item/commandExecution/requestApproval", "id": 71, "params": {}}])
        with self.assertRaises(CodexApprovalRequired) as caught:
            CodexAppServerAdapter(channel).receive_turn("thread-123", "turn-1")
        self.assertEqual(caught.exception.request_id, 71)
        self.assertEqual(channel.sent, [])

    def test_timeout_protocol_error_and_turn_mismatch_fail_closed(self) -> None:
        cases = [
            ([], CodexTransportTimeout),
            ([CodexTransportError("CODEX_APP_SERVER_EXITED")], CodexTransportError),
            ([{"method": "turn/completed", "params": {"threadId": "other", "turn": {"id": "turn-1", "status": "completed"}}}], CodexTransportError),
        ]
        for messages, error in cases:
            with self.subTest(messages=messages), self.assertRaises(error):
                CodexAppServerAdapter(FakeChannel(messages)).receive_turn("thread-123", "turn-1")

    def test_protocol_request_error_preserves_only_bounded_diagnostics(self) -> None:
        channel = FakeChannel([{"id": 1, "error": {"code": -32602, "message": "invalid params"}}])
        with self.assertRaises(CodexProtocolRequestError) as caught:
            CodexAppServerAdapter(channel).initialize()
        self.assertEqual(caught.exception.method, "initialize")
        self.assertEqual(caught.exception.code, -32602)
        self.assertEqual(caught.exception.provider_message, "invalid params")

    def test_protocol_error_redacts_credentials(self) -> None:
        error = CodexProtocolRequestError(
            "thread/start", -32602,
            "Authorization: Bearer secret-token OPENAI_API_KEY=secret-value sk-secret12345678",
        )
        self.assertNotIn("secret-token", error.provider_message)
        self.assertNotIn("secret-value", error.provider_message)
        self.assertNotIn("sk-secret", error.provider_message)
        self.assertEqual(error.method, "thread/start")

    def test_capabilities_are_discovered_but_execution_locked(self) -> None:
        binding = CodexThreadBinding("thread-123", "X:/Projects/bTest")
        status = locked_capability_status(profile(), binding)
        self.assertEqual(status["connection_status"], "DISCOVERED_LOCKED")
        self.assertTrue(all(value == "SUPPORTED_LOCKED" for value in status["features"].values()))
        self.assertTrue(status["execution_locked"])
        self.assertEqual(status["approval_policy"], "NEVER_AUTO_APPROVE")

    def test_workspace_only_binding_exposes_guard_without_thread_id(self) -> None:
        binding = CodexWorkspaceBinding.parse(json.dumps({
            "binding_type": "WORKSPACE_ONLY", "binding_version": "1",
            "project": "btest", "runtime": "WSL_CODEX_APP_SERVER",
            "distro": "Ubuntu", "windows_workspace": "X:/Projects/bTest",
            "wsl_workspace": "/mnt/x/Projects/bTest",
            "workspace_identity_sha256": "a" * 64, "git_branch": "main",
            "git_head": "b" * 40, "git_status_sha256": "c" * 64,
            "git_status_entry_count": 3,
        }))
        status = locked_capability_status(profile(), binding)
        self.assertEqual(status["binding_status"], "BOUND")
        self.assertFalse(status["workspace_binding"]["thread_bound"])
        self.assertEqual(status["workspace_binding"]["workspace_guard"], "ARMED")
        self.assertEqual(
            status["workspace_binding"]["developeros_turn_policy"],
            "SINGLE_ACTIVE_TURN",
        )
        self.assertEqual(status["dispatch_status"], "LOCKED_USER_APPROVAL_REQUIRED")
        self.assertNotIn("thread_id", json.dumps(status))


class DispatchPreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.control = OrchestrationControlStore(
            root / "control.json", ["btest"], AuditLog(root / "audit.jsonl"),
        )
        self.control.update_node("btest", "BTEST_MAINLINE", {
            "transport_ref": "mainline", "allowed_destinations": ["worker"],
        })
        self.control.add_node("btest", {
            "node_id": "worker", "display_name": "Codex worker", "role": "CODEX_WORKER",
            "transport_kind": "CODEX_THREAD",
            "transport_ref": json.dumps({"thread_id": "thread-123", "workspace": "X:/Projects/bTest"}),
            "enabled": True, "allowed_sources": ["BTEST_MAINLINE"], "allowed_destinations": [],
        })
        self.control.add_route("btest", {
            "route_id": "mainline-worker", "source_node_id": "BTEST_MAINLINE",
            "destination_node_id": "worker", "enabled": True, "handoff_type": "TASK",
        })
        self.previews = DispatchPreviewStore(root / "previews", self.control)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_route_to_preview_is_prepared_without_send_or_thread_id_in_message(self) -> None:
        preview = self.previews.prepare("btest", {
            "handoff_id": "handoff-1", "route_id": "mainline-worker", "message": "bounded task",
        })
        self.assertEqual(preview["state"], "PREPARED")
        self.assertEqual(preview["actual_send_count"], 0)
        self.assertNotIn("thread-123", json.dumps(preview["rendered_message"]))
        self.assertEqual(self.previews.list_for_project("btest")[0]["state"], "PREPARED")

    def test_duplicate_handoff_is_blocked(self) -> None:
        payload = {"handoff_id": "handoff-1", "route_id": "mainline-worker", "message": "bounded task"}
        self.previews.prepare("btest", payload)
        with self.assertRaisesRegex(ControlPlaneError, "DUPLICATE_HANDOFF_BLOCKED"):
            self.previews.prepare("btest", payload)

    def test_exactly_once_state_machine_blocks_second_send(self) -> None:
        self.previews.prepare("btest", {
            "handoff_id": "handoff-1", "route_id": "mainline-worker", "message": "bounded task",
        })
        sent = self.previews.transition("handoff-1", "SENT")
        self.assertEqual(sent["actual_send_count"], 1)
        self.assertEqual(self.previews.transition("handoff-1", "COMPLETED")["state"], "COMPLETED")
        with self.assertRaisesRegex(ControlPlaneError, "INVALID_DISPATCH_TRANSITION"):
            self.previews.transition("handoff-1", "SENT")

    def test_unbound_preview_can_bind_then_capture_completion(self) -> None:
        self.control.update_node("btest", "worker", {"transport_ref": ""})
        prepared = self.previews.prepare("btest", {
            "handoff_id": "handoff-smoke", "route_id": "mainline-worker", "message": "smoke",
        })
        self.assertEqual(prepared["destination"]["binding_status"], "UNBOUND")
        binding = CodexThreadBinding("thread-smoke", "X:/scratch")
        self.assertEqual(self.previews.bind("handoff-smoke", binding)["binding_status"], "BOUND")
        self.previews.transition("handoff-smoke", "SENT")
        completed = self.previews.record_completion("handoff-smoke", {
            "status": "completed",
            "turn": {"items": [{"type": "agentMessage", "text": "received"}]},
            "events": [{"method": "turn/started"}, {"method": "turn/completed"}],
        })
        self.assertEqual(completed["state"], "COMPLETED")
        self.assertEqual(completed["response_text"], "received")
        self.assertEqual(completed["actual_send_count"], 1)

    def test_smoke_preview_seals_payload_before_binding_and_blocks_reuse(self) -> None:
        prepared = self.previews.prepare_smoke(
            handoff_id="smoke-once",
            project="developer-os",
            message="transport smoke",
        )
        self.assertEqual(prepared["state"], "PREPARED")
        self.assertEqual(prepared["destination"]["binding_status"], "UNBOUND")
        self.assertEqual(len(prepared["payload_sha256"]), 64)
        with self.assertRaisesRegex(ControlPlaneError, "DUPLICATE_HANDOFF_BLOCKED"):
            self.previews.prepare_smoke(
                handoff_id="smoke-once",
                project="developer-os",
                message="transport smoke",
            )

    def test_failure_capture_is_terminal_and_visible(self) -> None:
        self.previews.prepare_smoke(
            handoff_id="smoke-failed", project="developer-os", message="transport smoke",
        )
        failed = self.previews.record_failure(
            "smoke-failed", "CODEX_PROTOCOL_REQUEST_FAILED",
            {"request_method": "thread/start", "json_rpc_error_code": -32602},
        )
        self.assertEqual(failed["state"], "FAILED")
        self.assertEqual(failed["error_code"], "CODEX_PROTOCOL_REQUEST_FAILED")
        failure = json.loads((self.previews.directory / "smoke-failed-failure.json").read_text(encoding="utf-8"))
        self.assertEqual(failure["safe_error_metadata"]["request_method"], "thread/start")
        with self.assertRaisesRegex(ControlPlaneError, "INVALID_DISPATCH_TRANSITION"):
            self.previews.transition("smoke-failed", "SENT")


class WorkspaceDispatchPreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.seal = WorkspaceBindingSeal(
            project="btest",
            windows_workspace="X:/Projects/bTest",
            wsl_workspace="/mnt/x/Projects/bTest",
            runtime="WSL_CODEX_APP_SERVER",
            distro="Ubuntu",
            workspace_identity_sha256="a" * 64,
            git_branch="main",
            git_head="b" * 40,
            git_status_sha256="c" * 64,
            git_status_entry_count=251,
        )
        self.control = OrchestrationControlStore(
            root / "control.json",
            ["btest"],
            AuditLog(root / "audit.jsonl"),
            capability_provider=lambda _node: {
                "connection_status": "DISCOVERED_LOCKED",
                "protocol_version": "codex-cli 0.147.0",
                "protocol_schema_sha256": "d" * 64,
            },
        )
        self.control.update_node("btest", "BTEST_MAINLINE", {
            "transport_ref": "mainline", "allowed_destinations": ["BTEST_CODEX_WORKER"],
        })
        self.control.add_node("btest", {
            "node_id": "BTEST_CODEX_WORKER", "display_name": "bTest Codex worker",
            "role": "CODEX_WORKER", "transport_kind": "CODEX_THREAD",
            "transport_ref": self.seal.as_transport_ref(), "enabled": True,
            "allowed_sources": ["BTEST_MAINLINE", "BTEST_MAINLINE_API"],
            "allowed_destinations": ["BTEST_MAINLINE", "BTEST_MAINLINE_API"],
        })
        self.control.add_route("btest", {
            "route_id": "mainline-worker", "source_node_id": "BTEST_MAINLINE",
            "destination_node_id": "BTEST_CODEX_WORKER", "enabled": True,
            "handoff_type": "TASK",
        })
        self.control.add_route("btest", {
            "route_id": "worker-mainline", "source_node_id": "BTEST_CODEX_WORKER",
            "destination_node_id": "BTEST_MAINLINE", "enabled": True,
            "handoff_type": "REPORT",
        })
        self.root = root

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _previews(self, verifier=None) -> DispatchPreviewStore:
        return DispatchPreviewStore(
            self.root / "previews",
            self.control,
            workspace_verifier=verifier or (lambda seal: seal),
        )

    def test_workspace_only_preview_seals_workspace_runtime_and_task(self) -> None:
        preview = self._previews().prepare("btest", {
            "handoff_id": "workspace-preview-1",
            "route_id": "mainline-worker",
            "message": "bounded task",
        })
        envelope = preview["dispatch_envelope"]
        self.assertEqual(preview["state"], "PREPARED")
        self.assertEqual(preview["actual_send_count"], 0)
        self.assertEqual(envelope["task_content_sha256"], preview["task_content_sha256"])
        self.assertEqual(envelope["payload_sha256"], preview["payload_sha256"])
        self.assertEqual(envelope["route"]["route_id"], "mainline-worker")
        self.assertEqual(envelope["source_node"]["node_id"], "BTEST_MAINLINE")
        self.assertEqual(envelope["destination_node"]["node_id"], "BTEST_CODEX_WORKER")
        self.assertEqual(envelope["workspace"]["windows_workspace"], "X:/Projects/bTest")
        self.assertEqual(envelope["workspace"]["wsl_workspace"], "/mnt/x/Projects/bTest")
        self.assertEqual(envelope["workspace"]["branch"], "main")
        self.assertEqual(envelope["workspace"]["head"], "b" * 40)
        self.assertEqual(envelope["workspace"]["workspace_fingerprint_sha256"], "c" * 64)
        self.assertEqual(envelope["runtime_protocol"]["protocol_schema_sha256"], "d" * 64)
        self.assertEqual(len(envelope["runtime_protocol_sha256"]), 64)
        self.assertEqual(len(preview["envelope_sha256"]), 64)

    def test_task_content_hash_changes_for_one_character(self) -> None:
        previews = self._previews()
        first = previews.prepare("btest", {
            "handoff_id": "workspace-preview-a", "route_id": "mainline-worker",
            "message": "bounded task",
        })
        second = previews.prepare("btest", {
            "handoff_id": "workspace-preview-b", "route_id": "mainline-worker",
            "message": "bounded tasks",
        })
        self.assertNotEqual(first["task_content_sha256"], second["task_content_sha256"])
        self.assertNotEqual(first["payload_sha256"], second["payload_sha256"])
        self.assertNotEqual(first["envelope_sha256"], second["envelope_sha256"])

    def test_prepared_api_mainline_handoff_becomes_one_workspace_preview(self) -> None:
        self.control.set_mode("btest", "SHADOW_REVIEW")
        previews = self._previews()
        source = {
            "approval_manifest_sha256": "1" * 64,
            "result_artifact_sha256": "2" * 64,
            "result_sha256": "3" * 64,
            "originating_user_input_sha256": "4" * 64,
            "exact_message_sha256": hashlib.sha256(b"bounded task").hexdigest(),
            "exact_message": "bounded task",
            "destination_node_id": "BTEST_CODEX_WORKER",
        }
        prepared = previews.prepare_mainline_handoff("btest", source)
        self.assertEqual(prepared["state"], "PREPARED")
        self.assertEqual(prepared["source_handoff"]["result_sha256"], "3" * 64)
        self.assertEqual(
            prepared["dispatch_envelope"]["source_handoff"]["exact_message_sha256"],
            source["exact_message_sha256"],
        )
        public = previews.list_for_project("btest")[0]
        self.assertEqual(public["source_node_id"], "BTEST_MAINLINE_API")
        self.assertEqual(public["destination_node_id"], "BTEST_CODEX_WORKER")
        self.assertEqual(public["route_id"], "BTEST_MAINLINE_API_TO_CODEX")
        self.assertEqual(public["approval_state"], "USER_APPROVAL_REQUIRED")
        self.assertEqual(public["duplicate_send_status"], "UNUSED")
        self.assertEqual(public["task_message"], "bounded task")
        with self.assertRaisesRegex(ControlPlaneError, "DUPLICATE_HANDOFF_BLOCKED"):
            previews.prepare_mainline_handoff("btest", source)

    def test_workspace_fingerprint_change_fails_before_artifact_creation(self) -> None:
        def changed(_seal: WorkspaceBindingSeal) -> WorkspaceBindingSeal:
            raise WorkspaceGuardError("WORKSPACE_CHANGED_EXTERNALLY")

        previews = self._previews(changed)
        with self.assertRaisesRegex(ControlPlaneError, "WORKSPACE_CHANGED_EXTERNALLY"):
            previews.prepare("btest", {
                "handoff_id": "workspace-preview-stale",
                "route_id": "mainline-worker",
                "message": "bounded task",
            })
        self.assertFalse((previews.directory / "workspace-preview-stale.json").exists())
        self.assertEqual(previews.list_for_project("btest"), [])

    def test_prepared_approval_creates_bound_record_and_stops_dispatchable(self) -> None:
        previews = self._previews()
        prepared = previews.prepare("btest", {
            "handoff_id": "workspace-approve", "route_id": "mainline-worker",
            "message": "bounded task",
        })
        approved = previews.decide(
            "btest", "workspace-approve", "approve", prepared["envelope_sha256"],
        )
        self.assertEqual(approved["state"], "DISPATCHABLE")
        self.assertEqual(approved["approval_state"], "APPROVED")
        self.assertEqual(
            [item["state"] for item in approved["state_history"]],
            ["PREPARED", "APPROVED", "DISPATCHABLE"],
        )
        self.assertTrue(approved["actual_send_locked"])
        self.assertEqual(approved["actual_send_count"], 0)
        record = json.loads(
            (previews.directory / "workspace-approve-approval.json").read_text(encoding="utf-8"),
        )
        self.assertEqual(record["binding"]["envelope_sha256"], prepared["envelope_sha256"])
        self.assertEqual(record["binding"]["task_content_sha256"], prepared["task_content_sha256"])
        self.assertEqual(record["binding"]["route"]["route_id"], "mainline-worker")
        self.assertEqual(record["binding"]["destination_node"]["node_id"], "BTEST_CODEX_WORKER")
        self.assertEqual(record["binding"]["workspace_fingerprint_sha256"], "c" * 64)
        self.assertEqual(record["binding"]["branch"], "main")
        self.assertEqual(record["binding"]["head"], "b" * 40)
        self.assertEqual(len(record["binding"]["runtime_protocol_sha256"]), 64)
        self.assertEqual(
            previews.validate_dispatchable("btest", "workspace-approve")["actual_send_count"],
            0,
        )

    def test_dispatch_start_writes_durable_attempt_and_consumes_approval(self) -> None:
        previews = self._previews()
        prepared = previews.prepare("btest", {
            "handoff_id": "workspace-dispatch", "route_id": "mainline-worker",
            "message": "read-only audit",
        })
        approved = previews.decide(
            "btest", "workspace-dispatch", "approve", prepared["envelope_sha256"],
        )

        started = previews.start_dispatch("btest", "workspace-dispatch")

        self.assertEqual(started["state"], "SENT")
        self.assertEqual(started["dispatch_status"], "SENDING")
        self.assertEqual(started["actual_send_count"], 1)
        attempt_path = previews.directory / "workspace-dispatch-attempt.json"
        attempt = json.loads(attempt_path.read_text(encoding="utf-8"))
        self.assertEqual(attempt["status"], "ATTEMPT_STARTED")
        self.assertEqual(attempt["attempt_count"], 1)
        self.assertEqual(attempt["envelope_sha256"], prepared["envelope_sha256"])
        self.assertEqual(
            attempt["approval_record_sha256"], approved["approval_record_sha256"],
        )
        with self.assertRaisesRegex(ControlPlaneError, "HANDOFF_NOT_DISPATCHABLE"):
            previews.start_dispatch("btest", "workspace-dispatch")

    def test_dispatch_start_rechecks_workspace_before_attempt_marker(self) -> None:
        observed = {"seal": self.seal}
        previews = self._previews(lambda _seal: observed["seal"])
        prepared = previews.prepare("btest", {
            "handoff_id": "workspace-dispatch-stale", "route_id": "mainline-worker",
            "message": "read-only audit",
        })
        previews.decide(
            "btest", "workspace-dispatch-stale", "approve", prepared["envelope_sha256"],
        )
        observed["seal"] = replace(self.seal, git_status_sha256="f" * 64)

        with self.assertRaisesRegex(ControlPlaneError, "WORKSPACE_CHANGED_EXTERNALLY"):
            previews.start_dispatch("btest", "workspace-dispatch-stale")
        self.assertFalse(
            (previews.directory / "workspace-dispatch-stale-attempt.json").exists(),
        )

    def test_rejection_is_terminal_and_requires_a_new_envelope(self) -> None:
        previews = self._previews()
        prepared = previews.prepare("btest", {
            "handoff_id": "workspace-reject", "route_id": "mainline-worker",
            "message": "bounded task",
        })
        rejected = previews.decide(
            "btest", "workspace-reject", "reject", prepared["envelope_sha256"],
        )
        self.assertEqual(rejected["state"], "REJECTED")
        self.assertEqual(rejected["actual_send_count"], 0)
        with self.assertRaisesRegex(ControlPlaneError, "DUPLICATE_OR_TERMINAL"):
            previews.decide(
                "btest", "workspace-reject", "approve", prepared["envelope_sha256"],
            )

    def test_duplicate_approval_is_blocked(self) -> None:
        previews = self._previews()
        prepared = previews.prepare("btest", {
            "handoff_id": "workspace-duplicate", "route_id": "mainline-worker",
            "message": "bounded task",
        })
        previews.decide(
            "btest", "workspace-duplicate", "approve", prepared["envelope_sha256"],
        )
        with self.assertRaisesRegex(ControlPlaneError, "DUPLICATE_OR_TERMINAL"):
            previews.decide(
                "btest", "workspace-duplicate", "approve", prepared["envelope_sha256"],
            )

    def test_existing_approval_is_invalid_after_route_change(self) -> None:
        previews = self._previews()
        prepared = previews.prepare("btest", {
            "handoff_id": "approved-then-route-changed", "route_id": "mainline-worker",
            "message": "bounded task",
        })
        previews.decide(
            "btest", "approved-then-route-changed", "approve", prepared["envelope_sha256"],
        )
        self.control.update_route("btest", "mainline-worker", {"handoff_type": "REPORT"})
        with self.assertRaisesRegex(ControlPlaneError, "DISPATCH_APPROVAL_STALE"):
            previews.validate_dispatchable("btest", "approved-then-route-changed")

    def test_existing_approval_is_invalid_after_workspace_change(self) -> None:
        observed = {"seal": self.seal}
        previews = self._previews(lambda _seal: observed["seal"])
        prepared = previews.prepare("btest", {
            "handoff_id": "approved-then-workspace-changed", "route_id": "mainline-worker",
            "message": "bounded task",
        })
        previews.decide(
            "btest", "approved-then-workspace-changed", "approve", prepared["envelope_sha256"],
        )
        observed["seal"] = replace(self.seal, git_status_sha256="f" * 64)
        with self.assertRaisesRegex(ControlPlaneError, "WORKSPACE_CHANGED_EXTERNALLY"):
            previews.validate_dispatchable("btest", "approved-then-workspace-changed")

    def test_changed_envelope_invalidates_approval(self) -> None:
        previews = self._previews()
        prepared = previews.prepare("btest", {
            "handoff_id": "workspace-tampered", "route_id": "mainline-worker",
            "message": "bounded task",
        })
        artifact_path = previews.directory / "workspace-tampered.json"
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        artifact["dispatch_envelope"]["route"]["handoff_type"] = "REPORT"
        artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
        with self.assertRaisesRegex(ControlPlaneError, "DISPATCH_ENVELOPE_CHANGED"):
            previews.decide(
                "btest", "workspace-tampered", "approve", prepared["envelope_sha256"],
            )
        self.assertFalse((previews.directory / "workspace-tampered-approval.json").exists())

    def test_workspace_branch_or_head_change_blocks_approval(self) -> None:
        observed = {"seal": self.seal}
        previews = self._previews(lambda _seal: observed["seal"])
        prepared = previews.prepare("btest", {
            "handoff_id": "workspace-git-changed", "route_id": "mainline-worker",
            "message": "bounded task",
        })
        observed["seal"] = replace(self.seal, git_branch="other", git_head="e" * 40)
        with self.assertRaisesRegex(ControlPlaneError, "WORKSPACE_CHANGED_EXTERNALLY"):
            previews.decide(
                "btest", "workspace-git-changed", "approve", prepared["envelope_sha256"],
            )
        self.assertFalse((previews.directory / "workspace-git-changed-approval.json").exists())

    def test_workspace_status_change_blocks_approval(self) -> None:
        observed = {"seal": self.seal}
        previews = self._previews(lambda _seal: observed["seal"])
        prepared = previews.prepare("btest", {
            "handoff_id": "workspace-status-changed", "route_id": "mainline-worker",
            "message": "bounded task",
        })
        observed["seal"] = replace(
            self.seal, git_status_sha256="f" * 64, git_status_entry_count=252,
        )
        with self.assertRaisesRegex(ControlPlaneError, "WORKSPACE_CHANGED_EXTERNALLY"):
            previews.decide(
                "btest", "workspace-status-changed", "approve", prepared["envelope_sha256"],
            )

    def test_public_preview_marks_changed_workspace_stale(self) -> None:
        observed = {"seal": self.seal}
        previews = self._previews(lambda _seal: observed["seal"])
        previews.prepare("btest", {
            "handoff_id": "workspace-public-stale", "route_id": "mainline-worker",
            "message": "bounded task",
        })
        observed["seal"] = replace(self.seal, git_head="e" * 40)

        public = previews.list_for_project("btest")[0]

        self.assertEqual(public["state"], "PREPARED")
        self.assertEqual(public["display_state"], "STALE_PREPARED_HANDOFF")
        self.assertEqual(public["workspace_guard"], "WORKSPACE_CHANGED_EXTERNALLY")
        self.assertFalse(public["approve_and_send_allowed"])

    def test_explicit_approve_and_send_consumes_exactly_once_and_captures_result(self) -> None:
        self.control.add_route("btest", {
            "route_id": "api-mainline-worker",
            "source_node_id": "BTEST_MAINLINE_API",
            "destination_node_id": "BTEST_CODEX_WORKER",
            "enabled": True,
            "handoff_type": "TASK",
        })
        self.control.set_mode("btest", "SEMI_AUTO")
        previews = self._previews()
        prepared = previews.prepare("btest", {
            "handoff_id": "semi-auto-once",
            "route_id": "api-mainline-worker",
            "message": "implement the sealed task",
        })
        calls: list[str] = []

        def transport(artifact, seal):
            calls.append(artifact["task_content_sha256"])
            self.assertEqual(seal, self.seal)
            return {
                "status": "completed",
                "turn": {"items": [{"type": "agentMessage", "text": "completed report"}]},
                "events": [{"method": "turn/started"}, {"method": "turn/completed"}],
                "actual_thread_count": 1,
                "actual_turn_count": 1,
            }

        dispatcher = SemiAutoCodexDispatcher(
            previews, self.control, self.root, transport_runner=transport,
        )
        completed = dispatcher.approve_and_send(
            "btest", "semi-auto-once", prepared["envelope_sha256"],
        )

        self.assertEqual(completed["state"], "COMPLETED")
        self.assertEqual(completed["actual_send_count"], 1)
        self.assertEqual(completed["response_text"], "completed report")
        self.assertEqual(len(calls), 1)
        with self.assertRaisesRegex(ControlPlaneError, "DUPLICATE_OR_TERMINAL"):
            dispatcher.approve_and_send(
                "btest", "semi-auto-once", prepared["envelope_sha256"],
            )
        self.assertEqual(len(calls), 1)

    def test_approve_and_send_requires_semi_auto_and_never_calls_transport(self) -> None:
        previews = self._previews()
        prepared = previews.prepare("btest", {
            "handoff_id": "semi-auto-mode-guard",
            "route_id": "mainline-worker",
            "message": "bounded task",
        })
        calls: list[str] = []
        dispatcher = SemiAutoCodexDispatcher(
            previews,
            self.control,
            self.root,
            transport_runner=lambda *_args: calls.append("called") or {},
        )

        with self.assertRaisesRegex(ControlPlaneError, "SEMI_AUTO_MODE_REQUIRED"):
            dispatcher.approve_and_send(
                "btest", "semi-auto-mode-guard", prepared["envelope_sha256"],
            )
        self.assertEqual(calls, [])

    def test_codex_approval_request_fails_closed_as_user_required(self) -> None:
        self.control.add_route("btest", {
            "route_id": "api-mainline-worker-approval",
            "source_node_id": "BTEST_MAINLINE_API",
            "destination_node_id": "BTEST_CODEX_WORKER",
            "enabled": True,
            "handoff_type": "TASK",
        })
        self.control.set_mode("btest", "SEMI_AUTO")
        previews = self._previews()
        prepared = previews.prepare("btest", {
            "handoff_id": "semi-auto-user-required",
            "route_id": "api-mainline-worker-approval",
            "message": "bounded task",
        })

        def approval_required(*_args):
            raise CodexApprovalRequired("item/tool/requestUserInput", 7)

        dispatcher = SemiAutoCodexDispatcher(
            previews, self.control, self.root, transport_runner=approval_required,
        )
        with self.assertRaisesRegex(ControlPlaneError, "CODEX_APPROVAL_USER_REQUIRED"):
            dispatcher.approve_and_send(
                "btest", "semi-auto-user-required", prepared["envelope_sha256"],
            )

        project = self.control.list_projects()["projects"][0]
        self.assertEqual(project["status"], "WAITING_FOR_USER")
        self.assertEqual(project["last_gate"], "USER_REQUIRED")
        self.assertEqual(project["current_cycle"], "semi-auto-user-required")
        self.assertEqual(previews.list_for_project("btest")[0]["state"], "FAILED")

    def test_route_change_blocks_stale_approval(self) -> None:
        previews = self._previews()
        prepared = previews.prepare("btest", {
            "handoff_id": "workspace-route-changed", "route_id": "mainline-worker",
            "message": "bounded task",
        })
        self.control.update_route("btest", "mainline-worker", {"handoff_type": "REPORT"})
        with self.assertRaisesRegex(ControlPlaneError, "DISPATCH_APPROVAL_STALE"):
            previews.decide(
                "btest", "workspace-route-changed", "approve", prepared["envelope_sha256"],
            )

    def _completed_dispatch(self, handoff_id: str = "workspace-return") -> DispatchPreviewStore:
        previews = self._previews()
        prepared = previews.prepare("btest", {
            "handoff_id": handoff_id, "route_id": "mainline-worker",
            "message": "read-only audit",
        })
        previews.decide("btest", handoff_id, "approve", prepared["envelope_sha256"])
        previews.start_dispatch("btest", handoff_id)
        previews.record_completion(handoff_id, {
            "status": "completed",
            "turn": {"items": [{"type": "agentMessage", "text": "exact result"}]},
            "events": [{"method": "turn/completed"}],
        })
        return previews

    def test_return_handoff_seals_exact_result_and_origin_without_send(self) -> None:
        previews = self._completed_dispatch()
        self.control.update_node("btest", "BTEST_MAINLINE", {
            "transport_kind": "CHATGPT_SESSION", "transport_ref": "",
        })
        returns = ReturnHandoffStore(self.root / "returns", previews.directory, self.control)

        value = returns.create(
            "btest", "workspace-return", return_route_id="worker-mainline",
        )

        import hashlib
        self.assertEqual(
            value["result_content_sha256"],
            hashlib.sha256(b"exact result").hexdigest(),
        )
        self.assertEqual(
            value["originating_task_sha256"],
            hashlib.sha256(b"read-only audit").hexdigest(),
        )
        self.assertEqual(value["source_node"]["node_id"], "BTEST_CODEX_WORKER")
        self.assertEqual(value["destination_node"]["node_id"], "BTEST_MAINLINE")
        self.assertEqual(value["route"]["handoff_type"], "REPORT")
        self.assertEqual(value["transport_capability"]["status"], "BLOCKED_UNSUPPORTED")
        self.assertEqual(value["delivery_status"], "USER_ASSISTED_EXACT_DELIVERY_CANDIDATE")
        self.assertEqual(value["actual_mainline_send_count"], 0)
        public_value = returns.list_for_project("btest")[0]
        self.assertNotIn("result_content", public_value)
        self.assertNotIn("transport_result", public_value)

    def test_return_handoff_blocks_duplicate_result(self) -> None:
        previews = self._completed_dispatch("workspace-return-duplicate")
        returns = ReturnHandoffStore(self.root / "returns", previews.directory, self.control)
        returns.create(
            "btest", "workspace-return-duplicate", return_route_id="worker-mainline",
        )
        with self.assertRaisesRegex(ControlPlaneError, "DUPLICATE_RETURN_HANDOFF_BLOCKED"):
            returns.create(
                "btest", "workspace-return-duplicate", return_route_id="worker-mainline",
            )

    def test_same_result_can_prepare_distinct_native_and_api_mainline_returns(self) -> None:
        previews = self._completed_dispatch("workspace-return-two-destinations")
        returns = ReturnHandoffStore(self.root / "returns-two", previews.directory, self.control)
        native = returns.create(
            "btest", "workspace-return-two-destinations", return_route_id="worker-mainline",
        )
        self.control.set_mode("btest", "SEMI_AUTO")
        self.control.apply_api_mainline_turn(
            "btest",
            {
                "action": "CONTINUE_USER_DIALOGUE",
                "destination": None,
                "updated_state_delta": {
                    "current_purpose": "continue the bounded cycle",
                    "scope_append": [],
                    "user_decisions_append": [],
                    "current_gate": "SAFE_CONTINUE",
                    "latest_relevant_handoff": None,
                },
            },
            response_id="resp-initial-mainline",
            model="gpt-5.6-sol",
            user_input_sha256="1" * 64,
            result_sha256="2" * 64,
        )
        api = returns.create(
            "btest",
            "workspace-return-two-destinations",
            return_route_id="BTEST_CODEX_TO_MAINLINE_API",
        )

        self.assertNotEqual(native["return_id"], api["return_id"])
        self.assertEqual(api["destination_node"]["node_id"], "BTEST_MAINLINE_API")
        self.assertEqual(api["state"], "PREPARED")
        self.assertEqual(
            api["transport_capability"]["status"],
            "PROGRAMMATIC_PREVIEW_READY_LIVE_API_LOCKED",
        )
        with self.assertRaisesRegex(ControlPlaneError, "DUPLICATE_RETURN_HANDOFF_BLOCKED"):
            returns.create(
                "btest",
                "workspace-return-two-destinations",
                return_route_id="BTEST_CODEX_TO_MAINLINE_API",
            )

        mainline_returns = ApiMainlineReturnStore(
            self.root / "api-mainline-returns",
            returns.directory,
            self.control,
            dispatch_directory=previews.directory,
        )
        prepared = mainline_returns.prepare("btest", api["return_id"])
        self.assertEqual(prepared["state"], "PREPARED")
        self.assertEqual(prepared["transport_capability"], "PREVIEW_READY_LIVE_API_LOCKED")
        self.assertEqual(prepared["actual_mainline_send_count"], 0)
        candidate = json.loads(
            (mainline_returns.directory / f"{api['return_id']}.json").read_text(encoding="utf-8"),
        )
        dynamic = json.loads(candidate["request"]["input"][1]["content"])
        self.assertEqual(dynamic["latest_codex_report"], "exact result")
        self.assertEqual(dynamic["current_task"], "read-only audit")
        self.assertEqual(candidate["manifest"]["exact_result_sha256"], api["result_content_sha256"])
        self.assertNotIn("previous_response_id", candidate["request"])
        self.assertFalse(candidate["approved_for_external_api"])
        self.assertFalse(candidate["approval_record"])
        self.assertFalse(candidate["attempt_record"])
        self.assertFalse(candidate["result_record"])
        self.assertEqual(candidate["network_calls"], 0)
        tampered = json.loads(json.dumps(candidate))
        tampered["exact_result"] += " changed"
        unsigned = dict(tampered)
        unsigned.pop("candidate_sha256")
        from console.devos_orchestration.manifest import sha256_json
        tampered["candidate_sha256"] = sha256_json(unsigned)
        with self.assertRaisesRegex(ControlPlaneError, "BINDING_MISMATCH"):
            mainline_returns.verify(tampered)
        with self.assertRaisesRegex(ControlPlaneError, "DUPLICATE_API_MAINLINE_RETURN_BLOCKED"):
            mainline_returns.prepare("btest", api["return_id"])

    def _api_return_execution(self, action: str):
        previews = self._completed_dispatch(f"workspace-api-return-{action.lower()}")
        returns = ReturnHandoffStore(self.root / f"returns-{action}", previews.directory, self.control)
        self.control.set_mode("btest", "SEMI_AUTO")
        self.control.apply_api_mainline_turn(
            "btest",
            {
                "action": "CONTINUE_USER_DIALOGUE",
                "destination": "USER",
                "updated_state_delta": {
                    "current_purpose": "continue the bounded cycle",
                    "scope_append": [],
                    "user_decisions_append": [],
                    "current_gate": None,
                    "latest_relevant_handoff": None,
                },
            },
            response_id="resp-initial-mainline",
            model="gpt-5.6-sol",
            user_input_sha256="1" * 64,
            result_sha256="2" * 64,
        )
        returned = returns.create(
            "btest",
            f"workspace-api-return-{action.lower()}",
            return_route_id="BTEST_CODEX_TO_MAINLINE_API",
        )
        delta = {
            "current_purpose": "continue the bounded cycle",
            "scope_append": [],
            "user_decisions_append": [],
            "current_gate": "SAFE_CONTINUE" if action == "HANDOFF_CODEX" else "USER_REQUIRED",
            "latest_relevant_handoff": returned["return_id"],
        }
        output = {
            "action": action,
            "assistant_message": None,
            "gate": "SAFE_CONTINUE" if action == "HANDOFF_CODEX" else "USER_REQUIRED",
            "destination": "CODEX_WORKER" if action == "HANDOFF_CODEX" else "USER",
            "handoff_message": "Perform the next bounded audit." if action == "HANDOFF_CODEX" else None,
            "decision_packet": None if action == "HANDOFF_CODEX" else {
                "question": "Choose the authority boundary.", "options": ["A", "B"],
            },
            "blocker": None,
            "updated_state_delta": delta,
        }
        requirement_id = extract_requirement_inventory("read-only audit")[0]["requirement_id"]
        review = valid_review_v2_4((requirement_id,))
        if action == "USER_REQUIRED":
            review.update({
                "orchestration_gate": "USER_REQUIRED",
                "routing_assessment": {
                    "resolution_kind": "USER_DECISION",
                    "safe_bounded_next_step_available": False,
                    "evidence_collection_possible": False,
                    "user_authority_required": True,
                    "blocker_class": "NONE",
                    "blocker_detail": None,
                },
                "next_instruction": None,
                "user_decision_packet": decision_packet(),
                "next_step_authority": {
                    "task_transition": "USER_DECISION_REQUIRED",
                    "next_step_basis": "USER_DECISION",
                    "source_refs": [],
                },
            })
            for assessment in review["task_requirement_assessment"]:
                assessment.update({
                    "status": "SATISFIED", "unresolved_action": None,
                    "acceptance_criteria_status": "MET", "unresolved_reason_kind": "NONE",
                })
        output["auto_advance_review"] = review

        class FakeReturnTransport:
            calls = 0

            def __call__(self, _request, _key, _timeout):
                self.calls += 1
                response = {
                    "id": f"resp-return-{action.lower()}",
                    "model": "gpt-5.6-sol",
                    "status": "completed",
                    "output": [{"type": "message", "content": [{
                        "type": "output_text", "text": json.dumps(output),
                    }]}],
                    "usage": {
                        "input_tokens": 120,
                        "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                        "output_tokens": 40,
                        "output_tokens_details": {"reasoning_tokens": 8},
                        "total_tokens": 160,
                    },
                }
                return HttpResult(200, {"x-request-id": "req-return"}, json.dumps(response).encode())

        env_file = self.root / f"return-{action}.env"
        env_file.write_text("OPENAI_ORCHESTRATION_API_KEY=test-only\n", encoding="utf-8")
        transport = FakeReturnTransport()
        store = ApiMainlineReturnStore(
            self.root / f"api-mainline-returns-{action}",
            returns.directory,
            self.control,
            dispatch_directory=previews.directory,
            env_file=env_file,
            transport=transport,
        )
        prepared = store.prepare("btest", returned["return_id"])
        return store, transport, prepared, returned

    def test_api_mainline_return_user_approval_executes_once_and_waits_for_user(self) -> None:
        store, transport, prepared, returned = self._api_return_execution("USER_REQUIRED")
        self.assertEqual(transport.calls, 0)
        result = store.approve_and_execute(
            "btest",
            returned["return_id"],
            prepared["candidate_sha256"],
            prepared["approval_manifest_sha256"],
        )
        self.assertEqual(transport.calls, 1)
        self.assertEqual(result["parsed_action"], "USER_REQUIRED")
        self.assertEqual(result["gate"], "USER_REQUIRED")
        self.assertIsNotNone(result["decision_packet"])
        self.assertIsNone(result["next_handoff"])
        self.assertEqual(result["dispatch_count"], 0)
        self.assertEqual(result["codex_turn_count"], 0)
        project = self.control.list_projects()["projects"][0]
        self.assertEqual(project["status"], "WAITING_FOR_USER")
        with self.assertRaisesRegex(ControlPlaneError, "CONSUMED|BINDING"):
            store.approve_and_execute(
                "btest",
                returned["return_id"],
                prepared["candidate_sha256"],
                prepared["approval_manifest_sha256"],
            )
        self.assertEqual(transport.calls, 1)

    def test_api_mainline_return_handoff_stops_at_prepared_without_codex_dispatch(self) -> None:
        store, transport, prepared, returned = self._api_return_execution("HANDOFF_CODEX")
        result = store.approve_and_execute(
            "btest",
            returned["return_id"],
            prepared["candidate_sha256"],
            prepared["approval_manifest_sha256"],
        )
        self.assertEqual(transport.calls, 1)
        self.assertEqual(result["parsed_action"], "HANDOFF_CODEX")
        self.assertEqual(result["gate"], "SAFE_CONTINUE")
        self.assertEqual(result["next_handoff"]["status"], "PREPARED")
        self.assertFalse(result["next_handoff"]["approval_record"])
        self.assertEqual(result["next_handoff"]["dispatch_count"], 0)
        self.assertEqual(result["codex_turn_count"], 0)

    def test_return_handoff_rejects_wrong_route_and_destination(self) -> None:
        previews = self._completed_dispatch("workspace-return-wrong-route")
        returns = ReturnHandoffStore(self.root / "returns", previews.directory, self.control)
        with self.assertRaisesRegex(ControlPlaneError, "INVALID_RETURN_ROUTE"):
            returns.create(
                "btest", "workspace-return-wrong-route", return_route_id="mainline-worker",
            )
        self.assertEqual(returns.list_for_project("btest"), [])

    def _return_handoff(self, handoff_id: str) -> tuple[ReturnHandoffStore, dict[str, object]]:
        previews = self._completed_dispatch(handoff_id)
        self.control.update_node("btest", "BTEST_MAINLINE", {
            "transport_kind": "CHATGPT_SESSION", "transport_ref": "",
        })
        returns = ReturnHandoffStore(self.root / f"returns-{handoff_id}", previews.directory, self.control)
        value = returns.create("btest", handoff_id, return_route_id="worker-mainline")
        return returns, value

    def test_exact_delivery_packet_copies_only_sealed_result_then_records_receipt(self) -> None:
        returns, return_value = self._return_handoff("workspace-exact-delivery")
        deliveries = ExactDeliveryStore(self.root / "deliveries", returns.directory)

        prepared = deliveries.create("btest", str(return_value["return_id"]))
        content = deliveries.exact_content(
            "btest", prepared["delivery_id"], prepared["delivery_packet_sha256"],
        )
        copied = deliveries.transition(
            "btest", prepared["delivery_id"], "copied", prepared["delivery_packet_sha256"],
        )
        delivered = deliveries.transition(
            "btest", prepared["delivery_id"], "delivered", prepared["delivery_packet_sha256"],
        )

        self.assertEqual(content["exact_message"], "exact result")
        self.assertEqual(set(content), {
            "delivery_id", "delivery_packet_sha256", "result_content_sha256", "exact_message",
        })
        self.assertEqual(copied["state"], "COPIED")
        self.assertEqual(delivered["state"], "DELIVERED")
        self.assertEqual(delivered["actual_mainline_send_count"], 0)
        receipt = json.loads(
            (deliveries.directory / f"{prepared['delivery_id']}-receipt.json").read_text(encoding="utf-8"),
        )
        self.assertTrue(receipt["explicit_user_action"])
        self.assertEqual(receipt["result_content_sha256"], prepared["result_content_sha256"])

    def test_exact_delivery_cancel_is_terminal_and_duplicate_packet_is_blocked(self) -> None:
        returns, return_value = self._return_handoff("workspace-exact-cancel")
        deliveries = ExactDeliveryStore(self.root / "deliveries-cancel", returns.directory)
        prepared = deliveries.create("btest", str(return_value["return_id"]))
        cancelled = deliveries.transition(
            "btest", prepared["delivery_id"], "cancel", prepared["delivery_packet_sha256"],
        )
        self.assertEqual(cancelled["state"], "CANCELLED")
        with self.assertRaisesRegex(ControlPlaneError, "INVALID_EXACT_DELIVERY_TRANSITION"):
            deliveries.transition(
                "btest", prepared["delivery_id"], "copied", prepared["delivery_packet_sha256"],
            )
        with self.assertRaisesRegex(ControlPlaneError, "DUPLICATE_EXACT_DELIVERY_BLOCKED"):
            deliveries.create("btest", str(return_value["return_id"]))

    def test_exact_delivery_rejects_wrong_packet_hash_and_out_of_order_delivery(self) -> None:
        returns, return_value = self._return_handoff("workspace-exact-order")
        deliveries = ExactDeliveryStore(self.root / "deliveries-order", returns.directory)
        prepared = deliveries.create("btest", str(return_value["return_id"]))
        with self.assertRaisesRegex(ControlPlaneError, "EXACT_DELIVERY_PACKET_CHANGED"):
            deliveries.exact_content("btest", prepared["delivery_id"], "0" * 64)
        with self.assertRaisesRegex(ControlPlaneError, "INVALID_EXACT_DELIVERY_TRANSITION"):
            deliveries.transition(
                "btest", prepared["delivery_id"], "delivered", prepared["delivery_packet_sha256"],
            )
        with self.assertRaisesRegex(ControlPlaneError, "EXACT_DELIVERY_PACKET_CHANGED"):
            deliveries.transition("btest", prepared["delivery_id"], "copied", "0" * 64)


if __name__ == "__main__":
    unittest.main()
