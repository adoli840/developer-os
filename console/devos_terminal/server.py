from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import mimetypes
import select
import secrets
import sys
import time
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_address
from typing import Any
from urllib.parse import parse_qs, urlparse

from .pty_session import PtySession
from .runner import TerminalRunner
from .settings import TerminalSettings, load_settings
from .websocket_transport import receive_frame, send_close, send_frame, websocket_accept


MAX_REQUEST_BODY = 8192
SESSION_COOKIE = "devos_terminal_session"
SESSION_TTL_SECONDS = 8 * 60 * 60


class TerminalApplication:
    def __init__(self, settings: TerminalSettings) -> None:
        self.settings = settings
        self.runner = TerminalRunner(
            settings.projects,
            settings.audit_path,
            settings.command_timeout_seconds,
            settings.max_output_bytes,
        )

    def create_session(self) -> tuple[str, str]:
        issued = str(int(time.time()))
        nonce = secrets.token_urlsafe(24)
        payload = f"{issued}.{nonce}"
        signature = hmac.new(
            self.settings.session_secret.encode("utf-8"),
            payload.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        session = f"{payload}.{signature}"
        csrf_token = hmac.new(
            self.settings.session_secret.encode("utf-8"),
            f"csrf.{session}".encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        return session, csrf_token

    def valid_session(self, value: str) -> bool:
        try:
            issued, nonce, signature = value.split(".", 2)
            if not nonce or int(time.time()) - int(issued) > SESSION_TTL_SECONDS:
                return False
        except (TypeError, ValueError):
            return False
        payload = f"{issued}.{nonce}"
        expected = hmac.new(
            self.settings.session_secret.encode("utf-8"),
            payload.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(signature, expected)

    def valid_csrf(self, session: str, token: str) -> bool:
        expected = hmac.new(
            self.settings.session_secret.encode("utf-8"),
            f"csrf.{session}".encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(token, expected)


class TerminalHandler(BaseHTTPRequestHandler):
    server_version = "DeveloperOSTerminal/1"
    application: TerminalApplication

    def log_message(self, format_string: str, *args: object) -> None:
        sys.stderr.write(
            "%s - - [%s] %s\n"
            % (self.address_string(), self.log_date_time_string(), format_string % args)
        )

    def _loopback_client(self) -> bool:
        try:
            return ip_address(self.client_address[0]).is_loopback
        except ValueError:
            return False

    def _security_headers(self, *, cache: str = "no-store") -> None:
        self.send_header("Cache-Control", cache)
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; connect-src 'self'; img-src 'self'; "
            "style-src 'self'; script-src 'self'; base-uri 'none'; "
            "form-action 'self'; frame-ancestors 'none'",
        )
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")

    def _json(self, status: int, value: Any, *, cookie: str | None = None) -> None:
        payload = json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self._security_headers()
        self.end_headers()
        self.wfile.write(payload)

    def _reject_non_loopback(self) -> bool:
        if self._loopback_client():
            return False
        self._json(HTTPStatus.FORBIDDEN, {"error": "Loopback access only."})
        return True

    def _cookie_value(self) -> str:
        cookie = SimpleCookie()
        cookie.load(self.headers.get("Cookie", ""))
        morsel = cookie.get(SESSION_COOKIE)
        return morsel.value if morsel else ""

    def _require_session(self) -> bool:
        if self.application.valid_session(self._cookie_value()):
            return True
        self._json(HTTPStatus.UNAUTHORIZED, {"error": "Terminal session expired."})
        return False

    def _same_origin(self) -> bool:
        origin = self.headers.get("Origin", "")
        host = self.headers.get("Host", "")
        return origin in {f"http://{host}", f"https://{host}"}

    def _body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Invalid request length.") from error
        if length <= 0 or length > MAX_REQUEST_BODY:
            raise ValueError("Invalid request body size.")
        try:
            value = json.loads(self.rfile.read(length))
        except json.JSONDecodeError as error:
            raise ValueError("Request body must be valid JSON.") from error
        if not isinstance(value, dict):
            raise ValueError("Request body must be an object.")
        return value

    def do_GET(self) -> None:
        if self._reject_non_loopback():
            return
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            self._json(HTTPStatus.OK, {"status": "ok"})
            return
        if parsed.path == "/api/terminal":
            self._open_terminal(parsed.query)
            return
        if parsed.path == "/api/session":
            session, csrf_token = self.application.create_session()
            cookie = (
                f"{SESSION_COOKIE}={session}; Path=/; HttpOnly; "
                f"SameSite=Strict; Max-Age={SESSION_TTL_SECONDS}"
            )
            self._json(
                HTTPStatus.OK,
                {
                    "csrf_token": csrf_token,
                    "projects": self.application.runner.projects(),
                    "command_timeout_seconds": self.application.settings.command_timeout_seconds,
                },
                cookie=cookie,
            )
            return
        if parsed.path.startswith("/api/"):
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        self._serve_static(parsed.path)

    def _open_terminal(self, query: str) -> None:
        if not self._require_session():
            return
        if not self._same_origin():
            self._json(HTTPStatus.FORBIDDEN, {"error": "Request validation failed."})
            return
        if self.headers.get("Upgrade", "").lower() != "websocket":
            self._json(HTTPStatus.UPGRADE_REQUIRED, {"error": "WebSocket upgrade required."})
            return
        if "upgrade" not in self.headers.get("Connection", "").lower():
            self._json(HTTPStatus.BAD_REQUEST, {"error": "Invalid WebSocket connection."})
            return
        if self.headers.get("Sec-WebSocket-Version") != "13":
            self._json(HTTPStatus.BAD_REQUEST, {"error": "Unsupported WebSocket version."})
            return

        key = self.headers.get("Sec-WebSocket-Key", "")
        try:
            if len(base64.b64decode(key, validate=True)) != 16:
                raise ValueError
        except (ValueError, base64.binascii.Error):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "Invalid WebSocket key."})
            return

        project_slug = parse_qs(query).get("project", [""])[0]
        try:
            project = self.application.runner.project(project_slug)
        except ValueError as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return

        self.send_response(HTTPStatus.SWITCHING_PROTOCOLS)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", websocket_accept(key))
        self.end_headers()
        self.wfile.flush()
        self.close_connection = True

        terminal: PtySession | None = None
        started = time.monotonic()
        self.application.runner.audit_terminal_session(project.slug, "terminal_opened")
        try:
            terminal = PtySession.open(project.path)
            while terminal.alive():
                readable, _, _ = select.select([self.connection, terminal.fd], [], [], 1.0)
                if terminal.fd in readable:
                    output = terminal.read()
                    if output:
                        send_frame(self.connection, output, opcode=0x2)
                    elif not terminal.alive():
                        break
                if self.connection in readable:
                    frame = receive_frame(self.connection)
                    if frame.opcode == 0x8:
                        break
                    if frame.opcode == 0x9:
                        send_frame(self.connection, frame.payload, opcode=0xA)
                        continue
                    if frame.opcode != 0x1:
                        continue
                    message = json.loads(frame.payload.decode("utf-8"))
                    if not isinstance(message, dict):
                        raise ValueError("Invalid terminal message.")
                    message_type = message.get("type")
                    if message_type == "input":
                        data = str(message.get("data", "")).encode("utf-8")
                        if len(data) > MAX_REQUEST_BODY:
                            raise ValueError("Terminal input is too large.")
                        terminal.write(data)
                    elif message_type == "resize":
                        columns = max(20, min(500, int(message.get("columns", 120))))
                        rows = max(5, min(200, int(message.get("rows", 32))))
                        terminal.resize(columns, rows)
                    else:
                        raise ValueError("Unknown terminal message.")
        except (BrokenPipeError, ConnectionError, json.JSONDecodeError, UnicodeDecodeError):
            pass
        except (OSError, ValueError) as error:
            sys.stderr.write(f"Terminal session error for {project.slug}: {error}\n")
            try:
                send_close(self.connection, 1008)
            except OSError:
                pass
        finally:
            if terminal is not None:
                terminal.close()
            duration_ms = int((time.monotonic() - started) * 1000)
            self.application.runner.audit_terminal_session(project.slug, "terminal_closed", duration_ms)

    def do_POST(self) -> None:
        if self._reject_non_loopback() or not self._require_session():
            return
        parsed = urlparse(self.path)
        if parsed.path != "/api/execute":
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        session = self._cookie_value()
        csrf_token = self.headers.get("X-Terminal-CSRF", "")
        if not self._same_origin() or not self.application.valid_csrf(session, csrf_token):
            self._json(HTTPStatus.FORBIDDEN, {"error": "Request validation failed."})
            return
        try:
            body = self._body()
            result = self.application.runner.execute(
                str(body.get("project", "")),
                str(body.get("command", "")),
            )
            self._json(
                HTTPStatus.OK,
                {
                    "ok": result.ok,
                    "returncode": result.returncode,
                    "output": result.output,
                    "duration_ms": result.duration_ms,
                    "timed_out": result.timed_out,
                    "truncated": result.truncated,
                },
            )
        except (ValueError, RuntimeError) as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except Exception:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Command execution failed."})

    def _serve_static(self, request_path: str) -> None:
        static_root = self.application.settings.repo_root / "console" / "terminal_static"
        relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
        candidate = (static_root / relative).resolve()
        try:
            candidate.relative_to(static_root.resolve())
        except ValueError:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        if not candidate.is_file():
            candidate = static_root / "index.html"
        payload = candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header(
            "Content-Type",
            f"{content_type}; charset=utf-8"
            if content_type.startswith("text/") or content_type == "application/javascript"
            else content_type,
        )
        self.send_header("Content-Length", str(len(payload)))
        self._security_headers(cache="public, max-age=300" if candidate.name != "index.html" else "no-cache")
        self.end_headers()
        self.wfile.write(payload)


def create_server(settings: TerminalSettings) -> ThreadingHTTPServer:
    application = TerminalApplication(settings)

    class BoundHandler(TerminalHandler):
        pass

    BoundHandler.application = application

    class TerminalHTTPServer(ThreadingHTTPServer):
        daemon_threads = True

    return TerminalHTTPServer((settings.bind, settings.port), BoundHandler)


def main() -> None:
    parser = argparse.ArgumentParser(description="DeveloperOS private browser terminal")
    parser.add_argument("--bind")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    settings = load_settings(bind=args.bind, port=args.port)
    server = create_server(settings)
    print(f"DeveloperOS terminal listening on http://{settings.bind}:{settings.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
