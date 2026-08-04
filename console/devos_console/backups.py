from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .runner import run_command
from .settings import ProjectSpec


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


def _timer_state(name: str) -> dict[str, Any]:
    result = run_command(
        (
            "systemctl",
            "show",
            name,
            "--property=ActiveState",
            "--property=LastTriggerUSec",
            "--property=NextElapseUSecRealtime",
        ),
        timeout=5,
    )
    if not result.ok:
        return {"available": False, "active": False, "last": None, "next": None}
    values: dict[str, str] = {}
    for line in result.stdout.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value
    return {
        "available": True,
        "active": values.get("ActiveState") == "active",
        "last": values.get("LastTriggerUSec") or None,
        "next": values.get("NextElapseUSecRealtime") or None,
    }


def collect_backup_status(
    projects: tuple[ProjectSpec, ...],
    status_dir: Path,
    memo_database: Path | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    items: list[dict[str, Any]] = []
    protected_data = [
        (project.slug, project.name)
        for project in projects
        if project.backup_expected
    ]
    if memo_database is not None:
        protected_data.insert(0, ("developer-os-memos", "DeveloperOS memos"))
    for project_slug, project_name in protected_data:
        path = status_dir / f"{project_slug}.json"
        if not path.is_file():
            items.append(
                {
                    "project": project_slug,
                    "name": project_name,
                    "status": "missing",
                    "message": "No successful backup has been recorded.",
                    "last_success_at": None,
                    "last_file": None,
                    "size_bytes": None,
                    "age_hours": None,
                    "verification_status": "missing",
                    "last_verification_at": None,
                }
            )
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            value = {}
        last_success = _parse_time(value.get("last_success_at"))
        last_verification = _parse_time(value.get("last_verification_at"))
        age_hours = (
            round((now - last_success).total_seconds() / 3600, 1)
            if last_success
            else None
        )
        verification_age_days = (
            (now - last_verification).total_seconds() / 86400
            if last_verification
            else None
        )
        last_error = str(value.get("last_error") or "").strip()
        if last_error:
            status = "failed"
            message = last_error[:240]
        elif age_hours is None:
            status = "missing"
            message = "No successful backup has been recorded."
        elif age_hours > 36:
            status = "stale"
            message = "The latest backup is older than 36 hours."
        else:
            status = "healthy"
            message = "The latest backup passed integrity checks."
        verification_status = str(value.get("verification_status") or "missing")
        backup_policy = str(value.get("backup_policy") or "full-cluster")
        if verification_status == "passed" and verification_age_days is not None and verification_age_days > 8:
            verification_status = "stale"
        items.append(
            {
                "project": project_slug,
                "name": project_name,
                "status": status,
                "message": message,
                "last_success_at": value.get("last_success_at"),
                "last_file": value.get("last_file"),
                "size_bytes": value.get("size_bytes"),
                "sha256": value.get("sha256"),
                "age_hours": age_hours,
                "verification_status": verification_status,
                "last_verification_at": value.get("last_verification_at"),
                "verified_file": value.get("verified_file"),
                "backup_policy": backup_policy,
                "retention_days": value.get("retention_days", 14),
            }
        )
    return {
        "items": items,
        "backup_timer": _timer_state("developer-os-backup.timer"),
        "verification_timer": _timer_state("developer-os-backup-verify.timer"),
    }
