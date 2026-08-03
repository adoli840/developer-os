#!/usr/bin/env python3
"""Build an incremental project index and select task-relevant context."""

from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


MAP_SCHEMA_VERSION = 1
INDEX_SCHEMA_VERSION = 1
GENERATOR_VERSION = "1.0.0"
DEFAULT_MAP_NAME = "PROJECT_AREAS.json"
DEFAULT_CACHE_PATH = ".developer-os/context-index.json"
MAX_INDEXED_BYTES = 1_000_000
MAX_VALUES_PER_FIELD = 80

BUILTIN_EXCLUDES = (
    ".git/**",
    ".developer-os/**",
    ".snapshots/**",
    "**/.snapshots/**",
    "node_modules/**",
    "**/node_modules/**",
    ".next/**",
    "**/.next/**",
    "dist/**",
    "**/dist/**",
    "build/**",
    "**/build/**",
    "__pycache__/**",
    "**/__pycache__/**",
    ".pytest_cache/**",
    "**/.pytest_cache/**",
    ".venv/**",
    "**/.venv/**",
    "venv/**",
    "**/venv/**",
    "backups/**",
    "**/backups/**",
    "*.dump",
    "*.sqlite",
    "*.sqlite3",
)

INDEXABLE_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".css",
    ".go",
    ".h",
    ".hpp",
    ".html",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".mjs",
    ".ps1",
    ".py",
    ".rs",
    ".scss",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
}

ROOT_ALLOWED_KEYS = {"schema_version", "project", "exclude_globs", "areas"}
AREA_ALLOWED_KEYS = {
    "id",
    "name",
    "description",
    "keywords",
    "path_globs",
    "entrypoints",
    "related_docs",
    "test_commands",
    "services",
    "data_stores",
    "risk_tags",
}
AREA_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ContextContractError(RuntimeError):
    """Raised when a project context contract is missing or invalid."""


def normalize_relative(value: str) -> str:
    normalized = value.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.rstrip("/")


def require_safe_relative(value: str, field: str) -> str:
    normalized = normalize_relative(value)
    path = PurePosixPath(normalized)
    if (
        not normalized
        or path.is_absolute()
        or ".." in path.parts
        or re.match(r"^[A-Za-z]:", normalized)
    ):
        raise ContextContractError(f"{field} must be a project-relative path or glob: {value}")
    return normalized


def require_string_list(value: Any, field: str, *, paths: bool = False) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ContextContractError(f"{field} must be an array of non-empty strings")
    items = [item.strip() for item in value]
    if paths:
        items = [require_safe_relative(item, field) for item in items]
    return items


