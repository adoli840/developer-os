from __future__ import annotations

import json
import re
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

## Roadmap Details

| Stage | Item | Status | Blocker Type | Description |
|---|---|---|---|---|
| Foundation | Parser | Done | None | The canonical roadmap parser accepts the standard fields. |
| Foundation | Visual renderer | In Progress | None | The public view renders every declared detail item. |
| Foundation | Operator approval | Blocked | Operator | The developer must approve the final publication boundary. |
| Publishing | Historical build | Blocked | Processing | Existing source data is still being processed. |
| Publishing | Paper observation | Blocked | Future | Evidence depends on future paper-runtime observations. |
| Publishing | Production bypass | Prohibited | None | Publication must never bypass the reviewed source document. |

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


def write_manifest(
    path: Path,
    tracks: list[dict[str, str]],
    *,
    schema_version: int = 1,
) -> None:
    (path / "ROADMAPS.json").write_text(
        json.dumps({"schema_version": schema_version, "tracks": tracks}),
        encoding="utf-8",
    )


def linked_track_roadmap() -> str:
    topics = """\
## Roadmap Topics

| Topic | Status | Completion Signal | Next Transition |
|---|---|---|---|
| Parser | Done | The canonical roadmap parser accepts the standard fields. | Reopen when the format changes |
| Visual renderer | In Progress | The public view renders every declared detail item. | Move to Done after visual verification |
| Operator approval | Blocked | The developer must approve the final publication boundary. | Move to Done after approval |
"""
    details = """\
## Roadmap Details

| Stage | Item | Status | Blocker Type | Description |
|---|---|---|---|---|
| Parser | Format contract | Done | None | Keep the canonical parser aligned with the shared format. |
| Visual renderer | Browser bundle | In Progress | None | Render the linked cards at desktop and mobile widths. |
| Operator approval | Publication decision | Blocked | Operator | Wait for the explicit publication decision. |
"""
    value = re.sub(
        r"## Roadmap Topics\n.*?(?=\n## Roadmap Details)",
        topics.rstrip(),
        STANDARD_ROADMAP,
        flags=re.DOTALL,
    )
    value = re.sub(
        r"## Roadmap Details\n.*?(?=\n## Current Priority)",
        details.rstrip(),
        value,
        flags=re.DOTALL,
    )
    return value.replace("# Example Roadmap", "# Delivery Roadmap")


