from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from .codex_transport import (
    CodexAppServerAdapter,
    CodexApprovalRequired,
    CodexProtocolRequestError,
    CodexRuntimeUnavailable,
    CodexThreadBinding,
    JsonLineProcessChannel,
    WslCodexRuntimeLauncher,
)
from .control_plane import ControlPlaneError, OrchestrationControlStore
from .dispatch_preview import DispatchPreviewStore
from .workspace_guard import WorkspaceBindingSeal, WorkspaceGuardError, WorkspaceTurnGuard


SEMI_AUTO_DEVELOPER_INSTRUCTIONS = """Execute only the exact user-approved handoff task.
Stay inside the bound workspace. Do not commit, push, deploy, or start another turn.
Do not broaden the task. If an approval or additional user decision is required, request it and
stop; never approve it yourself. Return one complete Codex report for this turn."""


TransportRunner = Callable[[dict[str, Any], WorkspaceBindingSeal], dict[str, Any]]


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


class SemiAutoCodexDispatcher:
    """Consumes one explicitly approved PREPARED handoff and never retries it."""

    def __init__(
        self,
        previews: DispatchPreviewStore,
        control: OrchestrationControlStore,
        runtime_dir: Path,
        *,
        distro: str = "Ubuntu",
        codex_path: str = "/home/devops/.local/bin/codex",
        timeout_seconds: float = 600.0,
        transport_runner: TransportRunner | None = None,
        turn_guard: WorkspaceTurnGuard | None = None,
    ) -> None:
        self.previews = previews
        self.control = control
        self.runtime_dir = runtime_dir
        self.distro = distro
        self.codex_path = codex_path
        self.timeout_seconds = timeout_seconds
        self.transport_runner = transport_runner or self._run_transport
        self.turn_guard = turn_guard or WorkspaceTurnGuard()

    @staticmethod
    def _seal(artifact: dict[str, Any]) -> WorkspaceBindingSeal:
        envelope = artifact.get("dispatch_envelope") or {}
        workspace = envelope.get("workspace") or {}
        runtime = envelope.get("runtime_protocol") or {}
        if workspace.get("binding_type") != "WORKSPACE_ONLY":
            raise ControlPlaneError("WORKSPACE_BOUND_ENVELOPE_REQUIRED")
        return WorkspaceBindingSeal(
            project=str(artifact.get("project") or ""),
            windows_workspace=str(workspace.get("windows_workspace") or ""),
            wsl_workspace=str(workspace.get("wsl_workspace") or ""),
            runtime=str(runtime.get("runtime") or ""),
            distro=str(runtime.get("distro") or ""),
            workspace_identity_sha256=str(workspace.get("workspace_identity_sha256") or ""),
            git_branch=str(workspace.get("branch") or ""),
            git_head=str(workspace.get("head") or ""),
            git_status_sha256=str(workspace.get("workspace_fingerprint_sha256") or ""),
            git_status_entry_count=int(workspace.get("workspace_status_entry_count") or 0),
        )

    def _require_semi_auto(self, project: str) -> None:
        state = next(
            (item for item in self.control.list_projects()["projects"] if item["project"] == project),
            None,
        )
        if state is None or state.get("mode") != "SEMI_AUTO":
            raise ControlPlaneError("SEMI_AUTO_MODE_REQUIRED")

    def approve_and_send(
        self,
        project: str,
        handoff_id: str,
        envelope_sha256: str,
    ) -> dict[str, Any]:
        if project != "btest":
            raise ControlPlaneError("BTEST_DISPATCH_ONLY")
        self._require_semi_auto(project)
        self.previews.decide(project, handoff_id, "APPROVE", envelope_sha256)
        artifact = self.previews.artifact_for_dispatch(project, handoff_id)
        envelope = artifact.get("dispatch_envelope") or {}
        if envelope.get("destination_node", {}).get("node_id") != "BTEST_CODEX_WORKER":
            raise ControlPlaneError("INVALID_CODEX_DESTINATION")
        seal = self._seal(artifact)
        self.turn_guard.acquire(seal.workspace_identity_sha256, handoff_id)
        attempt_started = False
        started = time.monotonic()
        try:
            self.previews.start_dispatch(project, handoff_id)
            attempt_started = True
            transport_result = self.transport_runner(artifact, seal)
            if transport_result.get("status") != "completed":
                raise ControlPlaneError(
                    f"CODEX_TURN_{str(transport_result.get('status') or 'UNKNOWN').upper()}"
                )
            transport_result = {
                **transport_result,
                "latency_seconds": round(time.monotonic() - started, 3),
                "retry_count": 0,
                "fallback_count": 0,
                "follow_up_turn_count": 0,
            }
            return self.previews.record_completion(handoff_id, transport_result)
        except CodexApprovalRequired as error:
            if attempt_started:
                self.previews.record_failure(
                    handoff_id,
                    "CODEX_APPROVAL_USER_REQUIRED",
                    _safe_failure_metadata(error, None),
                )
                self.control.record_dispatch_user_required(project, handoff_id)
            raise ControlPlaneError("CODEX_APPROVAL_USER_REQUIRED") from error
        except Exception as error:
            if attempt_started:
                try:
                    self.previews.record_failure(
                        handoff_id,
                        str(error)[:120],
                        _safe_failure_metadata(error, None),
                    )
                except ControlPlaneError:
                    pass
            if isinstance(error, ControlPlaneError):
                raise
            raise ControlPlaneError(str(error)[:120]) from error
        finally:
            self.turn_guard.release(seal.workspace_identity_sha256, handoff_id)

    def _run_transport(
        self,
        artifact: dict[str, Any],
        seal: WorkspaceBindingSeal,
    ) -> dict[str, Any]:
        launcher = WslCodexRuntimeLauncher(
            self.distro,
            self.codex_path,
            timeout_seconds=min(self.timeout_seconds, 30.0),
        )
        runtime_profile, protocol_profile = launcher.preflight(self.runtime_dir.parent)
        envelope_runtime = artifact["dispatch_envelope"]["runtime_protocol"]
        if (
            runtime_profile.cli_version != envelope_runtime.get("protocol_version")
            or protocol_profile.schema_bundle_sha256
            != envelope_runtime.get("protocol_schema_sha256")
        ):
            raise ControlPlaneError("CODEX_RUNTIME_PROTOCOL_CHANGED")
        channel = JsonLineProcessChannel(
            launcher.app_server_command(runtime_profile.command_path),
            cwd=runtime_profile.launch_cwd,
        )
        adapter = CodexAppServerAdapter(
            channel,
            timeout_seconds=self.timeout_seconds,
            allow_turn_start=True,
        )
        try:
            adapter.initialize()
            thread = adapter.start_thread(
                seal.wsl_workspace,
                developer_instructions=SEMI_AUTO_DEVELOPER_INSTRUCTIONS,
                sandbox="workspace-write",
            )
            thread_id = thread.get("thread", {}).get("id")
            if not isinstance(thread_id, str) or not thread_id:
                raise ControlPlaneError("BTEST_ORCHESTRATION_THREAD_NOT_CREATED")
            binding = CodexThreadBinding(thread_id, seal.wsl_workspace)
            message = str(artifact.get("rendered_message", {}).get("message") or "")
            turn = adapter.start_turn(binding, message)
            turn_id = turn.get("turn", {}).get("id")
            if not isinstance(turn_id, str) or not turn_id:
                raise ControlPlaneError("TURN_START_RESPONSE_INVALID")
            result = adapter.receive_turn(thread_id, turn_id)
            return {
                **result,
                "actual_thread_count": 1,
                "actual_turn_count": 1,
                "actual_dispatch_count": 1,
            }
        except (CodexRuntimeUnavailable, WorkspaceGuardError) as error:
            raise ControlPlaneError(str(error)) from error
        finally:
            adapter.close()