def load_project_map(project_root: Path, map_name: str = DEFAULT_MAP_NAME) -> dict[str, Any]:
    map_path = project_root / map_name
    if not map_path.is_file():
        raise ContextContractError(
            f"{map_name} is missing. Start from "
            "X:/Projects/DeveloperOS/03_Blueprints/Project/PROJECT_AREAS.json."
        )

    try:
        data = json.loads(map_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContextContractError(f"Cannot read {map_name}: {exc}") from exc

    if not isinstance(data, dict):
        raise ContextContractError(f"{map_name} must contain one JSON object")
    unknown_root = sorted(set(data) - ROOT_ALLOWED_KEYS)
    if unknown_root:
        raise ContextContractError(f"Unknown {map_name} fields: {', '.join(unknown_root)}")
    if data.get("schema_version") != MAP_SCHEMA_VERSION:
        raise ContextContractError(f"{map_name} schema_version must be {MAP_SCHEMA_VERSION}")
    if not isinstance(data.get("project"), str) or not data["project"].strip():
        raise ContextContractError(f"{map_name} project must be a non-empty string")

    exclude_globs = require_string_list(data.get("exclude_globs"), "exclude_globs", paths=True)
    raw_areas = data.get("areas")
    if not isinstance(raw_areas, list) or not raw_areas:
        raise ContextContractError(f"{map_name} areas must contain at least one area")
    if len(raw_areas) > 64:
        raise ContextContractError(f"{map_name} may declare at most 64 areas")

    areas: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for position, raw_area in enumerate(raw_areas, start=1):
        field_prefix = f"areas[{position}]"
        if not isinstance(raw_area, dict):
            raise ContextContractError(f"{field_prefix} must be an object")
        unknown_area = sorted(set(raw_area) - AREA_ALLOWED_KEYS)
        if unknown_area:
            raise ContextContractError(f"Unknown {field_prefix} fields: {', '.join(unknown_area)}")

        area_id = raw_area.get("id")
        if not isinstance(area_id, str) or not AREA_ID_PATTERN.fullmatch(area_id):
            raise ContextContractError(f"{field_prefix}.id must use lowercase words separated by single hyphens")
        if area_id in seen_ids:
            raise ContextContractError(f"Duplicate area id: {area_id}")
        seen_ids.add(area_id)

        name = raw_area.get("name")
        description = raw_area.get("description")
        if not isinstance(name, str) or not name.strip():
            raise ContextContractError(f"{field_prefix}.name must be a non-empty string")
        if not isinstance(description, str) or not description.strip():
            raise ContextContractError(f"{field_prefix}.description must be a non-empty string")

        path_globs = require_string_list(raw_area.get("path_globs"), f"{field_prefix}.path_globs", paths=True)
        if not path_globs:
            raise ContextContractError(f"{field_prefix}.path_globs must contain at least one glob")

        area = {
            "id": area_id,
            "name": name.strip(),
            "description": description.strip(),
            "keywords": require_string_list(raw_area.get("keywords"), f"{field_prefix}.keywords"),
            "path_globs": path_globs,
            "entrypoints": require_string_list(raw_area.get("entrypoints"), f"{field_prefix}.entrypoints", paths=True),
            "related_docs": require_string_list(raw_area.get("related_docs"), f"{field_prefix}.related_docs", paths=True),
            "test_commands": require_string_list(raw_area.get("test_commands"), f"{field_prefix}.test_commands"),
            "services": require_string_list(raw_area.get("services"), f"{field_prefix}.services"),
            "data_stores": require_string_list(raw_area.get("data_stores"), f"{field_prefix}.data_stores"),
            "risk_tags": require_string_list(raw_area.get("risk_tags"), f"{field_prefix}.risk_tags"),
        }
        for context_path in [*area["entrypoints"], *area["related_docs"]]:
            if not (project_root / Path(context_path)).is_file():
                raise ContextContractError(
                    f"{field_prefix} references a missing entrypoint or document: {context_path}"
                )
        areas.append(area)

    return {
        "schema_version": MAP_SCHEMA_VERSION,
        "project": data["project"].strip(),
        "exclude_globs": exclude_globs,
        "areas": areas,
    }


def run_git(project_root: Path, arguments: list[str], *, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        ["git", "-C", str(project_root), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ContextContractError(f"Git command failed ({' '.join(arguments)}): {detail}")
    return result


def decode_nul_paths(payload: bytes) -> list[str]:
    return [normalize_relative(item.decode("utf-8", errors="surrogateescape")) for item in payload.split(b"\0") if item]


def git_metadata(project_root: Path) -> dict[str, Any]:
    inside = run_git(project_root, ["rev-parse", "--is-inside-work-tree"], check=False)
    if inside.returncode != 0 or inside.stdout.strip() != b"true":
        raise ContextContractError("The project context index requires a Git worktree")

    tracked: dict[str, str] = {}
    stage_output = run_git(project_root, ["ls-files", "--stage", "-z"]).stdout
    for record in stage_output.split(b"\0"):
        if not record or b"\t" not in record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        parts = metadata.split()
        if len(parts) != 3 or parts[2] != b"0":
            continue
        path = normalize_relative(raw_path.decode("utf-8", errors="surrogateescape"))
        tracked[path] = parts[1].decode("ascii", errors="replace")

    dirty = set(decode_nul_paths(run_git(project_root, ["diff", "--name-only", "-z"]).stdout))
    dirty.update(decode_nul_paths(run_git(project_root, ["diff", "--cached", "--name-only", "-z"]).stdout))
    untracked = set(
        decode_nul_paths(run_git(project_root, ["ls-files", "--others", "--exclude-standard", "-z"]).stdout)
    )
    dirty.update(untracked)

    head_result = run_git(project_root, ["rev-parse", "HEAD"], check=False)
    head = head_result.stdout.decode("ascii", errors="replace").strip() if head_result.returncode == 0 else "unborn"
    branch_result = run_git(project_root, ["branch", "--show-current"], check=False)
    branch = branch_result.stdout.decode("utf-8", errors="replace").strip() or "detached"

    return {
        "tracked": tracked,
        "untracked": untracked,
        "dirty": dirty,
        "head": head,
        "branch": branch,
    }


def matches_glob(path: str, pattern: str) -> bool:
    if fnmatch.fnmatchcase(path, pattern):
        return True
    if pattern.endswith("/**") and path == pattern[:-3].rstrip("/"):
        return True
    return False


def is_excluded(path: str, patterns: Iterable[str]) -> bool:
    return any(matches_glob(path, pattern) for pattern in patterns)


def file_signature(path: Path, clean_blob: str | None) -> str:
    if clean_blob:
        return f"git:{clean_blob}"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(131_072), b""):
            digest.update(chunk)
    return f"worktree:{digest.hexdigest()}"


def unique_limited(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = value.strip()
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
            if len(result) >= MAX_VALUES_PER_FIELD:
                break
    return result


def python_analysis(text: str) -> tuple[list[str], list[str]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [], []
    symbols: list[str] = []
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(node.name)
        elif isinstance(node, ast.ClassDef):
            symbols.append(node.name)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return unique_limited(symbols), unique_limited(imports)


def analyze_text(relative_path: str, text: str) -> dict[str, list[str]]:
    suffix = PurePosixPath(relative_path).suffix.lower()
    symbols: list[str] = []
    imports: list[str] = []
    headings: list[str] = []
    routes: list[str] = []

    if suffix == ".py":
        symbols, imports = python_analysis(text)
    elif suffix == ".go":
        symbols = unique_limited(
            match.group(1) or match.group(2)
            for match in re.finditer(
                r"(?m)^\s*(?:func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)|type\s+([A-Za-z_]\w*))",
                text,
            )
        )
        imports = unique_limited(re.findall(r'(?m)^\s*"([A-Za-z0-9_./-]+)"\s*$', text))
    elif suffix in {".js", ".jsx", ".mjs", ".ts", ".tsx"}:
        symbols = unique_limited(
            re.findall(
                r"(?m)^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function|class|interface|type|enum|const|let|var)\s+([A-Za-z_$][\w$]*)",
                text,
            )
        )
        imports = unique_limited(
            list(re.findall(r"\bfrom\s+['\"]([^'\"]+)['\"]", text))
            + list(re.findall(r"\brequire\(\s*['\"]([^'\"]+)['\"]\s*\)", text))
        )
    elif suffix == ".sql":
        symbols = unique_limited(
            match.group(2)
            for match in re.finditer(
                r"(?im)\bcreate\s+(?:or\s+replace\s+)?(table|view|function|procedure|index)\s+(?:if\s+not\s+exists\s+)?([A-Za-z0-9_.\"]+)",
                text,
            )
        )
    elif suffix == ".md":
        headings = unique_limited(
            match.group(1).strip() for match in re.finditer(r"(?m)^#{1,6}\s+(.+?)\s*$", text)
        )
    elif PurePosixPath(relative_path).name.lower() in {"makefile", "gnumakefile"}:
        symbols = unique_limited(
            match.group(1)
            for match in re.finditer(r"(?m)^([A-Za-z0-9_.-]+)\s*:(?!=)", text)
            if not match.group(1).startswith(".")
        )

    route_patterns = (
        r"\b(?:app|router)\.(?:get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)['\"]",
        r"\bHandleFunc\s*\(\s*['\"]([^'\"]+)['\"]",
        r"@(?:app|router)\.(?:get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)['\"]",
    )
    for pattern in route_patterns:
        routes.extend(re.findall(pattern, text, flags=re.IGNORECASE))

    return {
        "symbols": unique_limited(symbols),
        "imports": unique_limited(imports),
        "headings": unique_limited(headings),
        "routes": unique_limited(routes),
    }


def classify_file(relative_path: str) -> str:
    name = PurePosixPath(relative_path).name.lower()
    suffix = PurePosixPath(relative_path).suffix.lower()
    if name in {"makefile", "gnumakefile"}:
        return "make"
    if suffix == ".md":
        return "documentation"
    if suffix in {".json", ".toml", ".yaml", ".yml"}:
        return "configuration"
    if suffix == ".sql":
        return "database"
    if suffix in {".css", ".html", ".scss"}:
        return "presentation"
    if suffix in INDEXABLE_EXTENSIONS:
        return "source"
    return "other"


def area_ids_for_path(relative_path: str, areas: list[dict[str, Any]]) -> list[str]:
    return [
        area["id"]
        for area in areas
        if any(matches_glob(relative_path, pattern) for pattern in area["path_globs"])
    ]


def map_fingerprint(project_map: dict[str, Any]) -> str:
    encoded = json.dumps(project_map, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_existing_index(cache_path: Path) -> dict[str, Any] | None:
    if not cache_path.is_file():
        return None
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("schema_version") != INDEX_SCHEMA_VERSION:
        return None
    if data.get("generator_version") != GENERATOR_VERSION:
        return None
    return data


def ensure_cache_ignored(project_root: Path, cache_relative: str) -> None:
    result = run_git(project_root, ["check-ignore", "-q", "--", cache_relative], check=False)
    if result.returncode != 0:
        raise ContextContractError(
            f"{cache_relative} is not ignored by Git. Add .developer-os/ to the project .gitignore first."
        )


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def build_index(
    project_root: Path,
    project_map: dict[str, Any],
    cache_relative: str = DEFAULT_CACHE_PATH,
    *,
    force: bool = False,
) -> tuple[dict[str, Any], dict[str, int]]:
    cache_relative = require_safe_relative(cache_relative, "cache path")
    ensure_cache_ignored(project_root, cache_relative)
    git = git_metadata(project_root)
    cache_path = project_root / Path(cache_relative)
    old_index = None if force else load_existing_index(cache_path)
    old_files = {
        item["path"]: item
        for item in (old_index or {}).get("files", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }

    patterns = (*BUILTIN_EXCLUDES, *project_map["exclude_globs"])
    candidates = sorted(set(git["tracked"]) | set(git["untracked"]))
    files: list[dict[str, Any]] = []
    refreshed = 0
    reused = 0
    skipped = 0

    for relative_path in candidates:
        if is_excluded(relative_path, patterns):
            skipped += 1
            continue
        absolute_path = project_root / Path(relative_path)
        if not absolute_path.is_file():
            continue
        size = absolute_path.stat().st_size
        suffix = absolute_path.suffix.lower()
        name = absolute_path.name.lower()
        indexable = suffix in INDEXABLE_EXTENSIONS or name in {"makefile", "gnumakefile"}
        if not indexable or size > MAX_INDEXED_BYTES:
            skipped += 1
            continue
        assigned_areas = area_ids_for_path(relative_path, project_map["areas"])
        if not assigned_areas:
            skipped += 1
            continue

        clean_blob = None
        if relative_path in git["tracked"] and relative_path not in git["dirty"]:
            clean_blob = git["tracked"][relative_path]
        signature = file_signature(absolute_path, clean_blob)
        old_entry = old_files.get(relative_path)
        if old_entry and old_entry.get("signature") == signature:
            analysis = {
                field: list(old_entry.get(field, []))
                for field in ("symbols", "imports", "headings", "routes")
            }
            reused += 1
        else:
            raw = absolute_path.read_bytes()
            if b"\0" in raw[:8192]:
                skipped += 1
                continue
            text = raw.decode("utf-8-sig", errors="replace")
            analysis = analyze_text(relative_path, text)
            refreshed += 1

        entry = {
            "path": relative_path,
            "signature": signature,
            "size": size,
            "kind": classify_file(relative_path),
            "areas": assigned_areas,
            **analysis,
        }
        files.append(entry)

    current_paths = {item["path"] for item in files}
    removed = len(set(old_files) - current_paths)
    index = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": project_map["project"],
        "map_fingerprint": map_fingerprint(project_map),
        "git": {
            "head": git["head"],
            "branch": git["branch"],
            "dirty_files": sorted(git["dirty"]),
        },
        "files": files,
    }
    write_json_atomic(cache_path, index)
    return index, {
        "refreshed": refreshed,
        "reused": reused,
        "removed": removed,
        "skipped": skipped,
    }


TOKEN_PATTERN = re.compile(r"[\w./:-]+", flags=re.UNICODE)
STOP_WORDS = {
    "a",
    "an",
    "and",
    "for",
    "from",
    "in",
    "of",
    "on",
    "the",
    "to",
    "with",
    "\uae30\ub2a5",
    "\ub300\ud55c",
    "\uc5d0\uc11c",
    "\uc73c\ub85c",
    "\uc791\uc5c5",
    "\ud504\ub85c젝\ud2b8",
}

FILE_SEARCH_STOP_WORDS = {
    "api",
    "app",
    "context",
    "data",
    "handler",
    "index",
    "make",
    "model",
    "project",
    "service",
    "status",
    "test",
}


def task_tokens(task: str) -> list[str]:
    return unique_limited(
        token.casefold()
        for token in TOKEN_PATTERN.findall(task)
        if len(token) >= 2 and token.casefold() not in STOP_WORDS
    )


def task_contains_term(normalized_task: str, tokens: list[str], term: str) -> bool:
    normalized_term = term.casefold().strip()
    if re.fullmatch(r"[a-z0-9_-]{1,3}", normalized_term):
        return normalized_term in tokens
    return normalized_term in normalized_task


def useful_file_token(token: str) -> bool:
    if token in FILE_SEARCH_STOP_WORDS:
        return False
    if token.isascii():
        return len(token) >= 4
    return len(token) >= 2


def entry_search_text(entry: dict[str, Any]) -> str:
    values = [entry["path"]]
    for field in ("symbols", "imports", "headings", "routes"):
        values.extend(entry.get(field, []))
    return " ".join(values).casefold()


def score_areas(
    project_map: dict[str, Any],
    index: dict[str, Any],
    task: str,
) -> tuple[dict[str, int], dict[str, list[str]]]:
    normalized_task = task.casefold()
    tokens = task_tokens(task)
    file_tokens = [token for token in tokens if useful_file_token(token)]
    scores = {area["id"]: 0 for area in project_map["areas"]}
    reasons = {area["id"]: [] for area in project_map["areas"]}

    for area in project_map["areas"]:
        area_id = area["id"]
        if area_id.casefold() in tokens:
            scores[area_id] += 14
            reasons[area_id].append(f"area id: {area_id}")
        if task_contains_term(normalized_task, tokens, area["name"]):
            scores[area_id] += 12
            reasons[area_id].append(f"area name: {area['name']}")
        for keyword in area["keywords"]:
            if task_contains_term(normalized_task, tokens, keyword):
                scores[area_id] += 10
                reasons[area_id].append(f"keyword: {keyword}")
        metadata = " ".join(
            [area_id, area["name"], area["description"], *area["keywords"]]
        ).casefold()
        overlap = [token for token in tokens if token in metadata]
        if overlap:
            scores[area_id] += min(8, len(overlap) * 2)

    for entry in index["files"]:
        search_text = entry_search_text(entry)
        matching = [token for token in file_tokens if token in search_text]
        if not matching:
            continue
        for area_id in entry["areas"]:
            scores[area_id] += min(6, len(matching) * 2)
            if len(reasons[area_id]) < 5:
                reasons[area_id].append(f"file match: {entry['path']}")

    return scores, reasons


def ordered_unique(values: Iterable[str]) -> list[str]:
    return unique_limited(values)


def select_context(
    project_map: dict[str, Any],
    index: dict[str, Any],
    task: str,
    explicit_areas: list[str] | None = None,
    *,
    limit: int = 30,
) -> dict[str, Any]:
    areas_by_id = {area["id"]: area for area in project_map["areas"]}
    explicit_areas = explicit_areas or []
    unknown = sorted(set(explicit_areas) - set(areas_by_id))
    if unknown:
        raise ContextContractError(f"Unknown area id: {', '.join(unknown)}")

    scores, reasons = score_areas(project_map, index, task)
    if explicit_areas:
        selected_ids = list(dict.fromkeys(explicit_areas))
        for area_id in selected_ids:
            scores[area_id] = max(scores[area_id], 100)
            reasons[area_id].insert(0, "explicit area selection")
    elif task.strip():
        ranked = sorted(scores, key=lambda area_id: (-scores[area_id], area_id))
        maximum = scores[ranked[0]] if ranked else 0
        threshold = max(4, int(maximum * 0.6))
        selected_ids = [area_id for area_id in ranked if scores[area_id] >= threshold and scores[area_id] > 0][:3]
    else:
        selected_ids = []

    selected_areas = [areas_by_id[area_id] for area_id in selected_ids]
    tokens = task_tokens(task)
    entrypoints = ordered_unique(path for area in selected_areas for path in area["entrypoints"])
    related_docs = ordered_unique(path for area in selected_areas for path in area["related_docs"])

    ranked_files: list[tuple[int, str, dict[str, Any]]] = []
    for entry in index["files"]:
        if selected_ids and not set(entry["areas"]).intersection(selected_ids):
            continue
        if not selected_ids:
            continue
        score = 0
        if entry["path"] in entrypoints:
            score += 100
        if entry["path"] in related_docs:
            score += 80
        search_text = entry_search_text(entry)
        score += sum(12 for token in tokens if token in entry["path"].casefold())
        score += sum(5 for token in tokens if token in search_text)
        if entry["kind"] in {"source", "database", "make"}:
            score += 3
        ranked_files.append((score, entry["path"], entry))
    ranked_files.sort(key=lambda item: (-item[0], item[1]))

    commands = ordered_unique(command for area in selected_areas for command in area["test_commands"])
    services = ordered_unique(value for area in selected_areas for value in area["services"])
    data_stores = ordered_unique(value for area in selected_areas for value in area["data_stores"])
    risk_tags = ordered_unique(value for area in selected_areas for value in area["risk_tags"])
    chosen_files = [entry for _, _, entry in ranked_files[:limit]]

    return {
        "project": project_map["project"],
        "task": task,
        "git": index["git"],
        "matched": bool(selected_ids),
        "selected_areas": [
            {
                **area,
                "score": scores[area["id"]],
                "reasons": reasons[area["id"]],
            }
            for area in selected_areas
        ],
        "area_catalog": [
            {"id": area["id"], "name": area["name"], "description": area["description"]}
            for area in project_map["areas"]
        ],
        "read_first": ordered_unique([*entrypoints, *related_docs]),
        "relevant_files": [
            {
                "path": entry["path"],
                "kind": entry["kind"],
                "symbols": entry["symbols"][:8],
                "routes": entry["routes"][:8],
            }
            for entry in chosen_files
        ],
        "relevant_file_total": len(ranked_files),
        "test_commands": commands,
        "services": services,
        "data_stores": data_stores,
        "risk_tags": risk_tags,
    }


def print_section(title: str, values: Iterable[str]) -> None:
    values = list(values)
    if not values:
        return
    print(f"\n{title}")
    for value in values:
        print(f"- {value}")


def render_text(selection: dict[str, Any], stats: dict[str, int], cache_relative: str) -> None:
    git = selection["git"]
    dirty = len(git["dirty_files"])
    state = "clean" if dirty == 0 else f"{dirty} dirty file(s)"
    print(f"Project context: {selection['project']}")
    if selection["task"]:
        print(f"Task: {selection['task']}")
    print(f"Git: {git['branch']} @ {git['head'][:12]} ({state})")
    print(
        f"Index: {cache_relative} "
        f"({stats['refreshed']} refreshed, {stats['reused']} reused, "
        f"{stats['removed']} removed, {stats['skipped']} skipped)"
    )

    if selection["selected_areas"]:
        print("\nSelected areas")
        for area in selection["selected_areas"]:
            reason = "; ".join(area["reasons"][:3]) or "metadata match"
            print(f"- {area['id']} ({area['score']}): {area['name']} [{reason}]")
    else:
        print("\nNo confident area match.")
        print("Available areas")
        for area in selection["area_catalog"]:
            print(f"- {area['id']}: {area['name']} - {area['description']}")
        print('Rerun with a more specific TASK or AREA="area-id".')

    print_section("Read first", selection["read_first"])
    if selection["relevant_files"]:
        shown = len(selection["relevant_files"])
        total = selection["relevant_file_total"]
        print(f"\nRelevant files ({shown} of {total})")
        for entry in selection["relevant_files"]:
            detail_values = [*entry["routes"], *entry["symbols"]]
            detail = f" [{', '.join(detail_values[:4])}]" if detail_values else ""
            print(f"- {entry['path']} ({entry['kind']}){detail}")

    print_section("Focused verification", selection["test_commands"])
    print_section("Services", selection["services"])
    print_section("Data stores", selection["data_stores"])
    print_section("Risk tags", selection["risk_tags"])
    if selection["matched"]:
        print("\nExpansion rule")
        print("- Start with this set; expand only when imports, shared contracts, or failing evidence cross the area boundary.")


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--map", default=DEFAULT_MAP_NAME)
    parser.add_argument("--cache", default=DEFAULT_CACHE_PATH)
    parser.add_argument("--task", default="")
    parser.add_argument("--area", action="append", default=[])
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--refresh", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_arguments(argv or sys.argv[1:])
    try:
        project_root = Path(args.project_root).resolve()
        if not project_root.is_dir():
            raise ContextContractError(f"Project root does not exist: {project_root}")
        if args.limit < 1 or args.limit > 200:
            raise ContextContractError("--limit must be between 1 and 200")
        project_map = load_project_map(project_root, args.map)
        index, stats = build_index(project_root, project_map, args.cache, force=args.refresh)
        selection = select_context(
            project_map,
            index,
            args.task,
            explicit_areas=args.area,
            limit=args.limit,
        )
        if args.format == "json":
            print(json.dumps({"selection": selection, "index_stats": stats}, ensure_ascii=False, indent=2))
        else:
            render_text(selection, stats, args.cache)
        return 0
    except ContextContractError as exc:
        print(f"Context error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
