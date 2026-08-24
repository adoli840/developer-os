from __future__ import annotations

import hashlib
import unittest
from pathlib import Path
from typing import Sequence
from unittest.mock import patch

from console.devos_orchestration.workspace_guard import (
    WorkspaceGuardError,
    WorkspaceTurnGuard,
    capture_workspace_binding,
    verify_workspace_binding,
    windows_to_wsl_path,
)


class FakeGitRunner:
    def __init__(self, *, change_after_linux: bool = False) -> None:
        self.change_after_linux = change_after_linux
        self.windows_head_reads = 0

    def __call__(self, command: Sequence[str], timeout_seconds: float) -> bytes:
        linux = bool(command and command[0] == "wsl.exe")
        if "--show-toplevel" in command:
            return (b"/mnt/x/Projects/bTest\n" if linux else b"X:/Projects/bTest\n")
        if "--show-current" in command:
            return b"main\n"
        if command[-2:] == ["rev-parse", "HEAD"]:
            if not linux:
                self.windows_head_reads += 1
            changed = self.change_after_linux and not linux and self.windows_head_reads > 1
            return (("b" if changed else "a") * 40 + "\n").encode()
        if "--porcelain=v1" in command:
            return b" M file.txt\0"
        raise AssertionError(command)


class WorkspaceGuardTests(unittest.TestCase):
    def test_windows_path_maps_to_drvfs_path(self) -> None:
        self.assertEqual(
            windows_to_wsl_path("X:/Projects/bTest"),
            "/mnt/x/Projects/bTest",
        )

    def test_binding_seals_matching_windows_and_wsl_git_state(self) -> None:
        with patch.object(Path, "resolve", return_value=Path("X:/Projects/bTest")):
            seal = capture_workspace_binding(
                "btest", Path("X:/Projects/bTest"), runner=FakeGitRunner(),
            )
        self.assertEqual(seal.git_head, "a" * 40)
        self.assertEqual(seal.git_status_entry_count, 1)
        self.assertEqual(seal.git_status_sha256, hashlib.sha256(b" M file.txt\0").hexdigest())
        self.assertEqual(seal.wsl_workspace, "/mnt/x/Projects/bTest")
        self.assertIn('"binding_type":"WORKSPACE_ONLY"', seal.as_transport_ref())

    def test_change_during_capture_fails_closed(self) -> None:
        with patch.object(Path, "resolve", return_value=Path("X:/Projects/bTest")):
            with self.assertRaisesRegex(WorkspaceGuardError, "WORKSPACE_CHANGED_EXTERNALLY"):
                capture_workspace_binding(
                    "btest", Path("X:/Projects/bTest"),
                    runner=FakeGitRunner(change_after_linux=True),
                )

    def test_bound_workspace_change_fails_closed(self) -> None:
        with patch.object(Path, "resolve", return_value=Path("X:/Projects/bTest")):
            expected = capture_workspace_binding(
                "btest", Path("X:/Projects/bTest"), runner=FakeGitRunner(),
            )
            with self.assertRaisesRegex(WorkspaceGuardError, "WORKSPACE_CHANGED_EXTERNALLY"):
                verify_workspace_binding(
                    expected, runner=FakeGitRunner(change_after_linux=True),
                )

    def test_workspace_allows_only_one_developeros_turn(self) -> None:
        guard = WorkspaceTurnGuard()
        guard.acquire("a" * 64, "handoff-1")
        with self.assertRaisesRegex(
            WorkspaceGuardError, "WORKSPACE_DEVELOPEROS_TURN_ALREADY_ACTIVE",
        ):
            guard.acquire("a" * 64, "handoff-2")
        guard.release("a" * 64, "handoff-1")
        guard.acquire("a" * 64, "handoff-2")


if __name__ == "__main__":
    unittest.main()
