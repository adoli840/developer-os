from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


DESKTOP_PREFIX = ["docker", "--context", "desktop-linux"]
NATIVE_PREFIX = [
    r"X:\Projects\DeveloperOS\04_Tools\bin\devos-native-docker.cmd"
]


class ForensicInventoryError(RuntimeError):
    pass


def _run(prefix: Sequence[str], arguments: Sequence[str]) -> str:
    completed = subprocess.run(
        [*prefix, *arguments],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise ForensicInventoryError(
            f"READ_ONLY_DOCKER_QUERY_FAILED: {arguments[0]} exit={completed.returncode}"
        )
    return completed.stdout


def _ids(prefix: Sequence[str], kind: str) -> list[str]:
    commands = {
        "container": ["container", "ls", "-aq", "--no-trunc"],
        "image": ["image", "ls", "-aq", "--no-trunc"],
        "volume": ["volume", "ls", "-q"],
        "network": ["network", "ls", "-q", "--no-trunc"],
    }
    return sorted(set(_run(prefix, commands[kind]).split()))


def _inspect(prefix: Sequence[str], kind: str, identifiers: list[str]) -> list[dict[str, Any]]:
    if not identifiers:
        return []
    arguments = [kind, "inspect"]
    if kind == "container":
        arguments.append("--size")
    values = json.loads(_run(prefix, [*arguments, *identifiers]))
    if not isinstance(values, list):
        raise ForensicInventoryError(f"INVALID_{kind.upper()}_INSPECT")
    return values


def _containers(prefix: Sequence[str]) -> list[dict[str, Any]]:
    result = []
    for item in _inspect(prefix, "container", _ids(prefix, "container")):
        state = item.get("State") or {}
        config = item.get("Config") or {}
        host = item.get("HostConfig") or {}
        networks = (item.get("NetworkSettings") or {}).get("Networks") or {}
        container_id = str(item.get("Id", ""))
        diff = _run(prefix, ["container", "diff", container_id]).splitlines()
        result.append(
            {
                "id": container_id,
                "name": str(item.get("Name", "")).lstrip("/"),
                "created": item.get("Created"),
                "status": state.get("Status"),
                "started_at": state.get("StartedAt"),
                "finished_at": state.get("FinishedAt"),
                "exit_code": state.get("ExitCode"),
                "image_reference": config.get("Image"),
                "image_id": item.get("Image"),
                "labels": config.get("Labels") or {},
                "mounts": item.get("Mounts") or [],
                "binds": host.get("Binds") or [],
                "networks": sorted(networks),
                "size_rw": item.get("SizeRw"),
                "size_root_fs": item.get("SizeRootFs"),
                "writable_layer_diff": diff,
            }
        )
    return result


def _images(prefix: Sequence[str]) -> list[dict[str, Any]]:
    result = []
    for item in _inspect(prefix, "image", _ids(prefix, "image")):
        config = item.get("Config") or {}
        result.append(
            {
                "id": item.get("Id"),
                "repo_tags": item.get("RepoTags") or [],
                "repo_digests": item.get("RepoDigests") or [],
                "created": item.get("Created"),
                "size": item.get("Size"),
                "labels": config.get("Labels") or {},
            }
        )
    return result


def _volumes(prefix: Sequence[str]) -> list[dict[str, Any]]:
    result = []
    for item in _inspect(prefix, "volume", _ids(prefix, "volume")):
        result.append(
            {
                "name": item.get("Name"),
                "driver": item.get("Driver"),
                "created_at": item.get("CreatedAt"),
                "labels": item.get("Labels") or {},
                "mountpoint": item.get("Mountpoint"),
                "scope": item.get("Scope"),
            }
        )
    return result


def _networks(prefix: Sequence[str]) -> list[dict[str, Any]]:
    result = []
    for item in _inspect(prefix, "network", _ids(prefix, "network")):
        containers = item.get("Containers") or {}
        result.append(
            {
                "id": item.get("Id"),
                "name": item.get("Name"),
                "created": item.get("Created"),
                "driver": item.get("Driver"),
                "scope": item.get("Scope"),
                "labels": item.get("Labels") or {},
                "container_names": sorted(
                    str(value.get("Name", "")) for value in containers.values()
                ),
            }
        )
    return result


def _json_lines(value: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in value.splitlines() if line.strip()]


def collect_engine(prefix: Sequence[str]) -> dict[str, Any]:
    return {
        "containers": _containers(prefix),
        "images": _images(prefix),
        "volumes": _volumes(prefix),
        "networks": _networks(prefix),
        "space_summary": _json_lines(_run(prefix, ["system", "df", "--format", "json"])),
        "build_cache": _json_lines(_run(prefix, ["builder", "du", "--format", "json"])),
    }


def write_inventory(output: Path, vhdx: Path) -> str:
    stat = vhdx.stat()
    inventory = {
        "schema_version": 1,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "safety": {
            "read_only_queries_only": True,
            "secret_bearing_environment_excluded": True,
            "mutation_commands": 0,
        },
        "vhdx": {
            "path": str(vhdx),
            "size_bytes": stat.st_size,
            "last_write_time_utc": datetime.fromtimestamp(
                stat.st_mtime, timezone.utc
            ).isoformat(),
        },
        "desktop": collect_engine(DESKTOP_PREFIX),
        "native": collect_engine(NATIVE_PREFIX),
    }
    encoded = json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = encoded + b"\n"
    output.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{digest}  {output.name}\n", encoding="ascii"
    )
    return digest


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture redacted Docker forensic inventory")
    parser.add_argument(
        "--vhdx",
        type=Path,
        default=Path(r"X:\Docker\DockerDesktopWSL\disk\docker_data.vhdx"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(r".console\docker-desktop-vhd-forensic\raw-inventory.json"),
    )
    args = parser.parse_args()
    print(write_inventory(args.output, args.vhdx))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
