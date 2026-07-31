from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TerminalProject:
    slug: str
    name: str
    path: Path


@dataclass(frozen=True)
class TerminalSettings:
    repo_root: Path
    bind: str
    port: int
    session_secret: str
    audit_path: Path
    projects: tuple[TerminalProject, ...]
    command_timeout_seconds: int
    max_output_bytes: int


def _load_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"Terminal project configuration is missing: {path}")
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("Terminal configuration must be a JSON object.")
    return value


def load_settings(*, bind: str | None = None, port: int | None = None) -> TerminalSettings:
    repo_root = Path(__file__).resolve().parents[2]
    config_path = Path(
        os.getenv(
            "DEVOS_TERMINAL_CONFIG",
            str(repo_root / "console" / "terminal-config.example.json"),
        )
    ).expanduser()
    config = _load_config(config_path)
    project_values = config.get("projects")
    if not isinstance(project_values, list) or not project_values:
        raise ValueError("Terminal configuration must contain at least one project.")

    projects: list[TerminalProject] = []
    seen: set[str] = set()
    for item in project_values:
        if not isinstance(item, dict):
            raise ValueError("Each terminal project must be an object.")
        slug = str(item.get("slug", "")).strip().lower()
        if not slug or not slug.replace("-", "").isalnum() or slug in seen:
            raise ValueError("Terminal project slugs must be unique letters, numbers, or hyphens.")
        raw_path = str(item.get("path", "")).strip()
        if not raw_path:
            raise ValueError(f"Terminal project path is required: {slug}")
        project_path = Path(raw_path).expanduser().resolve()
        if not project_path.is_absolute():
            raise ValueError(f"Terminal project path must be absolute: {slug}")
        seen.add(slug)
        projects.append(
            TerminalProject(
                slug=slug,
                name=str(item.get("name", slug)).strip() or slug,
                path=project_path,
            )
        )

    session_secret = os.getenv("DEVOS_TERMINAL_SECRET", "").strip()
    if len(session_secret) < 32:
        raise RuntimeError("DEVOS_TERMINAL_SECRET must contain at least 32 characters.")
    resolved_bind = bind or os.getenv("DEVOS_TERMINAL_BIND", "127.0.0.1")
    if resolved_bind not in {"127.0.0.1", "::1", "localhost"}:
        raise RuntimeError("The private terminal may bind only to a loopback address.")

    audit_path = Path(
        os.getenv(
            "DEVOS_TERMINAL_AUDIT",
            "/var/lib/developer-os-terminal/audit.jsonl",
        )
    ).expanduser()
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    return TerminalSettings(
        repo_root=repo_root,
        bind=resolved_bind,
        port=port or int(os.getenv("DEVOS_TERMINAL_PORT", "8022")),
        session_secret=session_secret,
        audit_path=audit_path,
        projects=tuple(projects),
        command_timeout_seconds=max(
            5,
            min(600, int(os.getenv("DEVOS_TERMINAL_TIMEOUT", "120"))),
        ),
        max_output_bytes=max(
            4096,
            min(1_048_576, int(os.getenv("DEVOS_TERMINAL_MAX_OUTPUT", "131072"))),
        ),
    )
