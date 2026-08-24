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
from console.devos_orchestration.control_plane import (
    ControlPlaneError,
    OrchestrationControlStore,
)
from console.devos_orchestration.codex_transport import CodexTransportHealth
from console.devos_orchestration.dispatch_preview import DispatchPreviewStore
from console.devos_orchestration.return_handoff import ReturnHandoffStore
from console.devos_orchestration.exact_delivery import ExactDeliveryStore
from console.devos_orchestration.api_mainline_bootstrap import (
    BOOTSTRAP_CANDIDATE_FILE,
    read_public_bootstrap_summary,
)
from console.devos_orchestration.api_mainline_start import (
    ApiMainlineStartError,
    ApiMainlineStartStore,
)
from console.devos_orchestration.api_mainline_run import (
    ApiMainlineRunError,
    ApiMainlineRunStore,
)
from console.devos_orchestration.api_mainline_return import ApiMainlineReturnStore
from console.devos_orchestration.mainline_dispatch import MainlineDispatchBridge
from console.devos_orchestration.semi_auto_dispatch import SemiAutoCodexDispatcher
from console.devos_orchestration.auto_safe_continue import (
    cumulative_cost_preflight,
    pilot_policy,
)
from console.devos_orchestration.activity_timeline import project_activity_timeline


MAX_REQUEST_BODY = 320 * 1024
OVERVIEW_CACHE_SECONDS = 60
class ConsoleApplication:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.audit = AuditLog(settings.runtime_dir / "audit.jsonl")
        self.sessions = SessionStore(settings.access_token, secure_cookie=settings.secure_cookie)
        memo_database = getattr(settings, "memo_database", settings.runtime_dir / "memos.sqlite3")
        self.memos = MemoStore(memo_database)
        self.codex_transport = CodexTransportHealth()
        self.orchestration = OrchestrationControlStore(
            settings.runtime_dir / "orchestration-control.json",
            [project.slug for project in settings.projects],
            self.audit,
            capability_provider=self.codex_transport.for_node,
            bootstrap_candidate_provider=lambda project: read_public_bootstrap_summary(
                settings.runtime_dir / "orchestration" / BOOTSTRAP_CANDIDATE_FILE
            ),
        )
        self.api_mainline_starts = ApiMainlineStartStore(
            settings.runtime_dir / "api-mainline-starts",
            self.orchestration,
        )
        self.api_mainline_runs = ApiMainlineRunStore(
            settings.runtime_dir / "api-mainline-runs",
            self.api_mainline_starts,
            self.orchestration,
        )
        self.dispatch_previews = DispatchPreviewStore(
            settings.runtime_dir / "dispatch-previews",
            self.orchestration,
        )
        self.return_handoffs = ReturnHandoffStore(
            settings.runtime_dir / "return-handoffs",
            settings.runtime_dir / "dispatch-previews",
            self.orchestration,
        )
        self.exact_deliveries = ExactDeliveryStore(
            settings.runtime_dir / "exact-deliveries",
            settings.runtime_dir / "return-handoffs",
        )
        self.api_mainline_returns = ApiMainlineReturnStore(
            settings.runtime_dir / "api-mainline-returns",
            settings.runtime_dir / "return-handoffs",
            self.orchestration,
            dispatch_directory=settings.runtime_dir / "dispatch-previews",
        )
        btest_project = next((item for item in settings.projects if item.slug == "btest"), None)
        self.mainline_dispatch = (
            MainlineDispatchBridge(
                self.api_mainline_runs,
                self.dispatch_previews,
                self.orchestration,
                btest_project.path,
            )
            if btest_project is not None
            else None
        )
        self.semi_auto_dispatch = SemiAutoCodexDispatcher(
            self.dispatch_previews,
            self.orchestration,
            settings.runtime_dir,
        ) if btest_project is not None else None
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

        if parsed.path == "/api/memos":
            self._json(HTTPStatus.OK, self.application.memos.list_all())
            return

        if parsed.path.startswith("/api/"):
            project_logs = parsed.path.startswith("/api/projects/") and parsed.path.endswith("/logs")
            preview_list = (
                parsed.path.startswith("/api/orchestration/")
                and parsed.path.endswith("/dispatch-previews")
                and len(parsed.path.strip("/").split("/")) == 4
            )
            api_mainline_start = (
                parsed.path.startswith("/api/orchestration/")
                and parsed.path.endswith("/api-mainline-start")
                and len(parsed.path.strip("/").split("/")) == 4
            )
            if parsed.path not in {"/api/overview", "/api/roadmaps", "/api/orchestration"} and not project_logs and not preview_list and not api_mainline_start:
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
                if parsed.path == "/api/orchestration":
                    self._json(HTTPStatus.OK, self.application.orchestration.list_projects())
                    return
                if preview_list:
                    project = parsed.path.strip("/").split("/")[2]
                    cost_basis = self.application.api_mainline_returns.latest_sealed_cost_preflight(project)
                    pilot = pilot_policy(cumulative_cost_preflight(
                        cost_basis["hard_worst_case_cost_usd"],
                        cost_basis.get("proposed_single_call_cap_usd"),
                    )) if cost_basis else pilot_policy({
                        "status": "SEALED_COST_PREFLIGHT_REQUIRED",
                        "approved_pilot_cap_usd": None,
                    })
                    self._json(HTTPStatus.OK, {
                        "previews": self.application.dispatch_previews.list_for_project(project),
                        "returns": self.application.return_handoffs.list_for_project(project),
                        "deliveries": self.application.exact_deliveries.list_for_project(project),
                        "mainline_returns": self.application.api_mainline_returns.list_for_project(project),
                        "auto_safe_continue_pilot": pilot,
                        "activity_timeline": project_activity_timeline(
                            project,
                            self.application.dispatch_previews.directory,
                            self.application.api_mainline_returns.directory,
                            self.application.settings.runtime_dir / "auto-safe-continue",
                        ),
                    })
                    return
                if api_mainline_start:
                    project = parsed.path.strip("/").split("/")[2]
                    self._json(HTTPStatus.OK, {
                        "start": self.application.api_mainline_starts.status(project),
                        "run": self.application.api_mainline_runs.status(project),
                    })
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
        if parsed.path.startswith("/api/orchestration/"):
            try:
                body = self._body()
                parts = parsed.path.strip("/").split("/")
                if (
                    len(parts) == 5
                    and parts[3] == "api-mainline-start"
                    and parts[4] in {"approve", "cancel"}
                ):
                    project, action = parts[2], parts[4]
                    arguments = (
                        project,
                        str(body.get("candidate_file_sha256") or ""),
                        str(body.get("approval_manifest_sha256") or ""),
                    )
                    value = (
                        self.application.api_mainline_runs.approve_and_execute(*arguments)
                        if action == "approve"
                        else self.application.api_mainline_runs.cancel(*arguments)
                    )
                    self._json(HTTPStatus.OK, {"run": value})
                    return
                if (
                    len(parts) == 6
                    and parts[3] == "api-mainline-returns"
                    and parts[5] == "approve"
                ):
                    value = self.application.api_mainline_returns.approve_and_execute(
                        parts[2],
                        parts[4],
                        str(body.get("candidate_sha256") or ""),
                        str(body.get("approval_manifest_sha256") or ""),
                    )
                    self._json(HTTPStatus.OK, {"mainline_return": value})
                    return
                if (
                    len(parts) == 6
                    and parts[3] == "dispatch-previews"
                    and parts[5] in {"approve", "approve-send", "reject"}
                ):
                    project, handoff_id, action = parts[2], parts[4], parts[5]
                    if action == "approve-send":
                        if self.application.semi_auto_dispatch is None:
                            raise ControlPlaneError("CODEX_DISPATCH_UNAVAILABLE")
                        value = self.application.semi_auto_dispatch.approve_and_send(
                            project, handoff_id, str(body.get("envelope_sha256") or ""),
                        )
                    else:
                        value = self.application.dispatch_previews.decide(
                            project,
                            handoff_id,
                            action,
                            str(body.get("envelope_sha256") or ""),
                        )
                    self._json(HTTPStatus.OK, {"preview": value})
                    return
                if (
                    len(parts) == 6
                    and parts[3] == "deliveries"
                    and parts[5] in {"content", "copied", "delivered", "cancel"}
                ):
                    project, delivery_id, action = parts[2], parts[4], parts[5]
                    if action == "content":
                        self._json(HTTPStatus.OK, self.application.exact_deliveries.exact_content(
                            project,
                            delivery_id,
                            str(body.get("delivery_packet_sha256") or ""),
                        ))
                        return
                    value = self.application.exact_deliveries.transition(
                        project,
                        delivery_id,
                        action,
                        str(body.get("delivery_packet_sha256") or ""),
                    )
                    self._json(HTTPStatus.OK, {"delivery": value})
                    return
                if len(parts) != 4:
                    raise ControlPlaneError("INVALID_ORCHESTRATION_PATH")
                project, resource = parts[2], parts[3]
                if resource == "mode":
                    value = self.application.orchestration.set_mode(project, body.get("mode"))
                elif resource == "control":
                    value = self.application.orchestration.control(project, body.get("action"))
                elif resource == "nodes":
                    value = self.application.orchestration.add_node(project, body)
                elif resource == "routes":
                    value = self.application.orchestration.add_route(project, body)
                elif resource == "dispatch-preview":
                    preview = self.application.dispatch_previews.prepare(project, body)
                    self._json(HTTPStatus.CREATED, {
                        "preview": preview,
                        "project": next(
                            item for item in self.application.orchestration.list_projects()["projects"]
                            if item["project"] == project
                        ),
                    })
                    return
                elif resource == "api-mainline-start":
                    value = self.application.api_mainline_starts.prepare(
                        project,
                        body.get("initial_request"),
                    )
                    self._json(HTTPStatus.CREATED, {"start": value})
                    return
                elif resource == "api-mainline-handoff":
                    if self.application.mainline_dispatch is None:
                        raise ControlPlaneError("API_MAINLINE_DISPATCH_UNAVAILABLE")
                    preview = self.application.mainline_dispatch.prepare(project)
                    self._json(HTTPStatus.CREATED, {"preview": preview})
                    return
                elif resource == "api-mainline-return":
                    preview = self.application.api_mainline_returns.prepare(
                        project,
                        str(body.get("return_id") or ""),
                    )
                    self._json(HTTPStatus.CREATED, {"mainline_return": preview})
                    return
                else:
                    raise ControlPlaneError("INVALID_ORCHESTRATION_PATH")
            except (ApiMainlineRunError, ApiMainlineStartError, ControlPlaneError, ValueError) as error:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            self._json(HTTPStatus.OK, {"project": value})
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

    def do_PUT(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/orchestration/"):
            session = self._require_session()
            if session is None or not self._require_csrf(session):
                return
            try:
                body = self._body()
                parts = parsed.path.strip("/").split("/")
                if len(parts) != 5:
                    raise ControlPlaneError("INVALID_ORCHESTRATION_PATH")
                project, resource, identifier = parts[2], parts[3], parts[4]
                if resource == "nodes":
                    value = self.application.orchestration.update_node(project, identifier, body)
                elif resource == "routes":
                    value = self.application.orchestration.update_route(project, identifier, body)
                else:
                    raise ControlPlaneError("INVALID_ORCHESTRATION_PATH")
            except (ControlPlaneError, ValueError) as error:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            self._json(HTTPStatus.OK, {"project": value})
            return
        prefix = "/api/memos/"
        if not parsed.path.startswith(prefix):
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
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

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        session = self._require_session()
        if session is None or not self._require_csrf(session):
            return
        try:
            parts = parsed.path.strip("/").split("/")
            if len(parts) != 5 or parts[:2] != ["api", "orchestration"]:
                raise ControlPlaneError("INVALID_ORCHESTRATION_PATH")
            project, resource, identifier = parts[2], parts[3], parts[4]
            if resource == "nodes":
                value = self.application.orchestration.delete_node(project, identifier)
            elif resource == "routes":
                value = self.application.orchestration.delete_route(project, identifier)
            else:
                raise ControlPlaneError("INVALID_ORCHESTRATION_PATH")
        except ControlPlaneError as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return
        self._json(HTTPStatus.OK, {"project": value})

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
