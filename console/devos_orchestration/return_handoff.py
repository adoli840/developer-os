from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from .control_plane import (
    ControlPlaneError,
    OrchestrationControlStore,
    transport_capabilities,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


class ReturnHandoffStore:
    """Seal captured Codex output for a later, separately authorized delivery."""

    def __init__(
        self,
        directory: Path,
        dispatch_directory: Path,
        control: OrchestrationControlStore,
    ) -> None:
        self.directory = directory
        self.dispatch_directory = dispatch_directory
        self.control = control
        self.ledger_path = directory / "return-ledger.json"
        self._lock = Lock()
        directory.mkdir(parents=True, exist_ok=True)

    def _ledger(self) -> dict[str, Any]:
        if not self.ledger_path.is_file():
            return {"schema_version": "1", "returns": {}}
        value = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        if value.get("schema_version") != "1" or not isinstance(value.get("returns"), dict):
            raise ControlPlaneError("INVALID_RETURN_HANDOFF_LEDGER")
        return value

    def _write_ledger(self, value: dict[str, Any]) -> None:
        temporary = self.ledger_path.with_suffix(".tmp")
        temporary.write_bytes(
            json.dumps(value, ensure_ascii=True, indent=2).encode("utf-8") + b"\n",
        )
        temporary.replace(self.ledger_path)

    @staticmethod
    def _read_json(path: Path, error_code: str) -> tuple[dict[str, Any], bytes]:
        if not path.is_file():
            raise ControlPlaneError(error_code)
        raw = path.read_bytes()
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise ControlPlaneError(error_code) from error
        if not isinstance(value, dict):
            raise ControlPlaneError(error_code)
        return value, raw

    def create(
        self,
        project: str,
        source_handoff_id: str,
        *,
        return_route_id: str,
    ) -> dict[str, Any]:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", source_handoff_id):
            raise ControlPlaneError("INVALID_HANDOFF_ID")
        dispatch_artifact, dispatch_bytes = self._read_json(
            self.dispatch_directory / f"{source_handoff_id}.json",
            "SOURCE_DISPATCH_ARTIFACT_MISSING",
        )
        dispatch_ledger, _ = self._read_json(
            self.dispatch_directory / "dispatch-ledger.json",
            "SOURCE_DISPATCH_LEDGER_MISSING",
        )
        dispatch_entry = dispatch_ledger.get("handoffs", {}).get(source_handoff_id)
        if not isinstance(dispatch_entry, dict) or dispatch_entry.get("state") != "COMPLETED":
            raise ControlPlaneError("SOURCE_DISPATCH_NOT_COMPLETED")
        if hashlib.sha256(dispatch_bytes).hexdigest() != dispatch_entry.get("artifact_sha256"):
            raise ControlPlaneError("SOURCE_DISPATCH_ARTIFACT_CHANGED")

        result_artifact, result_bytes = self._read_json(
            self.dispatch_directory / f"{source_handoff_id}-result.json",
            "SOURCE_CODEX_RESULT_MISSING",
        )
        result_artifact_hash = hashlib.sha256(result_bytes).hexdigest()
        if (
            result_artifact_hash != dispatch_entry.get("result_artifact_sha256")
            or result_artifact.get("status") != "COMPLETED"
            or result_artifact.get("handoff_id") != source_handoff_id
        ):
            raise ControlPlaneError("SOURCE_CODEX_RESULT_CHANGED")
        result_content = result_artifact.get("response_text")
        if not isinstance(result_content, str) or not result_content:
            raise ControlPlaneError("SOURCE_CODEX_RESULT_EMPTY")

        source_envelope = dispatch_artifact.get("dispatch_envelope")
        if not isinstance(source_envelope, dict):
            raise ControlPlaneError("SOURCE_DISPATCH_ENVELOPE_MISSING")
        route_state = self.control.resolve_route(project, return_route_id)
        route = route_state["route"]
        source = route_state["source"]
        destination = route_state["destination"]
        dispatched_to = source_envelope.get("destination_node", {}).get("node_id")
        if (
            dispatch_artifact.get("project") != project
            or source.get("node_id") != dispatched_to
            or source.get("role") != "CODEX_WORKER"
            or destination.get("role") != "MAINLINE"
            or route.get("handoff_type") != "REPORT"
        ):
            raise ControlPlaneError("INVALID_RETURN_ROUTE")

        capabilities = transport_capabilities(destination["transport_kind"])
        programmatic_mainline = destination["transport_kind"] == "OPENAI_RESPONSES"
        capability = {
            "transport_kind": destination["transport_kind"],
            "read": capabilities.can_read,
            "write": capabilities.can_write,
            "resume": capabilities.can_resume,
            "status": (
                "PROGRAMMATIC_PREVIEW_READY_LIVE_API_LOCKED"
                if programmatic_mainline
                else "READY" if capabilities.can_write else "BLOCKED_UNSUPPORTED"
            ),
        }
        delivery_status = (
            "API_MAINLINE_RETURN_PREVIEW_REQUIRED"
            if programmatic_mainline
            else "READY_FOR_SEPARATE_DELIVERY_APPROVAL"
            if capabilities.can_write
            else "USER_ASSISTED_EXACT_DELIVERY_CANDIDATE"
        )
        result_content_hash = hashlib.sha256(result_content.encode("utf-8")).hexdigest()
        return_id = (
            f"return-{source_handoff_id}-{destination['node_id'].lower()}"
            if programmatic_mainline
            else f"return-{source_handoff_id}"
        )
        envelope = {
            "return_envelope_version": "2" if programmatic_mainline else "1",
            "return_id": return_id,
            "project": project,
            "source_dispatch_id": source_handoff_id,
            "source_dispatch_envelope_sha256": dispatch_artifact.get("envelope_sha256"),
            "source_result_artifact_sha256": result_artifact_hash,
            "result_content_sha256": result_content_hash,
            "originating_task_sha256": dispatch_artifact.get("task_content_sha256"),
            "source_node": {"node_id": source["node_id"], "role": source["role"]},
            "destination_node": {
                "node_id": destination["node_id"],
                "role": destination["role"],
                "transport_kind": destination["transport_kind"],
            },
            "route": {
                "route_id": route["route_id"],
                "handoff_type": route["handoff_type"],
            },
            "workspace_seal": source_envelope.get("workspace"),
            "runtime_protocol_sha256": source_envelope.get("runtime_protocol_sha256"),
            "result_content": result_content,
            "transport_capability": capability,
            "delivery_status": delivery_status,
            "state": "PREPARED",
            "duplicate_status": "UNCONSUMED",
            "actual_mainline_send_count": 0,
            "created_at": _now(),
        }
        envelope_hash = hashlib.sha256(_canonical_bytes(envelope)).hexdigest()
        artifact = {**envelope, "return_envelope_sha256": envelope_hash}
        artifact_bytes = json.dumps(
            artifact, ensure_ascii=True, indent=2,
        ).encode("utf-8") + b"\n"
        artifact_hash = hashlib.sha256(artifact_bytes).hexdigest()
        path = self.directory / f"{return_id}.json"
        with self._lock:
            ledger = self._ledger()
            if return_id in ledger["returns"] or path.exists():
                raise ControlPlaneError("DUPLICATE_RETURN_HANDOFF_BLOCKED")
            if any(
                entry.get("source_result_artifact_sha256") == result_artifact_hash
                and entry.get("destination_node_id") == destination["node_id"]
                for entry in ledger["returns"].values()
            ):
                raise ControlPlaneError("DUPLICATE_RETURN_HANDOFF_BLOCKED")
            path.write_bytes(artifact_bytes)
            ledger["returns"][return_id] = {
                "project": project,
                "source_dispatch_id": source_handoff_id,
                "source_result_artifact_sha256": result_artifact_hash,
                "result_content_sha256": result_content_hash,
                "return_envelope_sha256": envelope_hash,
                "artifact_sha256": artifact_hash,
                "destination_node_id": destination["node_id"],
                "transport_capability": capability,
                "delivery_status": delivery_status,
                "state": "PREPARED",
                "duplicate_status": "UNCONSUMED",
                "actual_mainline_send_count": 0,
                "created_at": envelope["created_at"],
            }
            self._write_ledger(ledger)
        self.control.audit.write(
            "return_handoff_created",
            timestamp=envelope["created_at"],
            project=project,
            return_id=return_id,
            source_dispatch_id=source_handoff_id,
            return_envelope_sha256=envelope_hash,
            result_content_sha256=result_content_hash,
            delivery_status=delivery_status,
            actual_mainline_send_count=0,
        )
        return {**artifact, "artifact_sha256": artifact_hash}

    def list_for_project(self, project: str) -> list[dict[str, Any]]:
        with self._lock:
            entries = self._ledger()["returns"]
        return [
            {"return_id": return_id, **entry}
            for return_id, entry in entries.items()
            if entry.get("project") == project
        ]
