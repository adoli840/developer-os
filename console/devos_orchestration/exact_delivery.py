from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from .control_plane import ControlPlaneError


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


class ExactDeliveryStore:
    """Manual exact-content delivery with no native transport side effect."""

    def __init__(self, directory: Path, return_directory: Path) -> None:
        self.directory = directory
        self.return_directory = return_directory
        self.ledger_path = directory / "delivery-ledger.json"
        self._lock = Lock()
        directory.mkdir(parents=True, exist_ok=True)

    def _ledger(self) -> dict[str, Any]:
        if not self.ledger_path.is_file():
            return {"schema_version": "1", "deliveries": {}}
        value = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        if value.get("schema_version") != "1" or not isinstance(value.get("deliveries"), dict):
            raise ControlPlaneError("INVALID_EXACT_DELIVERY_LEDGER")
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

    @staticmethod
    def _identifier(value: str, label: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,191}", value):
            raise ControlPlaneError(f"INVALID_{label}")
        return value

    def create(self, project: str, return_id: str) -> dict[str, Any]:
        self._identifier(return_id, "RETURN_ID")
        return_artifact, return_bytes = self._read_json(
            self.return_directory / f"{return_id}.json",
            "RETURN_HANDOFF_ARTIFACT_MISSING",
        )
        return_ledger, _ = self._read_json(
            self.return_directory / "return-ledger.json",
            "RETURN_HANDOFF_LEDGER_MISSING",
        )
        return_entry = return_ledger.get("returns", {}).get(return_id)
        return_artifact_hash = hashlib.sha256(return_bytes).hexdigest()
        if (
            not isinstance(return_entry, dict)
            or return_entry.get("project") != project
            or return_entry.get("artifact_sha256") != return_artifact_hash
            or return_artifact.get("return_envelope_sha256")
            != return_entry.get("return_envelope_sha256")
        ):
            raise ControlPlaneError("RETURN_HANDOFF_ARTIFACT_CHANGED")
        exact_message = return_artifact.get("result_content")
        exact_message_hash = hashlib.sha256(str(exact_message).encode("utf-8")).hexdigest()
        if (
            not isinstance(exact_message, str)
            or not exact_message
            or exact_message_hash != return_artifact.get("result_content_sha256")
            or return_artifact.get("destination_node", {}).get("role") != "MAINLINE"
            or return_artifact.get("actual_mainline_send_count") != 0
        ):
            raise ControlPlaneError("RETURN_HANDOFF_NOT_DELIVERABLE")
        delivery_id = f"delivery-{return_id}"
        packet = {
            "delivery_packet_version": "1",
            "delivery_id": delivery_id,
            "project": project,
            "delivery_mode": "USER_ASSISTED_EXACT_DELIVERY",
            "return_id": return_id,
            "return_envelope_sha256": return_artifact["return_envelope_sha256"],
            "source_dispatch_id": return_artifact["source_dispatch_id"],
            "source_result_artifact_sha256": return_artifact["source_result_artifact_sha256"],
            "result_content_sha256": exact_message_hash,
            "destination_node_id": return_artifact["destination_node"]["node_id"],
            "exact_message": exact_message,
            "state": "PREPARED",
            "actual_mainline_send_count": 0,
            "created_at": _now(),
        }
        packet_hash = hashlib.sha256(_canonical_bytes(packet)).hexdigest()
        artifact = {**packet, "delivery_packet_sha256": packet_hash}
        artifact_bytes = json.dumps(
            artifact, ensure_ascii=True, indent=2,
        ).encode("utf-8") + b"\n"
        artifact_hash = hashlib.sha256(artifact_bytes).hexdigest()
        path = self.directory / f"{delivery_id}.json"
        with self._lock:
            ledger = self._ledger()
            if delivery_id in ledger["deliveries"] or path.exists() or any(
                item.get("return_envelope_sha256") == return_artifact["return_envelope_sha256"]
                for item in ledger["deliveries"].values()
            ):
                raise ControlPlaneError("DUPLICATE_EXACT_DELIVERY_BLOCKED")
            path.write_bytes(artifact_bytes)
            ledger["deliveries"][delivery_id] = {
                "project": project,
                "return_id": return_id,
                "source_dispatch_id": packet["source_dispatch_id"],
                "destination_node_id": packet["destination_node_id"],
                "result_content_sha256": exact_message_hash,
                "return_envelope_sha256": packet["return_envelope_sha256"],
                "delivery_packet_sha256": packet_hash,
                "artifact_sha256": artifact_hash,
                "state": "PREPARED",
                "actual_mainline_send_count": 0,
                "created_at": packet["created_at"],
            }
            self._write_ledger(ledger)
        return {**artifact, "artifact_sha256": artifact_hash}

    def _verified(self, project: str, delivery_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        self._identifier(delivery_id, "DELIVERY_ID")
        with self._lock:
            ledger = self._ledger()
            entry = ledger["deliveries"].get(delivery_id)
            if not isinstance(entry, dict) or entry.get("project") != project:
                raise ControlPlaneError("EXACT_DELIVERY_NOT_FOUND")
            artifact, raw = self._read_json(
                self.directory / f"{delivery_id}.json",
                "EXACT_DELIVERY_ARTIFACT_MISSING",
            )
            if (
                hashlib.sha256(raw).hexdigest() != entry.get("artifact_sha256")
                or artifact.get("delivery_packet_sha256") != entry.get("delivery_packet_sha256")
                or artifact.get("result_content_sha256") != entry.get("result_content_sha256")
            ):
                raise ControlPlaneError("EXACT_DELIVERY_ARTIFACT_CHANGED")
            return dict(entry), artifact

    def exact_content(
        self,
        project: str,
        delivery_id: str,
        expected_packet_sha256: str,
    ) -> dict[str, str]:
        entry, artifact = self._verified(project, delivery_id)
        if entry["state"] not in {"PREPARED", "COPIED"}:
            raise ControlPlaneError("EXACT_DELIVERY_TERMINAL")
        if expected_packet_sha256 != entry["delivery_packet_sha256"]:
            raise ControlPlaneError("EXACT_DELIVERY_PACKET_CHANGED")
        exact_message = artifact.get("exact_message")
        if (
            not isinstance(exact_message, str)
            or hashlib.sha256(exact_message.encode("utf-8")).hexdigest()
            != entry["result_content_sha256"]
        ):
            raise ControlPlaneError("EXACT_DELIVERY_CONTENT_CHANGED")
        return {
            "delivery_id": delivery_id,
            "delivery_packet_sha256": entry["delivery_packet_sha256"],
            "result_content_sha256": entry["result_content_sha256"],
            "exact_message": exact_message,
        }

    def transition(
        self,
        project: str,
        delivery_id: str,
        action: str,
        expected_packet_sha256: str,
    ) -> dict[str, Any]:
        entry, _ = self._verified(project, delivery_id)
        action = str(action or "").upper()
        transitions = {
            ("PREPARED", "COPIED"): "COPIED",
            ("COPIED", "DELIVERED"): "DELIVERED",
            ("PREPARED", "CANCEL"): "CANCELLED",
            ("COPIED", "CANCEL"): "CANCELLED",
        }
        new_state = transitions.get((entry["state"], action))
        if new_state is None:
            raise ControlPlaneError("INVALID_EXACT_DELIVERY_TRANSITION")
        if expected_packet_sha256 != entry["delivery_packet_sha256"]:
            raise ControlPlaneError("EXACT_DELIVERY_PACKET_CHANGED")
        acted_at = _now()
        record_kind = {
            "COPIED": "copy",
            "DELIVERED": "receipt",
            "CANCELLED": "cancellation",
        }[new_state]
        record = {
            "record_version": "1",
            "delivery_id": delivery_id,
            "project": project,
            "action": new_state,
            "explicit_user_action": True,
            "delivery_packet_sha256": entry["delivery_packet_sha256"],
            "result_content_sha256": entry["result_content_sha256"],
            "destination_node_id": entry["destination_node_id"],
            "actual_mainline_send_count": 0,
            "acted_at": acted_at,
        }
        record_bytes = json.dumps(
            record, ensure_ascii=True, indent=2,
        ).encode("utf-8") + b"\n"
        record_hash = hashlib.sha256(record_bytes).hexdigest()
        record_path = self.directory / f"{delivery_id}-{record_kind}.json"
        with self._lock:
            ledger = self._ledger()
            current = ledger["deliveries"].get(delivery_id)
            if (
                not isinstance(current, dict)
                or current.get("state") != entry["state"]
                or current.get("delivery_packet_sha256") != expected_packet_sha256
                or record_path.exists()
            ):
                raise ControlPlaneError("DUPLICATE_EXACT_DELIVERY_BLOCKED")
            record_path.write_bytes(record_bytes)
            current.update({
                "state": new_state,
                f"{record_kind}_record_sha256": record_hash,
                "updated_at": acted_at,
            })
            self._write_ledger(ledger)
            return {"delivery_id": delivery_id, **current}

    def list_for_project(self, project: str) -> list[dict[str, Any]]:
        with self._lock:
            entries = self._ledger()["deliveries"]
        return [
            {"delivery_id": delivery_id, **entry}
            for delivery_id, entry in entries.items()
            if entry.get("project") == project
        ]
