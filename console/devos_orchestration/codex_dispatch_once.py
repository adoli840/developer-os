from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path
from typing import Any

from console.devos_console.audit import AuditLog
from console.devos_console.settings import load_settings

from .codex_transport import (
    CodexAppServerAdapter,
    CodexApprovalRequired,
    CodexProtocolRequestError,
    CodexRuntimeUnavailable,
    CodexThreadBinding,
    CodexTransportError,
    CodexWorkspaceBinding,
    JsonLineProcessChannel,
    WslCodexRuntimeLauncher,
    locked_capability_status,
)
from .control_plane import ControlPlaneError, OrchestrationControlStore
from .dispatch_preview import DispatchPreviewStore
from .workspace_guard import (
    WorkspaceGuardError,
    WorkspaceTurnGuard,
    capture_workspace_binding,
    verify_workspace_binding,
)


READ_ONLY_AUDIT_TASK = """Perform one bounded, read-only audit of this bTest repository.
Do not create, modify, rename, or delete files. Do not run commands that can mutate files,
dependencies, caches, databases, containers, Git state, or external services. Do not run tests.
You may inspect Git metadata and existing source or documentation with read-only commands.
Report the current branch and HEAD, then give one concise repository-grounded observation about
the current project structure or an existing safety control. Do not propose or perform edits."""

READ_ONLY_DEVELOPER_INSTRUCTIONS = """This is an approved exactly-once read-only repository audit.
Use only read-only inspection. Never create, modify, rename, or delete files; never change Git,
dependencies, caches, databases, containers, or external services. Do not request approval for a
write. Return a concise report and stop after this single turn."""


def _safe_failure_metadata(error: Exception, channel: JsonLineProcessChannel | None) -> dict[str, Any]:
    metadata: dict[str, Any] = {"error_type": type(error).__name__}
    if channel is not None:
        metadata.update(channel.safe_diagnostics())
    if isinstance(error, CodexProtocolRequestError):
        metadata.update({
            "request_method": error.method,
            "jsonrpc_error_code": error.code,
            "sanitized_message": error.provider_message,
        })
    if isinstance(error, CodexApprovalRequired):
        metadata["request_method"] = error.method
    return metadata


