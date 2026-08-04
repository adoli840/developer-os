from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from http.cookiejar import CookieJar
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener

from console.devos_console.alerts import build_alerts
from console.devos_console.auth import SessionStore
from console.devos_console.backups import collect_backup_status
from console.devos_console.memos import MemoStore
from console.devos_console.projects import ProjectService
from console.devos_console.resources import _cpu_percent_between, _parse_size, collect_resource_breakdown
from console.devos_console.runner import CommandResult
from console.devos_console.server import ConsoleApplication, create_server
from console.devos_console.settings import ProjectSpec, WorkstationSpec, load_settings
from console.devos_console.usage import read_oracle_usage_snapshot, read_usage_snapshot, read_usage_snapshots
from console.devos_console.workstations import attach_server_comparisons, collect_workstations


class SessionStoreTests(unittest.TestCase):
    def test_valid_token_creates_and_resolves_session(self) -> None:
        store = SessionStore("expected-token", secure_cookie=False)
        session = store.login("expected-token", "127.0.0.1")
        self.assertIsNotNone(session)
        cookie = store.cookie_header(session)
        self.assertEqual(store.from_cookie(cookie).session_id, session.session_id)

    def test_invalid_token_is_rejected(self) -> None:
        store = SessionStore("expected-token", secure_cookie=False)
        self.assertIsNone(store.login("wrong-token", "127.0.0.1"))

    def test_trusted_session_is_created_without_access_token(self) -> None:
        store = SessionStore("", secure_cookie=False)
        session = store.create_trusted()
        self.assertEqual(store.from_cookie(store.cookie_header(session)), session)

    def test_scoped_cookie_does_not_replace_the_console_cookie(self) -> None:
        store = SessionStore(
            "expected-token",
            secure_cookie=False,
            cookie_name="devos_memo_session",
            cookie_path="/api/",
        )
        session = store.login("expected-token", "127.0.0.1")
        cookie = store.cookie_header(session)
        self.assertIn("devos_memo_session=", cookie)
        self.assertIn("Path=/api/", cookie)
        self.assertNotIn("devos_session=", cookie)


