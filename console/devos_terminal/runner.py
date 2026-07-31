from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import TextIO

from .settings import TerminalProject


MAX_COMMAND_LENGTH = 4096


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    returncode: int | None
    output: str
    duration_ms: int
    timed_out: bool
    truncated: bool


class TerminalRunner:
    def __init__(
        self,
        projects: tuple[TerminalProject, ...],
        audit_path: Path,
        timeout_seconds: int,
        max_output_bytes: int,
    ) -> None:
        self._projects = {project.slug: project for project in projects}
        self._locks = {project.slug: Lock() for project in projects}
        self._audit_path = audit_path
        self._audit_lock = Lock()
        self._timeout_seconds = timeout_seconds
        self._max_output_bytes = max_output_bytes

    def projects(self) -> list[dict[str, object]]:
        return [
            {
                "slug": project.slug,
                "name": project.name,
                "available": project.path.is_dir(),
            }
            for project in self._projects.values()
        ]

    def execute(self, project_slug: str, command: str) -> CommandResult:
        project = self._projects.get(project_slug)
        if project is None:
            raise ValueError("Unknown project.")
        if not project.path.is_dir():
            raise ValueError("The project directory is unavailable.")
        normalized = command.strip()
        if not normalized:
            raise ValueError("Command cannot be empty.")
        if "\x00" in normalized or len(normalized) > MAX_COMMAND_LENGTH:
            raise ValueError(f"Command must be at most {MAX_COMMAND_LENGTH} characters.")

        lock = self._locks[project_slug]
        if not lock.acquire(blocking=False):
            raise RuntimeError("Another command is already running for this project.")
        started = time.monotonic()
        returncode: int | None = None
        timed_out = False
        output = ""
        try:
            environment = {
                "HOME": os.getenv("HOME", "/home/opc"),
                "LANG": os.getenv("LANG", "C.UTF-8"),
                "LC_ALL": os.getenv("LC_ALL", "C.UTF-8"),
                "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                "TERM": "xterm-256color",
            }
            try:
                completed = subprocess.run(
                    [
                        "/usr/bin/timeout",
                        "--kill-after=5",
                        str(self._timeout_seconds),
                        "/bin/bash",
                        "-lc",
                        normalized,
                    ],
                    cwd=project.path,
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self._timeout_seconds + 10,
                    stdin=subprocess.DEVNULL,
                    check=False,
                )
                returncode = completed.returncode
                output = completed.stdout
                if returncode in {124, 137}:
                    timed_out = True
                    output += f"\nCommand stopped after {self._timeout_seconds} seconds."
            except subprocess.TimeoutExpired as error:
                timed_out = True
                raw_output = error.stdout or ""
                output = raw_output.decode("utf-8", "replace") if isinstance(raw_output, bytes) else raw_output
                output += f"\nCommand stopped after {self._timeout_seconds} seconds."

            encoded = output.encode("utf-8", "replace")
            truncated = len(encoded) > self._max_output_bytes
            if truncated:
                output = encoded[-self._max_output_bytes :].decode("utf-8", "replace")
                output = "[Earlier output truncated]\n" + output
            duration_ms = int((time.monotonic() - started) * 1000)
            result = CommandResult(
                ok=returncode == 0 and not timed_out,
                returncode=returncode,
                output=output,
                duration_ms=duration_ms,
                timed_out=timed_out,
                truncated=truncated,
            )
            self._audit(
                project=project_slug,
                command_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
                returncode=returncode,
                timed_out=timed_out,
                duration_ms=duration_ms,
            )
            return result
        finally:
            lock.release()

    def _audit(self, **fields: object) -> None:
        entry = {"timestamp": int(time.time()), **fields}
        with self._audit_lock:
            with self._audit_path.open("a", encoding="utf-8") as handle:
                self._write_json_line(handle, entry)

    @staticmethod
    def _write_json_line(handle: TextIO, entry: dict[str, object]) -> None:
        handle.write(json.dumps(entry, ensure_ascii=True, separators=(",", ":")) + "\n")
