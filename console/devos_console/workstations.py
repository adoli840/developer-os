from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .settings import WorkstationSpec


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _safe_repository(value: object) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        "branch": str(value.get("branch") or "detached"),
        "revision": str(value.get("revision") or "") or None,
        "modified": max(0, int(value.get("modified") or 0)),
        "staged": max(0, int(value.get("staged") or 0)),
        "unstaged": max(0, int(value.get("unstaged") or 0)),
        "untracked": max(0, int(value.get("untracked") or 0)),
        "upstream": str(value.get("upstream") or "") or None,
        "remote_revision": str(value.get("remote_revision") or "") or None,
        "ahead": max(0, int(value.get("ahead") or 0)),
        "behind": max(0, int(value.get("behind") or 0)),
        "last_commit_at": str(value.get("last_commit_at") or "") or None,
    }


def _safe_projects(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    projects: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        projects.append(
            {
                "slug": str(item.get("slug") or ""),
                "name": str(item.get("name") or item.get("slug") or "Project"),
                "available": bool(item.get("available")),
                "repository": _safe_repository(item.get("repository")),
            }
        )
    return projects


def collect_workstations(
    specs: tuple[WorkstationSpec, ...],
    status_dir: Path,
) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    results: list[dict[str, Any]] = []
    for spec in specs:
        path = status_dir / f"{spec.workstation_id}.json"
        if not path.is_file():
            results.append(
                {
                    "id": spec.workstation_id,
                    "name": spec.name,
                    "status": "never_reported",
                    "online": False,
                    "last_report_at": None,
                    "age_seconds": None,
                    "hostname": None,
                    "projects": [],
                    "summary": {"available": 0, "dirty": 0, "ahead": 0, "behind": 0},
                }
            )
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            value = {}
        if value.get("workstation") != spec.workstation_id:
            value = {}
        generated_at = _parse_time(value.get("generated_at"))
        age_seconds = int((now - generated_at).total_seconds()) if generated_at else None
        online = age_seconds is not None and 0 <= age_seconds <= spec.offline_after_seconds
        projects = _safe_projects(value.get("projects"))
        available_projects = [project for project in projects if project["available"]]
        repositories = [project["repository"] for project in available_projects if project["repository"]]
        results.append(
            {
                "id": spec.workstation_id,
                "name": spec.name,
                "status": "online" if online else ("offline" if generated_at else "invalid"),
                "online": online,
                "last_report_at": value.get("generated_at") if generated_at else None,
                "age_seconds": age_seconds,
                "hostname": str(value.get("hostname") or "") or None,
                "projects": projects,
                "summary": {
                    "available": len(available_projects),
                    "dirty": sum(1 for repository in repositories if repository["modified"] > 0),
                    "ahead": sum(repository["ahead"] for repository in repositories),
                    "behind": sum(repository["behind"] for repository in repositories),
                },
            }
        )
    return results


def _revisions_match(first: object, second: object) -> bool:
    left = str(first or "")
    right = str(second or "")
    return bool(left and right and (left.startswith(right) or right.startswith(left)))


def _service_status(server_project: dict[str, Any] | None) -> str:
    if not server_project or not server_project.get("available"):
        return "unavailable"
    containers = server_project.get("containers") or []
    if not containers:
        return "healthy" if server_project.get("slug") == "developer-os" else "unavailable"
    running = sum(
        1 for container in containers if str(container.get("state")).lower() == "running"
    )
    unhealthy = any(
        "unhealthy" in str(container.get("status")).lower() for container in containers
    )
    if running == len(containers) and not unhealthy:
        return "healthy"
    return "stopped" if running == 0 else "degraded"


def attach_server_comparisons(
    workstations: list[dict[str, Any]],
    server_projects: list[dict[str, Any]],
) -> None:
    server_by_slug = {project["slug"]: project for project in server_projects}
    for workstation in workstations:
        mismatches = 0
        for project in workstation["projects"]:
            local_revision = (project.get("repository") or {}).get("revision")
            remote_revision = (project.get("repository") or {}).get("remote_revision")
            server_project = server_by_slug.get(project["slug"])
            server_revision = (
                (server_project.get("repository") or {}).get("revision")
                if server_project and server_project.get("available")
                else None
            )
            deployed_revisions = (
                server_project.get("deployment", {}).get("deployed_revisions", [])
                if server_project
                else []
            )
            if not local_revision or not server_revision:
                server_status = "unavailable"
            else:
                server_status = "match" if _revisions_match(local_revision, server_revision) else "mismatch"
            if not local_revision or not deployed_revisions:
                deployment_status = "unavailable"
            else:
                deployment_status = (
                    "match"
                    if any(_revisions_match(local_revision, revision) for revision in deployed_revisions)
                    else "mismatch"
                )
            runtime_target = remote_revision or local_revision
            if not runtime_target or not deployed_revisions:
                runtime_status = "unavailable"
            else:
                runtime_status = (
                    "match"
                    if any(_revisions_match(runtime_target, revision) for revision in deployed_revisions)
                    else "mismatch"
                )
            if server_status == "mismatch" or deployment_status == "mismatch":
                mismatches += 1
            project["comparison"] = {
                "server_status": server_status,
                "server_revision": server_revision,
                "deployment_status": deployment_status,
                "deployed_revisions": deployed_revisions,
                "runtime_status": runtime_status,
                "service_status": _service_status(server_project),
            }
            project["port"] = server_project.get("port") if server_project else None
        workstation["summary"]["mismatches"] = mismatches
