#!/usr/bin/env python3
"""Measure context selection without changing its result or cache state."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .context_identity import canonical_json, namespace_sha256
from .project_context import (
    DEFAULT_CACHE_PATH,
    ContextContractError,
    build_index,
    load_project_map,
    render_text,
    select_context,
)


CONTEXT_EFFICIENCY_SNAPSHOT_VERSION = "ContextEfficiencySnapshotV1"
OBSERVER_VERSION = "1.0.0"
VALIDATION_STATES = {"VALID", "INVALID", "NOT_PROVIDED"}


class ContextObservabilityError(ValueError):
    """An observability input or snapshot violates the sidecar contract."""


def _required(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContextObservabilityError(f"{field} must be a non-empty string")
    return value.strip()


def _non_negative(value: int | float, field: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ContextObservabilityError(f"{field} must be non-negative")
    return value


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _ordered_unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _line_count(path: Path) -> int:
    raw = path.read_bytes()
    if not raw:
        return 0
    return raw.count(b"\n") + (0 if raw.endswith(b"\n") else 1)


def _validation_state(value: str, field: str) -> str:
    if value not in VALIDATION_STATES:
        raise ContextObservabilityError(
            f"{field} must be one of {sorted(VALIDATION_STATES)}"
        )
    return value


def _actual_api_usage(value: Mapping[str, Any] | None) -> dict[str, int] | None:
    if value is None:
        return None
    if value.get("measurement") != "PROVIDER_ACTUAL":
        raise ContextObservabilityError("API usage must be provider-reported actual usage")
    allowed = {
        "measurement",
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "total_tokens",
    }
    if set(value) - allowed:
        raise ContextObservabilityError("API usage contains unsupported fields")
    result: dict[str, Any] = {"measurement": "PROVIDER_ACTUAL"}
    for field in sorted(allowed - {"measurement"}):
        count = value.get(field)
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ContextObservabilityError(f"{field} must be a non-negative integer")
        result[field] = count
    return result


def build_context_efficiency_snapshot_v1(
    *,
    project_root: Path,
    lane: str,
    task: str,
    explicit_areas: list[str] | None = None,
    limit: int = 30,
    cache_relative: str = DEFAULT_CACHE_PATH,
    seal_validation_status: str = "NOT_PROVIDED",
    dirty_manifest_validation_status: str = "NOT_PROVIDED",
    actual_api_usage: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Return a metrics-only snapshot, the unchanged selection, and rendered output."""
    root = project_root.resolve()
    if not root.is_dir():
        raise ContextObservabilityError(f"project root does not exist: {root}")
    lane_value = _required(lane, "lane")
    seal_state = _validation_state(seal_validation_status, "seal_validation_status")
    dirty_state = _validation_state(
        dirty_manifest_validation_status,
        "dirty_manifest_validation_status",
    )

    started = time.perf_counter_ns()
    project_map = load_project_map(root)
    index, index_stats = build_index(
        root,
        project_map,
        cache_relative,
        persist_cache=False,
    )
    selection = select_context(
        project_map,
        index,
        task,
        explicit_areas=explicit_areas,
        limit=limit,
    )
    rendered = io.StringIO()
    with contextlib.redirect_stdout(rendered):
        render_text(selection, index_stats, cache_relative)
    report_text = rendered.getvalue()
    context_build_duration_ms = (time.perf_counter_ns() - started) / 1_000_000

    read_first = list(selection["read_first"])
    relevant = [entry["path"] for entry in selection["relevant_files"]]
    occurrences = [*read_first, *relevant]
    selected_paths = _ordered_unique(occurrences)
    index_by_path = {entry["path"]: entry for entry in index["files"]}

    selected_total_bytes = 0
    selected_total_lines = 0
    selected_git_blob_identities = 0
    selected_content_identities = 0
    selected_sizes: dict[str, int] = {}
    for relative_path in selected_paths:
        entry = index_by_path.get(relative_path)
        absolute_path = root / Path(relative_path)
        if not absolute_path.is_file():
            raise ContextObservabilityError(
                f"selected context path is absent from the workspace: {relative_path}"
            )
        size = int(entry["size"]) if entry is not None else absolute_path.stat().st_size
        selected_sizes[relative_path] = size
        selected_total_bytes += size
        selected_total_lines += _line_count(absolute_path)
        if entry is not None and str(entry["signature"]).startswith("git:"):
            selected_git_blob_identities += 1
        else:
            selected_content_identities += 1

    reason_paths = {
        "READ_FIRST": _ordered_unique(read_first),
        "RELEVANT_FILE": _ordered_unique(relevant),
    }
    inclusion_reasons = []
    for reason, paths in reason_paths.items():
        inclusion_reasons.append(
            {
                "reason": reason,
                "file_count": len(paths),
                "total_bytes": sum(selected_sizes[path] for path in paths),
            }
        )

    occurrence_counts = {path: occurrences.count(path) for path in selected_paths}
    repeated_sources = [
        {"path": path, "selection_count": occurrence_counts[path]}
        for path in selected_paths
        if occurrence_counts[path] > 1
    ]
    dirty_paths = set(index["git"]["dirty_files"])
    dirty_indexed_paths = dirty_paths.intersection(index_by_path)
    dirty_full_scan_paths = dirty_paths.intersection(set(index_by_path) | set(selected_paths))
    packet_bytes = len(canonical_json(selection))
    output_bytes = len(report_text.encode("utf-8"))

    snapshot = {
        "schema_version": CONTEXT_EFFICIENCY_SNAPSHOT_VERSION,
        "observer_version": OBSERVER_VERSION,
        "authority_status": "NON_AUTHORITATIVE_SIDECAR",
        "project": selection["project"],
        "lane": lane_value,
        "namespace_sha256": namespace_sha256(selection["project"], lane_value),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "task_context_request_sha256": _sha256_bytes(task.encode("utf-8")),
        "selection": {
            "selected_file_count": len(selected_paths),
            "selected_total_bytes": selected_total_bytes,
            "selected_total_lines": selected_total_lines,
            "selection_occurrence_count": len(occurrences),
            "inclusion_reasons": inclusion_reasons,
        },
        "expansion": {
            "stage_count": 1,
            "expansion_count": 0,
            "stages": [
                {
                    "stage": "INITIAL_SELECTION",
                    "selected_file_count": len(selected_paths),
                }
            ],
        },
        "repeated_selection": {
            "repeated_source_count": len(repeated_sources),
            "repeated_occurrence_count": sum(
                item["selection_count"] - 1 for item in repeated_sources
            ),
            "sources": repeated_sources,
        },
        "identity_reuse": {
            "index_reused_file_count": index_stats["reused"],
            "index_refreshed_file_count": index_stats["refreshed"],
            "selected_git_blob_identity_count": selected_git_blob_identities,
            "selected_content_identity_count": selected_content_identities,
        },
        "dirty_scan": {
            "dirty_full_scan": bool(dirty_full_scan_paths),
            "dirty_path_count": len(dirty_paths),
            "dirty_indexed_path_count": len(dirty_indexed_paths),
            "dirty_full_scan_path_count": len(dirty_full_scan_paths),
        },
        "identity_validation": {
            "development_context_seal": seal_state,
            "dirty_tree_scope_manifest": dirty_state,
        },
        "duration": {
            "context_build_duration_ms": round(context_build_duration_ms, 3),
        },
        "packet_sizes": {
            "final_context_packet_sha256": _sha256_bytes(canonical_json(selection)),
            "final_context_packet_bytes": packet_bytes,
            "report_output_bytes": output_bytes,
        },
        "actual_api_usage": _actual_api_usage(actual_api_usage),
        "snapshot_sha256": "PENDING",
    }
    validate_context_efficiency_snapshot_v1(snapshot, verify_hash=False)
    snapshot["snapshot_sha256"] = _sha256_bytes(
        canonical_json({key: value for key, value in snapshot.items() if key != "snapshot_sha256"})
    )
    validate_context_efficiency_snapshot_v1(snapshot, verify_hash=True)
    return snapshot, selection, report_text


