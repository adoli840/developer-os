from __future__ import annotations

import argparse
import json
import subprocess
import uuid
from pathlib import Path
from typing import Any

from .codex_transport import (
    CodexAppServerAdapter,
    CodexApprovalRequired,
    CodexProtocolRequestError,
    CodexRuntimeUnavailable,
    CodexThreadBinding,
    JsonLineProcessChannel,
    WslCodexRuntimeLauncher,
)
from .control_plane import ControlPlaneError
from .dispatch_preview import DispatchPreviewStore


SMOKE_MESSAGE = (
    "Transport smoke test only.\n"
    "Do not read, create, modify, or delete files.\n"
    "Do not run shell commands.\n"
    "Return a short confirmation that the message was received."
)


class _NoControl:
    pass


class WslScratchWorkspace:
    def __init__(self, distro: str, path: str) -> None:
        self.distro = distro
        self.path = path

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["wsl.exe", "-d", self.distro, "--", *args],
            check=True, capture_output=True, text=True, timeout=30,
        )

    def create_empty(self) -> None:
        absent = subprocess.run(
            ["wsl.exe", "-d", self.distro, "--", "test", "!", "-e", self.path],
            capture_output=True, timeout=30,
        )
        if absent.returncode != 0:
            raise RuntimeError("SCRATCH_WORKSPACE_ALREADY_EXISTS")
        self._run("mkdir", "-p", self.path)

    def entries(self) -> list[str]:
        result = self._run("find", self.path, "-mindepth", "1", "-print")
        return [line for line in result.stdout.splitlines() if line]


def _safe_failure_metadata(error: Exception, channel: JsonLineProcessChannel) -> dict[str, Any]:
    metadata = channel.safe_diagnostics()
    if isinstance(error, CodexProtocolRequestError):
        metadata.update({
            "request_method": error.method,
            "json_rpc_error_code": error.code,
            "sanitized_message": error.provider_message,
        })
    return metadata


