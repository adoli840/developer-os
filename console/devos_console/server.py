from __future__ import annotations

import argparse
import ipaddress
import json
import mimetypes
import sys
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .alerts import build_alerts
from .audit import AuditLog
from .auth import Session, SessionStore
from .backups import collect_backup_status
from .projects import ProjectService
from .roadmaps import collect_roadmaps
from .resources import collect_resource_breakdown
from .settings import Settings, load_settings
from .system_info import collect_system_info
from .usage import read_usage_snapshots
from .workstations import attach_server_comparisons, collect_workstations


MAX_REQUEST_BODY = 16_384


class ConsoleApplication:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.audit = AuditLog(settings.runtime_dir / "audit.jsonl")
        self.sessions = SessionStore(settings.access_token, secure_cookie=settings.secure_cookie)
        self.projects = ProjectService(settings.projects, self.audit)

    def overview(self, *, public: bool = False) -> dict[str, Any]:
        with ThreadPoolExecutor(max_workers=4) as executor:
            system_future = executor.submit(collect_system_info, self.settings.workspace_root)
            projects_future = executor.submit(self.projects.collect_all)
            backups_future = executor.submit(
                collect_backup_status,
                self.settings.projects,
                self.settings.backup_status_dir,
            )
            workstations_future = executor.submit(
                collect_workstations,
                self.settings.workstations,
                self.settings.workstation_status_dir,
            )
            system = system_future.result()
            projects = projects_future.result()
            backups = backups_future.result()
            workstations = workstations_future.result()
        system["resources"] = collect_resource_breakdown(
            self.settings.projects,
            projects,
            system,
        )
        attach_server_comparisons(workstations, projects)
        if public:
            for project in projects:
                project.pop("path", None)
                project["actions"] = []
            for workstation in workstations:
                workstation.pop("hostname", None)
        alerts = build_alerts(
            system,
            projects,
            backups,
            workstations,
            public_read_only=public,
        )
        return {
            "system": system,
            "projects": projects,
            "backups": backups,
            "workstations": workstations,
            "alerts": alerts,
            "usage": read_usage_snapshots(
                self.settings.usage_snapshot,
                self.settings.oracle_usage_snapshot,
            ),
            "audit": [] if public else self.audit.recent(20),
            "read_only": public,
        }

    def roadmaps(self) -> dict[str, Any]:
        return collect_roadmaps(self.settings.projects)


