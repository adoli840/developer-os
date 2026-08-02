from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .settings import ProjectSpec


MAX_ROADMAP_BYTES = 131_072
MAX_MANIFEST_BYTES = 16_384
MAX_ROADMAP_TRACKS = 8
ROADMAP_FILENAME = "ROADMAP.md"
ROADMAP_MANIFEST_FILENAME = "ROADMAPS.json"
ROADMAP_STATUSES = (
    "Planned",
    "In Progress",
    "Blocked",
    "Paused",
    "Done",
    "Prohibited",
    "Cancelled",
)
ROADMAP_DETAIL_STATUSES = ("Done", "In Progress", "Blocked", "Prohibited")
ROADMAP_BLOCKER_TYPES = ("None", "Operator", "Processing", "Future")
REQUIRED_SECTIONS = (
    "Direction",
    "Current Milestone",
    "Roadmap Topics",
    "Current Priority",
    "Latest Status Change",
    "Next Status Transitions",
    "Risks And Blockers",
)


def collect_roadmaps(projects: Iterable[ProjectSpec]) -> dict[str, Any]:
    items = [_read_project_roadmap(project) for project in projects]
    counts = {
        state: sum(item["state"] == state for item in items)
        for state in ("available", "missing", "invalid")
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {"total": len(items), **counts},
        "projects": items,
    }


def parse_roadmap(text: str, *, slug: str, name: str) -> dict[str, Any]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    title = _first_match(lines, re.compile(r"^#\s+(.+?)\s*$"), "roadmap title")
    updated_at = _first_match(
        lines,
        re.compile(r"^Updated:\s*(\d{4}-\d{2}-\d{2})\s*$"),
        "Updated date",
    )
    try:
        datetime.strptime(updated_at, "%Y-%m-%d")
    except ValueError as error:
        raise ValueError("Updated date must be a real YYYY-MM-DD date.") from error

    sections = _sections(lines)
    missing_sections = [name for name in REQUIRED_SECTIONS if name not in sections]
    if missing_sections:
        raise ValueError(f"Missing required section: {missing_sections[0]}.")

    direction = _paragraph(sections["Direction"])
    if not direction:
        raise ValueError("Direction must not be empty.")

    milestone = _required_labels(
        sections["Current Milestone"],
        ("Objective", "Status", "Completion signal"),
        "Current Milestone",
    )
    milestone["Status"] = _canonical_status(milestone["Status"])

    latest_change = _required_labels(
        sections["Latest Status Change"],
        ("Topic", "Change", "Evidence or reason"),
        "Latest Status Change",
    )
    topics = _topic_rows(sections["Roadmap Topics"])
    detail_mode = "derived"
    if "Roadmap Details" in sections:
        details = _detail_rows(sections["Roadmap Details"], topics)
        for topic in topics:
            topic["items"] = details[topic["topic"]]
        detail_mode = "explicit"
    else:
        for topic in topics:
            topic["items"] = _derived_detail_items(topic)
    priorities = _ordered_items(sections["Current Priority"])
    transitions = _ordered_items(sections["Next Status Transitions"])
    risks = _bullet_items(sections["Risks And Blockers"])
    if not priorities:
        raise ValueError("Current Priority must contain an ordered item.")
    if not transitions:
        raise ValueError("Next Status Transitions must contain an ordered item.")
    if not risks:
        raise ValueError("Risks And Blockers must contain a bullet item.")

    return {
        "slug": slug,
        "name": name,
        "state": "available",
        "title": title,
        "updated_at": updated_at,
        "direction": direction,
        "milestone": {
            "objective": milestone["Objective"],
            "status": milestone["Status"],
            "completion_signal": milestone["Completion signal"],
        },
        "topics": topics,
        "detail_mode": detail_mode,
        "current_priority": priorities,
        "latest_status_change": {
            "topic": latest_change["Topic"],
            "change": latest_change["Change"],
            "evidence_or_reason": latest_change["Evidence or reason"],
        },
        "next_status_transitions": transitions,
        "risks_and_blockers": risks,
    }


def _read_project_roadmap(project: ProjectSpec) -> dict[str, Any]:
    manifest_path = project.path / ROADMAP_MANIFEST_FILENAME
    if manifest_path.is_file():
        return _read_multi_track_roadmap(project, manifest_path)

    roadmap_path = project.path / ROADMAP_FILENAME
    if not roadmap_path.is_file():
        return _unavailable(project, "missing", "Standard ROADMAP.md is not available.")
    try:
        roadmap = _read_roadmap_file(
            roadmap_path,
            slug=project.slug,
            name=project.name,
        )
        roadmap["roadmap_mode"] = "single"
        roadmap["tracks"] = []
        return roadmap
    except (OSError, UnicodeError, ValueError):
        return _unavailable(
            project,
            "invalid",
            "Roadmap does not match the DeveloperOS standard format.",
        )