def run_once(
    *,
    runtime_dir: Path,
    btest_workspace: Path,
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

    seal = capture_workspace_binding("btest", btest_workspace, distro=distro)

    def capability_provider(node: dict[str, Any]) -> dict[str, Any]:
        binding = None
        try:
            binding = CodexWorkspaceBinding.parse(str(node.get("transport_ref") or ""))
        except CodexTransportError:
            pass
        return locked_capability_status(protocol_profile, binding)

    control = OrchestrationControlStore(
        runtime_dir / "orchestration-control.json",
        ["developer-os", "btest", "oa", "gaia"],
        AuditLog(runtime_dir / "audit.jsonl"),
        capability_provider=capability_provider,
    )
    control.update_node(
        "btest", "BTEST_CODEX_WORKER", {"transport_ref": seal.as_transport_ref()},
    )
    previews = DispatchPreviewStore(runtime_dir / "dispatch-previews", control)
    handoff_id = handoff_id or f"btest-read-only-audit-{uuid.uuid4().hex}"
    prepared = previews.prepare("btest", {
        "handoff_id": handoff_id,
        "route_id": "BTEST_MAINLINE_TO_CODEX",
        "message": READ_ONLY_AUDIT_TASK,
    })
    approved = previews.decide(
        "btest", handoff_id, "APPROVE", prepared["envelope_sha256"],
    )

    guard = WorkspaceTurnGuard()
    guard.acquire(seal.workspace_identity_sha256, handoff_id)
    channel: JsonLineProcessChannel | None = None
    adapter: CodexAppServerAdapter | None = None
    actual_thread_count = 0
    actual_turn_count = 0
    approval_occurred = False
    started = time.monotonic()
    completed: dict[str, Any] | None = None
    post_seal = None
    try:
        if verify_workspace_binding(seal) != seal:
            raise WorkspaceGuardError("WORKSPACE_CHANGED_EXTERNALLY")
        previews.start_dispatch("btest", handoff_id)
        channel = JsonLineProcessChannel(
            launcher.app_server_command(runtime_profile.command_path),
            cwd=runtime_profile.launch_cwd,
        )
        adapter = CodexAppServerAdapter(
            channel, timeout_seconds=timeout_seconds, allow_turn_start=True,
        )
        adapter.initialize()
        thread_result = adapter.start_thread(
            seal.wsl_workspace,
            developer_instructions=READ_ONLY_DEVELOPER_INSTRUCTIONS,
        )
        actual_thread_count = 1
        thread_id = thread_result.get("thread", {}).get("id")
        if not isinstance(thread_id, str) or not thread_id:
            raise RuntimeError("BTEST_ORCHESTRATION_THREAD_NOT_CREATED")
        binding = CodexThreadBinding(thread_id, seal.wsl_workspace)
        turn_result = adapter.start_turn(binding, READ_ONLY_AUDIT_TASK)
        actual_turn_count = 1
        turn_id = turn_result.get("turn", {}).get("id")
        if not isinstance(turn_id, str) or not turn_id:
            raise RuntimeError("TURN_START_RESPONSE_INVALID")
        transport_result = adapter.receive_turn(thread_id, turn_id)
        post_seal = capture_workspace_binding("btest", btest_workspace, distro=distro)
        if post_seal != seal:
            raise WorkspaceGuardError("WORKSPACE_CHANGED_EXTERNALLY")
        completed = previews.record_completion(handoff_id, transport_result)
    except CodexApprovalRequired as error:
        approval_occurred = True
        try:
            previews.record_failure(
                handoff_id, "CODEX_APPROVAL_USER_REQUIRED", _safe_failure_metadata(error, channel),
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
        if adapter is not None:
            adapter.close()
        elif channel is not None:
            channel.close()
        guard.release(seal.workspace_identity_sha256, handoff_id)

    duplicate_blocked = False
    try:
        previews.start_dispatch("btest", handoff_id)
    except ControlPlaneError:
        duplicate_blocked = True
    if completed is None or post_seal is None:
        raise RuntimeError("DISPATCH_RESULT_NOT_CAPTURED")
    return {
        "handoff_id": handoff_id,
        "envelope_sha256": prepared["envelope_sha256"],
        "approval_record_sha256": approved["approval_record_sha256"],
        "workspace_seal": {
            "workspace_identity_sha256": seal.workspace_identity_sha256,
            "branch": seal.git_branch,
            "head": seal.git_head,
            "workspace_fingerprint_sha256": seal.git_status_sha256,
            "status_entry_count": seal.git_status_entry_count,
        },
        "actual_thread_count": actual_thread_count,
        "actual_turn_count": actual_turn_count,
        "actual_dispatch_count": completed["actual_send_count"],
        "response_capture_status": "COMPLETED",
        "response_text": completed["response_text"],
        "result_artifact_sha256": completed["result_artifact_sha256"],
        "latency_seconds": round(time.monotonic() - started, 3),
        "duplicate_send_blocked": duplicate_blocked,
        "approval_occurred": approval_occurred,
        "post_workspace_fingerprint_match": post_seal == seal,
        "btest_mutation_count": 0 if post_seal == seal else 1,
        "retry_count": 0,
        "fallback_count": 0,
        "follow_up_turn_count": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--runtime-dir", type=Path)
    parser.add_argument("--handoff-id")
    parser.add_argument("--distro", default="Ubuntu")
    parser.add_argument("--codex-path", default="/home/devops/.local/bin/codex")
    args = parser.parse_args()
    if not args.execute:
        raise SystemExit("EXPLICIT_EXECUTE_REQUIRED")
    settings = load_settings(dev_mode=True)
    runtime_dir = (args.runtime_dir or settings.runtime_dir).resolve()
    project = next(item for item in settings.projects if item.slug == "btest")
    result = run_once(
        runtime_dir=runtime_dir,
        btest_workspace=project.path,
        distro=args.distro,
        codex_path=args.codex_path,
        handoff_id=args.handoff_id,
    )
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
