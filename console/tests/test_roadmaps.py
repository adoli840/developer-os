from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen

from console.devos_console.roadmaps import collect_roadmaps, parse_roadmap
from console.devos_console.server import create_server
from console.devos_console.settings import ProjectSpec, Settings


STANDARD_ROADMAP = """\
# Example Roadmap

Updated: 2026-08-02

## Direction

Build a small, reliable example project.

## Current Milestone

- Objective: Deliver the first useful release across
  supported environments.
- Status: In Progress
- Completion signal: The release passes its focused checks.

## Roadmap Topics

| Topic | Status | Completion Signal | Next Transition |
|---|---|---|---|
| Foundation | In Progress | Focused checks pass | Move to Done after verification |
| Publishing | Planned | Read-only page is available | Start after Foundation |

## Current Priority

1. Complete Foundation.
2. Begin Publishing.

## Latest Status Change

- Topic: Foundation
- Change: Planned -> In Progress
- Evidence or reason: Implementation started.

## Next Status Transitions

1. Move Foundation to `Done` after verification.

## Risks And Blockers

- None known.

## Completed Topics

- None yet.
"""


def project_spec(path: Path, slug: str = "example", name: str = "Example") -> ProjectSpec:
    return ProjectSpec(
        slug=slug,
        name=name,
        path=path,
        compose_project=slug,
        port=None,
        backup_expected=False,
    )


def write_manifest(path: Path, tracks: list[dict[str, str]]) -> None:
    (path / "ROADMAPS.json").write_text(
        json.dumps({"schema_version": 1, "tracks": tracks}),
        encoding="utf-8",
    )


class RoadmapParserTests(unittest.TestCase):
    def test_standard_roadmap_is_parsed_into_public_fields(self) -> None:
        result = parse_roadmap(STANDARD_ROADMAP, slug="example", name="Example")

        self.assertEqual(result["state"], "available")
        self.assertEqual(result["milestone"]["status"], "In Progress")
        self.assertEqual(
            result["milestone"]["objective"],
            "Deliver the first useful release across supported environments.",
        )
        self.assertEqual(len(result["topics"]), 2)
        self.assertNotIn("path", result)
        self.assertNotIn("raw", result)

    def test_unknown_status_is_rejected(self) -> None:
        invalid = STANDARD_ROADMAP.replace("- Status: In Progress", "- Status: Almost")
        with self.assertRaisesRegex(ValueError, "Unsupported roadmap status"):
            parse_roadmap(invalid, slug="example", name="Example")

    def test_collection_distinguishes_missing_and_invalid_documents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            valid_path = root / "valid"
            invalid_path = root / "invalid"
            missing_path = root / "missing"
            valid_path.mkdir()
            invalid_path.mkdir()
            missing_path.mkdir()
            (valid_path / "ROADMAP.md").write_text(STANDARD_ROADMAP, encoding="utf-8")
            (invalid_path / "ROADMAP.md").write_text("# Invalid", encoding="utf-8")

            result = collect_roadmaps(
                (
                    project_spec(valid_path, "valid", "Valid"),
                    project_spec(invalid_path, "invalid", "Invalid"),
                    project_spec(missing_path, "missing", "Missing"),
                )
            )

        self.assertEqual(
            result["summary"],
            {"total": 3, "available": 1, "missing": 1, "invalid": 1},
        )
        self.assertEqual(
            [project["state"] for project in result["projects"]],
            ["available", "invalid", "missing"],
        )

    def test_manifest_collects_overview_and_tracks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tracks_path = root / "docs" / "roadmaps"
            tracks_path.mkdir(parents=True)
            (root / "ROADMAP.md").write_text(STANDARD_ROADMAP, encoding="utf-8")
            (tracks_path / "delivery.md").write_text(
                STANDARD_ROADMAP.replace("# Example Roadmap", "# Delivery Roadmap"),
                encoding="utf-8",
            )
            write_manifest(
                root,
                [{"slug": "delivery", "name": "Delivery", "path": "docs/roadmaps/delivery.md"}],
            )

            result = collect_roadmaps((project_spec(root),))["projects"][0]

        self.assertEqual(result["state"], "available")
        self.assertEqual(result["roadmap_mode"], "multi")
        self.assertEqual(result["tracks"][0]["slug"], "delivery")
        self.assertEqual(result["tracks"][0]["title"], "Delivery Roadmap")
        self.assertNotIn("path", result["tracks"][0])

    def test_manifest_rejects_duplicate_track_slugs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.mkdir(exist_ok=True)
            (root / "ROADMAP.md").write_text(STANDARD_ROADMAP, encoding="utf-8")
            write_manifest(
                root,
                [
                    {"slug": "delivery", "name": "Delivery", "path": "docs/one.md"},
                    {"slug": "delivery", "name": "Support", "path": "docs/two.md"},
                ],
            )

            result = collect_roadmaps((project_spec(root),))["projects"][0]

        self.assertEqual(result["state"], "invalid")

    def test_manifest_rejects_paths_outside_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            root.mkdir()
            (root / "ROADMAP.md").write_text(STANDARD_ROADMAP, encoding="utf-8")
            (workspace / "outside.md").write_text(STANDARD_ROADMAP, encoding="utf-8")
            write_manifest(
                root,
                [{"slug": "outside", "name": "Outside", "path": "../outside.md"}],
            )

            result = collect_roadmaps((project_spec(root),))["projects"][0]

        self.assertEqual(result["state"], "invalid")
        self.assertNotIn(str(workspace), json.dumps(result))

    def test_manifest_is_invalid_when_a_track_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ROADMAP.md").write_text(STANDARD_ROADMAP, encoding="utf-8")
            write_manifest(
                root,
                [{"slug": "missing", "name": "Missing", "path": "docs/missing.md"}],
            )

            result = collect_roadmaps((project_spec(root),))["projects"][0]

        self.assertEqual(result["state"], "invalid")


