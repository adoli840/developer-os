from __future__ import annotations

import os
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from console.devos_terminal.runner import MAX_COMMAND_LENGTH, TerminalRunner
from console.devos_terminal.server import TerminalApplication
from console.devos_terminal.settings import TerminalProject, TerminalSettings
from console.devos_terminal.websocket_transport import receive_frame, send_frame, websocket_accept


def terminal_settings(root: Path) -> TerminalSettings:
    return TerminalSettings(
        repo_root=root,
        bind="127.0.0.1",
        port=8022,
        session_secret="a" * 64,
        audit_path=root / "audit.jsonl",
        projects=(
            TerminalProject(slug="gaia", name="Gaia", path=root / "gaia"),
        ),
        command_timeout_seconds=120,
        max_output_bytes=4096,
    )


class TerminalSessionTests(unittest.TestCase):
    def test_session_and_csrf_are_bound_together(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = terminal_settings(Path(directory))
            application = TerminalApplication(settings)
            session, csrf_token = application.create_session()

            self.assertTrue(application.valid_session(session))
            self.assertTrue(application.valid_csrf(session, csrf_token))
            self.assertFalse(application.valid_csrf(session, "wrong"))
            self.assertFalse(application.valid_session(session + "x"))

    def test_websocket_protocol_accepts_masked_client_frames(self) -> None:
        self.assertEqual(
            websocket_accept("dGhlIHNhbXBsZSBub25jZQ=="),
            "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=",
        )
        server_socket, client_socket = socket.socketpair()
        self.addCleanup(server_socket.close)
        self.addCleanup(client_socket.close)
        payload = b'{"type":"input","data":"nano test.txt"}'
        mask = b"\x01\x02\x03\x04"
        masked = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
        client_socket.sendall(bytes([0x81, 0x80 | len(payload)]) + mask + masked)

        frame = receive_frame(server_socket)

        self.assertEqual(frame.opcode, 0x1)
        self.assertEqual(frame.payload, payload)

    def test_websocket_server_frames_are_unmasked(self) -> None:
        server_socket, client_socket = socket.socketpair()
        self.addCleanup(server_socket.close)
        self.addCleanup(client_socket.close)

        send_frame(server_socket, b"nano", opcode=0x2)

        self.assertEqual(client_socket.recv(6), b"\x82\x04nano")


class WorkstationTunnelContractTests(unittest.TestCase):
    def test_home_reporter_maintains_terminal_tunnel_without_affecting_office(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        manager = (repository / "deployment" / "workstations" / "Manage-DeveloperOSWorkstationReporter.ps1").read_text(
            encoding="utf-8"
        )
        reporter = (repository / "deployment" / "workstations" / "Report-DeveloperOSGitStatus.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn('if ($Workstation -eq "home") { "-MaintainTerminalTunnel" }', manager)
        self.assertIn('[switch]$MaintainTerminalTunnel', reporter)
        self.assertIn('$MaintainTerminalTunnel -and $Workstation -eq "home"', reporter)
        self.assertIn('Ensure-DeveloperOSServerTerminalTunnel.ps1', reporter)
        self.assertIn('WARNING terminal tunnel unavailable', reporter)


class TerminalRunnerTests(unittest.TestCase):
    def test_command_runs_in_allowlisted_project_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project_path = root / "gaia"
            project_path.mkdir()
            runner = TerminalRunner(
                (TerminalProject("gaia", "Gaia", project_path),),
                root / "audit.jsonl",
                timeout_seconds=10,
                max_output_bytes=4096,
            )
            completed = subprocess.CompletedProcess(
                args=["/bin/bash", "-lc", "pwd"],
                returncode=0,
                stdout="/srv/gaia\n",
            )
            with patch("console.devos_terminal.runner.subprocess.run", return_value=completed) as run:
                result = runner.execute("gaia", "pwd")

            self.assertTrue(result.ok)
            self.assertEqual(result.output, "/srv/gaia\n")
            self.assertEqual(run.call_args.kwargs["cwd"], project_path)
            audit = (root / "audit.jsonl").read_text(encoding="utf-8")
            self.assertNotIn("pwd", audit)
            self.assertIn("command_sha256", audit)

    def test_terminal_session_audit_records_metadata_without_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project_path = root / "gaia"
            project_path.mkdir()
            runner = TerminalRunner(
                (TerminalProject("gaia", "Gaia", project_path),),
                root / "audit.jsonl",
                timeout_seconds=10,
                max_output_bytes=4096,
            )

            runner.audit_terminal_session("gaia", "terminal_opened")
            runner.audit_terminal_session("gaia", "terminal_closed", 1250)

            audit = (root / "audit.jsonl").read_text(encoding="utf-8")
            self.assertIn('"event":"terminal_opened"', audit)
            self.assertIn('"duration_ms":1250', audit)
            self.assertNotIn("command", audit)

    def test_interactive_terminal_assets_use_xterm_and_websocket_pty(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        page = (repository / "console" / "terminal_static" / "index.html").read_text(encoding="utf-8")
        javascript = (repository / "console" / "terminal_static" / "terminal.js").read_text(encoding="utf-8")
        server = (repository / "console" / "devos_terminal" / "server.py").read_text(encoding="utf-8")
        readme = (repository / "console" / "README.md").read_text(encoding="utf-8")

        self.assertIn('/vendor/xterm/xterm.js?v=5.5.0', page)
        self.assertIn('/vendor/xterm/addon-fit.js?v=0.10.0', page)
        self.assertIn('/terminal.css?v=4', page)
        self.assertIn('/terminal.js?v=3', page)
        self.assertIn('id="terminal-viewport"', page)
        self.assertIn("new WebSocket(url)", javascript)
        self.assertIn("state.terminal.onData", javascript)
        self.assertIn('type: "resize"', javascript)
        self.assertIn('cursorBlink: false', javascript)
        self.assertIn('cursorInactiveStyle: "block"', javascript)
        stylesheet = (repository / "console" / "terminal_static" / "terminal.css").read_text(encoding="utf-8")
        self.assertIn('.xterm-cursor.xterm-cursor-block', stylesheet)
        self.assertIn('width: 1ch', stylesheet)
        self.assertIn("PtySession.open(project.path)", server)
        self.assertIn("actual Linux PTY", readme)
        self.assertNotIn("Interactive programs\nsuch as editors", readme)

    def test_unknown_project_and_long_command_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project_path = root / "gaia"
            project_path.mkdir()
            runner = TerminalRunner(
                (TerminalProject("gaia", "Gaia", project_path),),
                root / "audit.jsonl",
                timeout_seconds=10,
                max_output_bytes=4096,
            )
            with self.assertRaisesRegex(ValueError, "Unknown project"):
                runner.execute("oa", "pwd")
            with self.assertRaisesRegex(ValueError, "at most"):
                runner.execute("gaia", "x" * (MAX_COMMAND_LENGTH + 1))

    def test_unavailable_project_is_reported_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = TerminalRunner(
                (TerminalProject("gaia", "Gaia", root / "missing"),),
                root / "audit.jsonl",
                timeout_seconds=10,
                max_output_bytes=4096,
            )
            self.assertEqual(
                runner.projects(),
                [{"slug": "gaia", "name": "Gaia", "available": False}],
            )
            with self.assertRaisesRegex(ValueError, "unavailable"):
                runner.execute("gaia", "pwd")

    def test_server_workspace_context_is_allowlisted_without_root_privilege(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        example = (repository / "console" / "terminal-config.example.json").read_text(encoding="utf-8")
        deployment = (repository / "deployment" / "console" / "Manage-DeveloperOSConsole.ps1").read_text(encoding="utf-8")

        self.assertIn('"slug": "server"', example)
        self.assertIn('"path": "X:/Projects"', example)
        self.assertIn('{"slug":"server","name":"Server","path":"/home/opc"}', deployment)
        self.assertNotIn('{"slug":"server","name":"Server","path":"/"}', deployment)


if __name__ == "__main__":
    unittest.main()