def run_once(
    *,
    runtime_dir: Path,
    distro: str = "Ubuntu",
    codex_path: str = "/home/devops/.local/bin/codex",
    handoff_id: str | None = None,
    timeout_seconds: float = 600.0,
) -> dict[str, Any]:
    launcher = WslCodexRuntimeLauncher(
        distro, codex_path, timeout_seconds=min(timeout_seconds, 30.0),
    )
    runtime_profile, protocol_profile = launcher.preflight(runtime_dir.parent)
    if not protocol_profile.supports_required_contract():
        raise CodexRuntimeUnavailable("schema_contract", "Required App Server methods are missing")

    handoff_id = handoff_id or f"devos-phase2b1r4-smoke-{uuid.uuid4().hex}"
    workspace_path = f"/home/devops/.developer-os/orchestration-smoke/{handoff_id}"
    scratch = WslScratchWorkspace(distro, workspace_path)
    scratch.create_empty()
    if scratch.entries():
        raise RuntimeError("SCRATCH_WORKSPACE_NOT_EMPTY")

    previews = DispatchPreviewStore(runtime_dir / "dispatch-previews", _NoControl())  # type: ignore[arg-type]
    prepared = previews.prepare_smoke(
        handoff_id=handoff_id,
        project="developer-os",
        message=SMOKE_MESSAGE,
    )
    channel = JsonLineProcessChannel(
        launcher.app_server_command(runtime_profile.command_path),
        cwd=runtime_profile.launch_cwd,
    )
    adapter = CodexAppServerAdapter(
        channel, timeout_seconds=timeout_seconds, allow_turn_start=True,
    )
    actual_turn_count = 0
    approval_occurred = False
    try:
        adapter.initialize()
        thread_result = adapter.start_thread(workspace_path)
        thread_id = thread_result.get("thread", {}).get("id")
        if not isinstance(thread_id, str) or not thread_id:
            raise RuntimeError("SCRATCH_THREAD_NOT_CREATED")
        binding = CodexThreadBinding(thread_id, workspace_path)
        previews.bind(handoff_id, binding)
        previews.transition(handoff_id, "SENT")
        actual_turn_count = 1
        turn_result = adapter.start_turn(binding, SMOKE_MESSAGE)
        turn_id = turn_result.get("turn", {}).get("id")
        if not isinstance(turn_id, str) or not turn_id:
            raise RuntimeError("TURN_START_RESPONSE_INVALID")
        completion = adapter.receive_turn(thread_id, turn_id)
        methods = [event.get("method") for event in completion["events"]]
        if "turn/started" not in methods or "turn/completed" not in methods:
            raise RuntimeError("TURN_EVENT_CONTRACT_INCOMPLETE")
        forbidden_items = [
            item
            for item in completion.get("turn", {}).get("items", [])
            if isinstance(item, dict) and item.get("type") in {
                "commandExecution", "fileChange", "mcpToolCall", "dynamicToolCall",
            }
        ]
        if forbidden_items:
            raise RuntimeError("SMOKE_TEST_TOOL_ACTIVITY_DETECTED")
        completed = previews.record_completion(handoff_id, completion)
    except CodexApprovalRequired as error:
        approval_occurred = True
        try:
            previews.record_failure(
                handoff_id,
                "CODEX_APPROVAL_USER_REQUIRED",
                {"request_method": error.method},
            )
        except ControlPlaneError:
            pass
        raise
    except Exception as error:
        try:
            previews.record_failure(
                handoff_id, str(error)[:120], _safe_failure_metadata(error, channel),
            )
        except ControlPlaneError:
            pass
        raise
    finally:
        adapter.close()

    duplicate_blocked = False
    try:
        previews.transition(handoff_id, "SENT")
    except ControlPlaneError:
        duplicate_blocked = True
    scratch_entries = scratch.entries()
    return {
        "handoff_id": handoff_id,
        "payload_sha256": prepared["payload_sha256"],
        "runtime": {
            "runtime_kind": runtime_profile.runtime_kind,
            "distro": runtime_profile.distro,
            "command_path": runtime_profile.command_path,
            "cli_version": runtime_profile.cli_version,
            "schema_bundle_sha256": runtime_profile.schema_bundle_sha256,
            "initialize_status": runtime_profile.initialize_status,
            "initialized_status": runtime_profile.initialized_status,
        },
        "scratch_workspace": workspace_path,
        "scratch_thread_created": True,
        "actual_turn_count": actual_turn_count,
        "handoff_state": completed["state"],
        "turn_started_received": True,
        "completion_received": completed["completion_received"],
        "event_count": completed["event_count"],
        "response_text": completed["response_text"],
        "result_artifact_sha256": completed["result_artifact_sha256"],
        "duplicate_send_blocked": duplicate_blocked,
        "approval_occurred": approval_occurred,
        "scratch_mutation_count": len(scratch_entries),
        "btest_access_count": 0,
        "btest_mutation_count": 0,
        "retry_count": 0,
        "fallback_count": 0,
        "follow_up_turn_count": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--distro", default="Ubuntu")
    parser.add_argument("--codex-path", default="/home/devops/.local/bin/codex")
    parser.add_argument("--handoff-id")
    args = parser.parse_args()
    if not args.execute:
        raise SystemExit("EXPLICIT_EXECUTE_REQUIRED")
    try:
        result = run_once(
            runtime_dir=args.runtime_dir,
            distro=args.distro,
            codex_path=args.codex_path,
            handoff_id=args.handoff_id,
        )
    except CodexRuntimeUnavailable as error:
        print(json.dumps({
            "status": "WSL_CODEX_RUNTIME_REPAIR_REQUIRED",
            "stage": error.stage,
            "sanitized_message": error.provider_message,
            "safe_error_metadata": error.diagnostics,
            "handoff_created": False,
            "actual_turn_count": 0,
        }, ensure_ascii=True, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
