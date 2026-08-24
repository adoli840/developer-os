from __future__ import annotations

import argparse
import ntpath
import os
import subprocess
import sys
from pathlib import PurePosixPath
from typing import Sequence


DISTRO = "Ubuntu"
DOCKER_HOST = "unix:///run/docker-wsl.sock"
DOCKER_CONFIG = "/home/devops/.docker-native"
DOCKER_CLI = "/usr/bin/docker"
COMPOSE_CLI = "/usr/libexec/docker/cli-plugins/docker-compose"


class NativeDockerError(RuntimeError):
    pass


def windows_to_wsl_path(value: str) -> str:
    normalized = ntpath.abspath(value)
    drive, tail = ntpath.splitdrive(normalized)
    if len(drive) != 2 or drive[1] != ":" or not tail.startswith(("\\", "/")):
        raise NativeDockerError("WORKING_DIRECTORY_MUST_BE_A_WINDOWS_DRIVE_PATH")
    parts = [part for part in tail.replace("\\", "/").split("/") if part]
    if any(part == ".." for part in parts):
        raise NativeDockerError("INVALID_WORKING_DIRECTORY")
    return str(PurePosixPath("/mnt") / drive[0].lower() / PurePosixPath(*parts))


def _reject_boundary_override(arguments: Sequence[str]) -> None:
    forbidden = {"-H", "--host", "--context", "--config"}
    for argument in arguments:
        if argument in forbidden or any(
            argument.startswith(prefix) for prefix in ("--host=", "--context=", "--config=")
        ):
            raise NativeDockerError("CANONICAL_DOCKER_BOUNDARY_OVERRIDE_FORBIDDEN")
    if len(arguments) >= 2 and arguments[0] == "context" and arguments[1] not in {
        "inspect",
        "ls",
        "show",
    }:
        raise NativeDockerError("CANONICAL_DOCKER_CONTEXT_MUTATION_FORBIDDEN")


def build_wsl_command(working_directory: str, arguments: Sequence[str]) -> list[str]:
    if not arguments:
        raise NativeDockerError("DOCKER_COMMAND_REQUIRED")
    _reject_boundary_override(arguments)
    wsl_directory = windows_to_wsl_path(working_directory)
    command_arguments = list(arguments)
    executable = DOCKER_CLI
    if command_arguments[0] == "compose":
        executable = COMPOSE_CLI
        command_arguments = command_arguments[1:]
    return [
        "wsl.exe",
        "-d",
        DISTRO,
        "--cd",
        wsl_directory,
        "--",
        "env",
        "-u",
        "DOCKER_CONTEXT",
        "-u",
        "DOCKER_TLS_VERIFY",
        "-u",
        "DOCKER_CERT_PATH",
        f"DOCKER_HOST={DOCKER_HOST}",
        f"DOCKER_CONFIG={DOCKER_CONFIG}",
        executable,
        *command_arguments,
    ]


def run(working_directory: str, arguments: Sequence[str]) -> int:
    command = build_wsl_command(working_directory, arguments)
    try:
        return subprocess.run(command, check=False).returncode
    except OSError as error:
        print(f"Native Docker launcher failed: {error}", file=sys.stderr)
        return 127


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Docker through the canonical Ubuntu WSL native daemon boundary."
    )
    parser.add_argument("--working-directory", default=os.getcwd())
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    values = parser.parse_args(argv)
    arguments = list(values.arguments)
    if arguments and arguments[0] == "--":
        arguments = arguments[1:]
    try:
        return run(values.working_directory, arguments)
    except NativeDockerError as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
