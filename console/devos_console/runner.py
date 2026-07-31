from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Sequence


MAX_OUTPUT = 80_000
_docker_prefix: tuple[str, ...] | None = None
_docker_lock = Lock()


@dataclass(frozen=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


def run_command(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    timeout: float = 15,
) -> CommandResult:
    command = tuple(str(value) for value in args)
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=creationflags,
            check=False,
        )
        return CommandResult(
            args=command,
            returncode=completed.returncode,
            stdout=completed.stdout[-MAX_OUTPUT:],
            stderr=completed.stderr[-MAX_OUTPUT:],
        )
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout.decode("utf-8", "replace") if isinstance(error.stdout, bytes) else (error.stdout or "")
        stderr = error.stderr.decode("utf-8", "replace") if isinstance(error.stderr, bytes) else (error.stderr or "")
        return CommandResult(
            args=command,
            returncode=124,
            stdout=stdout[-MAX_OUTPUT:],
            stderr=stderr[-MAX_OUTPUT:],
            timed_out=True,
        )
    except OSError as error:
        return CommandResult(command, 127, "", str(error))


def docker_prefix() -> tuple[str, ...]:
    global _docker_prefix
    with _docker_lock:
        if _docker_prefix is not None:
            return _docker_prefix
        if shutil.which("docker"):
            direct = run_command(("docker", "info"), timeout=4)
            if direct.ok:
                _docker_prefix = ("docker",)
                return _docker_prefix
        if os.name != "nt" and shutil.which("sudo") and shutil.which("docker"):
            elevated = run_command(("sudo", "-n", "docker", "info"), timeout=4)
            if elevated.ok:
                _docker_prefix = ("sudo", "-n", "docker")
                return _docker_prefix
        _docker_prefix = ("docker",)
        return _docker_prefix


def run_docker(args: Sequence[str], *, timeout: float = 15) -> CommandResult:
    return run_command((*docker_prefix(), *args), timeout=timeout)
