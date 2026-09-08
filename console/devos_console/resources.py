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
    if isinstance(value, dict):
        return {str(name): str(label_value) for name, label_value in value.items()}
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
        result = run_command(
            (
                "sudo",
                "-n",
                "/usr/local/sbin/developer-os-project-disk-usage",
                str(path),
            ),
            timeout=20,
        )
    if not result.ok:
        return None
    try:
        return int(result.stdout.split()[0])
    except (ValueError, IndexError):
        return None


def _add_component(components: dict[str, float], name: str, value: float) -> None:
    components[name] = components.get(name, 0) + value


DISK_COMPONENT_DETAILS = {
    "Project files": (
        "Registered project workspace files measured from the configured project path.",
        "project",
    ),
    "Bind-mounted project data": (
        "Host data mounted only by this project's managed containers and outside every registered project workspace.",
        "project",
    ),
    "Docker volumes": (
        "Docker volumes attributed by Compose label or exclusive attachment to this project's containers.",
        "project",
    ),
    "Container writes": (
        "Writable container layers carrying this project's Compose label.",
        "project",
    ),
    "Exclusive Docker image data": (
        "Unique image bytes used only by this project's managed containers.",
        "project",
    ),
}


def _image_keys(image: object, image_id: object = None) -> set[str]:
    keys: set[str] = set()
    normalized_image = str(image or "").strip()
    normalized_id = str(image_id or "").strip().removeprefix("sha256:")
    if normalized_image:
        keys.add(normalized_image)
    if normalized_id:
        keys.add(normalized_id)
    return keys


def _disk_image_keys(item: dict[str, Any]) -> set[str]:
    repository = str(item.get("Repository") or "").strip()
    tag = str(item.get("Tag") or "").strip()
    image_name = f"{repository}:{tag}" if repository and tag and tag != "<none>" else repository
    return _image_keys(image_name, item.get("Image ID") or item.get("ID"))


def _disk_image_size(item: dict[str, Any]) -> int:
    unique_size = _parse_size(item.get("UniqueSize"))
    if unique_size is not None:
        return unique_size
    return _parse_size(item.get("Size")) or 0


def _matching_image_owners(
    item: dict[str, Any],
    owner_keys: dict[str, set[str]],
) -> set[str]:
    owners: set[str] = set()
    for item_key in _disk_image_keys(item):
        for owner_key, slugs in owner_keys.items():
            exact = item_key == owner_key
            digest_prefix = (
                len(item_key) >= 12
                and len(owner_key) >= 12
                and re.fullmatch(r"[0-9a-f]+", item_key, re.IGNORECASE)
                and re.fullmatch(r"[0-9a-f]+", owner_key, re.IGNORECASE)
                and (item_key.startswith(owner_key) or owner_key.startswith(item_key))
            )
            if exact or digest_prefix:
                owners.update(slugs)
    return owners


