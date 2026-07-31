from __future__ import annotations

from typing import Any


def build_alerts(
    system: dict[str, Any],
    projects: list[dict[str, Any]],
    backups: dict[str, Any],
    workstations: list[dict[str, Any]] | None = None,
    *,
    public_read_only: bool,
) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []

    disk_percent = system.get("disk", {}).get("percent")
    memory_percent = system.get("memory", {}).get("percent")
    if isinstance(disk_percent, (int, float)) and disk_percent >= 80:
        alerts.append({"severity": "critical" if disk_percent >= 90 else "warning", "source": "server", "message": f"Root disk usage is {disk_percent}%."})
    if isinstance(memory_percent, (int, float)) and memory_percent >= 85:
        alerts.append({"severity": "critical" if memory_percent >= 95 else "warning", "source": "server", "message": f"Memory usage is {memory_percent}%."})
    docker = system.get("docker", {})
    if not docker.get("available"):
        alerts.append({"severity": "critical", "source": "docker", "message": "Docker is unavailable."})
    elif docker.get("unhealthy", 0):
        alerts.append({"severity": "critical", "source": "docker", "message": f'{docker["unhealthy"]} containers are unhealthy.'})

    for project in projects:
        name = str(project.get("name") or project.get("slug"))
        if not project.get("available"):
            alerts.append({"severity": "info", "source": name, "message": "Project is not installed on this server."})
            continue
        repository = project.get("repository") or {}
        if repository.get("modified", 0):
            alerts.append({"severity": "warning", "source": name, "message": f'{repository["modified"]} uncommitted changes are present.'})
        if repository.get("ahead", 0):
            alerts.append({"severity": "warning", "source": name, "message": f'{repository["ahead"]} commits have not been pushed.'})
        if repository.get("behind", 0):
            alerts.append({"severity": "warning", "source": name, "message": f'{repository["behind"]} commits are behind the tracking branch.'})
        if project.get("deployment", {}).get("status") == "out_of_sync":
            alerts.append({"severity": "warning", "source": name, "message": "Running image does not match repository HEAD."})
        containers = project.get("containers") or []
        stopped = sum(1 for container in containers if str(container.get("state")).lower() != "running")
        unhealthy = sum(1 for container in containers if "unhealthy" in str(container.get("status")).lower())
        if stopped:
            alerts.append({"severity": "critical", "source": name, "message": f"{stopped} containers are stopped."})
        if unhealthy:
            alerts.append({"severity": "critical", "source": name, "message": f"{unhealthy} containers are unhealthy."})

    for backup in backups.get("items", []):
        if backup["status"] != "healthy":
            alerts.append(
                {
                    "severity": "critical" if backup["status"] == "failed" else "warning",
                    "source": f'{backup["name"]} backup',
                    "message": backup["message"],
                }
            )
        if backup["verification_status"] not in {"passed"}:
            alerts.append(
                {
                    "severity": "warning",
                    "source": f'{backup["name"]} restore',
                    "message": "A recent isolated restore verification is not available.",
                }
            )

    for workstation in workstations or []:
        if not workstation.get("online"):
            continue
        for project in workstation.get("projects", []):
            repository = project.get("repository") or {}
            source = f'{workstation["name"]} / {project["name"]}'
            if repository.get("modified", 0):
                alerts.append({"severity": "warning", "source": source, "message": f'{repository["modified"]} local changes are not committed.'})
            if repository.get("ahead", 0):
                alerts.append({"severity": "warning", "source": source, "message": f'{repository["ahead"]} local commits are not pushed.'})
            if repository.get("behind", 0):
                alerts.append({"severity": "warning", "source": source, "message": f'{repository["behind"]} commits are behind the tracking branch.'})
            comparison = project.get("comparison") or {}
            if comparison.get("server_status") == "mismatch":
                alerts.append({"severity": "warning", "source": source, "message": "Local revision differs from the server checkout."})
            if comparison.get("deployment_status") == "mismatch":
                alerts.append({"severity": "warning", "source": source, "message": "Local revision differs from the running deployment."})

    if public_read_only:
        alerts.append(
            {
                "severity": "info",
                "source": "security",
                "message": "Public HTTP mode is read-only; administrative commands remain disabled.",
            }
        )
    order = {"critical": 0, "warning": 1, "info": 2}
    return sorted(alerts, key=lambda item: order.get(item["severity"], 9))