class ConsoleHandler(BaseHTTPRequestHandler):
    server_version = "DeveloperOSConsole/1"
    application: ConsoleApplication

    def log_message(self, format_string: str, *args: object) -> None:
        if sys.stderr is not None:
            sys.stderr.write(
                "%s - - [%s] %s\n"
                % (self.address_string(), self.log_date_time_string(), format_string % args)
            )

    def _security_headers(self, *, cache: str = "no-store") -> None:
        self.send_header("Cache-Control", cache)
        self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; img-src 'self'; style-src 'self'; script-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
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

    def _session(self) -> Session | None:
        return self.application.sessions.from_cookie(self.headers.get("Cookie"))

    def _trusted_local_session(self) -> Session | None:
        if not self.application.settings.trusted_local:
            return None
        try:
            if not ipaddress.ip_address(self.client_address[0]).is_loopback:
                return None
        except ValueError:
            return None
        return self.application.sessions.create_trusted()

    def _require_session(self) -> Session | None:
        session = self._session()
        if session is None:
            self._json(HTTPStatus.UNAUTHORIZED, {"error": "Authentication required."})
        return session

    def _require_csrf(self, session: Session) -> bool:
        token = self.headers.get("X-CSRF-Token", "")
        if token != session.csrf_token:
            self._json(HTTPStatus.FORBIDDEN, {"error": "CSRF validation failed."})
            return False
        return True

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            self._json(HTTPStatus.OK, {"status": "ok"})
            return
        if parsed.path == "/api/session":
            session = self._session()
            if session is None:
                session = self._trusted_local_session()
                if session is not None:
                    self._json(
                        HTTPStatus.OK,
                        {
                            "authenticated": True,
                            "public_read_only": False,
                            "trusted_local": True,
                            "csrf_token": session.csrf_token,
                        },
                        cookie=self.application.sessions.cookie_header(session),
                    )
                    return
            if session is None:
                if self.application.settings.public_read_only:
                    self._json(HTTPStatus.OK, {"authenticated": False, "public_read_only": True})
                else:
                    self._json(HTTPStatus.UNAUTHORIZED, {"authenticated": False, "public_read_only": False})
            else:
                self._json(
                    HTTPStatus.OK,
                    {
                        "authenticated": True,
                        "public_read_only": False,
                        "trusted_local": self.application.settings.trusted_local,
                        "csrf_token": session.csrf_token,
                    },
                )
            return

        if parsed.path.startswith("/api/"):
            public_read = (
                self.application.settings.public_read_only
                and parsed.path in {"/api/overview", "/api/roadmaps"}
            )
            if not public_read and self._require_session() is None:
                return
            try:
                if parsed.path == "/api/overview":
                    self._json(HTTPStatus.OK, self.application.overview(public=public_read))
                    return
                if parsed.path == "/api/roadmaps":
                    self._json(HTTPStatus.OK, self.application.roadmaps())
                    return
                if parsed.path.startswith("/api/projects/") and parsed.path.endswith("/logs"):
                    slug = parsed.path.split("/")[3]
                    values = parse_qs(parsed.query)
                    lines = int(values.get("lines", ["120"])[0])
                    self._json(HTTPStatus.OK, self.application.projects.logs(slug, lines))
                    return
            except (ValueError, RuntimeError) as error:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            except Exception:
                self.application.audit.write("api_error", path=parsed.path)
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "The console could not complete the request."})
                return
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return

        self._serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/login":
            if self.application.settings.public_read_only:
                self._json(HTTPStatus.FORBIDDEN, {"error": "Login is disabled on the public HTTP endpoint."})
                return
            try:
                body = self._body()
                token = str(body.get("token", ""))
            except ValueError as error:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            session = self.application.sessions.login(token, self.client_address[0])
            if session is None:
                self.application.audit.write("login_failed", remote=self.client_address[0])
                self._json(HTTPStatus.UNAUTHORIZED, {"error": "Invalid token or too many attempts."})
                return
            self.application.audit.write("login_succeeded", remote=self.client_address[0])
            self._json(
                HTTPStatus.OK,
                {"authenticated": True, "csrf_token": session.csrf_token},
                cookie=self.application.sessions.cookie_header(session),
            )
            return

        session = self._require_session()
        if session is None or not self._require_csrf(session):
            return
        if parsed.path == "/api/logout":
            self.application.sessions.logout(session)
            self._json(
                HTTPStatus.OK,
                {"authenticated": False},
                cookie=self.application.sessions.expired_cookie_header(),
            )
            return
        if parsed.path == "/api/actions":
            try:
                body = self._body()
                result = self.application.projects.run_action(
                    str(body.get("project", "")),
                    str(body.get("action", "")),
                    str(body.get("confirmation", "")),
                    self.client_address[0],
                )
                self._json(HTTPStatus.OK if result["ok"] else HTTPStatus.CONFLICT, result)
            except (ValueError, RuntimeError) as error:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            except Exception:
                self.application.audit.write("action_error", remote=self.client_address[0])
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "The action could not be completed."})
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

    def _serve_static(self, request_path: str) -> None:
        static_root = self.application.settings.repo_root / "console" / "static"
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
        self.send_header("Content-Type", f"{content_type}; charset=utf-8" if content_type.startswith("text/") or content_type == "application/javascript" else content_type)
        self.send_header("Content-Length", str(len(payload)))
        self._security_headers(cache="public, max-age=300" if candidate.name != "index.html" else "no-cache")
        self.end_headers()
        self.wfile.write(payload)


def create_server(settings: Settings) -> ThreadingHTTPServer:
    application = ConsoleApplication(settings)

    class BoundHandler(ConsoleHandler):
        pass

    BoundHandler.application = application
    return ThreadingHTTPServer((settings.bind, settings.port), BoundHandler)


def main() -> None:
    parser = argparse.ArgumentParser(description="DeveloperOS browser console")
    parser.add_argument("--dev", action="store_true", help="Allow startup without an access token and use an insecure cookie.")
    parser.add_argument("--bind")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    settings = load_settings(dev_mode=args.dev, bind=args.bind, port=args.port)
    server = create_server(settings)
    print(f"DeveloperOS console listening on http://{settings.bind}:{settings.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
