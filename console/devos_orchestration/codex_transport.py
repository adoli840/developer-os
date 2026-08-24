from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from threading import Thread
from typing import Any, Callable, Protocol


REQUIRED_CLIENT_METHODS = {
    "initialize", "thread/read", "thread/start", "thread/resume",
    "turn/start", "turn/interrupt",
}
REQUIRED_NOTIFICATIONS = {"turn/started", "turn/completed"}
APPROVAL_METHODS = {
    "item/commandExecution/requestApproval",
    "item/fileChange/requestApproval",
    "item/permissions/requestApproval",
    "item/tool/requestUserInput",
    "mcpServer/elicitation/request",
    "applyPatchApproval",
    "execCommandApproval",
}
TERMINAL_TURN_STATUSES = {"completed", "failed", "interrupted"}
CAPABILITY_NAMES = (
    "READ_THREAD", "START_OR_RESUME_THREAD", "SEND_TURN", "STREAM_EVENTS",
    "RECEIVE_COMPLETION", "RECEIVE_APPROVAL_REQUEST",
)


class CodexTransportError(RuntimeError):
    pass


class CodexTransportTimeout(CodexTransportError):
    pass


class CodexProtocolRequestError(CodexTransportError):
    def __init__(
        self,
        method: str,
        code: Any,
        message: str,
        diagnostics: dict[str, Any] | None = None,
    ) -> None:
        super().__init__("CODEX_PROTOCOL_REQUEST_FAILED")
        self.method = method
        self.code = code if isinstance(code, int) else None
        self.provider_message = _sanitize_diagnostic(message)[:500]
        self.diagnostics = diagnostics or {}


class CodexRuntimeUnavailable(CodexTransportError):
    def __init__(self, stage: str, message: str, diagnostics: dict[str, Any] | None = None) -> None:
        super().__init__("CODEX_RUNTIME_UNAVAILABLE")
        self.stage = stage
        self.provider_message = _sanitize_diagnostic(message)[:500]
        self.diagnostics = diagnostics or {}


class CodexApprovalRequired(CodexTransportError):
    def __init__(self, method: str, request_id: Any) -> None:
        super().__init__("CODEX_APPROVAL_REQUIRED")
        self.method = method
        self.request_id = request_id


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sanitize_diagnostic(value: str) -> str:
    value = re.sub(r"(?i)bearer\s+\S+", "Bearer [REDACTED]", value)
    value = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "[REDACTED_API_KEY]", value)
    value = re.sub(
        r"(?i)(OPENAI(?:_[A-Z0-9]+)*_API_KEY\s*[=:]\s*)\S+",
        r"\1[REDACTED]",
        value,
    )
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _schema_methods_value(value: Any) -> set[str]:
    found: set[str] = set()

    def walk(item: Any) -> None:
        if isinstance(item, dict):
            method = item.get("properties", {}).get("method")
            if isinstance(method, dict):
                if isinstance(method.get("const"), str):
                    found.add(method["const"])
                for candidate in method.get("enum", []):
                    if isinstance(candidate, str):
                        found.add(candidate)
            for child in item.values():
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)

    walk(value)
    return found


def _schema_methods(path: Path) -> set[str]:
    return _schema_methods_value(json.loads(path.read_text(encoding="utf-8")))


@dataclass(frozen=True)
class CodexProtocolProfile:
    cli_version: str
    schema_bundle_sha256: str
    client_methods: frozenset[str]
    server_notifications: frozenset[str]
    server_requests: frozenset[str]
    discovered_at: str

    def supports_required_contract(self) -> bool:
        return (
            REQUIRED_CLIENT_METHODS <= self.client_methods
            and REQUIRED_NOTIFICATIONS <= self.server_notifications
            and APPROVAL_METHODS <= self.server_requests
        )