class MemoStoreTests(unittest.TestCase):
    def test_memos_persist_across_store_instances(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "memos.sqlite3"
            first = MemoStore(database)
            first.save("oa", "세금 신고 아이디어")
            second = MemoStore(database)
            items = {item["project"]: item for item in second.list_all()["items"]}

        self.assertEqual(items["oa"]["content"], "세금 신고 아이디어")
        self.assertEqual(list(items), ["developer-os", "btest", "oa", "gaia"])

    def test_unknown_project_and_oversized_content_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = MemoStore(Path(directory) / "memos.sqlite3")
            with self.assertRaises(ValueError):
                store.save("other", "text")
            with self.assertRaises(ValueError):
                store.save("oa", "x" * (256 * 1024 + 1))


class ConsoleSurfaceTests(unittest.TestCase):
    def test_recovery_replaces_operations_and_browser_commands(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        html = (repository / "console" / "static" / "index.html").read_text(encoding="utf-8")
        javascript = (repository / "console" / "static" / "app.js").read_text(encoding="utf-8")
        server = (repository / "console" / "devos_console" / "server.py").read_text(encoding="utf-8")

        self.assertIn('data-tab="recovery"', html)
        self.assertIn('id="tab-recovery"', html)
        self.assertIn('data-tab="roadmap"', html)
        self.assertIn('id="tab-roadmap"', html)
        self.assertNotIn('data-tab="operations"', html)
        self.assertNotIn('data-tab="commands"', html)
        self.assertIn("/api/roadmaps", javascript)
        self.assertIn("/api/roadmaps", server)
        self.assertIn("/roadmap-assets", server)
        self.assertNotIn("/api/actions", javascript)
        self.assertNotIn("/api/actions", server)
        self.assertFalse(hasattr(ProjectService, "run_action"))

    def test_resources_replace_overview_and_are_always_expanded(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        html = (repository / "console" / "static" / "index.html").read_text(encoding="utf-8")
        javascript = (repository / "console" / "static" / "app.js").read_text(encoding="utf-8")
        stylesheet = (repository / "console" / "static" / "styles.css").read_text(encoding="utf-8")

        self.assertIn('data-tab="resources"', html)
        self.assertIn('id="tab-resources"', html)
        self.assertNotIn('data-tab="overview"', html)
        self.assertNotIn('id="alert-summary"', html)
        self.assertNotIn('id="workstation-summary"', html)
        self.assertNotIn('data-metric=', javascript)
        self.assertIn("resourceBreakdown(metric.key", javascript)
        self.assertLess(javascript.index('{key: "cpu"'), javascript.index('{key: "memory"'))
        self.assertLess(javascript.index('{key: "memory"'), javascript.index('{key: "disk"'))
        self.assertIn('{key: "disk", label: "Disk"', javascript)
        self.assertNotIn('label: "Root disk"', javascript)
        self.assertIn("const sortedRows = sortResourceItems(rows);", javascript)
        self.assertIn("sortResourceItems(row.components || [])", javascript)
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr));", stylesheet)
        self.assertIn(".resource-breakdown {\n  display: grid;\n  grid-template-columns: 1fr;", stylesheet)

    def test_header_is_quiet_and_project_memos_use_the_server_database(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        html = (repository / "console" / "static" / "index.html").read_text(encoding="utf-8")
        javascript = (repository / "console" / "static" / "app.js").read_text(encoding="utf-8")

        self.assertNotIn('id="mode-badge"', html)
        self.assertNotIn('id="sync-state"', html)
        self.assertNotIn('id="refresh-button"', html)
        self.assertNotIn("elements.modeBadge", javascript)
        self.assertNotIn("elements.syncState", javascript)
        self.assertNotIn("elements.refreshButton", javascript)
        self.assertIn('data-tab="memo"', html)
        self.assertIn('id="tab-memo"', html)
        memo_items = [
            'data-memo-project="developer-os"',
            'data-memo-project="btest"',
            'data-memo-project="oa"',
            'data-memo-project="gaia"',
        ]
        self.assertEqual(memo_items, sorted(memo_items, key=html.index))
        self.assertIn('id="memo-login-form"', html)
        self.assertIn('id="memo-logout-button"', html)
        self.assertNotIn("localStorage", javascript)
        self.assertIn('request("/api/memo/session")', javascript)
        self.assertIn('request("/api/memos")', javascript)
        self.assertIn("`/api/memos/${encodeURIComponent(project)}`", javascript)

    def test_projects_use_one_compact_home_office_comparison_table(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        html = (repository / "console" / "static" / "index.html").read_text(encoding="utf-8")
        javascript = (repository / "console" / "static" / "app.js").read_text(encoding="utf-8")

        self.assertNotIn("APPLICATION REPOSITORIES", html)
        self.assertNotIn("<h1>Projects</h1>", html)
        self.assertNotIn("repositories</h2>", javascript)
        self.assertNotIn("Live local state.", javascript)
        self.assertIn("workstationIndicator(home)", javascript)
        self.assertIn("workstationIndicator(office)", javascript)
        self.assertEqual(javascript.count('class="project-heading">Project</th>'), 1)
        self.assertEqual(javascript.count('workstationRepositoryCell(commonStatusProject, "github")'), 1)
        self.assertIn('class="terminal-link terminal-root-link"', javascript)
        self.assertIn('href="http://127.0.0.1:8092/?project=server"', javascript)
        self.assertIn('class="project-toggle"', javascript)
        self.assertIn('class="project-container-row"', javascript)
        self.assertIn('renderProjectContainers(serverProject)', javascript)
        self.assertIn('classList.toggle("full-width-workspace"', javascript)

    def test_projects_precede_resources_and_both_use_the_full_workspace(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        html = (repository / "console" / "static" / "index.html").read_text(encoding="utf-8")
        javascript = (repository / "console" / "static" / "app.js").read_text(encoding="utf-8")

        self.assertLess(html.index('data-tab="projects"'), html.index('data-tab="resources"'))
        self.assertIn('<section class="tab-view active" id="tab-projects">', html)
        self.assertNotIn("SERVER CAPACITY", html)
        self.assertNotIn("<h1>Resources</h1>", html)
        self.assertNotIn('id="resource-time"', html)
        self.assertIn('href="/styles.css?v=5"', html)
        self.assertIn('src="/app.js?v=8"', html)
        self.assertIn('statusBadge(`${repo.behind} behind`, "behind")', javascript)
        self.assertIn(".status.behind", (repository / "console" / "static" / "styles.css").read_text(encoding="utf-8"))
        self.assertIn('const UI_STATE_KEY = "developer-os-console-ui-state-v1"', javascript)
        self.assertIn("window.sessionStorage.getItem(UI_STATE_KEY)", javascript)
        self.assertIn("window.sessionStorage.setItem(UI_STATE_KEY", javascript)
        self.assertIn("activeRoadmapTracks: state.activeRoadmapTracks", javascript)
        self.assertIn('state.activeRoadmapTracks[state.activeRoadmap] || "overall"', javascript)
        self.assertIn('state.activeTab !== "roadmap"', javascript)


class OverviewCacheTests(unittest.TestCase):
    def test_repeated_overview_reads_reuse_an_isolated_cached_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = SimpleNamespace(
                runtime_dir=Path(directory),
                access_token="",
                secure_cookie=False,
                projects=(),
            )
            application = ConsoleApplication(settings)
            with patch.object(
                application,
                "_collect_overview",
                return_value={"system": {"collected_at": 1}},
            ) as collect:
                first = application.overview(public=True)
                first["system"]["collected_at"] = 999
                second = application.overview(public=True)

        self.assertEqual(second["system"]["collected_at"], 1)
        self.assertEqual(collect.call_count, 1)


class UsageSnapshotTests(unittest.TestCase):
    def test_missing_snapshot_does_not_request_a_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = read_usage_snapshot(Path(directory) / "missing.json")
        self.assertEqual(result["status"], "not_configured")
        self.assertIsNone(result["remaining_usd"])

    def test_snapshot_calculates_remaining_budget(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "usage.json"
            path.write_text(
                json.dumps({"cost_usd": 12.25, "budget_usd": 30}),
                encoding="utf-8",
            )
            result = read_usage_snapshot(path)
        self.assertEqual(result["status"], "snapshot")
        self.assertEqual(result["remaining_usd"], 17.75)

    def test_oracle_snapshot_keeps_free_usage_and_projection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oracle.json"
            path.write_text(
                json.dumps(
                    {
                        "cost": 1.25,
                        "currency": "USD",
                        "budget": 10,
                        "resources": [
                            {
                                "label": "Ampere A1 OCPU",
                                "unit": "OCPU-hours",
                                "used": 96,
                                "free_allowance": 3000,
                                "free_remaining": 2904,
                                "projected_month_usage": 2976,
                            }
                        ],
                        "projected_cost": 2.5,
                        "completed_days": 15,
                        "days_in_month": 31,
                    }
                ),
                encoding="utf-8",
            )
            result = read_oracle_usage_snapshot(path)
        self.assertEqual(result["remaining"], 8.75)
        self.assertEqual(result["resources"][0]["unit"], "OCPU-hours")
        self.assertEqual(result["resources"][0]["free_remaining"], 2904)
        self.assertEqual(result["projected_cost"], 2.5)
        self.assertEqual(result["completed_days"], 15)

    def test_provider_collection_is_present_when_oracle_is_not_configured(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = read_usage_snapshots(root / "openai.json", root / "oracle.json")
        self.assertEqual([item["provider"] for item in result["providers"]], ["OpenAI", "Oracle Cloud"])

    def test_windows_utf8_bom_usage_snapshot_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "usage.json"
            path.write_text(
                json.dumps({"cost_usd": 2, "budget_usd": 5}),
                encoding="utf-8-sig",
            )
            result = read_usage_snapshot(path)
        self.assertEqual(result["status"], "snapshot")
        self.assertEqual(result["remaining_usd"], 3)


class SettingsTests(unittest.TestCase):
    def test_production_requires_access_token(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                load_settings()

    def test_public_read_only_environment_is_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            values = {
                "DEVOS_CONSOLE_TOKEN": "test-token",
                "DEVOS_RUNTIME_DIR": directory,
                "DEVOS_WORKSPACE_ROOT": directory,
                "DEVOS_PUBLIC_READ_ONLY": "1",
            }
            with patch.dict(os.environ, values, clear=True):
                settings = load_settings()
        self.assertTrue(settings.public_read_only)
        self.assertEqual(settings.port, 8080)
        self.assertEqual(settings.memo_database, Path(directory) / "memos.sqlite3")

    def test_btest_backup_is_enabled_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            values = {
                "DEVOS_CONSOLE_TOKEN": "test-token",
                "DEVOS_RUNTIME_DIR": directory,
                "DEVOS_WORKSPACE_ROOT": directory,
            }
            with patch.dict(os.environ, values, clear=True):
                settings = load_settings()
        btest = next(project for project in settings.projects if project.slug == "btest")
        self.assertTrue(btest.backup_expected)
        self.assertEqual(btest.port, 8081)

    def test_loopback_development_mode_enables_trusted_local_session(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            values = {
                "DEVOS_RUNTIME_DIR": directory,
                "DEVOS_WORKSPACE_ROOT": directory,
            }
            with patch.dict(os.environ, values, clear=True):
                settings = load_settings(dev_mode=True, bind="127.0.0.1")
        self.assertTrue(settings.trusted_local)

    def test_public_read_only_disables_trusted_local_session(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            values = {
                "DEVOS_RUNTIME_DIR": directory,
                "DEVOS_WORKSPACE_ROOT": directory,
                "DEVOS_PUBLIC_READ_ONLY": "1",
            }
            with patch.dict(os.environ, values, clear=True):
                settings = load_settings(dev_mode=True, bind="127.0.0.1")
        self.assertTrue(settings.public_read_only)
        self.assertFalse(settings.trusted_local)


class LocalSessionTests(unittest.TestCase):
    def test_loopback_development_session_skips_login(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            values = {
                "DEVOS_RUNTIME_DIR": directory,
                "DEVOS_WORKSPACE_ROOT": directory,
            }
            with patch.dict(os.environ, values, clear=True):
                settings = load_settings(dev_mode=True, bind="127.0.0.1", port=0)
            server = create_server(settings)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            opener = build_opener(HTTPCookieProcessor(CookieJar()))
            try:
                url = f"http://127.0.0.1:{server.server_address[1]}/api/session"
                with opener.open(url, timeout=5) as response:
                    payload = json.load(response)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertTrue(payload["authenticated"])
        self.assertTrue(payload["trusted_local"])
        self.assertTrue(payload["csrf_token"])

    def test_default_workstations_include_home_and_office(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            values = {
                "DEVOS_CONSOLE_TOKEN": "test-token",
                "DEVOS_RUNTIME_DIR": directory,
                "DEVOS_WORKSPACE_ROOT": directory,
            }
            with patch.dict(os.environ, values, clear=True):
                settings = load_settings()
        self.assertEqual(
            [workstation.workstation_id for workstation in settings.workstations],
            ["home", "office"],
        )


class MemoApiTests(unittest.TestCase):
    def test_public_memo_login_is_scoped_and_persists_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            values = {
                "DEVOS_CONSOLE_TOKEN": "test-token",
                "DEVOS_MEMO_TOKEN": "memo-token",
                "DEVOS_RUNTIME_DIR": directory,
                "DEVOS_WORKSPACE_ROOT": directory,
                "DEVOS_PUBLIC_READ_ONLY": "1",
                "DEVOS_SECURE_COOKIE": "0",
            }
            with patch.dict(os.environ, values, clear=True):
                settings = load_settings(port=0)
            server = create_server(settings)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            opener = build_opener(HTTPCookieProcessor(CookieJar()))
            base_url = f"http://127.0.0.1:{server.server_address[1]}"

            def call(path: str, *, method: str = "GET", body: dict | None = None, headers: dict | None = None) -> dict:
                payload = None if body is None else json.dumps(body).encode("utf-8")
                request = Request(
                    f"{base_url}{path}",
                    data=payload,
                    method=method,
                    headers={"Content-Type": "application/json", **(headers or {})},
                )
                with opener.open(request, timeout=5) as response:
                    return json.load(response)

            try:
                self.assertFalse(call("/api/memo/session")["authenticated"])
                with self.assertRaises(HTTPError) as wrong_token:
                    call("/api/memo/login", method="POST", body={"token": "test-token"})
                login = call("/api/memo/login", method="POST", body={"token": "memo-token"})
                saved = call(
                    "/api/memos/gaia",
                    method="PUT",
                    body={"content": "게임 AI 아이디어"},
                    headers={"X-Memo-CSRF-Token": login["csrf_token"]},
                )
                memos = call("/api/memos")
                with self.assertRaises(HTTPError) as error:
                    call("/api/projects/oa/logs")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(saved["item"]["content"], "게임 AI 아이디어")
        self.assertEqual(wrong_token.exception.code, 401)
        self.assertEqual(
            next(item for item in memos["items"] if item["project"] == "gaia")["content"],
            "게임 AI 아이디어",
        )
        self.assertEqual(error.exception.code, 401)


class ProjectStatusTests(unittest.TestCase):
    def test_status_counts_distinguish_worktree_states(self) -> None:
        result = ProjectService._status_counts(["M  staged.py", " M changed.py", "?? new.py"])
        self.assertEqual(result, {"modified": 3, "staged": 1, "unstaged": 1, "untracked": 1})

    def test_commit_tag_is_detected_as_image_revision(self) -> None:
        self.assertEqual(ProjectService._image_revision("example/app:0123456789abcdef"), "0123456789abcdef")
        self.assertIsNone(ProjectService._image_revision("postgres:17-alpine"))

    def test_immutable_release_does_not_require_git_upstream(self) -> None:
        repository = {
            "branch": "deployed",
            "revision": "abc1234",
            "modified": 0,
            "upstream": None,
            "ahead": 0,
            "behind": 0,
        }
        deployment = {"status": "current"}
        result = ProjectService._work_end_checks(True, repository, [], deployment)
        self.assertTrue(result["ready"])


class ResourceBreakdownTests(unittest.TestCase):
    def test_cpu_percent_uses_the_same_sampling_window(self) -> None:
        self.assertEqual(_cpu_percent_between((1_000, 600), (1_400, 800)), 50.0)

    def test_size_parser_accepts_docker_decimal_and_binary_units(self) -> None:
        self.assertEqual(_parse_size("1.5GB"), 1_500_000_000)
        self.assertEqual(_parse_size("2MiB"), 2_097_152)
        self.assertIsNone(_parse_size("N/A"))

    def test_cpu_component_rounding_preserves_the_displayed_residual(self) -> None:
        from console.devos_console.resources import _bounded_residual_components

        components = _bounded_residual_components(
            "cpu",
            31.2,
            [
                {"name": "A", "value": 10.04},
                {"name": "B", "value": 10.04},
                {"name": "C", "value": 11.12},
            ],
        )
        self.assertEqual(sum(item["value"] for item in components), 31.2)

    def test_resources_are_grouped_by_project_and_component(self) -> None:
        spec = ProjectSpec(
            slug="oa",
            name="OA",
            path=Path("."),
            compose_project="oa",
            port=8082,
            backup_expected=True,
        )
        projects = [
            {
                "slug": "oa",
                "containers": [{"id": "container-id", "name": "oa", "service": "app"}],
            }
        ]
        stats = CommandResult(
            ("docker", "stats"),
            0,
            json.dumps(
                {
                    "Container": "container-id",
                    "Name": "renamed-oa",
                    "CPUPerc": "40%",
                    "MemUsage": "200MiB / 8GiB",
                }
            ),
            "",
        )
        disk = CommandResult(
            ("docker", "system", "df"),
            0,
            json.dumps(
                {
                    "Containers": [
                        {"Labels": "com.docker.compose.project=oa", "Size": "10MB"}
                    ],
                    "Volumes": [
                        {"Labels": "com.docker.compose.project=oa", "Size": "1GB"}
                    ],
                    "Images": [{"UniqueSize": "500MB", "Size": "800MB"}],
                    "BuildCache": [{"Size": "250MB"}],
                }
            ),
            "",
        )
        system = {
            "cpu_count": 4,
            "cpu_percent": 25,
            "memory": {"used": 1_000_000_000},
            "disk": {"used": 5_000_000_000},
        }
        with (
            patch("console.devos_console.resources.run_docker", side_effect=[stats, disk]),
            patch("console.devos_console.resources._directory_size", return_value=100_000_000),
            patch("console.devos_console.resources._cpu_ticks", return_value=None),
            patch("console.devos_console.resources._child_cpu_seconds", return_value=None),
            patch("console.devos_console.resources._process_snapshot", return_value={}),
            patch(
                "console.devos_console.resources._host_disk_sizes",
                return_value={
                    "/usr": 900_000_000,
                    "/boot": 80_000_000,
                    "/etc": 20_000_000,
                    "/var/log": 100_000_000,
                    "/var/backups": 200_000_000,
                },
            ),
        ):
            result = collect_resource_breakdown((spec,), projects, system)

        self.assertEqual(result["cpu"][0]["name"], "OA")
        self.assertEqual(result["cpu"][0]["value"], 10.0)
        self.assertEqual(result["memory"][0]["value"], 209_715_200)
        self.assertEqual(result["disk"][0]["value"], 1_110_000_000)
        self.assertEqual(
            [item["name"] for item in result["disk"][0]["components"]],
            ["Docker volumes", "Project files", "Container writes"],
        )
        server_disk = result["disk"][-1]
        self.assertEqual(server_disk["name"], "Server & other")
        self.assertEqual(
            [item["name"] for item in server_disk["components"]],
            [
                "Shared Docker images",
                "Docker build cache",
                "System files & packages",
                "System logs",
                "Protected backups",
                "Other host files",
            ],
        )
        self.assertEqual(server_disk["components"][2]["disposition"], "baseline")
        self.assertEqual(server_disk["components"][-1]["disposition"], "unattributed")


class BackupStatusTests(unittest.TestCase):
    def test_memo_database_backup_is_included_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            status_dir = Path(directory)
            now = datetime.now(timezone.utc).isoformat()
            (status_dir / "developer-os-memos.json").write_text(
                json.dumps(
                    {
                        "last_success_at": now,
                        "last_file": "developer-os-memos.sqlite3",
                        "size_bytes": 100,
                        "verification_status": "passed",
                        "last_verification_at": now,
                        "backup_policy": "sqlite-full",
                        "retention_days": 14,
                    }
                ),
                encoding="utf-8",
            )
            with patch("console.devos_console.backups._timer_state", return_value={"available": True, "active": True}):
                result = collect_backup_status((), status_dir, status_dir / "memos.sqlite3")

        self.assertEqual(result["items"][0]["name"], "DeveloperOS memos")
        self.assertEqual(result["items"][0]["backup_policy"], "sqlite-full")
        self.assertEqual(result["items"][0]["status"], "healthy")

    def test_recent_verified_backup_is_healthy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            status_dir = Path(directory)
            now = datetime.now(timezone.utc).isoformat()
            (status_dir / "oa.json").write_text(
                json.dumps(
                    {
                        "last_success_at": now,
                        "last_file": "oa.sql.gz",
                        "size_bytes": 100,
                        "verification_status": "passed",
                        "last_verification_at": now,
                        "backup_policy": "full-cluster",
                        "retention_days": 14,
                    }
                ),
                encoding="utf-8",
            )
            project = ProjectSpec(
                slug="oa",
                name="OA",
                path=status_dir,
                compose_project="oa",
                port=8082,
                backup_expected=True,
            )
            with patch("console.devos_console.backups._timer_state", return_value={"available": True, "active": True}):
                result = collect_backup_status((project,), status_dir)
        self.assertEqual(result["items"][0]["status"], "healthy")
        self.assertEqual(result["items"][0]["verification_status"], "passed")
        self.assertEqual(result["items"][0]["backup_policy"], "full-cluster")
        self.assertEqual(result["items"][0]["retention_days"], 14)

    def test_missing_backup_becomes_warning(self) -> None:
        backups = {
            "items": [
                {
                    "name": "OA",
                    "status": "missing",
                    "message": "No successful backup has been recorded.",
                    "verification_status": "missing",
                }
            ]
        }
        system = {
            "disk": {"percent": 10},
            "memory": {"percent": 10},
            "docker": {"available": True, "unhealthy": 0},
        }
        alerts = build_alerts(system, [], backups, public_read_only=False)
        self.assertEqual([item["severity"] for item in alerts], ["warning", "warning"])


class WorkstationStatusTests(unittest.TestCase):
    def test_recent_home_report_is_online(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            status_dir = Path(directory)
            (status_dir / "home.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "workstation": "home",
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "hostname": "HOME-PC",
                        "projects": [
                            {
                                "slug": "gaia",
                                "name": "Gaia",
                                "available": True,
                                "repository": {
                                    "branch": "main",
                                    "revision": "abc1234",
                                    "remote_revision": "abc123456789",
                                    "remote_refresh_status": "success",
                                    "modified": 1,
                                    "ahead": 2,
                                    "behind": 0,
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            spec = WorkstationSpec(
                workstation_id="home",
                name="Home",
                offline_after_seconds=900,
            )
            result = collect_workstations((spec,), status_dir)[0]
        self.assertTrue(result["online"])
        self.assertEqual(result["summary"]["dirty"], 1)
        self.assertEqual(result["summary"]["ahead"], 2)
        self.assertEqual(
            result["projects"][0]["repository"]["remote_revision"],
            "abc123456789",
        )
        self.assertEqual(
            result["projects"][0]["repository"]["remote_refresh_status"],
            "success",
        )

    def test_legacy_remote_refresh_status_is_unverified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            status_dir = Path(directory)
            (status_dir / "home.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "workstation": "home",
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "projects": [
                            {
                                "slug": "oa",
                                "name": "OA",
                                "available": True,
                                "repository": {
                                    "revision": "local111",
                                    "upstream": "origin/main",
                                    "remote_revision": "cached222",
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            spec = WorkstationSpec("home", "Home", 900)
            result = collect_workstations((spec,), status_dir)[0]

        self.assertTrue(result["online"])
        self.assertEqual(
            result["projects"][0]["repository"]["remote_refresh_status"],
            "unknown",
        )

    def test_recent_office_report_is_online(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            status_dir = Path(directory)
            (status_dir / "office.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "workstation": "office",
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "hostname": "OFFICE-PC",
                        "projects": [],
                    }
                ),
                encoding="utf-8",
            )
            spec = WorkstationSpec("office", "Office", 900)
            result = collect_workstations((spec,), status_dir)[0]
        self.assertEqual(result["name"], "Office")
        self.assertTrue(result["online"])

    def test_missing_home_report_is_not_connected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            spec = WorkstationSpec(
                workstation_id="home",
                name="Home",
                offline_after_seconds=900,
            )
            result = collect_workstations((spec,), Path(directory))[0]
        self.assertEqual(result["status"], "never_reported")
        self.assertFalse(result["online"])

    def test_windows_utf8_bom_report_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            status_dir = Path(directory)
            payload = {
                "schema_version": 1,
                "workstation": "home",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "projects": [],
            }
            (status_dir / "home.json").write_bytes(
                b"\xef\xbb\xbf" + json.dumps(payload).encode("utf-8")
            )
            spec = WorkstationSpec("home", "Home", 900)
            result = collect_workstations((spec,), status_dir)[0]
        self.assertEqual(result["status"], "online")

    def test_local_revision_is_compared_with_server_and_deployment(self) -> None:
        workstations = [
            {
                "online": True,
                "projects": [
                    {
                        "slug": "gaia",
                        "repository": {
                            "revision": "abc1234",
                            "remote_revision": "abc123456789",
                            "remote_refresh_status": "success",
                        },
                    }
                ],
                "summary": {},
            }
        ]
        server_projects = [
            {
                "slug": "gaia",
                "available": True,
                "port": 8083,
                "repository": {"revision": "abc1234"},
                "deployment": {"deployed_revisions": ["abc123456789"]},
                "containers": [
                    {"state": "running", "status": "Up 1 hour (healthy)"}
                ],
            }
        ]
        attach_server_comparisons(workstations, server_projects)
        comparison = workstations[0]["projects"][0]["comparison"]
        self.assertTrue(comparison["fresh"])
        self.assertEqual(comparison["server_status"], "match")
        self.assertEqual(comparison["deployment_status"], "match")
        self.assertEqual(comparison["runtime_status"], "match")
        self.assertEqual(comparison["service_status"], "healthy")
        self.assertEqual(workstations[0]["projects"][0]["port"], 8083)
        self.assertEqual(workstations[0]["summary"]["mismatches"], 0)

    def test_runtime_is_compared_with_the_tracked_github_revision(self) -> None:
        workstations = [
            {
                "online": True,
                "projects": [
                    {
                        "slug": "oa",
                        "repository": {
                            "revision": "local111",
                            "remote_revision": "remote222",
                            "remote_refresh_status": "success",
                        },
                    }
                ],
                "summary": {},
            }
        ]
        server_projects = [
            {
                "slug": "oa",
                "available": True,
                "repository": {"revision": "remote222"},
                "deployment": {"deployed_revisions": ["remote222-full"]},
                "containers": [{"state": "running", "status": "Up 1 hour"}],
            }
        ]
        attach_server_comparisons(workstations, server_projects)

        comparison = workstations[0]["projects"][0]["comparison"]
        self.assertEqual(comparison["deployment_status"], "mismatch")
        self.assertEqual(comparison["runtime_status"], "match")

    def test_failed_remote_refresh_does_not_fall_back_to_local_revision(self) -> None:
        workstations = [
            {
                "online": True,
                "projects": [
                    {
                        "slug": "oa",
                        "repository": {
                            "revision": "same111",
                            "remote_revision": None,
                            "remote_refresh_status": "failed",
                        },
                    }
                ],
                "summary": {},
            }
        ]
        server_projects = [
            {
                "slug": "oa",
                "available": True,
                "repository": {"revision": "same111"},
                "deployment": {"deployed_revisions": ["same111-full"]},
                "containers": [{"state": "running", "status": "Up 1 hour"}],
            }
        ]

        attach_server_comparisons(workstations, server_projects)

        comparison = workstations[0]["projects"][0]["comparison"]
        self.assertEqual(comparison["server_status"], "match")
        self.assertEqual(comparison["deployment_status"], "match")
        self.assertEqual(comparison["runtime_status"], "unavailable")

    def test_unknown_remote_refresh_is_not_treated_as_current(self) -> None:
        workstations = [
            {
                "online": True,
                "projects": [
                    {
                        "slug": "oa",
                        "repository": {
                            "revision": "local111",
                            "remote_revision": "cached222",
                            "remote_refresh_status": "unknown",
                        },
                    }
                ],
                "summary": {},
            }
        ]
        server_projects = [
            {
                "slug": "oa",
                "available": True,
                "repository": {"revision": "cached222"},
                "deployment": {"deployed_revisions": ["cached222-full"]},
                "containers": [{"state": "running", "status": "Up 1 hour"}],
            }
        ]

        attach_server_comparisons(workstations, server_projects)

        self.assertEqual(
            workstations[0]["projects"][0]["comparison"]["runtime_status"],
            "unavailable",
        )

    def test_offline_comparisons_are_stale_not_mismatched(self) -> None:
        workstations = [
            {
                "online": False,
                "projects": [
                    {
                        "slug": "developer-os",
                        "repository": {
                            "revision": "733a70d",
                            "remote_revision": "733a70d",
                            "remote_refresh_status": "success",
                        },
                    },
                    {
                        "slug": "oa",
                        "repository": {
                            "revision": "local111",
                            "remote_revision": None,
                            "remote_refresh_status": "failed",
                        },
                    },
                    {"slug": "unknown", "repository": None},
                ],
                "summary": {},
            }
        ]
        server_projects = [
            {
                "slug": "developer-os",
                "available": True,
                "port": 8080,
                "repository": {"revision": "c6d6156"},
                "deployment": {"deployed_revisions": ["c6d6156"]},
                "containers": [],
            },
            {
                "slug": "oa",
                "available": True,
                "port": 8082,
                "repository": {"revision": "remote222"},
                "deployment": {"deployed_revisions": ["remote222"]},
                "containers": [{"state": "running", "status": "Up 1 hour"}],
            },
        ]

        attach_server_comparisons(workstations, server_projects)

        comparisons = {
            project["slug"]: project["comparison"]
            for project in workstations[0]["projects"]
        }
        stale = comparisons["developer-os"]
        self.assertFalse(stale["fresh"])
        self.assertEqual(stale["server_status"], "stale")
        self.assertEqual(stale["deployment_status"], "stale")
        self.assertEqual(stale["runtime_status"], "stale")
        self.assertEqual(stale["server_revision"], "c6d6156")
        self.assertEqual(stale["deployed_revisions"], ["c6d6156"])
        self.assertEqual(comparisons["oa"]["runtime_status"], "unavailable")
        self.assertEqual(comparisons["unknown"]["server_status"], "unavailable")
        self.assertEqual(comparisons["unknown"]["deployment_status"], "unavailable")
        self.assertEqual(comparisons["unknown"]["runtime_status"], "unavailable")
        self.assertIsNone(workstations[0]["summary"]["mismatches"])

    def test_projects_are_sorted_by_server_port(self) -> None:
        workstations = [
            {
                "online": True,
                "projects": [
                    {"slug": "gaia", "name": "Gaia", "repository": None},
                    {"slug": "unknown", "name": "Unknown", "repository": None},
                    {"slug": "developer-os", "name": "DeveloperOS", "repository": None},
                    {"slug": "btest", "name": "bTest", "repository": None},
                    {"slug": "oa", "name": "OA", "repository": None},
                ],
                "summary": {},
            }
        ]
        server_projects = [
            {"slug": "oa", "available": True, "port": 8082},
            {"slug": "gaia", "available": True, "port": 8083},
            {"slug": "developer-os", "available": True, "port": 8080},
            {"slug": "btest", "available": True, "port": 8081},
        ]

        attach_server_comparisons(workstations, server_projects)

        self.assertEqual(
            [project["slug"] for project in workstations[0]["projects"]],
            ["developer-os", "btest", "oa", "gaia", "unknown"],
        )


if __name__ == "__main__":
    unittest.main()
