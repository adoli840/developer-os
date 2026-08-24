from __future__ import annotations

import hashlib
import json
import ntpath
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Sequence


class WorkspaceGuardError(RuntimeError):
    pass


Runner = Callable[[Sequence[str], float], bytes]


def _run(command: Sequence[str], timeout_seconds: float) -> bytes:
    return subprocess.run(
        list(command), check=True, capture_output=True, timeout=timeout_seconds,
    ).stdout


def windows_to_wsl_path(value: str) -> str:
    drive, tail = ntpath.splitdrive(value)
    if len(drive) != 2 or drive[1] != ":" or not tail.startswith(("\\", "/")):
        raise WorkspaceGuardError("INVALID_WINDOWS_WORKSPACE")
    parts = [part for part in tail.replace("\\", "/").split("/") if part]
    if any(part == ".." for part in parts):
        raise WorkspaceGuardError("INVALID_WINDOWS_WORKSPACE")
    return str(PurePosixPath("/mnt") / drive[0].lower() / PurePosixPath(*parts))


@dataclass(frozen=True)
class GitWorkspaceFingerprint:
    root: str
    branch: str
    head: str
    status_sha256: str
    status_entry_count: int

    def state_key(self) -> tuple[str, str, str, int]:
        return self.branch, self.head, self.status_sha256, self.status_entry_count


@dataclass(frozen=True)
class WorkspaceBindingSeal:
    project: str
    windows_workspace: str
    wsl_workspace: str
    runtime: str
    distro: str
    workspace_identity_sha256: str
    git_branch: str
    git_head: str
    git_status_sha256: str
    git_status_entry_count: int

    def as_transport_ref(self) -> str:
        return json.dumps({
            "binding_type": "WORKSPACE_ONLY",
            "binding_version": "1",
            "project": self.project,
            "runtime": self.runtime,
            "distro": self.distro,
            "windows_workspace": self.windows_workspace,
            "wsl_workspace": self.wsl_workspace,
            "workspace_identity_sha256": self.workspace_identity_sha256,
            "git_branch": self.git_branch,
            "git_head": self.git_head,
            "git_status_sha256": self.git_status_sha256,
            "git_status_entry_count": self.git_status_entry_count,
        }, ensure_ascii=True, separators=(",", ":"))


def _text(command: Sequence[str], runner: Runner, timeout_seconds: float) -> str:
    return runner(command, timeout_seconds).decode("utf-8", errors="strict").strip()


def capture_git_fingerprint(
    command_prefix: Sequence[str],
    workspace: str,
    *,
    runner: Runner = _run,
    timeout_seconds: float = 120.0,
) -> GitWorkspaceFingerprint:
    base = [*command_prefix, "git", "-C", workspace]
    try:
        root = _text([*base, "rev-parse", "--show-toplevel"], runner, timeout_seconds)
        branch = _text([*base, "branch", "--show-current"], runner, timeout_seconds)
        head = _text([*base, "rev-parse", "HEAD"], runner, timeout_seconds)
        status = runner(
            [*base, "status", "--porcelain=v1", "-z", "--untracked-files=all"],
            timeout_seconds,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError) as error:
        raise WorkspaceGuardError("WORKSPACE_GIT_INSPECTION_FAILED") from error
    if not root or not branch or len(head) != 40:
        raise WorkspaceGuardError("INVALID_GIT_WORKSPACE")
    return GitWorkspaceFingerprint(
        root=root.replace("\\", "/"),
        branch=branch,
        head=head,
        status_sha256=hashlib.sha256(status).hexdigest(),
        status_entry_count=len([item for item in status.split(b"\0") if item]),
    )


def capture_workspace_binding(
    project: str,
    windows_workspace: Path,
    *,
    distro: str = "Ubuntu",
    runner: Runner = _run,
    timeout_seconds: float = 120.0,
) -> WorkspaceBindingSeal:
    windows_path = str(windows_workspace.resolve()).replace("\\", "/")
    wsl_path = windows_to_wsl_path(windows_path)
    windows_prefix: list[str] = []
    wsl_prefix = ["wsl.exe", "-d", distro, "--"]
    first = capture_git_fingerprint(
        windows_prefix, windows_path, runner=runner, timeout_seconds=timeout_seconds,
    )
    linux = capture_git_fingerprint(
        wsl_prefix, wsl_path, runner=runner, timeout_seconds=timeout_seconds,
    )
    final = capture_git_fingerprint(
        windows_prefix, windows_path, runner=runner, timeout_seconds=timeout_seconds,
    )
    if first != final:
        raise WorkspaceGuardError("WORKSPACE_CHANGED_EXTERNALLY")
    if first.state_key() != linux.state_key():
        raise WorkspaceGuardError("WINDOWS_WSL_WORKSPACE_MISMATCH")
    if first.root.casefold() != windows_path.casefold() or linux.root != wsl_path:
        raise WorkspaceGuardError("WORKSPACE_ROOT_MISMATCH")
    identity = hashlib.sha256(json.dumps({
        "project": project,
        "windows_workspace": windows_path.casefold(),
        "wsl_workspace": wsl_path,
        "git_head": first.head,
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return WorkspaceBindingSeal(
        project=project,
        windows_workspace=windows_path,
        wsl_workspace=wsl_path,
        runtime="WSL_CODEX_APP_SERVER",
        distro=distro,
        workspace_identity_sha256=identity,
        git_branch=first.branch,
        git_head=first.head,
        git_status_sha256=first.status_sha256,
        git_status_entry_count=first.status_entry_count,
    )


def verify_workspace_binding(
    expected: WorkspaceBindingSeal,
    *,
    runner: Runner = _run,
    timeout_seconds: float = 120.0,
) -> WorkspaceBindingSeal:
    current = capture_workspace_binding(
        expected.project,
        Path(expected.windows_workspace),
        distro=expected.distro,
        runner=runner,
        timeout_seconds=timeout_seconds,
    )
    if current != expected:
        raise WorkspaceGuardError("WORKSPACE_CHANGED_EXTERNALLY")
    return current


class WorkspaceTurnGuard:
    """Process-local single-turn lease; durable handoff state remains authoritative."""

    def __init__(self) -> None:
        self._active: dict[str, str] = {}

    def acquire(self, workspace_identity_sha256: str, handoff_id: str) -> None:
        active = self._active.get(workspace_identity_sha256)
        if active is not None:
            raise WorkspaceGuardError("WORKSPACE_DEVELOPEROS_TURN_ALREADY_ACTIVE")
        self._active[workspace_identity_sha256] = handoff_id

    def release(self, workspace_identity_sha256: str, handoff_id: str) -> None:
        if self._active.get(workspace_identity_sha256) != handoff_id:
            raise WorkspaceGuardError("WORKSPACE_TURN_LEASE_MISMATCH")
        del self._active[workspace_identity_sha256]
