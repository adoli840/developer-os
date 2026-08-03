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


PROCESS_CATEGORIES = {
    "developer_os": (
        "DeveloperOS services",
        "Console and monitoring processes. Required for this view; reducible only by disabling DeveloperOS services.",
        "service",
    ),
    "docker": (
        "Docker engine",
        "Docker daemon, container runtime, and proxy processes required while containerized projects run.",
        "service",
    ),
    "remote_access": (
        "Remote access",
        "SSH processes that keep private administration available.",
        "service",
    ),
    "unmanaged_containers": (
        "Unmanaged containers",
        "Container processes that are not attributed to a registered DeveloperOS project.",
        "reviewable",
    ),
    "host_processes": (
        "Other host processes",
        "System and user processes outside registered project containers.",
        "reviewable",
    ),
}


def _process_category(command: str, cmdline: str, cgroup: str, container_ids: set[str]) -> str:
    normalized = f"{command} {cmdline}".lower()
    managed_container = any(container_id in cgroup for container_id in container_ids)
    container_process = "docker" in cgroup or "containerd" in cgroup or "kubepods" in cgroup
    if managed_container:
        return "managed"
    if command in {"dockerd", "containerd", "containerd-shim", "docker-proxy"}:
        return "docker"
    if "devos_console" in normalized or "developer-os-console" in normalized:
        return "developer_os"
    if command == "sshd" or normalized.startswith("ssh "):
        return "remote_access"
    if container_process:
        return "unmanaged_containers"
    return "host_processes"