def validate_context_efficiency_snapshot_v1(
    snapshot: Mapping[str, Any],
    *,
    verify_hash: bool = True,
    expected_project: str | None = None,
    expected_lane: str | None = None,
) -> None:
    value = dict(snapshot)
    required = {
        "schema_version",
        "observer_version",
        "authority_status",
        "project",
        "lane",
        "namespace_sha256",
        "captured_at",
        "task_context_request_sha256",
        "selection",
        "expansion",
        "repeated_selection",
        "identity_reuse",
        "dirty_scan",
        "identity_validation",
        "duration",
        "packet_sizes",
        "actual_api_usage",
        "snapshot_sha256",
    }
    if set(value) != required:
        raise ContextObservabilityError("snapshot fields do not match ContextEfficiencySnapshotV1")
    if value["schema_version"] != CONTEXT_EFFICIENCY_SNAPSHOT_VERSION:
        raise ContextObservabilityError("unsupported snapshot schema version")
    if value["observer_version"] != OBSERVER_VERSION:
        raise ContextObservabilityError("unsupported observer version")
    if value["authority_status"] != "NON_AUTHORITATIVE_SIDECAR":
        raise ContextObservabilityError("snapshot must remain non-authoritative")
    project = _required(value["project"], "project")
    lane = _required(value["lane"], "lane")
    if value["namespace_sha256"] != namespace_sha256(project, lane):
        raise ContextObservabilityError("project/lane namespace mismatch")
    if expected_project is not None and project != expected_project:
        raise ContextObservabilityError("snapshot project mismatch")
    if expected_lane is not None and lane != expected_lane:
        raise ContextObservabilityError("snapshot lane mismatch")
    if len(value["task_context_request_sha256"]) != 64:
        raise ContextObservabilityError("task context request identity must be SHA-256")
    for field in ("selected_file_count", "selected_total_bytes", "selected_total_lines"):
        _non_negative(value["selection"][field], field)
    _non_negative(value["duration"]["context_build_duration_ms"], "context build duration")
    if len(value["packet_sizes"]["final_context_packet_sha256"]) != 64:
        raise ContextObservabilityError("final context packet identity must be SHA-256")
    _non_negative(value["packet_sizes"]["final_context_packet_bytes"], "packet bytes")
    _non_negative(value["packet_sizes"]["report_output_bytes"], "report bytes")
    _validation_state(
        value["identity_validation"]["development_context_seal"],
        "development_context_seal",
    )
    _validation_state(
        value["identity_validation"]["dirty_tree_scope_manifest"],
        "dirty_tree_scope_manifest",
    )
    _actual_api_usage(value["actual_api_usage"])
    if verify_hash:
        expected = _sha256_bytes(
            canonical_json({key: item for key, item in value.items() if key != "snapshot_sha256"})
        )
        if value["snapshot_sha256"] != expected:
            raise ContextObservabilityError("snapshot hash mismatch")


def write_snapshot(path: Path, snapshot: Mapping[str, Any]) -> None:
    validate_context_efficiency_snapshot_v1(snapshot)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--lane", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--area", action="append", default=[])
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--output")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_arguments(argv or sys.argv[1:])
    try:
        snapshot, _, _ = build_context_efficiency_snapshot_v1(
            project_root=Path(args.project_root),
            lane=args.lane,
            task=args.task,
            explicit_areas=args.area,
            limit=args.limit,
        )
        if args.output:
            write_snapshot(Path(args.output), snapshot)
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        return 0
    except (ContextContractError, ContextObservabilityError) as exc:
        print(f"Context observability error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
