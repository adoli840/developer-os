from __future__ import annotations

import argparse
import json
from pathlib import Path

from console.devos_console.audit import AuditLog
from console.devos_console.settings import load_settings

from .codex_transport import CodexTransportHealth
from .control_plane import OrchestrationControlStore
from .workspace_guard import capture_workspace_binding


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-dir", type=Path)
    parser.add_argument("--distro", default="Ubuntu")
    args = parser.parse_args()
    settings = load_settings(dev_mode=True)
    runtime_dir = (args.runtime_dir or settings.runtime_dir).resolve()
    project = next(item for item in settings.projects if item.slug == "btest")
    seal = capture_workspace_binding("btest", project.path, distro=args.distro)
    store = OrchestrationControlStore(
        runtime_dir / "orchestration-control.json",
        [item.slug for item in settings.projects],
        AuditLog(runtime_dir / "audit.jsonl"),
        capability_provider=CodexTransportHealth().for_node,
    )
    current = next(item for item in store.list_projects()["projects"] if item["project"] == "btest")
    existing_node_ids = {item["node_id"] for item in current["nodes"]}
    if existing_node_ids - {"BTEST_MAINLINE", "BTEST_MAINLINE_API"} or current["routes"]:
        raise SystemExit("BTEST_ORCHESTRATION_GRAPH_NOT_EMPTY")
    store.add_node("btest", {
        "node_id": "BTEST_CODEX_WORKER", "display_name": "bTest Codex Worker",
        "role": "CODEX_WORKER", "transport_kind": "CODEX_THREAD",
        "transport_ref": seal.as_transport_ref(), "enabled": True,
        "allowed_sources": ["BTEST_MAINLINE"],
        "allowed_destinations": ["BTEST_MAINLINE"],
    })
    store.add_route("btest", {
        "route_id": "BTEST_MAINLINE_TO_CODEX", "source_node_id": "BTEST_MAINLINE",
        "destination_node_id": "BTEST_CODEX_WORKER", "enabled": True,
        "handoff_type": "TASK",
    })
    state = store.add_route("btest", {
        "route_id": "BTEST_CODEX_TO_MAINLINE", "source_node_id": "BTEST_CODEX_WORKER",
        "destination_node_id": "BTEST_MAINLINE", "enabled": True,
        "handoff_type": "REPORT",
    })
    worker = next(item for item in state["nodes"] if item["node_id"] == "BTEST_CODEX_WORKER")
    print(json.dumps({
        "project": "btest", "node_id": worker["node_id"],
        "mode": state["mode"], "status": state["status"],
        "routes": [item["route_id"] for item in state["routes"]],
        "codex_transport": worker["codex_transport"],
        "actual_thread_start_count": 0, "actual_turn_start_count": 0,
        "btest_mutation_count": 0,
    }, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
