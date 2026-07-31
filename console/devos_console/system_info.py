from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import time
from pathlib import Path
from typing import Any

from .runner import run_docker


def _read_proc_values(path: Path) -> dict[str, int]:
    values: dict[str, int] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if ":" not in line:
            continue
        name, raw_value = line.split(":", 1)
        token = raw_value.strip().split()[0]
        try:
            values[name] = int(token) * 1024
        except (ValueError, IndexError):
            continue
    return values


def _cpu_sample() -> float | None:
    if os.name == "nt":
        return None

    def read() -> tuple[int, int] | None:
        try:
            fields = Path("/proc/stat").read_text(encoding="ascii").splitlines()[0].split()[1:]
            numbers = [int(value) for value in fields]
        except (OSError, ValueError, IndexError):
            return None
        idle = numbers[3] + (numbers[4] if len(numbers) > 4 else 0)
        return sum(numbers), idle

    first = read()
    if first is None:
        return None
    time.sleep(0.12)
    second = read()
    if second is None:
        return None
    total_delta = second[0] - first[0]
    idle_delta = second[1] - first[1]
    if total_delta <= 0:
        return None
    return round((1 - idle_delta / total_delta) * 100, 1)


def _docker_summary() -> dict[str, Any]:
    result = run_docker(("ps", "-a", "--format", "{{json .}}"), timeout=8)
    if not result.ok:
        return {"available": False, "error": (result.stderr or result.stdout).strip()[:300]}
    containers = []
    for line in result.stdout.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        containers.append(value)
    running = sum(1 for item in containers if str(item.get("State", "")).lower() == "running")
    unhealthy = sum(1 for item in containers if "unhealthy" in str(item.get("Status", "")).lower())
    version = run_docker(("version", "--format", "{{.Server.Version}}"), timeout=5)
    return {
        "available": True,
        "version": version.stdout.strip() if version.ok else None,
        "containers": len(containers),
        "running": running,
        "unhealthy": unhealthy,
    }


def collect_system_info(disk_path: Path) -> dict[str, Any]:
    memory = _read_proc_values(Path("/proc/meminfo"))
    total_memory = memory.get("MemTotal")
    available_memory = memory.get("MemAvailable")
    used_memory = total_memory - available_memory if total_memory and available_memory is not None else None
    disk = shutil.disk_usage(disk_path)
    try:
        load = os.getloadavg()
    except (AttributeError, OSError):
        load = (None, None, None)
    uptime_seconds = None
    try:
        uptime_seconds = int(float(Path("/proc/uptime").read_text(encoding="ascii").split()[0]))
    except (OSError, ValueError, IndexError):
        pass

    return {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "cpu_count": os.cpu_count(),
        "cpu_percent": _cpu_sample(),
        "load": list(load),
        "memory": {
            "total": total_memory,
            "used": used_memory,
            "percent": round(used_memory / total_memory * 100, 1) if total_memory and used_memory is not None else None,
        },
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": round(disk.used / disk.total * 100, 1) if disk.total else None,
        },
        "uptime_seconds": uptime_seconds,
        "docker": _docker_summary(),
        "collected_at": time.time(),
    }
