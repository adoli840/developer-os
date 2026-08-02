from __future__ import annotations

import json
import re
import time
from pathlib import Path
from threading import Lock
from typing import Any

from .audit import AuditLog
from .runner import CommandResult, run_command, run_docker
from .settings import ProjectSpec


COMPOSE_FILES = (
    "docker-compose.prod.yml",
    "docker-compose.yml",
    "compose.yml",
    "docker-compose.yaml",
    "compose.yaml",
)

ACTION_LABELS = {
    "git-pull": "Fast-forward Git pull",
    "start": "Start containers",
    "restart": "Restart containers",
    "stop": "Stop containers",
}

HEX_REVISION = re.compile(r"^[0-9a-f]{7,64}$", re.IGNORECASE)


class ProjectService:
    def __init__(self, projects: tuple[ProjectSpec, ...], audit: AuditLog) -> None:
        self._projects = {project.slug: project for project in projects}
        self._audit = audit
        self._locks = {project.slug: Lock() for project in projects}

    def project(self, slug: str) -> ProjectSpec | None:
        return self._projects.get(slug)

    @staticmethod
    def _git(project: ProjectSpec, *args: str, timeout: float = 8) -> CommandResult:
        return run_command(("git", "-C", str(project.path), *args), timeout=timeout)

    @staticmethod
    def _compose_file(project: ProjectSpec) -> Path | None:
        for name in COMPOSE_FILES:
            candidate = project.path / name
            if candidate.is_file():
                return candidate
        return None

    @staticmethod
    def _labels(raw_labels: str | None) -> dict[str, str]:
        labels: dict[str, str] = {}
        for item in (raw_labels or "").split(","):
            if "=" not in item:
                continue
            name, value = item.split("=", 1)
            labels[name] = value
        return labels

    @staticmethod
    def _image_details(image: str) -> dict[str, Any]:
        result = run_docker(
            (
                "image",
                "inspect",
                image,
                "--format",
                "{{.Id}}|{{json .RepoDigests}}|{{.Created}}",
            ),
            timeout=8,
        )
        if not result.ok:
            return {"id": None, "digests": [], "created_at": None}
        image_id, separator, remainder = result.stdout.strip().partition("|")
        raw_digests, separator, created_at = remainder.partition("|")
        try:
            digests = json.loads(raw_digests) if raw_digests else []
        except json.JSONDecodeError:
            digests = []
        return {
            "id": image_id.removeprefix("sha256:")[:12] or None,
            "digests": digests if isinstance(digests, list) else [],
            "created_at": created_at or None,
        }

    @staticmethod
    def _container_runtime(name: str) -> dict[str, Any]:
        result = run_docker(
            (
                "inspect",
                name,
                "--format",
                "{{.Image}}|{{.Created}}|{{.State.StartedAt}}",
            ),
            timeout=8,
        )
        if not result.ok:
            return {"image_id": None, "created_at": None, "started_at": None}
        image_id, separator, remainder = result.stdout.strip().partition("|")
        created_at, separator, started_at = remainder.partition("|")
        return {
            "image_id": image_id.removeprefix("sha256:")[:12] or None,
            "created_at": created_at or None,
            "started_at": started_at or None,
        }

    def _containers(self, project: ProjectSpec) -> list[dict[str, Any]]:
        result = run_docker(
            (
                "ps",
                "-a",
                "--filter",
                f"label=com.docker.compose.project={project.compose_project}",
                "--format",
                "{{json .}}",
            ),
            timeout=8,
        )
        if not result.ok:
            return []
        containers = []
        image_cache: dict[str, dict[str, Any]] = {}
        for line in result.stdout.splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            labels = self._labels(item.get("Labels"))
            image = str(item.get("Image") or "")
            if image not in image_cache:
                image_cache[image] = self._image_details(image)
            runtime = self._container_runtime(str(item.get("Names") or ""))
            containers.append(
                {
                    "id": item.get("ID"),
                    "name": item.get("Names"),
                    "service": labels.get("com.docker.compose.service") or item.get("Names"),
                    "compose_project": labels.get("com.docker.compose.project"),
                    "state": item.get("State"),
                    "status": item.get("Status"),
                    "ports": item.get("Ports"),
                    "image": image,
                    "image_id": runtime["image_id"] or image_cache[image]["id"],
                    "image_digests": image_cache[image]["digests"],
                    "image_created_at": image_cache[image]["created_at"],
                    "created_at": runtime["created_at"],
                    "started_at": runtime["started_at"],
                }
            )
        return containers

    @staticmethod
    def _status_counts(lines: list[str]) -> dict[str, int]:
        return {
            "modified": len(lines),
            "staged": sum(1 for line in lines if len(line) >= 2 and line[0] not in {" ", "?"}),
            "unstaged": sum(1 for line in lines if len(line) >= 2 and line[1] not in {" ", "?"}),
            "untracked": sum(1 for line in lines if line.startswith("??")),
        }

    def _stale_branches(self, project: ProjectSpec, current_branch: str) -> int | None:
        result = self._git(
            project,
            "for-each-ref",
            "--format=%(refname:short)|%(committerdate:unix)",
            "refs/heads",
        )
        if not result.ok:
            return None
        cutoff = int(time.time()) - 90 * 86400
        stale = 0
        for line in result.stdout.splitlines():
            branch, separator, raw_timestamp = line.partition("|")
            if not separator or branch == current_branch:
                continue
            try:
                stale += int(raw_timestamp) < cutoff
            except ValueError:
                continue
        return stale

    @staticmethod
    def _image_revision(image: str) -> str | None:
        tag = image.rsplit(":", 1)[-1] if ":" in image else ""
        return tag if HEX_REVISION.fullmatch(tag) else None

    def _deployment(
        self,
        project: ProjectSpec,
        repository: dict[str, Any] | None,
        containers: list[dict[str, Any]],
    ) -> dict[str, Any]:
        deployed_revisions = sorted(
            {
                revision
                for container in containers
                if (revision := self._image_revision(str(container.get("image") or "")))
            }
        )
        current_revision = str(repository.get("revision") or "") if repository else ""
        matches = bool(
            current_revision
            and deployed_revisions
            and any(
                revision.startswith(current_revision) or current_revision.startswith(revision)
                for revision in deployed_revisions
            )
        )
        started_at = max(
            (str(container.get("started_at")) for container in containers if container.get("started_at")),
            default=None,
        )
        images = []
        seen_images: set[tuple[str, str | None]] = set()
        for container in containers:
            key = (str(container.get("image") or ""), container.get("image_id"))
            if key in seen_images:
                continue
            seen_images.add(key)
            images.append(
                {
                    "name": key[0],
                    "id": key[1],
                    "digests": container.get("image_digests") or [],
                    "created_at": container.get("image_created_at"),
                }
            )

        revision_file = project.path / ".devos-revision"
        deployed_at_file = project.path / ".devos-deployed-at"
        if revision_file.is_file() and not containers:
            deployed_revision = revision_file.read_text(encoding="utf-8").strip()
            return {
                "status": "current",
                "mode": "systemd",
                "current_revision": deployed_revision,
                "deployed_revisions": [deployed_revision],
                "matches_current": True,
                "deployed_at": (
                    deployed_at_file.read_text(encoding="utf-8").strip()
                    if deployed_at_file.is_file()
                    else None
                ),
                "images": [],
            }

        if not containers:
            status = "not_deployed"
        elif deployed_revisions and current_revision:
            status = "current" if matches else "out_of_sync"
        else:
            status = "running"
        return {
            "status": status,
            "mode": "compose" if containers else None,
            "current_revision": current_revision or None,
            "deployed_revisions": deployed_revisions,
            "matches_current": matches if deployed_revisions else None,
            "deployed_at": started_at,
            "images": images,
        }

    @staticmethod
    def _work_end_checks(
        available: bool,
        repository: dict[str, Any] | None,
        containers: list[dict[str, Any]],
        deployment: dict[str, Any],
    ) -> dict[str, Any]:
        checks: list[dict[str, str]] = []
        if not available:
            checks.append({"id": "repository", "status": "warn", "label": "Project is not present on this server"})
        elif repository is None:
            checks.append({"id": "repository", "status": "neutral", "label": "No Git repository detected"})
        elif repository.get("branch") == "deployed":
            checks.append({"id": "artifact", "status": "good", "label": "Immutable deployed release detected"})
        else:
            checks.append(
                {
                    "id": "working_tree",
                    "status": "good" if repository["modified"] == 0 else "warn",
                    "label": "Working tree clean" if repository["modified"] == 0 else f'{repository["modified"]} uncommitted changes',
                }
            )
            if repository["upstream"] is None:
                checks.append({"id": "upstream", "status": "warn", "label": "No upstream branch"})
            elif repository["ahead"] > 0:
                checks.append({"id": "push", "status": "warn", "label": f'{repository["ahead"]} commits not pushed'})
            elif repository["behind"] > 0:
                checks.append({"id": "pull", "status": "warn", "label": f'{repository["behind"]} commits behind remote'})
            else:
                checks.append({"id": "sync", "status": "good", "label": "Tracking branch synchronized"})
            if repository.get("stale_branches"):
                checks.append({"id": "branches", "status": "neutral", "label": f'{repository["stale_branches"]} stale local branches'})

        if containers:
            running = sum(1 for container in containers if str(container.get("state")).lower() == "running")
            unhealthy = sum(1 for container in containers if "unhealthy" in str(container.get("status")).lower())
            status = "good" if running == len(containers) and unhealthy == 0 else "bad"
            checks.append({"id": "containers", "status": status, "label": f"{running}/{len(containers)} containers running"})
        if deployment["status"] == "out_of_sync":
            checks.append({"id": "deployment", "status": "warn", "label": "Server image differs from repository HEAD"})
        elif deployment["status"] == "current":
            checks.append({"id": "deployment", "status": "good", "label": "Deployed revision matches current revision"})
        blocking = sum(1 for check in checks if check["status"] in {"warn", "bad"})
        return {"ready": blocking == 0, "blocking": blocking, "checks": checks}

    def collect(self, project: ProjectSpec) -> dict[str, Any]:
        containers = self._containers(project)
        if not project.path.is_dir():
            deployment = self._deployment(project, None, containers)
            return {
                "slug": project.slug,
                "name": project.name,
                "path": str(project.path),
                "port": project.port,
                "available": False,
                "repository": None,
                "containers": containers,
                "deployment": deployment,
                "work_end": self._work_end_checks(False, None, containers, deployment),
                "actions": [],
            }

        git_repo = self._git(project, "rev-parse", "--is-inside-work-tree")
        repository: dict[str, Any] | None = None
        if git_repo.ok:
            branch = self._git(project, "branch", "--show-current")
            revision = self._git(project, "rev-parse", "--short", "HEAD")
            status = self._git(project, "status", "--porcelain")
            status_lines = [line for line in status.stdout.splitlines() if line.strip()] if status.ok else []
            upstream = self._git(project, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
            last_commit = self._git(project, "log", "-1", "--format=%cI")
            ahead = behind = 0
            if upstream.ok:
                counts = self._git(project, "rev-list", "--left-right", "--count", "HEAD...@{u}")
                if counts.ok:
                    try:
                        ahead, behind = (int(value) for value in counts.stdout.strip().split())
                    except (TypeError, ValueError):
                        ahead = behind = 0
            current_branch = branch.stdout.strip() if branch.ok else "detached"
            repository = {
                "branch": current_branch,
                "revision": revision.stdout.strip() if revision.ok else None,
                **self._status_counts(status_lines),
                "upstream": upstream.stdout.strip() if upstream.ok else None,
                "ahead": ahead,
                "behind": behind,
                "last_commit_at": last_commit.stdout.strip() if last_commit.ok else None,
                "stale_branches": self._stale_branches(project, current_branch),
            }
        else:
            revision_file = project.path / ".devos-revision"
            if revision_file.is_file():
                repository = {
                    "branch": "deployed",
                    "revision": revision_file.read_text(encoding="utf-8").strip(),
                    "modified": 0,
                    "upstream": None,
                    "ahead": 0,
                    "behind": 0,
                }

        deployment = self._deployment(project, repository, containers)
        compose_file = self._compose_file(project)
        actions = ["git-pull"] if repository else []
        if compose_file:
            actions.extend(("start", "restart", "stop"))
        return {
            "slug": project.slug,
            "name": project.name,
            "path": str(project.path),
            "port": project.port,
            "available": True,
            "compose_file": compose_file.name if compose_file else None,
            "repository": repository,
            "containers": containers,
            "deployment": deployment,
            "work_end": self._work_end_checks(True, repository, containers, deployment),
            "actions": [{"id": action, "label": ACTION_LABELS[action]} for action in actions],
        }

    def collect_all(self) -> list[dict[str, Any]]:
        return [self.collect(project) for project in self._projects.values()]

    def run_action(self, slug: str, action: str, confirmation: str, remote: str) -> dict[str, Any]:
        project = self.project(slug)
        if project is None:
            raise ValueError("Unknown project.")
        if action not in ACTION_LABELS:
            raise ValueError("Unsupported action.")
        if confirmation != f"{slug}:{action}":
            raise ValueError("Action confirmation does not match.")
        if not project.path.is_dir():
            raise ValueError("Project directory is missing.")

        lock = self._locks[slug]
        if not lock.acquire(blocking=False):
            raise RuntimeError("Another project action is already running.")
        try:
            self._audit.write("action_started", project=slug, action=action, remote=remote)
            if action == "git-pull":
                status = self._git(project, "status", "--porcelain")
                if not status.ok or status.stdout.strip():
                    raise RuntimeError("Git pull requires a clean working tree.")
                result = self._git(project, "pull", "--ff-only", timeout=90)
            else:
                compose_file = self._compose_file(project)
                if compose_file is None:
                    raise RuntimeError("No supported Compose file was found.")
                compose_args = ("compose", "-f", str(compose_file))
                if action == "start":
                    result = run_docker((*compose_args, "up", "-d"), timeout=120)
                elif action == "restart":
                    result = run_docker((*compose_args, "restart"), timeout=120)
                else:
                    result = run_docker((*compose_args, "stop"), timeout=120)
            self._audit.write(
                "action_finished",
                project=slug,
                action=action,
                remote=remote,
                ok=result.ok,
                returncode=result.returncode,
            )
            return {
                "ok": result.ok,
                "returncode": result.returncode,
                "stdout": result.stdout[-12_000:],
                "stderr": result.stderr[-12_000:],
            }
        finally:
            lock.release()

    def logs(self, slug: str, lines: int) -> dict[str, Any]:
        project = self.project(slug)
        if project is None:
            raise ValueError("Unknown project.")
        compose_file = self._compose_file(project)
        if compose_file is None:
            raise ValueError("No supported Compose file was found.")
        safe_lines = max(20, min(lines, 500))
        result = run_docker(
            ("compose", "-f", str(compose_file), "logs", "--no-color", f"--tail={safe_lines}"),
            timeout=20,
        )
        return {
            "ok": result.ok,
            "output": (result.stdout + result.stderr)[-60_000:],
        }
