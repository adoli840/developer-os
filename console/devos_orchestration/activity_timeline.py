from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


TIMELINE_VERSION = "2c.timeline.1"


def project_activity_timeline(
    project: str,
    dispatch_directory: Path,
    mainline_return_directory: Path,
    pilot_directory: Path | None = None,
) -> dict[str, Any]:
    if project != "btest":
        return {"version": TIMELINE_VERSION, "events": []}
    events: list[dict[str, Any]] = []
    dispatch_ledger = _read_json(dispatch_directory / "dispatch-ledger.json")
    for handoff_id, entry in dispatch_ledger.get("handoffs", {}).items():
        if entry.get("state") != "COMPLETED":
            continue
        artifact = _read_json(dispatch_directory / f"{handoff_id}.json")
        sent_at = entry.get("attempt_started_at") or _history_time(entry, "SENT")
        completed_at = entry.get("updated_at")
        detail = {
            "handoff_id": handoff_id,
            "gate": None,
            "message_preview": _preview(artifact.get("task_message")),
            "token_usage": None,
            "cost_usd": None,
            "hashes": {
                "task": entry.get("task_content_sha256"),
                "envelope": entry.get("envelope_sha256"),
            },
        }
        if sent_at:
            events.append(_event(
                sent_at, artifact.get("source_node_id") or "BTEST_MAINLINE_API",
                artifact.get("destination_node_id") or "BTEST_CODEX_WORKER",
                "TASK_SENT", "COMPLETED", detail,
            ))
        if completed_at:
            events.append(_event(
                completed_at, "BTEST_CODEX_WORKER", "BTEST_MAINLINE_API",
                "REPORT_RECEIVED", "COMPLETED", detail,
            ))

    return_ledger = _read_json(mainline_return_directory / "ledger.json")
    for return_id, entry in return_ledger.get("returns", {}).items():
        if entry.get("project") != project or entry.get("state") != "COMPLETED":
            continue
        result = _read_json(mainline_return_directory / f"{return_id}-result.json")
        timestamp = result.get("completed_at") or entry.get("terminal_at")
        detail = {
            "handoff_id": return_id,
            "gate": result.get("gate"),
            "message_preview": _preview((result.get("next_handoff") or {}).get("exact_message")),
            "token_usage": result.get("token_usage"),
            "cost_usd": result.get("usage_based_estimated_cost_usd"),
            "hashes": {
                "result": result.get("result_sha256"),
                "next_task": (result.get("next_handoff") or {}).get("exact_message_sha256"),
            },
        }
        if timestamp:
            events.append(_event(
                timestamp, "BTEST_MAINLINE_API", result.get("destination") or "SYSTEM",
                "GATE_DECIDED", result.get("gate") or result.get("status"), detail,
            ))
            if (result.get("next_handoff") or {}).get("status") == "PREPARED":
                events.append(_event(
                    timestamp, "BTEST_MAINLINE_API", "BTEST_CODEX_WORKER",
                    "NEXT_TASK_PREPARED", "USER_APPROVAL_REQUIRED", detail,
                ))
    if pilot_directory is not None:
        pilot_ledger = _read_json(pilot_directory / "ledger.json")
        for run_id, entry in pilot_ledger.get("runs", {}).items():
            if entry.get("project") != project:
                continue
            timestamp = entry.get("completed_at")
            if timestamp:
                events.append(_event(
                    timestamp, "AUTO_SAFE_CONTINUE", "SYSTEM",
                    "AUTO_PILOT_STOPPED", entry.get("stop_reason") or entry.get("status"),
                    {
                        "handoff_id": run_id,
                        "gate": None,
                        "message_preview": None,
                        "token_usage": None,
                        "cost_usd": entry.get("cumulative_usage_based_cost_usd", "0"),
                        "hashes": {"result": entry.get("result_file_sha256")},
                    },
                ))
    events.sort(key=lambda item: (item["timestamp"], item["event_id"]))
    return {"version": TIMELINE_VERSION, "events": events}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _history_time(entry: dict[str, Any], state: str) -> str | None:
    for item in entry.get("state_history") or []:
        if item.get("state") == state:
            return item.get("at")
    return None


def _preview(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    compact = " ".join(value.split())
    return compact if len(compact) <= 240 else compact[:237] + "..."


def _event(
    timestamp: str,
    source: str,
    destination: str,
    event_type: str,
    status: str,
    detail: dict[str, Any],
) -> dict[str, Any]:
    core = {
        "timestamp": timestamp,
        "source": source,
        "destination": destination,
        "event_type": event_type,
        "status": status,
        "detail": detail,
    }
    event_id = hashlib.sha256(
        json.dumps(core, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8"),
    ).hexdigest()
    return {"event_id": event_id, **core}