class CodexProtocolDiscovery:
    def __init__(self, executable: str = "codex", timeout_seconds: float = 30.0) -> None:
        self.executable = executable
        self.timeout_seconds = timeout_seconds

    def discover(self) -> CodexProtocolProfile:
        version = subprocess.run(
            [self.executable, "--version"], check=True, capture_output=True,
            text=True, timeout=self.timeout_seconds,
        ).stdout.strip()
        with tempfile.TemporaryDirectory(prefix="devos-codex-schema-") as directory:
            subprocess.run(
                [self.executable, "app-server", "generate-json-schema", "--experimental", "--out", directory],
                check=True, capture_output=True, text=True, timeout=self.timeout_seconds,
            )
            root = Path(directory)
            required = [root / name for name in (
                "ClientRequest.json", "ServerNotification.json", "ServerRequest.json",
                "codex_app_server_protocol.schemas.json",
            )]
            if any(not path.is_file() for path in required):
                raise CodexTransportError("CODEX_PROTOCOL_SCHEMA_INCOMPLETE")
            return CodexProtocolProfile(
                cli_version=version,
                schema_bundle_sha256=_sha256(required[-1]),
                client_methods=frozenset(_schema_methods(required[0])),
                server_notifications=frozenset(_schema_methods(required[1])),
                server_requests=frozenset(_schema_methods(required[2])),
                discovered_at=_now(),
            )