def _read_multi_track_roadmap(
    project: ProjectSpec,
    manifest_path: Path,
) -> dict[str, Any]:
    try:
        manifest = _load_manifest(project.path, manifest_path)
        overview = _read_roadmap_file(
            project.path / ROADMAP_FILENAME,
            slug=project.slug,
            name=project.name,
        )
        overview["roadmap_mode"] = "multi"
        overview["tracks"] = [
            _read_roadmap_file(
                track["path"],
                slug=track["slug"],
                name=track["name"],
            )
            for track in manifest
        ]
        return overview
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError):
        return _unavailable(
            project,
            "invalid",
            "Roadmap manifest or one of its roadmaps is invalid.",
        )


def _load_manifest(project_root: Path, manifest_path: Path) -> list[dict[str, Any]]:
    if manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError("Roadmap manifest exceeds the supported size limit.")
    value = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("Roadmap manifest must use schema version 1.")

    tracks = value.get("tracks")
    if not isinstance(tracks, list) or not 1 <= len(tracks) <= MAX_ROADMAP_TRACKS:
        raise ValueError("Roadmap manifest must contain between 1 and 8 tracks.")

    result: list[dict[str, Any]] = []
    seen_slugs: set[str] = set()
    seen_names: set[str] = set()
    seen_paths: set[Path] = set()
    for track in tracks:
        if not isinstance(track, dict):
            raise ValueError("Each roadmap track must be an object.")
        slug = track.get("slug")
        name = track.get("name")
        relative_path = track.get("path")
        if not isinstance(slug, str) or not re.fullmatch(
            r"[a-z0-9]+(?:-[a-z0-9]+)*",
            slug,
        ):
            raise ValueError("Roadmap track slug is invalid.")
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
            raise ValueError("Roadmap track name is invalid.")
        if slug in seen_slugs or name.strip().casefold() in seen_names:
            raise ValueError("Roadmap track slugs and names must be unique.")

        path = _safe_roadmap_path(project_root, relative_path)
        if path in seen_paths or path == (project_root / ROADMAP_FILENAME).resolve():
            raise ValueError("Roadmap track paths must be unique.")
        seen_slugs.add(slug)
        seen_names.add(name.strip().casefold())
        seen_paths.add(path)
        result.append({"slug": slug, "name": name.strip(), "path": path})
    return result


