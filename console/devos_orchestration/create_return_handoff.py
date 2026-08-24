from __future__ import annotations

import argparse
import json
from pathlib import Path

from console.devos_console.audit import AuditLog
from console.devos_console.settings import load_settings

from .control_plane import OrchestrationControlStore
from .return_handoff import ReturnHandoffStore


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-handoff-id", required=True)
    parser.add_argument("--return-route-id", default="BTEST_CODEX_TO_MAINLINE")
    parser.add_argument("--runtime-dir", type=Path)
    args = parser.parse_args()
    settings = load_settings(dev_mode=True)
    runtime_dir = (args.runtime_dir or settings.runtime_dir).resolve()
    control = OrchestrationControlStore(
        runtime_dir / "orchestration-control.json",
        [project.slug for project in settings.projects],
        AuditLog(runtime_dir / "audit.jsonl"),
    )
    store = ReturnHandoffStore(
        runtime_dir / "return-handoffs",
        runtime_dir / "dispatch-previews",
        control,
    )
    value = store.create(
        "btest",
        args.source_handoff_id,
        return_route_id=args.return_route_id,
    )
    print(json.dumps({
        "return_id": value["return_id"],
        "return_envelope_sha256": value["return_envelope_sha256"],
        "result_content_sha256": value["result_content_sha256"],
        "source_result_artifact_sha256": value["source_result_artifact_sha256"],
        "route": value["route"],
        "destination_node": value["destination_node"],
        "transport_capability": value["transport_capability"],
        "delivery_status": value["delivery_status"],
        "actual_mainline_send_count": value["actual_mainline_send_count"],
    }, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