class RoadmapParserTests(unittest.TestCase):
    def test_developer_os_roadmap_omits_the_self_referential_continuity_stage(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        result = parse_roadmap(
            (repository / "ROADMAP.md").read_text(encoding="utf-8-sig"),
            slug="developer-os",
            name="DeveloperOS",
        )

        self.assertNotIn(
            "Project roadmap continuity",
            [topic["topic"] for topic in result["topics"]],
        )
        self.assertIn(
            "Roadmap web publication",
            [topic["topic"] for topic in result["topics"]],
        )

    def test_standard_roadmap_is_parsed_into_public_fields(self) -> None:
        result = parse_roadmap(STANDARD_ROADMAP, slug="example", name="Example")

        self.assertEqual(result["state"], "available")
        self.assertEqual(result["milestone"]["status"], "In Progress")
        self.assertEqual(
            result["milestone"]["objective"],
            "Deliver the first useful release across supported environments.",
        )
        self.assertEqual(len(result["topics"]), 2)
        self.assertEqual(result["detail_mode"], "explicit")
        self.assertEqual(len(result["topics"][0]["items"]), 3)
        self.assertEqual(result["topics"][0]["items"][2]["blocker_type"], "Operator")
        self.assertNotIn("path", result)
        self.assertNotIn("raw", result)

    def test_unknown_status_is_rejected(self) -> None:
        invalid = STANDARD_ROADMAP.replace("- Status: In Progress", "- Status: Almost")
        with self.assertRaisesRegex(ValueError, "Unsupported roadmap status"):
            parse_roadmap(invalid, slug="example", name="Example")

    def test_duplicate_topic_names_are_rejected(self) -> None:
        invalid = STANDARD_ROADMAP.replace(
            "| Publishing | Planned |",
            "| Foundation | Planned |",
        )
        with self.assertRaisesRegex(ValueError, "topic names must be unique"):
            parse_roadmap(invalid, slug="example", name="Example")

    def test_blocked_detail_requires_a_specific_blocker_type(self) -> None:
        invalid = STANDARD_ROADMAP.replace(
            "| Foundation | Operator approval | Blocked | Operator |",
            "| Foundation | Operator approval | Blocked | None |",
        )
        with self.assertRaisesRegex(ValueError, "must declare a blocker type"):
            parse_roadmap(invalid, slug="example", name="Example")

    def test_legacy_roadmap_derives_compatible_detail_items(self) -> None:
        legacy = re.sub(
            r"\n## Roadmap Details\n.*?(?=\n## Current Priority)",
            "",
            STANDARD_ROADMAP,
            flags=re.DOTALL,
        )
        result = parse_roadmap(legacy, slug="example", name="Example")

        self.assertEqual(result["detail_mode"], "derived")
        self.assertEqual(
            [item["item"] for item in result["topics"][0]["items"]],
            ["Completion signal", "Next transition"],
        )

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
        self.assertEqual(result["roadmap_manifest_version"], 1)
        self.assertEqual(result["track_summary_mode"], "independent")
        self.assertEqual(result["tracks"][0]["slug"], "delivery")
        self.assertEqual(result["tracks"][0]["title"], "Delivery Roadmap")
        self.assertNotIn("path", result["tracks"][0])

    def test_manifest_v2_links_overview_items_to_track_topics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tracks_path = root / "docs" / "roadmaps"
            tracks_path.mkdir(parents=True)
            (root / "ROADMAP.md").write_text(STANDARD_ROADMAP, encoding="utf-8")
            (tracks_path / "delivery.md").write_text(
                linked_track_roadmap(),
                encoding="utf-8",
            )
            write_manifest(
                root,
                [
                    {
                        "slug": "delivery",
                        "name": "Delivery",
                        "path": "docs/roadmaps/delivery.md",
                        "overview_topic": "Foundation",
                    }
                ],
                schema_version=2,
            )

            result = collect_roadmaps((project_spec(root),))["projects"][0]

        track = result["tracks"][0]
        self.assertEqual(result["state"], "available")
        self.assertEqual(result["roadmap_manifest_version"], 2)
        self.assertEqual(result["track_summary_mode"], "linked")
        self.assertEqual(track["overview_topic"], "Foundation")
        self.assertEqual(
            [item["item"] for item in result["topics"][0]["items"]],
            [topic["topic"] for topic in track["topics"]],
        )
        self.assertEqual(track["topics"][2]["display_status"], "Blocked")
        self.assertEqual(track["topics"][2]["blocker_type"], "Operator")
        self.assertEqual(
            track["topics"][2]["description"],
            "The developer must approve the final publication boundary.",
        )

    def test_manifest_v2_rejects_overview_track_card_drift(self) -> None:
        drifted_tracks = {
            "name": linked_track_roadmap().replace(
                "| Visual renderer | In Progress |",
                "| Different renderer | In Progress |",
            ),
            "status": linked_track_roadmap().replace(
                "| Visual renderer | In Progress |",
                "| Visual renderer | Done |",
            ),
            "description": linked_track_roadmap().replace(
                "The public view renders every declared detail item.",
                "The public view renders a different completion signal.",
            ),
        }
        for drift, track_text in drifted_tracks.items():
            with self.subTest(drift=drift), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                tracks_path = root / "docs" / "roadmaps"
                tracks_path.mkdir(parents=True)
                (root / "ROADMAP.md").write_text(
                    STANDARD_ROADMAP,
                    encoding="utf-8",
                )
                (tracks_path / "delivery.md").write_text(
                    track_text,
                    encoding="utf-8",
                )
                write_manifest(
                    root,
                    [
                        {
                            "slug": "delivery",
                            "name": "Delivery",
                            "path": "docs/roadmaps/delivery.md",
                            "overview_topic": "Foundation",
                        }
                    ],
                    schema_version=2,
                )

                result = collect_roadmaps((project_spec(root),))["projects"][0]

            self.assertEqual(result["state"], "invalid")

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
                with urlopen(f"{base_url}/roadmap-assets/roadmap-view.js", timeout=5) as response:
                    renderer = response.read().decode("utf-8")
                with urlopen(f"{base_url}/roadmap-assets/roadmap-view.css", timeout=5) as response:
                    renderer_css = response.read().decode("utf-8")
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
        self.assertNotIn('id="roadmap-summary"', page)
        self.assertNotIn('id="roadmap-time"', page)
        self.assertIn('src="/roadmap-assets/roadmap-view.js?v=3.0.1"', page)
        self.assertIn('href="/roadmap-assets/roadmap-view.css?v=3.0.1"', page)
        self.assertIn('src="/app.js"', page)
        self.assertIn("DeveloperOSRoadmapView", renderer)
        self.assertIn('const VERSION = "3.0.1"', renderer)
        self.assertIn("grid-template-columns: repeat(${stageCount}, minmax(218px, 1fr))", renderer)
        self.assertIn("min-width: ${stageMinWidth}px", renderer)
        self.assertNotIn("roadmap-milestone-strip", renderer)
        self.assertIn(".devos-roadmap-view", renderer_css)


if __name__ == "__main__":
    unittest.main()
