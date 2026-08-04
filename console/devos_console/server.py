from __future__ import annotations

import argparse
import copy
import ipaddress
import json
import mimetypes
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock, Thread
from typing import Any
from urllib.parse import parse_qs, urlparse

from .alerts import build_alerts
from .audit import AuditLog
from .auth import Session, SessionStore
from .backups import collect_backup_status
from .memos import MemoStore
from .projects import ProjectService
from .roadmaps import collect_roadmaps
from .resources import collect_resource_breakdown
from .settings import Settings, load_settings
from .system_info import collect_system_info
from .usage import read_usage_snapshots
from .workstations import attach_server_comparisons, collect_workstations


MAX_REQUEST_BODY = 320 * 1024
OVERVIEW_CACHE_SECONDS = 60
MEMO_SESSION_COOKIE = "devos_memo_session"


class ConsoleApplication:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.audit = AuditLog(settings.runtime_dir / "audit.jsonl")
        self.sessions = SessionStore(settings.access_token, secure_cookie=settings.secure_cookie)
        self.memo_sessions = SessionStore(
            getattr(settings, "memo_access_token", settings.access_token),
            secure_cookie=settings.secure_cookie,
            cookie_name=MEMO_SESSION_COOKIE,
            cookie_path="/api/",
        )
        memo_database = getattr(settings, "memo_database", settings.runtime_dir / "memos.sqlite3")
        self.memos = MemoStore(memo_database)
        self.projects = ProjectService(settings.projects)
        self._overview_cache: dict[bool, tuple[float, dict[str, Any]]] = {}
        self._overview_refreshing: set[bool] = set()
        self._overview_lock = Lock()

    def _collect_overview(self, *, public: bool) -> dict[str, Any]:
        with ThreadPoolExecutor(max_workers=4) as executor:
            system_future = executor.submit(collect_system_info, self.settings.workspace_root)
            projects_future = executor.submit(self.projects.collect_all)
            backups_future = executor.submit(
                collect_backup_status,
                self.settings.projects,
                self.settings.backup_status_dir,
                self.settings.memo_database,
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
            backups,
        )
        attach_server_comparisons(workstations, projects)
        if public:
            for project in projects:
                project.pop("path", None)
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

    def _refresh_overview_cache(self, public: bool) -> None:
        try:
            value = self._collect_overview(public=public)
            with self._overview_lock:
                self._overview_cache[public] = (time.monotonic(), value)
        except Exception as error:
            self.audit.write(
                "overview_refresh_failed",
                public=public,
                error=type(error).__name__,
            )
        finally:
            with self._overview_lock:
                self._overview_refreshing.discard(public)

    def _start_overview_refresh(self, public: bool) -> None:
        with self._overview_lock:
            if public in self._overview_refreshing:
                return
            self._overview_refreshing.add(public)
        Thread(
            target=self._refresh_overview_cache,
            args=(public,),
            name=f"overview-refresh-{'public' if public else 'private'}",
            daemon=True,
        ).start()

    def warm_overview(self, *, public: bool) -> None:
        self._start_overview_refresh(public)

    def overview(self, *, public: bool = False) -> dict[str, Any]:
        with self._overview_lock:
            cached = self._overview_cache.get(public)
        if cached is None:
            value = self._collect_overview(public=public)
            with self._overview_lock:
                self._overview_cache[public] = (time.monotonic(), value)
            return copy.deepcopy(value)

        collected_at, value = cached
        if time.monotonic() - collected_at >= OVERVIEW_CACHE_SECONDS:
            self._start_overview_refresh(public)
        return copy.deepcopy(value)

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

    def _memo_session(self) -> Session | None:
        return self.application.memo_sessions.from_cookie(self.headers.get("Cookie"))

    def _is_trusted_local_request(self) -> bool:
        if not self.application.settings.trusted_local:
            return False
        try:
            return ipaddress.ip_address(self.client_address[0]).is_loopback
        except ValueError:
            return False

    def _trusted_local_session(self) -> Session | None:
        if not self._is_trusted_local_request():
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

    def _require_memo_session(self) -> Session | None:
        session = self._memo_session()
        if session is None:
            self._json(HTTPStatus.UNAUTHORIZED, {"error": "Memo unlock required."})
        return session

    def _require_memo_csrf(self, session: Session) -> bool:
        token = self.headers.get("X-Memo-CSRF-Token", "")
        if token != session.csrf_token:
            self._json(HTTPStatus.FORBIDDEN, {"error": "Memo CSRF validation failed."})
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

        if parsed.path == "/api/memo/session":
            session = self._memo_session()
            can_logout = session is not None and self.application.settings.public_read_only
            if session is None and (self._session() is not None or self._is_trusted_local_request()):
                session = self.application.memo_sessions.create_trusted()
                can_logout = False
            if session is None:
                self._json(HTTPStatus.OK, {"authenticated": False})
            else:
                self._json(
                    HTTPStatus.OK,
                    {
                        "authenticated": True,
                        "csrf_token": session.csrf_token,
                        "can_logout": can_logout,
                    },
                    cookie=self.application.memo_sessions.cookie_header(session),
                )
            return

        if parsed.path == "/api/memos":
            if self._require_memo_session() is None:
                return
            self._json(HTTPStatus.OK, self.application.memos.list_all())
            return

        if parsed.path.startswith("/api/"):
            project_logs = parsed.path.startswith("/api/projects/") and parsed.path.endswith("/logs")
            if parsed.path not in {"/api/overview", "/api/roadmaps"} and not project_logs:
                self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
                return
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
                if project_logs:
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
        if parsed.path == "/api/memo/login":
            try:
                body = self._body()
                token = str(body.get("token", ""))
            except ValueError as error:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            session = self.application.memo_sessions.login(token, self.client_address[0])
            if session is None:
                self.application.audit.write("memo_login_failed", remote=self.client_address[0])
                self._json(HTTPStatus.UNAUTHORIZED, {"error": "Invalid token or too many attempts."})
                return
            self.application.audit.write("memo_login_succeeded", remote=self.client_address[0])
            self._json(
                HTTPStatus.OK,
                {
                    "authenticated": True,
                    "csrf_token": session.csrf_token,
                    "can_logout": True,
                },
                cookie=self.application.memo_sessions.cookie_header(session),
            )
            return

        if parsed.path == "/api/memo/logout":
            session = self._require_memo_session()
            if session is None or not self._require_memo_csrf(session):
                return
            self.application.memo_sessions.logout(session)
            self._json(
                HTTPStatus.OK,
                {"authenticated": False},
                cookie=self.application.memo_sessions.expired_cookie_header(),
            )
            return

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
        self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

    def do_PUT(self) -> None:
        parsed = urlparse(self.path)
        prefix = "/api/memos/"
        if not parsed.path.startswith(prefix):
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        session = self._require_memo_session()
        if session is None or not self._require_memo_csrf(session):
            return
        project = parsed.path.removeprefix(prefix)
        if not project or "/" in project:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        try:
            body = self._body()
            item = self.application.memos.save(project, body.get("content"))
        except ValueError as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return
        except Exception:
            self.application.audit.write("memo_save_failed", project=project)
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "The memo could not be saved."})
            return
        self.application.audit.write("memo_saved", project=project)
        self._json(HTTPStatus.OK, {"item": item})

    def _serve_static(self, request_path: str) -> None:
        roadmap_prefix = "/roadmap-assets/"
        if request_path.startswith(roadmap_prefix):
            static_root = self.application.settings.repo_root / "04_Tools" / "roadmap-web" / "assets"
            relative = request_path.removeprefix(roadmap_prefix)
            fallback_to_index = False
        else:
            static_root = self.application.settings.repo_root / "console" / "static"
            relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
            fallback_to_index = True
        candidate = (static_root / relative).resolve()
        try:
            candidate.relative_to(static_root.resolve())
        except ValueError:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        if not candidate.is_file() and fallback_to_index:
            candidate = static_root / "index.html"
        if not candidate.is_file():
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        payload = candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8" if content_type.startswith("text/") or content_type == "application/javascript" else content_type)
        self.send_header("Content-Length", str(len(payload)))
        self._security_headers(cache="public, max-age=300" if candidate.name != "index.html" else "no-cache")
        self.end_headers()
        self.wfile.write(payload)


def create_server(settings: Settings, *, prewarm: bool = False) -> ThreadingHTTPServer:
    application = ConsoleApplication(settings)
    if prewarm:
        application.warm_overview(public=settings.public_read_only)

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
    server = create_server(settings, prewarm=True)
    print(f"DeveloperOS console listening on http://{settings.bind}:{settings.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