def _process_snapshot(container_ids: set[str]) -> dict[int, dict[str, Any]]:
    if os.name == "nt":
        return {}
    snapshot: dict[int, dict[str, Any]] = {}
    for process_dir in Path("/proc").iterdir():
        if not process_dir.name.isdigit():
            continue
        try:
            stat = (process_dir / "stat").read_text(encoding="utf-8", errors="replace")
            fields = stat[stat.rfind(")") + 2 :].split()
            command = (process_dir / "comm").read_text(encoding="utf-8", errors="replace").strip()
            cmdline = (process_dir / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", errors="replace")
            cgroup = (process_dir / "cgroup").read_text(encoding="utf-8", errors="replace")
            status = (process_dir / "status").read_text(encoding="utf-8", errors="replace")
            rss_match = re.search(r"^VmRSS:\s+(\d+)\s+kB$", status, re.MULTILINE)
            snapshot[int(process_dir.name)] = {
                "ticks": int(fields[11]) + int(fields[12]),
                "rss": int(rss_match.group(1)) * 1024 if rss_match else 0,
                "category": _process_category(command, cmdline, cgroup, container_ids),
            }
        except (OSError, ValueError, IndexError):
            continue
    return snapshot


def _process_cpu_components(
    first: dict[int, dict[str, Any]],
    second: dict[int, dict[str, Any]],
    total_tick_delta: int,
) -> list[dict[str, Any]]:
    values: dict[str, float] = {}
    if total_tick_delta <= 0:
        return []
    for process_id, end in second.items():
        start = first.get(process_id)
        if not start or end["category"] == "managed" or start["category"] != end["category"]:
            continue
        delta = max(0, int(end["ticks"]) - int(start["ticks"]))
        values[end["category"]] = values.get(end["category"], 0.0) + delta / total_tick_delta * 100
    return _process_components(values)


def _process_memory_components(snapshot: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    values: dict[str, float] = {}
    for process in snapshot.values():
        category = process["category"]
        if category != "managed":
            values[category] = values.get(category, 0.0) + int(process["rss"])
    return _process_components(values)


def _process_components(values: dict[str, float]) -> list[dict[str, Any]]:
    components = []
    for key, value in sorted(values.items(), key=lambda item: item[1], reverse=True):
        if value <= 0 or key not in PROCESS_CATEGORIES:
            continue
        name, note, disposition = PROCESS_CATEGORIES[key]
        components.append({"name": name, "value": value, "note": note, "disposition": disposition})
    return components


def _host_disk_sizes() -> dict[str, int]:
    if os.name == "nt":
        return {}
    paths = ("/usr", "/boot", "/etc", "/var/log", "/var/backups")
    result = run_command(("du", "-sb", *paths), timeout=20)
    sizes: dict[str, int] = {}
    for line in result.stdout.splitlines():
        fields = line.split(maxsplit=1)
        if len(fields) != 2:
            continue
        try:
            sizes[fields[1].strip()] = int(fields[0])
        except ValueError:
            continue
    return sizes


def _kernel_memory_baseline() -> int:
    if os.name == "nt":
        return 0
    values: dict[str, int] = {}
    try:
        lines = Path("/proc/meminfo").read_text(encoding="ascii").splitlines()
    except OSError:
        return 0
    for line in lines:
        name, separator, raw_value = line.partition(":")
        if not separator:
            continue
        try:
            values[name] = int(raw_value.strip().split()[0]) * 1024
        except (ValueError, IndexError):
            continue
    unreclaimable_slab = values.get("SUnreclaim", max(0, values.get("Slab", 0) - values.get("SReclaimable", 0)))
    return unreclaimable_slab + sum(values.get(name, 0) for name in ("KernelStack", "PageTables", "Percpu"))


def _bounded_residual_components(
    metric: str,
    residual: float,
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    remaining = max(0.0, residual)
    components: list[dict[str, Any]] = []
    for candidate in candidates:
        value = min(remaining, max(0.0, float(candidate.get("value") or 0)))
        if value <= (0.05 if metric == "cpu" else 0):
            continue
        components.append({**candidate, "value": round(value, 1) if metric == "cpu" else int(value)})
        remaining -= value
    if remaining > (0.05 if metric == "cpu" else 0):
        labels = {
            "cpu": (
                "Kernel & sampling difference",
                "Kernel work and the unavoidable difference between host and per-process sampling windows.",
            ),
            "memory": (
                "Kernel & shared memory",
                "Kernel allocations, shared pages, and memory that process RSS cannot attribute safely.",
            ),
            "disk": (
                "Other host files",
                "Filesystem usage outside registered projects and the measured shared categories above.",
            ),
        }
        name, note = labels[metric]
        components.append(
            {
                "name": name,
                "value": round(remaining, 1) if metric == "cpu" else int(remaining),
                "note": note,
                "disposition": "baseline" if metric != "disk" else "unattributed",
            }
        )
    return components


def _metric_rows(
    usage: dict[str, dict[str, Any]],
    metric: str,
    total: float | int | None,
    residual_candidates: list[dict[str, Any]],
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
                    "components": _bounded_residual_components(metric, other, residual_candidates),
                }
            )
    return rows


def collect_resource_breakdown(
    specs: tuple[ProjectSpec, ...],
    projects: list[dict[str, Any]],
    system: dict[str, Any],
    backups: dict[str, Any] | None = None,
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
    container_ids = {value for value in container_map if len(value) >= 8}
    cpu_start = _cpu_ticks()
    process_start = _process_snapshot(container_ids)
    child_cpu_start = _child_cpu_seconds()
    sample_started_at = time.monotonic()
    stats = run_docker(("stats", "--no-stream", "--format", "{{json .}}"), timeout=15)
    sample_seconds = max(time.monotonic() - sample_started_at, 0.001)
    child_cpu_end = _child_cpu_seconds()
    cpu_end = _cpu_ticks()
    process_end = _process_snapshot(container_ids)
    synchronized_cpu = _cpu_percent_between(cpu_start, cpu_end)
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
            '{"Containers":{{json .Containers}},"Volumes":{{json .Volumes}},"Images":{{json .Images}},"BuildCache":{{json .BuildCache}}}',
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

    cpu_candidates: list[dict[str, Any]] = []
    if cpu_start is not None and cpu_end is not None:
        cpu_candidates = _process_cpu_components(process_start, process_end, cpu_end[0] - cpu_start[0])
    memory_candidates: list[dict[str, Any]] = []
    kernel_memory = _kernel_memory_baseline()
    if kernel_memory:
        memory_candidates.append(
            {
                "name": "Kernel baseline",
                "value": kernel_memory,
                "note": "Unreclaimable kernel slabs, stacks, page tables, and per-CPU allocations required by the host.",
                "disposition": "baseline",
            }
        )
    memory_candidates.extend(_process_memory_components(process_end))
    disk_candidates: list[dict[str, Any]] = []
    images_size = sum(
        _parse_size(item.get("UniqueSize")) or _parse_size(item.get("Size")) or 0
        for item in disk_payload.get("Images") or []
    )
    build_cache_size = sum(
        _parse_size(item.get("Size")) or 0 for item in disk_payload.get("BuildCache") or []
    )
    if images_size:
        disk_candidates.append(
            {
                "name": "Shared Docker images",
                "value": images_size,
                "note": "Image layers shared by projects. Remove only images confirmed unused by every deployment.",
                "disposition": "shared",
            }
        )
    if build_cache_size:
        disk_candidates.append(
            {
                "name": "Docker build cache",
                "value": build_cache_size,
                "note": "Rebuild acceleration data. Reviewable, but ordinary cleanup policy preserves it.",
                "disposition": "reviewable",
            }
        )
    host_sizes = _host_disk_sizes()
    latest_verified_backups = sum(
        int(item.get("size_bytes") or 0) for item in (backups or {}).get("items") or []
    )
    disk_candidates.extend(
        [
            {
                "name": "System files & packages",
                "value": sum(host_sizes.get(path, 0) for path in ("/usr", "/boot", "/etc")),
                "note": "Operating system, boot files, and configuration. Treat as required baseline.",
                "disposition": "baseline",
            },
            {
                "name": "System logs",
                "value": host_sizes.get("/var/log", 0),
                "note": "Host logs. Reduce only through retention policy, not manual deletion.",
                "disposition": "reviewable",
            },
            {
                "name": "Protected backups",
                "value": max(host_sizes.get("/var/backups", 0), latest_verified_backups),
                "note": "Recovery data (at least the latest verified files). Keep unless retention explicitly authorizes removal.",
                "disposition": "protected",
            },
        ]
    )

    memory_total = (system.get("memory") or {}).get("used")
    disk_total = (system.get("disk") or {}).get("used")
    return {
        "cpu": _metric_rows(usage, "cpu", system.get("cpu_percent"), cpu_candidates),
        "memory": _metric_rows(usage, "memory", memory_total, memory_candidates),
        "disk": _metric_rows(usage, "disk", disk_total, disk_candidates),
    }
