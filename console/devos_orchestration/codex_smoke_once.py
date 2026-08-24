from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import uuid
from pathlib import Path
from typing import Any

from .codex_transport import (
    CodexAppServerAdapter,
    CodexApprovalRequired,
    CodexProtocolRequestError,
    CodexRuntimeLauncher,
    CodexRuntimeUnavailable,
    CodexThreadBinding,
    JsonLineProcessChannel,
)
from .control_plane import ControlPlaneError
from .dispatch_preview import DispatchPreviewStore


SMOKE_MESSAGE = (
    "Transport smoke test only.\n"
    "Do not read, create, modify, or delete files.\n"
    "Do not run shell commands.\n"
    "Return a short confirmation that the message was received."
)


def _workspace_inventory(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in sorted(path.rglob("*")):
        if item.is_file():
            relative = item.relative_to(path).as_posix()
            result[relative] = hashlib.sha256(item.read_bytes()).hexdigest()
    return result


def _git_fingerprint(path: Path) -> dict[str, str]:
    status = subprocess.run(
        ["git", "-C", str(path), "status", "--porcelain=v1", "-z"],
        check=True, capture_output=True,
    ).stdout
    head = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return {"head": head, "status_sha256": hashlib.sha256(status).hexdigest()}


class _NoControl:
    pass


def run_once(
    *,
    executable: str,
    runtime_dir: Path,
    workspace: Path,
    btest_path: Path,
    handoff_id: str | None = None,
    timeout_seconds: float = 600.0,
) -> dict[str, Any]:
    launcher = CodexRuntimeLauncher(executable, timeout_seconds=min(timeout_seconds, 30.0))
    runtime_profile, protocol_profile = launcher.preflight(runtime_dir.parent)
    if not protocol_profile.supports_required_contract():
        raise CodexRuntimeUnavailable("schema_contract", "Required App Server methods are missing")
    handoff_id = handoff_id or f"devos-phase2b1r-smoke-{uuid.uuid4().hex}"
    workspace.mkdir(parents=True, exist_ok=True)
    before_workspace = _workspace_inventory(workspace)
    if before_workspace:
        raise RuntimeError("SCRATCH_WORKSPACE_NOT_EMPTY")
    before_btest = _git_fingerprint(btest_path)
    previews = DispatchPreviewStore(runtime_dir / "dispatch-previews", _NoControl())  # type: ignore[arg-type]
    prepared = previews.prepare_smoke(
        handoff_id=handoff_id,
        project="developer-os",
        message=SMOKE_MESSAGE,
    )
    channel = JsonLineProcessChannel(
        [runtime_profile.command_path, "app-server", "--listen", "stdio://"],
        cwd=runtime_profile.launch_cwd,
    )
    adapter = CodexAppServerAdapter(
        channel,
        timeout_seconds=timeout_seconds,
        allow_turn_start=True,
    )
    actual_turn_count = 0
    approval_occurred = False
    try:
        adapter.initialize()
        thread_result = adapter.start_thread(str(workspace))
        thread_id = thread_result.get("thread", {}).get("id")
        if not isinstance(thread_id, str) or not thread_id:
            raise RuntimeError("SCRATCH_THREAD_NOT_CREATED")
        binding = CodexThreadBinding(thread_id, str(workspace))
        previews.bind(handoff_id, binding)
        previews.transition(handoff_id, "SENT")
        actual_turn_count += 1
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
    except CodexApprovalRequired:
        approval_occurred = True
        try:
            previews.record_failure(handoff_id, "CODEX_APPROVAL_REQUIRED")
        except ControlPlaneError:
            pass
        raise
    except Exception as error:
        metadata: dict[str, Any] = {}
        if isinstance(error, CodexProtocolRequestError):
            metadata = {
                "request_method": error.method,
                "json_rpc_error_code": error.code,
                "sanitized_message": error.provider_message,
                **error.diagnostics,
            }
        elif hasattr(channel, "safe_diagnostics"):
            metadata = channel.safe_diagnostics()
        try:
            previews.record_failure(handoff_id, str(error)[:120], metadata)
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
    after_workspace = _workspace_inventory(workspace)
    after_btest = _git_fingerprint(btest_path)
    return {
        "handoff_id": handoff_id,
        "payload_sha256": prepared["payload_sha256"],
        "runtime": {
            "command_source": runtime_profile.command_source,
            "command_path": runtime_profile.command_path,
            "cli_version": runtime_profile.cli_version,
            "launch_cwd": runtime_profile.launch_cwd,
            "schema_bundle_sha256": runtime_profile.schema_bundle_sha256,
            "initialize_status": runtime_profile.initialize_status,
            "initialized_status": runtime_profile.initialized_status,
        },
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
        "scratch_file_change_count": len(set(before_workspace) ^ set(after_workspace)),
        "btest_change_count": 0 if before_btest == after_btest else 1,
        "retry_count": 0,
        "follow_up_turn_count": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--executable", required=True)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--btest-path", type=Path, required=True)
    parser.add_argument("--handoff-id")
    args = parser.parse_args()
    if not args.execute:
        raise SystemExit("EXPLICIT_EXECUTE_REQUIRED")
    try:
        result = run_once(
            executable=args.executable,
            runtime_dir=args.runtime_dir,
            workspace=args.workspace,
            btest_path=args.btest_path,
            handoff_id=args.handoff_id,
        )
    except CodexRuntimeUnavailable as error:
        print(json.dumps({
            "status": "CODEX_RUNTIME_USER_ACTION_REQUIRED",
            "stage": error.stage,
            "sanitized_message": error.provider_message,
            "safe_error_metadata": error.diagnostics,
            "handoff_created": False,
            "actual_turn_count": 0,
            "retry_count": 0,
        }, ensure_ascii=True, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
