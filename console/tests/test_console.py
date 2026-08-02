from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from console.devos_console.alerts import build_alerts
from console.devos_console.auth import SessionStore
from console.devos_console.backups import collect_backup_status
from console.devos_console.projects import ProjectService
from console.devos_console.settings import ProjectSpec, WorkstationSpec, load_settings
from console.devos_console.usage import read_usage_snapshot
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


class BackupStatusTests(unittest.TestCase):
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
                "projects": [
                    {
                        "slug": "gaia",
                        "repository": {"revision": "abc1234"},
                    }
                ],
                "summary": {},
            }
        ]
        server_projects = [
            {
                "slug": "gaia",
                "available": True,
                "repository": {"revision": "abc1234"},
                "deployment": {"deployed_revisions": ["abc123456789"]},
            }
        ]
        attach_server_comparisons(workstations, server_projects)
        comparison = workstations[0]["projects"][0]["comparison"]
        self.assertEqual(comparison["server_status"], "match")
        self.assertEqual(comparison["deployment_status"], "match")
        self.assertEqual(workstations[0]["summary"]["mismatches"], 0)


if __name__ == "__main__":
    unittest.main()