class RoadmapRouteTests(unittest.TestCase):
    def test_public_console_serves_roadmap_page_and_structured_api(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project_path = root / "project"
            runtime_path = root / "runtime"
            project_path.mkdir()
            runtime_path.mkdir()
            (project_path / "ROADMAP.md").write_text(STANDARD_ROADMAP, encoding="utf-8")
            track_path = project_path / "docs" / "roadmaps"
            track_path.mkdir(parents=True)
            (track_path / "delivery.md").write_text(
                STANDARD_ROADMAP.replace("# Example Roadmap", "# Delivery Roadmap"),
                encoding="utf-8",
            )
            write_manifest(
                project_path,
                [{"slug": "delivery", "name": "Delivery", "path": "docs/roadmaps/delivery.md"}],
            )
            settings = Settings(
                repo_root=Path(__file__).resolve().parents[2],
                workspace_root=root,
                runtime_dir=runtime_path,
                bind="127.0.0.1",
                port=0,
                access_token="test-token",
                secure_cookie=False,
                public_read_only=True,
                trusted_local=False,
                projects=(project_spec(project_path),),
                usage_snapshot=runtime_path / "usage.json",
                oracle_usage_snapshot=runtime_path / "oracle-usage.json",
                backup_status_dir=runtime_path / "backups",
                workstations=(),
                workstation_status_dir=runtime_path / "workstations",
            )
            server = create_server(settings)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                with urlopen(f"{base_url}/api/roadmaps", timeout=5) as response:
                    payload = json.load(response)
                with urlopen(f"{base_url}/roadmap", timeout=5) as response:
                    page = response.read().decode("utf-8")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(payload["projects"][0]["title"], "Example Roadmap")
        self.assertEqual(payload["projects"][0]["roadmap_mode"], "multi")
        self.assertEqual(payload["projects"][0]["tracks"][0]["title"], "Delivery Roadmap")
        self.assertNotIn("path", payload["projects"][0])
        self.assertNotIn("path", payload["projects"][0]["tracks"][0])
        self.assertIn('id="tab-roadmap"', page)
        self.assertIn('id="roadmap-track-tabs"', page)
        self.assertIn('src="/app.js"', page)


if __name__ == "__main__":
    unittest.main()