def _managed_mount_owners(
    projects: list[dict[str, Any]],
    compose_to_slug: dict[str, str],
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    refs: list[str] = []
    fallback_owners: dict[str, str] = {}
    for project in projects:
        slug = str(project.get("slug") or "")
        for container in project.get("containers") or []:
            container_id = str(container.get("id") or "").strip()
            name = str(container.get("name") or "").strip().removeprefix("/")
            ref = container_id or name
            if not ref or not slug:
                continue
            refs.append(ref)
            if container_id:
                fallback_owners[container_id] = slug
            if name:
                fallback_owners[name] = slug
    if not refs:
        return {}, {}
    template = (
        '{"Id":{{json .Id}},"Name":{{json .Name}},'
        '"Labels":{{json .Config.Labels}},"Mounts":{{json .Mounts}}}'
    )
    result = run_docker(("inspect", "--format", template, *sorted(set(refs))), timeout=20)
    if not result.ok:
        return {}, {}
    volume_owners: dict[str, set[str]] = {}
    bind_owners: dict[str, set[str]] = {}
    for item in _json_lines(result.stdout):
        labels = _labels(item.get("Labels"))
        slug = compose_to_slug.get(labels.get("com.docker.compose.project", ""))
        if not slug:
            container_id = str(item.get("Id") or "").removeprefix("sha256:")
            name = str(item.get("Name") or "").removeprefix("/")
            slug = fallback_owners.get(name)
            if not slug:
                slug = next(
                    (
                        owner
                        for identity, owner in fallback_owners.items()
                        if len(identity) >= 8 and container_id.startswith(identity)
                    ),
                    None,
                )
        if not slug:
            continue
        for mount in item.get("Mounts") or []:
            if not isinstance(mount, dict):
                continue
            mount_type = str(mount.get("Type") or "").lower()
            if mount_type == "volume" and mount.get("Name"):
                volume_owners.setdefault(str(mount["Name"]), set()).add(slug)
            elif mount_type == "bind" and mount.get("Source"):
                bind_owners.setdefault(str(Path(str(mount["Source"]))), set()).add(slug)
    return volume_owners, bind_owners


def _path_contains(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


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
    if metric == "cpu" and components:
        displayed_total = round(residual, 1)
        displayed_components = round(sum(float(item["value"]) for item in components), 1)
        components[-1]["value"] = round(float(components[-1]["value"]) + displayed_total - displayed_components, 1)
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
        rendered_components = []
        for name, component_value in components if metric == "disk" else components[:4]:
            component = {
                "name": name,
                "value": round(component_value, 1) if metric == "cpu" else int(component_value),
            }
            if metric == "disk" and name in DISK_COMPONENT_DETAILS:
                component["note"], component["disposition"] = DISK_COMPONENT_DETAILS[name]
            rendered_components.append(component)
        rows.append(
            {
                "slug": project["slug"],
                "name": project["name"],
                "value": round(value, 1) if metric == "cpu" else int(value),
                "components": rendered_components,
            }
        )
    rows.sort(key=lambda item: item["value"], reverse=True)
    if total is not None:
        other = max(0.0, float(total) - managed_total)
        if other > (0.05 if metric == "cpu" else 0):
            rows.append(
                {
                    "slug": "other",
                    "name": "Shared, system & unassigned" if metric == "disk" else "Server & other",
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
    image_owner_keys: dict[str, set[str]] = {}
    for project in projects:
        project_slug = str(project.get("slug") or "")
        for container in project.get("containers") or []:
            name = str(container.get("name") or "")
            container_id = str(container.get("id") or "")
            service = str(container.get("service") or name or "Container")
            if name and project_slug in usage:
                container_map[name] = (project_slug, service)
            if container_id and project_slug in usage:
                container_map[container_id] = (project_slug, service)
            if project_slug in usage:
                for key in _image_keys(container.get("image"), container.get("image_id")):
                    image_owner_keys.setdefault(key, set()).add(project_slug)

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
    volume_mount_owners, bind_mount_owners = _managed_mount_owners(projects, compose_to_slug)
    for item in disk_payload.get("Containers") or []:
        labels = _labels(item.get("Labels"))
        slug = compose_to_slug.get(labels.get("com.docker.compose.project", ""))
        size = _parse_size(item.get("Size"))
        if slug and size is not None:
            usage[slug]["disk"] += size
            _add_component(usage[slug]["disk_components"], "Container writes", size)
    shared_volume_size = 0
    unassigned_volume_size = 0
    for item in disk_payload.get("Volumes") or []:
        labels = _labels(item.get("Labels"))
        label_slug = compose_to_slug.get(labels.get("com.docker.compose.project", ""))
        volume_name = str(item.get("Name") or item.get("Volume Name") or "")
        owners = set(volume_mount_owners.get(volume_name, set()))
        if label_slug:
            owners.add(label_slug)
        size = _parse_size(item.get("Size"))
        if len(owners) == 1 and size is not None:
            slug = next(iter(owners))
            usage[slug]["disk"] += size
            _add_component(usage[slug]["disk_components"], "Docker volumes", size)
        elif len(owners) > 1 and size is not None:
            shared_volume_size += size
        elif size is not None:
            unassigned_volume_size += size

    registered_paths = {spec.slug: spec.path.resolve() for spec in specs}
    for slug, path in registered_paths.items():
        size = _directory_size(path)
        if size is not None:
            usage[slug]["disk"] += size
            _add_component(usage[slug]["disk_components"], "Project files", size)

    shared_bind_size = 0
    kept_bind_paths: dict[str, list[Path]] = {slug: [] for slug in usage}
    resolved_bind_owners: dict[Path, set[str]] = {}
    for raw_path, owners in bind_mount_owners.items():
        resolved_bind_owners.setdefault(Path(raw_path).resolve(), set()).update(owners)
    for path, owners in sorted(resolved_bind_owners.items(), key=lambda item: len(item[0].parts)):
        if not path.is_dir():
            continue
        if any(
            _path_contains(project_path, path) or _path_contains(path, project_path)
            for project_path in registered_paths.values()
        ):
            continue
        if len(owners) == 1:
            slug = next(iter(owners))
            if slug not in usage or any(_path_contains(parent, path) for parent in kept_bind_paths[slug]):
                continue
            size = _directory_size(path)
            if size is not None:
                usage[slug]["disk"] += size
                _add_component(usage[slug]["disk_components"], "Bind-mounted project data", size)
                kept_bind_paths[slug].append(path)
        elif len(owners) > 1:
            size = _directory_size(path)
            if size is not None:
                shared_bind_size += size

    shared_image_size = 0
    unassigned_image_size = 0
    for item in disk_payload.get("Images") or []:
        size = _disk_image_size(item)
        owners = _matching_image_owners(item, image_owner_keys)
        if len(owners) == 1:
            slug = next(iter(owners))
            usage[slug]["disk"] += size
            _add_component(usage[slug]["disk_components"], "Exclusive Docker image data", size)
        elif len(owners) > 1:
            shared_image_size += size
        else:
            unassigned_image_size += size

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
    build_cache_size = sum(
        _parse_size(item.get("Size")) or 0 for item in disk_payload.get("BuildCache") or []
    )
    if shared_image_size:
        disk_candidates.append(
            {
                "name": "Shared Docker images",
                "value": shared_image_size,
                "note": "Unique image bytes used by managed containers from more than one registered project.",
                "disposition": "shared",
            }
        )
    if unassigned_image_size:
        disk_candidates.append(
            {
                "name": "Unassigned Docker images",
                "value": unassigned_image_size,
                "note": "Image data with no managed-container ownership evidence. It is not charged to a project.",
                "disposition": "unattributed",
            }
        )
    if shared_volume_size:
        disk_candidates.append(
            {
                "name": "Shared Docker volumes",
                "value": shared_volume_size,
                "note": "Volume data attached to managed containers from multiple registered projects.",
                "disposition": "shared",
            }
        )
    if unassigned_volume_size:
        disk_candidates.append(
            {
                "name": "Unassigned Docker volumes",
                "value": unassigned_volume_size,
                "note": "Volume data without a recognized Compose label or managed-container attachment.",
                "disposition": "unattributed",
            }
        )
    if shared_bind_size:
        disk_candidates.append(
            {
                "name": "Shared bind-mounted data",
                "value": shared_bind_size,
                "note": "Host data mounted by containers from multiple registered projects.",
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
