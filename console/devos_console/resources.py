from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .runner import run_command, run_docker
from .settings import ProjectSpec


SIZE_PATTERN = re.compile(r"^([0-9]+(?:\.[0-9]+)?)\s*([kmgt]?i?b)$", re.IGNORECASE)
SIZE_FACTORS = {
    "b": 1,
    "kb": 1_000,
    "mb": 1_000_000,
    "gb": 1_000_000_000,
    "tb": 1_000_000_000_000,
    "kib": 1_024,
    "mib": 1_048_576,
    "gib": 1_073_741_824,
    "tib": 1_099_511_627_776,
}


def _parse_size(value: object) -> int | None:
    match = SIZE_PATTERN.fullmatch(str(value or "").strip())
    if not match:
        return None
    return int(float(match.group(1)) * SIZE_FACTORS[match.group(2).lower()])


def _parse_percent(value: object) -> float | None:
    try:
        return float(str(value or "").strip().removesuffix("%"))
    except ValueError:
        return None


def _labels(value: object) -> dict[str, str]:
    labels: dict[str, str] = {}
    for item in str(value or "").split(","):
        name, separator, label_value = item.partition("=")
        if separator:
            labels[name] = label_value
    return labels


def _json_lines(value: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for line in value.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            items.append(item)
    return items


def _directory_size(path: Path) -> int | None:
    result = run_command(("du", "-sb", str(path)), timeout=12)
    if not result.ok:
        return None
    try:
        return int(result.stdout.split()[0])
    except (ValueError, IndexError):
        return None


def _add_component(components: dict[str, float], name: str, value: float) -> None:
    components[name] = components.get(name, 0) + value


def _metric_rows(
    usage: dict[str, dict[str, Any]],
    metric: str,
    total: float | int | None,
    other_name: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    managed_total = 0.0
    for project in usage.values():
        value = project[metric]
        managed_total += value
        if value <= 0:
            continue
        components = sorted(
            project[f"{metric}_components"].items(),
            key=lambda item: item[1],
            reverse=True,
        )
        rows.append(
            {
                "slug": project["slug"],
                "name": project["name"],
                "value": round(value, 1) if metric == "cpu" else int(value),
                "components": [
                    {
                        "name": name,
                        "value": round(component_value, 1) if metric == "cpu" else int(component_value),
                    }
                    for name, component_value in components[:4]
                ],
            }
        )
    rows.sort(key=lambda item: item["value"], reverse=True)
    if total is not None:
        other = max(0.0, float(total) - managed_total)
        if other > (0.05 if metric == "cpu" else 0):
            rows.append(
                {
                    "slug": "other",
                    "name": "Server & other",
                    "value": round(other, 1) if metric == "cpu" else int(other),
                    "components": [{"name": other_name, "value": round(other, 1) if metric == "cpu" else int(other)}],
                }
            )
    return rows


def collect_resource_breakdown(
    specs: tuple[ProjectSpec, ...],
    projects: list[dict[str, Any]],
    system: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    usage: dict[str, dict[str, Any]] = {
        spec.slug: {
            "slug": spec.slug,
            "name": spec.name,
            "cpu": 0.0,
            "memory": 0,
            "disk": 0,
            "cpu_components": {},
            "memory_components": {},
            "disk_components": {},
        }
        for spec in specs
    }
    compose_to_slug = {spec.compose_project: spec.slug for spec in specs}
    container_map: dict[str, tuple[str, str]] = {}
    for project in projects:
        for container in project.get("containers") or []:
            name = str(container.get("name") or "")
            service = str(container.get("service") or name or "Container")
            if name and project.get("slug") in usage:
                container_map[name] = (str(project["slug"]), service)

    cpu_count = max(1, int(system.get("cpu_count") or 1))
    stats = run_docker(("stats", "--no-stream", "--format", "{{json .}}"), timeout=15)
    if stats.ok:
        for item in _json_lines(stats.stdout):
            target = container_map.get(str(item.get("Name") or ""))
            if not target:
                continue
            slug, service = target
            cpu = _parse_percent(item.get("CPUPerc"))
            memory = _parse_size(str(item.get("MemUsage") or "").partition("/")[0].strip())
            if cpu is not None:
                host_cpu = cpu / cpu_count
                usage[slug]["cpu"] += host_cpu
                _add_component(usage[slug]["cpu_components"], service, host_cpu)
            if memory is not None:
                usage[slug]["memory"] += memory
                _add_component(usage[slug]["memory_components"], service, memory)

    disk_report = run_docker(
        (
            "system",
            "df",
            "-v",
            "--format",
            '{"Containers":{{json .Containers}},"Volumes":{{json .Volumes}}}',
        ),
        timeout=20,
    )
    disk_items = _json_lines(disk_report.stdout) if disk_report.ok else []
    disk_payload = disk_items[0] if disk_items else {}
    for item in disk_payload.get("Containers") or []:
        labels = _labels(item.get("Labels"))
        slug = compose_to_slug.get(labels.get("com.docker.compose.project", ""))
        size = _parse_size(item.get("Size"))
        if slug and size is not None:
            usage[slug]["disk"] += size
            _add_component(usage[slug]["disk_components"], "Container writes", size)
    for item in disk_payload.get("Volumes") or []:
        labels = _labels(item.get("Labels"))
        slug = compose_to_slug.get(labels.get("com.docker.compose.project", ""))
        size = _parse_size(item.get("Size"))
        if slug and size is not None:
            usage[slug]["disk"] += size
            _add_component(usage[slug]["disk_components"], "Docker volumes", size)
    for spec in specs:
        size = _directory_size(spec.path) if spec.path.is_dir() else None
        if size is not None:
            usage[spec.slug]["disk"] += size
            _add_component(usage[spec.slug]["disk_components"], "Project files", size)

    memory_total = (system.get("memory") or {}).get("used")
    disk_total = (system.get("disk") or {}).get("used")
    return {
        "cpu": _metric_rows(usage, "cpu", system.get("cpu_percent"), "OS and unmanaged services"),
        "memory": _metric_rows(usage, "memory", memory_total, "OS cache and unmanaged services"),
        "disk": _metric_rows(usage, "disk", disk_total, "OS, images, backups, and unassigned files"),
    }