def _safe_roadmap_path(project_root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Roadmap track path is invalid.")
    relative = Path(value)
    if relative.is_absolute() or relative.suffix.casefold() != ".md":
        raise ValueError("Roadmap track path must be a relative Markdown path.")
    root = project_root.resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ValueError("Roadmap track path must stay inside the project.") from error
    return candidate


def _read_roadmap_file(path: Path, *, slug: str, name: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError("Roadmap file is missing.")
    if path.stat().st_size > MAX_ROADMAP_BYTES:
        raise ValueError("Roadmap exceeds the supported size limit.")
    return parse_roadmap(
        path.read_text(encoding="utf-8-sig"),
        slug=slug,
        name=name,
    )


def _unavailable(project: ProjectSpec, state: str, message: str) -> dict[str, Any]:
    return {
        "slug": project.slug,
        "name": project.name,
        "state": state,
        "message": message,
    }


def _first_match(lines: list[str], pattern: re.Pattern[str], label: str) -> str:
    for line in lines:
        match = pattern.match(line.strip())
        if match:
            return match.group(1).strip()
    raise ValueError(f"Missing {label}.")


def _sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in lines:
        match = re.match(r"^##\s+(.+?)\s*$", line.strip())
        if match:
            current = []
            sections[match.group(1)] = current
        elif current is not None:
            current.append(line)
    return sections


def _paragraph(lines: list[str]) -> str:
    return _collapse(line.strip() for line in lines if line.strip())


def _required_labels(
    lines: list[str], required: tuple[str, ...], section_name: str
) -> dict[str, str]:
    values: dict[str, str] = {}
    current_key: str | None = None
    labels = {label.casefold(): label for label in required}
    for line in lines:
        match = re.match(r"^\s*-\s+([^:]+):\s*(.*)$", line)
        if match:
            key = labels.get(match.group(1).strip().casefold())
            current_key = key
            if key:
                values[key] = match.group(2).strip()
            continue
        if current_key and line.strip():
            values[current_key] = _collapse((values[current_key], line.strip()))
    for label in required:
        if not values.get(label):
            raise ValueError(f"{section_name} is missing {label}.")
    return values


def _topic_rows(lines: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    header_seen = False
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [cell.strip() for cell in stripped[1:-1].split("|")]
        if cells == ["Topic", "Status", "Completion Signal", "Next Transition"]:
            header_seen = True
            continue
        if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        if len(cells) != 4 or not all(cells):
            raise ValueError("Roadmap Topics contains a malformed row.")
        rows.append(
            {
                "topic": cells[0],
                "status": _canonical_status(cells[1]),
                "completion_signal": cells[2],
                "next_transition": cells[3],
            }
        )
    if not header_seen:
        raise ValueError("Roadmap Topics must use the standard table header.")
    if not rows:
        raise ValueError("Roadmap Topics must contain at least one topic.")
    return rows


def _detail_rows(
    lines: list[str],
    topics: list[dict[str, Any]],
) -> dict[str, list[dict[str, str]]]:
    topic_names = {topic["topic"] for topic in topics}
    rows = {name: [] for name in topic_names}
    seen_items: set[tuple[str, str]] = set()
    header_seen = False
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [cell.strip() for cell in stripped[1:-1].split("|")]
        if cells == ["Stage", "Item", "Status", "Blocker Type", "Description"]:
            header_seen = True
            continue
        if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        if len(cells) != 5 or not all(cells):
            raise ValueError("Roadmap Details contains a malformed row.")
        stage, item, status, blocker_type, description = cells
        if stage not in topic_names:
            raise ValueError(f"Roadmap Details references an unknown stage: {stage}.")
        status = _canonical_detail_status(status)
        blocker_type = _canonical_blocker_type(blocker_type)
        if status == "Blocked" and blocker_type == "None":
            raise ValueError("Blocked roadmap details must declare a blocker type.")
        if status != "Blocked" and blocker_type != "None":
            raise ValueError("Only blocked roadmap details may declare a blocker type.")
        item_key = (stage.casefold(), item.casefold())
        if item_key in seen_items:
            raise ValueError("Roadmap detail item names must be unique within a stage.")
        seen_items.add(item_key)
        rows[stage].append(
            {
                "item": item,
                "status": status,
                "blocker_type": blocker_type,
                "description": description,
            }
        )
    if not header_seen:
        raise ValueError("Roadmap Details must use the standard table header.")
    missing = next((name for name, items in rows.items() if not items), None)
    if missing:
        raise ValueError(f"Roadmap Details must include every stage: {missing}.")
    return rows


def _derived_detail_items(topic: dict[str, str]) -> list[dict[str, str]]:
    status = _detail_status_for_topic(topic["status"])
    return [
        {
            "item": "Completion signal",
            "status": status,
            "blocker_type": "None",
            "description": topic["completion_signal"],
        },
        {
            "item": "Next transition",
            "status": status,
            "blocker_type": "None",
            "description": topic["next_transition"],
        },
    ]


def _detail_status_for_topic(status: str) -> str:
    if status == "Done":
        return "Done"
    if status in {"Blocked", "Paused"}:
        return "Blocked"
    if status in {"Prohibited", "Cancelled"}:
        return "Prohibited"
    return "In Progress"


def _ordered_items(lines: list[str]) -> list[str]:
    return _list_items(lines, re.compile(r"^\s*\d+\.\s+(.+)$"))


def _bullet_items(lines: list[str]) -> list[str]:
    return _list_items(lines, re.compile(r"^\s*-\s+(.+)$"))


def _list_items(lines: list[str], pattern: re.Pattern[str]) -> list[str]:
    items: list[str] = []
    for line in lines:
        match = pattern.match(line)
        if match:
            items.append(match.group(1).strip())
        elif items and line.strip():
            items[-1] = _collapse((items[-1], line.strip()))
    return [item for item in items if item]


def _canonical_status(value: str) -> str:
    normalized = value.strip().casefold()
    for status in ROADMAP_STATUSES:
        if status.casefold() == normalized:
            return status
    raise ValueError(f"Unsupported roadmap status: {value}.")


def _canonical_detail_status(value: str) -> str:
    normalized = value.strip().casefold()
    for status in ROADMAP_DETAIL_STATUSES:
        if status.casefold() == normalized:
            return status
    raise ValueError(f"Unsupported roadmap detail status: {value}.")


def _canonical_blocker_type(value: str) -> str:
    normalized = value.strip().casefold()
    for blocker_type in ROADMAP_BLOCKER_TYPES:
        if blocker_type.casefold() == normalized:
            return blocker_type
    raise ValueError(f"Unsupported roadmap blocker type: {value}.")


def _collapse(parts: Iterable[str]) -> str:
    return " ".join(" ".join(parts).split())
