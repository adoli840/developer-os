from __future__ import annotations

import json
import os
import re
import time
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


def _cpu_ticks() -> tuple[int, int] | None:
    if os.name == "nt":
        return None
    try:
        fields = Path("/proc/stat").read_text(encoding="ascii").splitlines()[0].split()[1:]
        values = [int(value) for value in fields]
    except (OSError, ValueError, IndexError):
        return None
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    return sum(values), idle


def _cpu_percent_between(
    first: tuple[int, int] | None,
    second: tuple[int, int] | None,
) -> float | None:
    if first is None or second is None:
        return None
    total_delta = second[0] - first[0]
    idle_delta = second[1] - first[1]
    if total_delta <= 0:
        return None
    return round((1 - idle_delta / total_delta) * 100, 1)


def _child_cpu_seconds() -> float | None:
    if os.name == "nt":
        return None
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    except (ImportError, OSError):
        return None
    return usage.ru_utime + usage.ru_stime


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
            container_id = str(container.get("id") or "")
            service = str(container.get("service") or name or "Container")
            if name and project.get("slug") in usage:
                container_map[name] = (str(project["slug"]), service)
            if container_id and project.get("slug") in usage:
                container_map[container_id] = (str(project["slug"]), service)

    cpu_count = max(1, int(system.get("cpu_count") or 1))
    cpu_start = _cpu_ticks()
    child_cpu_start = _child_cpu_seconds()
    sample_started_at = time.monotonic()
    stats = run_docker(("stats", "--no-stream", "--format", "{{json .}}"), timeout=15)
    sample_seconds = max(time.monotonic() - sample_started_at, 0.001)
    child_cpu_end = _child_cpu_seconds()
    synchronized_cpu = _cpu_percent_between(cpu_start, _cpu_ticks())
    if synchronized_cpu is not None:
        system["cpu_percent"] = synchronized_cpu
    if stats.ok:
        for item in _json_lines(stats.stdout):
            target = (
                container_map.get(str(item.get("Container") or ""))
                or container_map.get(str(item.get("ID") or ""))
                or container_map.get(str(item.get("Name") or ""))
            )
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
    developer_os = usage.get("developer-os")
    if developer_os is not None and child_cpu_start is not None and child_cpu_end is not None:
        monitoring_cpu = max(0.0, child_cpu_end - child_cpu_start) / sample_seconds / cpu_count * 100
        if synchronized_cpu is not None:
            container_cpu = sum(float(project["cpu"]) for project in usage.values())
            monitoring_cpu = min(monitoring_cpu, max(0.0, synchronized_cpu - container_cpu))
        if monitoring_cpu > 0.05:
            developer_os["cpu"] += monitoring_cpu
            _add_component(developer_os["cpu_components"], "Resource monitoring", monitoring_cpu)

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