@dataclass(frozen=True)
class CodexThreadBinding:
    thread_id: str
    workspace: str

    @classmethod
    def parse(cls, transport_ref: str) -> "CodexThreadBinding":
        try:
            value = json.loads(transport_ref)
        except (TypeError, json.JSONDecodeError) as error:
            raise CodexTransportError("INVALID_CODEX_THREAD_BINDING") from error
        if not isinstance(value, dict) or set(value) != {"thread_id", "workspace"}:
            raise CodexTransportError("INVALID_CODEX_THREAD_BINDING")
        thread_id = value["thread_id"]
        workspace = value["workspace"]
        if not isinstance(thread_id, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", thread_id):
            raise CodexTransportError("INVALID_CODEX_THREAD_ID")
        windows_absolute = isinstance(workspace, str) and Path(workspace).is_absolute()
        wsl_path = PurePosixPath(workspace) if isinstance(workspace, str) else None
        wsl_absolute = bool(
            wsl_path
            and wsl_path.is_absolute()
            and ".." not in wsl_path.parts
        )
        if not isinstance(workspace, str) or not (windows_absolute or wsl_absolute):
            raise CodexTransportError("INVALID_CODEX_WORKSPACE")
        return cls(thread_id, workspace)

    def public_summary(self) -> dict[str, Any]:
        return {
            "thread_bound": True,
            "workspace_bound": True,
            "workspace_name": Path(self.workspace).name,
        }


@dataclass(frozen=True)
class CodexWorkspaceBinding:
    project: str
    runtime: str
    distro: str
    windows_workspace: str
    wsl_workspace: str
    workspace_identity_sha256: str
    git_branch: str
    git_head: str
    git_status_sha256: str
    git_status_entry_count: int

    @classmethod
    def parse(cls, transport_ref: str) -> "CodexWorkspaceBinding":
        try:
            value = json.loads(transport_ref)
        except (TypeError, json.JSONDecodeError) as error:
            raise CodexTransportError("INVALID_CODEX_WORKSPACE_BINDING") from error
        required = {
            "binding_type", "binding_version", "project", "runtime", "distro",
            "windows_workspace", "wsl_workspace", "workspace_identity_sha256",
            "git_branch", "git_head", "git_status_sha256", "git_status_entry_count",
        }
        if not isinstance(value, dict) or set(value) != required:
            raise CodexTransportError("INVALID_CODEX_WORKSPACE_BINDING")
        if value["binding_type"] != "WORKSPACE_ONLY" or value["binding_version"] != "1":
            raise CodexTransportError("INVALID_CODEX_WORKSPACE_BINDING")
        if value["runtime"] != "WSL_CODEX_APP_SERVER" or value["distro"] != "Ubuntu":
            raise CodexTransportError("INVALID_CODEX_WORKSPACE_RUNTIME")
        windows_workspace = str(value["windows_workspace"])
        wsl_workspace = str(value["wsl_workspace"])
        if not Path(windows_workspace).is_absolute() or not PurePosixPath(wsl_workspace).is_absolute():
            raise CodexTransportError("INVALID_CODEX_WORKSPACE")
        for name in ("workspace_identity_sha256", "git_status_sha256"):
            if not re.fullmatch(r"[0-9a-f]{64}", str(value[name])):
                raise CodexTransportError("INVALID_CODEX_WORKSPACE_FINGERPRINT")
        if not re.fullmatch(r"[0-9a-f]{40}", str(value["git_head"])):
            raise CodexTransportError("INVALID_CODEX_WORKSPACE_FINGERPRINT")
        if not isinstance(value["git_status_entry_count"], int) or value["git_status_entry_count"] < 0:
            raise CodexTransportError("INVALID_CODEX_WORKSPACE_FINGERPRINT")
        return cls(
            project=str(value["project"]), runtime=str(value["runtime"]),
            distro=str(value["distro"]), windows_workspace=windows_workspace,
            wsl_workspace=wsl_workspace,
            workspace_identity_sha256=str(value["workspace_identity_sha256"]),
            git_branch=str(value["git_branch"]), git_head=str(value["git_head"]),
            git_status_sha256=str(value["git_status_sha256"]),
            git_status_entry_count=value["git_status_entry_count"],
        )

    def public_summary(self) -> dict[str, Any]:
        return {
            "thread_bound": False,
            "workspace_bound": True,
            "workspace_name": PurePosixPath(self.wsl_workspace).name,
            "windows_workspace": self.windows_workspace,
            "wsl_workspace": self.wsl_workspace,
            "workspace_identity_sha256": self.workspace_identity_sha256,
            "git_branch": self.git_branch,
            "git_head": self.git_head,
            "git_status_sha256": self.git_status_sha256,
            "git_status_entry_count": self.git_status_entry_count,
            "workspace_guard": "ARMED",
            "developeros_turn_policy": "SINGLE_ACTIVE_TURN",
        }


class MessageChannel(Protocol):
    def send(self, message: dict[str, Any]) -> None: ...
    def receive(self, timeout_seconds: float) -> dict[str, Any]: ...
    def close(self) -> None: ...


class JsonLineProcessChannel:
    def __init__(self, command: list[str], *, cwd: str | None = None) -> None:
        try:
            self.process = subprocess.Popen(
                command, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1,
            )
        except OSError as error:
            raise CodexRuntimeUnavailable(
                "process_start", str(error), {"process_exit_code": None, "stderr_line_count": 0},
            ) from error
        self._messages: queue.Queue[object] = queue.Queue()
        self.stderr_lines: list[str] = []
        Thread(target=self._read, daemon=True, name="codex-app-server-reader").start()
        Thread(target=self._read_stderr, daemon=True, name="codex-app-server-stderr").start()

    def _read(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            try:
                self._messages.put(json.loads(line))
            except json.JSONDecodeError:
                self._messages.put(CodexTransportError("MALFORMED_CODEX_PROTOCOL"))
                return
        self._messages.put(CodexTransportError("CODEX_APP_SERVER_EXITED"))

    def _read_stderr(self) -> None:
        if self.process.stderr is None:
            return
        for line in self.process.stderr:
            if len(self.stderr_lines) < 200:
                self.stderr_lines.append(line.rstrip())

    def send(self, message: dict[str, Any]) -> None:
        if self.process.poll() is not None or self.process.stdin is None:
            raise CodexTransportError("CODEX_APP_SERVER_EXITED")
        self.process.stdin.write(json.dumps(message, ensure_ascii=True, separators=(",", ":")) + "\n")
        self.process.stdin.flush()

    def receive(self, timeout_seconds: float) -> dict[str, Any]:
        try:
            value = self._messages.get(timeout=timeout_seconds)
        except queue.Empty as error:
            raise CodexTransportTimeout("CODEX_APP_SERVER_TIMEOUT") from error
        if isinstance(value, Exception):
            raise value
        if not isinstance(value, dict):
            raise CodexTransportError("MALFORMED_CODEX_PROTOCOL")
        return value

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def safe_diagnostics(self) -> dict[str, Any]:
        safe_lines = [_sanitize_diagnostic(line)[:500] for line in self.stderr_lines[-5:]]
        stderr_bytes = "\n".join(safe_lines).encode("utf-8")
        return {
            "process_exit_code": self.process.poll(),
            "stderr_line_count": len(self.stderr_lines),
            "safe_stderr_sha256": hashlib.sha256(stderr_bytes).hexdigest(),
            "safe_stderr_tail": safe_lines,
        }


@dataclass(frozen=True)
class CodexRuntimeProfile:
    runtime_kind: str
    distro: str | None
    command_source: str
    command_path: str
    cli_version: str
    launch_cwd: str
    schema_bundle_sha256: str
    initialize_status: str
    initialized_status: str
    process_alive: bool


class CodexRuntimeLauncher:
    """Resolve and launch the installed CLI without copying package assets."""

    def __init__(self, command: str = "codex", *, timeout_seconds: float = 30.0) -> None:
        self.command = command
        self.timeout_seconds = timeout_seconds

    def resolve(self) -> tuple[str, str]:
        resolved = shutil.which(self.command)
        if not resolved:
            raise CodexRuntimeUnavailable("resolution", "Codex CLI was not found on PATH")
        return "PATH", str(Path(resolved))

    def preflight(self, launch_cwd: Path) -> tuple[CodexRuntimeProfile, CodexProtocolProfile]:
        source, path = self.resolve()
        try:
            protocol = CodexProtocolDiscovery(path, self.timeout_seconds).discover()
        except (OSError, subprocess.SubprocessError, CodexTransportError) as error:
            raise CodexRuntimeUnavailable(
                "schema_discovery",
                str(error),
                {
                    "command_source": source,
                    "command_path": path,
                    "launch_cwd": str(launch_cwd),
                    "process_exit_code": None,
                    "stderr_line_count": 0,
                },
            ) from error
        channel = JsonLineProcessChannel(
            [path, "app-server", "--listen", "stdio://"], cwd=str(launch_cwd),
        )
        adapter = CodexAppServerAdapter(channel, timeout_seconds=self.timeout_seconds)
        try:
            adapter.initialize()
            time.sleep(0.1)
            alive = channel.process.poll() is None
            if not alive:
                raise CodexRuntimeUnavailable(
                    "initialized", "Codex App Server exited after initialization",
                    channel.safe_diagnostics(),
                )
            runtime = CodexRuntimeProfile(
                runtime_kind="WINDOWS_NATIVE",
                distro=None,
                command_source=source,
                command_path=path,
                cli_version=protocol.cli_version,
                launch_cwd=str(launch_cwd),
                schema_bundle_sha256=protocol.schema_bundle_sha256,
                initialize_status="PASS",
                initialized_status="PASS",
                process_alive=True,
            )
            return runtime, protocol
        except CodexProtocolRequestError as error:
            raise CodexRuntimeUnavailable(
                "initialize", error.provider_message, channel.safe_diagnostics(),
            ) from error
        except (CodexTransportError, OSError) as error:
            raise CodexRuntimeUnavailable(
                "initialize", str(error), channel.safe_diagnostics(),
            ) from error
        finally:
            adapter.close()


class WslCodexProtocolDiscovery:
    def __init__(
        self,
        distro: str = "Ubuntu",
        codex_path: str = "/home/devops/.local/bin/codex",
        *,
        wsl_executable: str = "wsl.exe",
        timeout_seconds: float = 30.0,
    ) -> None:
        self.distro = distro
        self.codex_path = codex_path
        self.wsl_executable = wsl_executable
        self.timeout_seconds = timeout_seconds

    def command(self, *args: str) -> list[str]:
        return [self.wsl_executable, "-d", self.distro, "--", self.codex_path, *args]

    def _run(self, args: list[str], *, text: bool = True) -> subprocess.CompletedProcess[Any]:
        options: dict[str, Any] = {
            "check": True,
            "capture_output": True,
            "text": text,
            "timeout": self.timeout_seconds,
        }
        if text:
            options.update({"encoding": "utf-8", "errors": "replace"})
        return subprocess.run(
            [self.wsl_executable, "-d", self.distro, "--", *args], **options,
        )

    def resolve(self) -> str:
        result = self._run(["readlink", "-f", self.codex_path]).stdout.strip()
        if not result.startswith("/") or result.startswith("/mnt/"):
            raise CodexRuntimeUnavailable("resolution", "Codex path is not Linux-native")
        self._run(["test", "-x", result])
        return result

    def login_ready(self) -> bool:
        result = self._run([self.codex_path, "login", "status"])
        status = f"{result.stdout}\n{result.stderr}"
        return "Logged in" in status

    def discover(self) -> tuple[str, CodexProtocolProfile]:
        resolved = self.resolve()
        version = self._run([resolved, "--version"]).stdout.strip()
        directory = f"/tmp/devos-codex-schema-{uuid.uuid4().hex}"
        self._run(["mkdir", "-m", "700", directory])
        try:
            self._run([
                resolved, "app-server", "generate-json-schema", "--experimental",
                "--out", directory,
            ])
            names = (
                "ClientRequest.json", "ServerNotification.json", "ServerRequest.json",
                "codex_app_server_protocol.schemas.json",
            )
            contents: list[bytes] = []
            for name in names:
                contents.append(self._run(["cat", f"{directory}/{name}"], text=False).stdout)
            values = [json.loads(content.decode("utf-8")) for content in contents]
            profile = CodexProtocolProfile(
                cli_version=version,
                schema_bundle_sha256=hashlib.sha256(contents[-1]).hexdigest(),
                client_methods=frozenset(_schema_methods_value(values[0])),
                server_notifications=frozenset(_schema_methods_value(values[1])),
                server_requests=frozenset(_schema_methods_value(values[2])),
                discovered_at=_now(),
            )
            return resolved, profile
        finally:
            self._run(["rm", "-rf", "--", directory])


class WslCodexRuntimeLauncher:
    """Launch the orchestration-only Linux CLI through bounded wsl.exe stdio."""

    def __init__(
        self,
        distro: str = "Ubuntu",
        codex_path: str = "/home/devops/.local/bin/codex",
        *,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.discovery = WslCodexProtocolDiscovery(
            distro,
            codex_path,
            timeout_seconds=timeout_seconds,
        )
        self.timeout_seconds = timeout_seconds

    def app_server_command(self, resolved_path: str | None = None) -> list[str]:
        return self.discovery.command(
            "app-server", "--listen", "stdio://",
        ) if resolved_path is None else [
            self.discovery.wsl_executable, "-d", self.discovery.distro, "--",
            resolved_path, "app-server", "--listen", "stdio://",
        ]

    def preflight(self, launch_cwd: Path) -> tuple[CodexRuntimeProfile, CodexProtocolProfile]:
        try:
            resolved, protocol = self.discovery.discover()
            if not self.discovery.login_ready():
                raise CodexRuntimeUnavailable("authentication", "Codex CLI is not logged in")
        except (OSError, subprocess.SubprocessError, CodexTransportError, ValueError) as error:
            if isinstance(error, CodexRuntimeUnavailable):
                raise
            raise CodexRuntimeUnavailable(
                "schema_discovery",
                str(error),
                {
                    "command_source": f"WSL:{self.discovery.distro}",
                    "command_path": self.discovery.codex_path,
                    "launch_cwd": str(launch_cwd),
                },
            ) from error
        channel = JsonLineProcessChannel(
            self.app_server_command(resolved), cwd=str(launch_cwd),
        )
        adapter = CodexAppServerAdapter(channel, timeout_seconds=self.timeout_seconds)
        try:
            adapter.initialize()
            time.sleep(0.1)
            if channel.process.poll() is not None:
                raise CodexRuntimeUnavailable(
                    "initialized", "WSL Codex App Server exited after initialization",
                    channel.safe_diagnostics(),
                )
            return CodexRuntimeProfile(
                runtime_kind="WSL",
                distro=self.discovery.distro,
                command_source=f"WSL:{self.discovery.distro}",
                command_path=resolved,
                cli_version=protocol.cli_version,
                launch_cwd=str(launch_cwd),
                schema_bundle_sha256=protocol.schema_bundle_sha256,
                initialize_status="PASS",
                initialized_status="PASS",
                process_alive=True,
            ), protocol
        except CodexProtocolRequestError as error:
            raise CodexRuntimeUnavailable(
                "initialize", error.provider_message, channel.safe_diagnostics(),
            ) from error
        except (CodexTransportError, OSError) as error:
            raise CodexRuntimeUnavailable(
                "initialize", str(error), channel.safe_diagnostics(),
            ) from error
        finally:
            adapter.close()


class CodexAppServerAdapter:
    """Version-discovered App Server client. Live turn start stays locked by default."""

    def __init__(
        self,
        channel: MessageChannel,
        *,
        timeout_seconds: float = 600.0,
        allow_turn_start: bool = False,
    ) -> None:
        if timeout_seconds <= 0 or timeout_seconds > 600:
            raise CodexTransportError("INVALID_CODEX_TIMEOUT")
        self.channel = channel
        self.timeout_seconds = timeout_seconds
        self.allow_turn_start = allow_turn_start
        self._request_id = 0
        self.initialized = False
        self._pending_events: list[dict[str, Any]] = []

    def _receive_before(self, deadline: float) -> dict[str, Any]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise CodexTransportTimeout("CODEX_APP_SERVER_TIMEOUT")
        return self.channel.receive(remaining)

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._request_id += 1
        request_id = self._request_id
        self.channel.send({"method": method, "id": request_id, "params": params})
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            message = self._receive_before(deadline)
            if message.get("method") in APPROVAL_METHODS and "id" in message:
                raise CodexApprovalRequired(str(message["method"]), message["id"])
            if message.get("id") == request_id:
                if "error" in message:
                    error = message.get("error")
                    if not isinstance(error, dict):
                        raise CodexTransportError("MALFORMED_CODEX_PROTOCOL")
                    raise CodexProtocolRequestError(
                        method,
                        error.get("code"),
                        str(error.get("message") or "Request failed"),
                        (
                            self.channel.safe_diagnostics()  # type: ignore[attr-defined]
                            if hasattr(self.channel, "safe_diagnostics") else {}
                        ),
                    )
                result = message.get("result")
                if not isinstance(result, dict):
                    raise CodexTransportError("MALFORMED_CODEX_PROTOCOL")
                return result
            if isinstance(message.get("method"), str):
                self._pending_events.append(message)

    def initialize(self) -> dict[str, Any]:
        result = self._request("initialize", {
            "clientInfo": {"name": "DeveloperOS", "title": "DeveloperOS", "version": "2B"},
            "capabilities": {"experimentalApi": True},
        })
        self.channel.send({"method": "initialized"})
        self.initialized = True
        return result

    def read_thread(self, thread_id: str, *, include_turns: bool = True) -> dict[str, Any]:
        return self._request("thread/read", {"threadId": thread_id, "includeTurns": include_turns})

    def resume_thread(self, binding: CodexThreadBinding) -> dict[str, Any]:
        return self._request("thread/resume", {
            "threadId": binding.thread_id, "cwd": binding.workspace,
            "runtimeWorkspaceRoots": [binding.workspace],
        })

    def start_thread(
        self,
        workspace: str,
        *,
        developer_instructions: str | None = None,
        sandbox: str = "read-only",
    ) -> dict[str, Any]:
        if not self.allow_turn_start:
            raise CodexTransportError("CODEX_THREAD_START_LOCKED")
        if sandbox not in {"read-only", "workspace-write"}:
            raise CodexTransportError("INVALID_CODEX_SANDBOX")
        return self._request("thread/start", {
            "cwd": workspace,
            "runtimeWorkspaceRoots": [workspace],
            "approvalPolicy": "on-request",
            "approvalsReviewer": "user",
            "sandbox": sandbox,
            "developerInstructions": developer_instructions or (
                "This is a transport-only smoke test. Do not use tools, read files, "
                "run commands, or modify any state. Reply briefly to the user message."
            ),
        })

    def start_turn(self, binding: CodexThreadBinding, message: str) -> dict[str, Any]:
        if not self.allow_turn_start:
            raise CodexTransportError("CODEX_TURN_START_LOCKED")
        return self._request("turn/start", {
            "threadId": binding.thread_id,
            "input": [{"type": "text", "text": message, "text_elements": []}],
            "cwd": binding.workspace,
            "runtimeWorkspaceRoots": [binding.workspace],
        })

    def interrupt_turn(self, thread_id: str, turn_id: str) -> dict[str, Any]:
        return self._request("turn/interrupt", {"threadId": thread_id, "turnId": turn_id})

    def receive_turn(self, thread_id: str, turn_id: str) -> dict[str, Any]:
        events: list[dict[str, Any]] = []
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            message = (
                self._pending_events.pop(0)
                if self._pending_events
                else self._receive_before(deadline)
            )
            method = message.get("method")
            if method in APPROVAL_METHODS and "id" in message:
                raise CodexApprovalRequired(str(method), message["id"])
            if not isinstance(method, str):
                raise CodexTransportError("MALFORMED_CODEX_PROTOCOL")
            events.append(message)
            if method == "turn/completed":
                params = message.get("params", {})
                turn = params.get("turn", {}) if isinstance(params, dict) else {}
                if params.get("threadId") != thread_id or turn.get("id") != turn_id:
                    raise CodexTransportError("CODEX_TURN_ID_MISMATCH")
                status = turn.get("status")
                if status not in TERMINAL_TURN_STATUSES:
                    raise CodexTransportError("INVALID_CODEX_TURN_STATUS")
                if not turn.get("items"):
                    completed_items = [
                        event.get("params", {}).get("item")
                        for event in events
                        if event.get("method") == "item/completed"
                        and isinstance(event.get("params"), dict)
                        and isinstance(event.get("params", {}).get("item"), dict)
                    ]
                    if completed_items:
                        turn = {**turn, "items": completed_items}
                return {"status": status, "turn": turn, "events": events}

    def close(self) -> None:
        self.channel.close()


def locked_capability_status(
    profile: CodexProtocolProfile | None,
    binding: CodexThreadBinding | CodexWorkspaceBinding | None,
    *,
    error: str | None = None,
) -> dict[str, Any]:
    supported = profile is not None and profile.supports_required_contract()
    result = {
        "connection_status": "DISCOVERED_LOCKED" if supported else "UNAVAILABLE",
        "binding_status": "BOUND" if binding else "UNBOUND",
        "last_transport_health_check": profile.discovered_at if profile else None,
        "protocol_version": profile.cli_version if profile else None,
        "protocol_schema_sha256": profile.schema_bundle_sha256 if profile else None,
        "features": {
            name: ("SUPPORTED_LOCKED" if supported else "UNAVAILABLE")
            for name in CAPABILITY_NAMES
        },
        "execution_locked": True,
        "approval_policy": "NEVER_AUTO_APPROVE",
        "dispatch_status": "LOCKED_USER_APPROVAL_REQUIRED",
        "development_client": "Codex Desktop",
        "orchestration_runtime": "Ubuntu WSL Codex CLI/App Server",
        "error": error,
    }
    if binding is not None:
        result["workspace_binding"] = binding.public_summary()
    return result


class CodexTransportHealth:
    def __init__(self, executable: str | None = None) -> None:
        self.distro = os.environ.get("DEVOS_CODEX_WSL_DISTRO", "Ubuntu")
        self.codex_path = os.environ.get(
            "DEVOS_CODEX_WSL_PATH", "/home/devops/.local/bin/codex",
        )
        self._profile: CodexProtocolProfile | None = None
        self._error: str | None = None
        self._checked = False

    def _discover_once(self) -> None:
        if self._checked:
            return
        self._checked = True
        try:
            _, self._profile = WslCodexProtocolDiscovery(
                self.distro, self.codex_path, timeout_seconds=30,
            ).discover()
            if not self._profile.supports_required_contract():
                self._error = "CODEX_PROTOCOL_CAPABILITY_MISMATCH"
        except (OSError, subprocess.SubprocessError, CodexTransportError, ValueError):
            self._error = "CODEX_PROTOCOL_DISCOVERY_FAILED"

    def for_node(self, node: dict[str, Any]) -> dict[str, Any]:
        self._discover_once()
        binding = None
        binding_error = None
        try:
            binding = CodexThreadBinding.parse(str(node.get("transport_ref") or ""))
        except CodexTransportError:
            try:
                binding = CodexWorkspaceBinding.parse(str(node.get("transport_ref") or ""))
            except CodexTransportError as error:
                binding_error = str(error)
        return locked_capability_status(
            self._profile,
            binding,
            error=binding_error or self._error,
        )
