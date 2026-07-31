from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProjectSpec:
    slug: str
    name: str
    path: Path
    compose_project: str
    port: int | None
    backup_expected: bool


@dataclass(frozen=True)
class WorkstationSpec:
    workstation_id: str
    name: str
    offline_after_seconds: int


@dataclass(frozen=True)
class Settings:
    repo_root: Path
    workspace_root: Path
    runtime_dir: Path
    bind: str
    port: int
    access_token: str
    secure_cookie: bool
    public_read_only: bool
    projects: tuple[ProjectSpec, ...]
    usage_snapshot: Path
    backup_status_dir: Path
    workstations: tuple[WorkstationSpec, ...]
    workstation_status_dir: Path


DEFAULT_PROJECTS = (
    {"slug": "developer-os", "name": "DeveloperOS", "directory": "DeveloperOS", "compose_project": "developer-os-console", "port": 8080, "backup_expected": False},
    {"slug": "btest", "name": "bTest", "directory": "bTest", "compose_project": "btest", "port": 8080, "backup_expected": False},
    {"slug": "oa", "name": "OA", "directory": "oa", "compose_project": "oa", "port": 8082, "backup_expected": True},
    {"slug": "gaia", "name": "Gaia", "directory": "gaia", "compose_project": "gaia", "port": 8083, "backup_expected": True},
)

DEFAULT_WORKSTATIONS = (
    {"id": "home", "name": "Home", "offline_after_seconds": 900},
)


def _load_optional_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("Console configuration must be a JSON object.")
    return value


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_settings(*, dev_mode: bool = False, bind: str | None = None, port: int | None = None) -> Settings:
    repo_root = Path(__file__).resolve().parents[2]
    workspace_root = Path(os.getenv("DEVOS_WORKSPACE_ROOT", str(repo_root.parent))).expanduser().resolve()
    runtime_dir = Path(os.getenv("DEVOS_RUNTIME_DIR", str(repo_root / ".console"))).expanduser().resolve()
    config_path = Path(
        os.getenv("DEVOS_CONSOLE_CONFIG", str(runtime_dir / "config.json"))
    ).expanduser()
    config = _load_optional_config(config_path)

    project_values = config.get("projects", DEFAULT_PROJECTS)
    if not isinstance(project_values, list) and not isinstance(project_values, tuple):
        raise ValueError("projects must be an array.")

    projects: list[ProjectSpec] = []
    for item in project_values:
        if not isinstance(item, dict):
            raise ValueError("Each project must be an object.")
        slug = str(item["slug"])
        directory = str(item.get("directory", slug))
        configured_path = item.get("path")
        project_path = (
            Path(str(configured_path).format(workspace=str(workspace_root)))
            if configured_path
            else workspace_root / directory
        )
        projects.append(
            ProjectSpec(
                slug=slug,
                name=str(item.get("name", slug)),
                path=project_path.resolve(),
                compose_project=str(item.get("compose_project", slug)),
                port=int(item["port"]) if item.get("port") is not None else None,
                backup_expected=bool(item.get("backup_expected", False)),
            )
        )

    workstation_values = config.get("workstations", DEFAULT_WORKSTATIONS)
    if not isinstance(workstation_values, list) and not isinstance(workstation_values, tuple):
        raise ValueError("workstations must be an array.")
    workstations: list[WorkstationSpec] = []
    for item in workstation_values:
        if not isinstance(item, dict):
            raise ValueError("Each workstation must be an object.")
        workstation_id = str(item["id"]).strip().lower()
        if not workstation_id.replace("-", "").isalnum():
            raise ValueError("Workstation IDs may contain letters, numbers, and hyphens only.")
        workstations.append(
            WorkstationSpec(
                workstation_id=workstation_id,
                name=str(item.get("name", workstation_id)),
                offline_after_seconds=max(300, int(item.get("offline_after_seconds", 900))),
            )
        )

    access_token = os.getenv("DEVOS_CONSOLE_TOKEN", "").strip()
    if not dev_mode and not access_token:
        raise RuntimeError("DEVOS_CONSOLE_TOKEN is required outside development mode.")

    runtime_dir.mkdir(parents=True, exist_ok=True)
    usage_snapshot = Path(
        os.getenv(
            "DEVOS_OPENAI_USAGE_SNAPSHOT",
            str(runtime_dir / "openai-usage.json"),
        )
    ).expanduser()
    backup_status_dir = Path(
        os.getenv(
            "DEVOS_BACKUP_STATUS_DIR",
            str(runtime_dir / "backup-status"),
        )
    ).expanduser()
    workstation_status_dir = Path(
        os.getenv(
            "DEVOS_WORKSTATION_STATUS_DIR",
            str(runtime_dir / "workstations"),
        )
    ).expanduser()

    return Settings(
        repo_root=repo_root,
        workspace_root=workspace_root,
        runtime_dir=runtime_dir,
        bind=bind or os.getenv("DEVOS_BIND", "127.0.0.1"),
        port=port or int(os.getenv("DEVOS_PORT", "8080")),
        access_token=access_token,
        secure_cookie=_bool_env("DEVOS_SECURE_COOKIE", not dev_mode),
        public_read_only=_bool_env("DEVOS_PUBLIC_READ_ONLY", False),
        projects=tuple(projects),
        usage_snapshot=usage_snapshot,
        backup_status_dir=backup_status_dir,
        workstations=tuple(workstations),
        workstation_status_dir=workstation_status_dir,
    )
