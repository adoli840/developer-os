from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).parents[1] / "native_docker.py"
SEAL_SCRIPT_PATH = Path(__file__).parents[1] / "Seal-NativeDockerInfrastructure.ps1"
WINDOWS_DOCKER_SHIM_PATH = Path(__file__).parents[1] / "windows-cli" / "docker.cmd"
SPEC = importlib.util.spec_from_file_location("devos_native_docker", MODULE_PATH)
assert SPEC and SPEC.loader
native_docker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(native_docker)


class NativeDockerLauncherTests(unittest.TestCase):
    def test_docker_command_binds_distro_socket_config_cli_and_cwd(self) -> None:
        command = native_docker.build_wsl_command(
            r"X:\Projects\bTest", ["ps", "--all"]
        )
        self.assertEqual(command[:6], ["wsl.exe", "-d", "Ubuntu", "--cd", "/mnt/x/Projects/bTest", "--"])
        self.assertIn("DOCKER_HOST=unix:///run/docker-wsl.sock", command)
        self.assertIn("DOCKER_CONFIG=/home/devops/.docker-native", command)
        self.assertIn("DOCKER_CONTEXT", command)
        self.assertIn("DOCKER_TLS_VERIFY", command)
        self.assertIn("DOCKER_CERT_PATH", command)
        self.assertEqual(command[-3:], ["/usr/bin/docker", "ps", "--all"])

    def test_compose_uses_native_binary_and_preserves_arguments(self) -> None:
        command = native_docker.build_wsl_command(
            r"X:\Projects\oa", ["compose", "-f", "docker-compose.yml", "up", "--no-build"]
        )
        self.assertEqual(command[-5:], [
            "/usr/libexec/docker/cli-plugins/docker-compose",
            "-f",
            "docker-compose.yml",
            "up",
            "--no-build",
        ])

    def test_endpoint_config_and_context_overrides_are_rejected(self) -> None:
        for arguments in (["--host=tcp://example", "ps"], ["--context", "desktop-linux", "ps"], ["--config=x", "ps"]):
            with self.subTest(arguments=arguments):
                with self.assertRaisesRegex(native_docker.NativeDockerError, "OVERRIDE_FORBIDDEN"):
                    native_docker.build_wsl_command(r"X:\Projects\bTest", arguments)

    def test_mutating_context_commands_are_rejected(self) -> None:
        with self.assertRaisesRegex(native_docker.NativeDockerError, "CONTEXT_MUTATION_FORBIDDEN"):
            native_docker.build_wsl_command(r"X:\Projects\bTest", ["context", "use", "default"])

    def test_exit_code_is_preserved(self) -> None:
        with patch.object(native_docker.subprocess, "run") as run:
            run.return_value.returncode = 23
            self.assertEqual(native_docker.run(r"X:\Projects\bTest", ["ps"]), 23)

    def test_seal_audit_history_is_append_only(self) -> None:
        script = SEAL_SCRIPT_PATH.read_text(encoding="utf-8-sig")
        self.assertIn("native-docker-infrastructure-audit.jsonl", script)
        self.assertIn("Add-Content -LiteralPath $auditHistoryPath", script)

    def test_windows_docker_shim_delegates_to_canonical_launcher(self) -> None:
        shim = WINDOWS_DOCKER_SHIM_PATH.read_text(encoding="ascii")
        self.assertIn(r"..\..\bin\devos-native-docker.cmd", shim)
        self.assertIn("%*", shim)
        self.assertNotIn("docker.exe", shim.lower())


if __name__ == "__main__":
    unittest.main()
