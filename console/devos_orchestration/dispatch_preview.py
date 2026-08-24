from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Callable

from .codex_transport import CodexThreadBinding, CodexTransportError, CodexWorkspaceBinding
from .control_plane import ControlPlaneError, OrchestrationControlStore
from .workspace_guard import WorkspaceBindingSeal, WorkspaceGuardError, verify_workspace_binding


DISPATCH_STATES = {
    "PREPARED", "APPROVED", "DISPATCHABLE", "REJECTED",
    "SENT", "COMPLETED", "FAILED",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


class DispatchPreviewStore:
    def __init__(
        self,
        directory: Path,
        control: OrchestrationControlStore,
        *,
        workspace_verifier: Callable[[WorkspaceBindingSeal], WorkspaceBindingSeal] = verify_workspace_binding,
    ) -> None:
        self.directory = directory
        self.control = control
        self.workspace_verifier = workspace_verifier
        self.ledger_path = directory / "dispatch-ledger.json"
        self._lock = Lock()
        self.directory.mkdir(parents=True, exist_ok=True)

    def _ledger(self) -> dict[str, Any]:
        if not self.ledger_path.is_file():
            return {"schema_version": "1", "handoffs": {}}
        value = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        if value.get("schema_version") != "1" or not isinstance(value.get("handoffs"), dict):
            raise ControlPlaneError("INVALID_DISPATCH_LEDGER")
        return value

    def _write_ledger(self, value: dict[str, Any]) -> None:
        temporary = self.ledger_path.with_name(f".{self.ledger_path.name}.tmp")
        temporary.write_bytes(json.dumps(value, ensure_ascii=True, indent=2).encode("utf-8") + b"\n")
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, self.ledger_path)

    def _read_artifact(self, handoff_id: str, entry: dict[str, Any]) -> dict[str, Any]:
        path = self.directory / f"{handoff_id}.json"
        if not path.is_file():
            raise ControlPlaneError("DISPATCH_ENVELOPE_NOT_FOUND")
        artifact_bytes = path.read_bytes()
        if hashlib.sha256(artifact_bytes).hexdigest() != entry.get("artifact_sha256"):
            raise ControlPlaneError("DISPATCH_ENVELOPE_CHANGED")
        try:
            artifact = json.loads(artifact_bytes.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise ControlPlaneError("INVALID_DISPATCH_ENVELOPE") from error
        return artifact

    @staticmethod
    def _sealed_approval_binding(artifact: dict[str, Any]) -> dict[str, Any]:
        envelope = artifact.get("dispatch_envelope")
        if not isinstance(envelope, dict):
            raise ControlPlaneError("WORKSPACE_BOUND_ENVELOPE_REQUIRED")
        task_hash = hashlib.sha256(
            str(artifact.get("rendered_message", {}).get("message") or "").encode("utf-8"),
        ).hexdigest()
        payload_hash = hashlib.sha256(_canonical_bytes(artifact.get("rendered_message"))).hexdigest()
        envelope_hash = hashlib.sha256(_canonical_bytes(envelope)).hexdigest()
        if (
            task_hash != artifact.get("task_content_sha256")
            or task_hash != envelope.get("task_content_sha256")
            or payload_hash != artifact.get("payload_sha256")
            or payload_hash != envelope.get("payload_sha256")
            or envelope_hash != artifact.get("envelope_sha256")
        ):
            raise ControlPlaneError("DISPATCH_ENVELOPE_CHANGED")
        workspace = envelope.get("workspace")
        runtime_protocol = envelope.get("runtime_protocol")
        if not isinstance(workspace, dict) or not isinstance(runtime_protocol, dict):
            raise ControlPlaneError("INVALID_DISPATCH_ENVELOPE")
        runtime_hash = hashlib.sha256(_canonical_bytes(runtime_protocol)).hexdigest()
        if runtime_hash != envelope.get("runtime_protocol_sha256"):
            raise ControlPlaneError("DISPATCH_ENVELOPE_CHANGED")
        return {
            "dispatch_envelope_id": artifact["handoff_id"],
            "envelope_sha256": envelope_hash,
            "task_content_sha256": task_hash,
            "route": envelope.get("route"),
            "destination_node": envelope.get("destination_node"),
            "workspace_fingerprint_sha256": workspace.get("workspace_fingerprint_sha256"),
            "branch": workspace.get("branch"),
            "head": workspace.get("head"),
            "runtime_protocol_sha256": runtime_hash,
        }

    def _verify_approval_binding(
        self,
        project: str,
        artifact: dict[str, Any],
    ) -> dict[str, Any]:
        binding = self._sealed_approval_binding(artifact)
        envelope = artifact["dispatch_envelope"]
        route_id = str(envelope.get("route", {}).get("route_id") or "")
        current = self.control.resolve_route(project, route_id)
        expected_route = {
            "route_id": current["route"]["route_id"],
            "handoff_type": current["route"]["handoff_type"],
        }
        expected_source = {
            "node_id": current["source"]["node_id"],
            "role": current["source"]["role"],
            "transport_kind": current["source"]["transport_kind"],
        }
        expected_destination = {
            "node_id": current["destination"]["node_id"],
            "role": current["destination"]["role"],
            "transport_kind": current["destination"]["transport_kind"],
        }
        if (
            envelope.get("route") != expected_route
            or envelope.get("source_node") != expected_source
            or envelope.get("destination_node") != expected_destination
        ):
            raise ControlPlaneError("DISPATCH_APPROVAL_STALE")
        try:
            workspace_binding = CodexWorkspaceBinding.parse(current["destination"]["transport_ref"])
        except CodexTransportError as error:
            raise ControlPlaneError("DISPATCH_APPROVAL_STALE") from error
        expected_seal = WorkspaceBindingSeal(
            project=workspace_binding.project,
            windows_workspace=workspace_binding.windows_workspace,
            wsl_workspace=workspace_binding.wsl_workspace,
            runtime=workspace_binding.runtime,
            distro=workspace_binding.distro,
            workspace_identity_sha256=workspace_binding.workspace_identity_sha256,
            git_branch=workspace_binding.git_branch,
            git_head=workspace_binding.git_head,
            git_status_sha256=workspace_binding.git_status_sha256,
            git_status_entry_count=workspace_binding.git_status_entry_count,
        )
        try:
            verified = self.workspace_verifier(expected_seal)
        except WorkspaceGuardError as error:
            raise ControlPlaneError(str(error)) from error
        workspace_contract = envelope["workspace"]
        if verified != expected_seal or workspace_contract != {
            "binding_type": "WORKSPACE_ONLY",
            "windows_workspace": verified.windows_workspace,
            "wsl_workspace": verified.wsl_workspace,
            "workspace_identity_sha256": verified.workspace_identity_sha256,
            "branch": verified.git_branch,
            "head": verified.git_head,
            "workspace_fingerprint_sha256": verified.git_status_sha256,
            "workspace_status_entry_count": verified.git_status_entry_count,
        }:
            raise ControlPlaneError("WORKSPACE_CHANGED_EXTERNALLY")
        transport_status = self.control.transport_status(project, expected_destination["node_id"])
        current_runtime = {
            "runtime": verified.runtime,
            "distro": verified.distro,
            "protocol_version": transport_status.get("protocol_version") if transport_status else None,
            "protocol_schema_sha256": transport_status.get("protocol_schema_sha256") if transport_status else None,
        }
        if (
            not transport_status
            or transport_status.get("connection_status") != "DISCOVERED_LOCKED"
            or current_runtime != envelope.get("runtime_protocol")
        ):
            raise ControlPlaneError("DISPATCH_APPROVAL_STALE")
        return binding

    def decide(
        self,
        project: str,
        handoff_id: str,
        decision: str,
        expected_envelope_sha256: str,
    ) -> dict[str, Any]:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", handoff_id):
            raise ControlPlaneError("INVALID_HANDOFF_ID")
        decision = str(decision or "").upper()
        if decision not in {"APPROVE", "REJECT"}:
            raise ControlPlaneError("INVALID_DISPATCH_DECISION")
        with self._lock:
            ledger = self._ledger()
            entry = ledger["handoffs"].get(handoff_id)
            if entry is None:
                raise ControlPlaneError("HANDOFF_NOT_FOUND")
            if entry["state"] != "PREPARED":
                raise ControlPlaneError("DUPLICATE_OR_TERMINAL_DISPATCH_DECISION")
            artifact = self._read_artifact(handoff_id, entry)
        binding = self._sealed_approval_binding(artifact)
        if expected_envelope_sha256 != binding["envelope_sha256"]:
            raise ControlPlaneError("DISPATCH_APPROVAL_STALE")
        if decision == "APPROVE":
            binding = self._verify_approval_binding(project, artifact)
        decided_at = _now()
        record = {
            "schema_version": "1",
            "handoff_id": handoff_id,
            "project": project,
            "decision": "APPROVED" if decision == "APPROVE" else "REJECTED",
            "explicit_user_action": True,
            "binding": binding,
            "decided_at": decided_at,
        }
        record_bytes = json.dumps(record, ensure_ascii=True, indent=2).encode("utf-8") + b"\n"
        record_hash = hashlib.sha256(record_bytes).hexdigest()
        suffix = "approval" if decision == "APPROVE" else "rejection"
        record_path = self.directory / f"{handoff_id}-{suffix}.json"
        decision_paths = [
            self.directory / f"{handoff_id}-approval.json",
            self.directory / f"{handoff_id}-rejection.json",
        ]
        with self._lock:
            ledger = self._ledger()
            entry = ledger["handoffs"].get(handoff_id)
            if (
                entry is None
                or entry["state"] != "PREPARED"
                or any(path.exists() for path in decision_paths)
            ):
                raise ControlPlaneError("DUPLICATE_OR_TERMINAL_DISPATCH_DECISION")
            current_artifact = self._read_artifact(handoff_id, entry)
            if current_artifact != artifact:
                raise ControlPlaneError("DISPATCH_ENVELOPE_CHANGED")
            record_path.write_bytes(record_bytes)
            history = list(entry.get("state_history") or [{
                "state": "PREPARED", "at": entry["created_at"],
            }])
            if decision == "APPROVE":
                history.extend([
                    {"state": "APPROVED", "at": decided_at},
                    {"state": "DISPATCHABLE", "at": decided_at},
                ])
                entry.update({
                    "state": "DISPATCHABLE",
                    "approval_state": "APPROVED",
                    "dispatch_status": "DISPATCHABLE",
                    "approval_record_sha256": record_hash,
                    "approved_at": decided_at,
                })
            else:
                history.append({"state": "REJECTED", "at": decided_at})
                entry.update({
                    "state": "REJECTED",
                    "approval_state": "REJECTED",
                    "dispatch_status": "REJECTED",
                    "rejection_record_sha256": record_hash,
                    "rejected_at": decided_at,
                })
            entry.update({
                "state_history": history,
                "actual_send_locked": True,
                "updated_at": decided_at,
            })
            self._write_ledger(ledger)
            result = dict(entry)
        self.control.audit.write(
            "dispatch_decision",
            timestamp=decided_at,
            project=project,
            handoff_id=handoff_id,
            decision=record["decision"],
            envelope_sha256=binding["envelope_sha256"],
            record_sha256=record_hash,
            actual_send_count=0,
        )
        return result

    def validate_dispatchable(self, project: str, handoff_id: str) -> dict[str, Any]:
        with self._lock:
            ledger = self._ledger()
            entry = ledger["handoffs"].get(handoff_id)
            if entry is None:
                raise ControlPlaneError("HANDOFF_NOT_FOUND")
            if entry["state"] != "DISPATCHABLE" or entry.get("approval_state") != "APPROVED":
                raise ControlPlaneError("HANDOFF_NOT_DISPATCHABLE")
            artifact = self._read_artifact(handoff_id, entry)
            approval_path = self.directory / f"{handoff_id}-approval.json"
            if not approval_path.is_file():
                raise ControlPlaneError("DISPATCH_APPROVAL_RECORD_MISSING")
            approval_bytes = approval_path.read_bytes()
            if hashlib.sha256(approval_bytes).hexdigest() != entry.get("approval_record_sha256"):
                raise ControlPlaneError("DISPATCH_APPROVAL_CHANGED")
            try:
                approval = json.loads(approval_bytes.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError) as error:
                raise ControlPlaneError("DISPATCH_APPROVAL_CHANGED") from error
        current_binding = self._verify_approval_binding(project, artifact)
        if approval.get("binding") != current_binding:
            raise ControlPlaneError("DISPATCH_APPROVAL_STALE")
        return dict(entry)

    def artifact_for_dispatch(self, project: str, handoff_id: str) -> dict[str, Any]:
        """Return the immutable envelope after checking project ownership."""
        with self._lock:
            entry = self._ledger()["handoffs"].get(handoff_id)
            if entry is None:
                raise ControlPlaneError("HANDOFF_NOT_FOUND")
            if entry.get("project") != project:
                raise ControlPlaneError("HANDOFF_PROJECT_MISMATCH")
            return self._read_artifact(handoff_id, entry)

    def start_dispatch(self, project: str, handoff_id: str) -> dict[str, Any]:
        """Consume one approved envelope before any transport side effect."""
        validated = self.validate_dispatchable(project, handoff_id)
        started_at = _now()
        attempt = {
            "schema_version": "1",
            "handoff_id": handoff_id,
            "project": project,
            "status": "ATTEMPT_STARTED",
            "attempt_count": 1,
            "envelope_sha256": validated["envelope_sha256"],
            "task_content_sha256": validated["task_content_sha256"],
            "approval_record_sha256": validated["approval_record_sha256"],
            "started_at": started_at,
        }
        attempt_bytes = json.dumps(
            attempt, ensure_ascii=True, indent=2,
        ).encode("utf-8") + b"\n"
        attempt_hash = hashlib.sha256(attempt_bytes).hexdigest()
        attempt_path = self.directory / f"{handoff_id}-attempt.json"
        terminal_paths = [
            self.directory / f"{handoff_id}-result.json",
            self.directory / f"{handoff_id}-failure.json",
        ]
        with self._lock:
            ledger = self._ledger()
            entry = ledger["handoffs"].get(handoff_id)
            if (
                entry is None
                or entry["state"] != "DISPATCHABLE"
                or entry.get("approval_record_sha256") != validated["approval_record_sha256"]
                or attempt_path.exists()
                or any(path.exists() for path in terminal_paths)
            ):
                raise ControlPlaneError("DUPLICATE_HANDOFF_BLOCKED")
            current_artifact = self._read_artifact(handoff_id, entry)
            if current_artifact.get("envelope_sha256") != validated["envelope_sha256"]:
                raise ControlPlaneError("DISPATCH_ENVELOPE_CHANGED")
            attempt_path.write_bytes(attempt_bytes)
            history = list(entry.get("state_history") or [])
            history.append({"state": "SENT", "at": started_at})
            entry.update({
                "state": "SENT",
                "state_history": history,
                "dispatch_status": "SENDING",
                "actual_send_locked": True,
                "actual_send_count": 1,
                "attempt_artifact_sha256": attempt_hash,
                "attempt_started_at": started_at,
                "updated_at": started_at,
            })
            self._write_ledger(ledger)
            result = dict(entry)
        self.control.audit.write(
            "dispatch_attempt_started",
            timestamp=started_at,
            project=project,
            handoff_id=handoff_id,
            envelope_sha256=validated["envelope_sha256"],
            approval_record_sha256=validated["approval_record_sha256"],
            attempt_artifact_sha256=attempt_hash,
            actual_send_count=1,
        )
        return result

    def prepare_mainline_handoff(
        self,
        project: str,
        source_handoff: dict[str, Any],
        *,
        route_id: str = "BTEST_MAINLINE_API_TO_CODEX",
    ) -> dict[str, Any]:
        required = {
            "approval_manifest_sha256", "result_artifact_sha256", "result_sha256",
            "originating_user_input_sha256", "exact_message_sha256", "exact_message",
            "destination_node_id",
        }
        if set(source_handoff) != required:
            raise ControlPlaneError("INVALID_API_MAINLINE_HANDOFF")
        message = source_handoff["exact_message"]
        if (
            not isinstance(message, str)
            or not message.strip()
            or source_handoff["destination_node_id"] != "BTEST_CODEX_WORKER"
            or hashlib.sha256(message.encode("utf-8")).hexdigest()
            != source_handoff["exact_message_sha256"]
        ):
            raise ControlPlaneError("INVALID_API_MAINLINE_HANDOFF")
        hash_fields = required - {"exact_message", "destination_node_id"}
        if any(
            not isinstance(source_handoff[field], str)
            or not re.fullmatch(r"[0-9a-f]{64}", source_handoff[field])
            for field in hash_fields
        ):
            raise ControlPlaneError("INVALID_API_MAINLINE_HANDOFF")
        route = self.control.resolve_route(project, route_id)
        if (
            route["source"].get("role") != "MAINLINE"
            or route["source"].get("node_id") != "BTEST_MAINLINE_API"
            or route["destination"].get("node_id") != "BTEST_CODEX_WORKER"
        ):
            raise ControlPlaneError("INVALID_API_MAINLINE_ROUTE")
        handoff_id = f"api-mainline-{source_handoff['result_sha256'][:32]}"
        source_binding = {
            "source_type": "API_MAINLINE_PREPARED_HANDOFF",
            **{key: value for key, value in source_handoff.items() if key != "exact_message"},
        }
        return self.prepare(
            project,
            {"handoff_id": handoff_id, "route_id": route_id, "message": message},
            source_handoff=source_binding,
        )

    def prepare(
        self,
        project: str,
        payload: dict[str, Any],
        *,
        source_handoff: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        handoff_id = str(payload.get("handoff_id") or "").strip()
        route_id = str(payload.get("route_id") or "").strip()
        message = str(payload.get("message") or "")
        if (
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", handoff_id)
            or not route_id
            or not message.strip()
        ):
            raise ControlPlaneError("INVALID_DISPATCH_PREVIEW")
        if len(message.encode("utf-8")) > 128 * 1024:
            raise ControlPlaneError("DISPATCH_PREVIEW_TOO_LARGE")
        state = self.control.resolve_route(project, route_id)
        route = state["route"]
        destination = state["destination"]
        if destination["transport_kind"] != "CODEX_THREAD":
            raise ControlPlaneError("DESTINATION_NOT_CODEX_THREAD")
        thread_binding = None
        workspace_binding = None
        if destination["transport_ref"]:
            try:
                thread_binding = CodexThreadBinding.parse(destination["transport_ref"])
            except CodexTransportError:
                try:
                    workspace_binding = CodexWorkspaceBinding.parse(destination["transport_ref"])
                except CodexTransportError as error:
                    raise ControlPlaneError(str(error)) from error
        rendered = {
            "handoff_type": route["handoff_type"],
            "source_node_id": route["source_node_id"],
            "destination_node_id": route["destination_node_id"],
            "message": message,
        }
        task_content_hash = hashlib.sha256(message.encode("utf-8")).hexdigest()
        payload_hash = hashlib.sha256(_canonical_bytes(rendered)).hexdigest()
        dispatch_envelope = None
        envelope_hash = None
        destination_summary = {
            "node_id": destination["node_id"],
            "transport_kind": "CODEX_THREAD",
            "binding_status": "BOUND" if thread_binding or workspace_binding else "UNBOUND",
            "thread_binding_sha256": (
                hashlib.sha256(thread_binding.thread_id.encode("utf-8")).hexdigest()
                if thread_binding else None
            ),
            "workspace": thread_binding.workspace if thread_binding else None,
            "workspace_binding_type": "WORKSPACE_ONLY" if workspace_binding else None,
        }
        if workspace_binding is not None:
            expected = WorkspaceBindingSeal(
                project=workspace_binding.project,
                windows_workspace=workspace_binding.windows_workspace,
                wsl_workspace=workspace_binding.wsl_workspace,
                runtime=workspace_binding.runtime,
                distro=workspace_binding.distro,
                workspace_identity_sha256=workspace_binding.workspace_identity_sha256,
                git_branch=workspace_binding.git_branch,
                git_head=workspace_binding.git_head,
                git_status_sha256=workspace_binding.git_status_sha256,
                git_status_entry_count=workspace_binding.git_status_entry_count,
            )
            try:
                verified = self.workspace_verifier(expected)
            except WorkspaceGuardError as error:
                raise ControlPlaneError(str(error)) from error
            if verified != expected:
                raise ControlPlaneError("WORKSPACE_CHANGED_EXTERNALLY")
            transport_status = self.control.transport_status(project, destination["node_id"])
            if not transport_status or transport_status.get("connection_status") != "DISCOVERED_LOCKED":
                raise ControlPlaneError("CODEX_PROTOCOL_BINDING_REQUIRED")
            protocol_schema_hash = str(transport_status.get("protocol_schema_sha256") or "")
            if len(protocol_schema_hash) != 64 or any(char not in "0123456789abcdef" for char in protocol_schema_hash):
                raise ControlPlaneError("CODEX_PROTOCOL_BINDING_REQUIRED")
            runtime_contract = {
                "runtime": verified.runtime,
                "distro": verified.distro,
                "protocol_version": transport_status.get("protocol_version"),
                "protocol_schema_sha256": protocol_schema_hash,
            }
            runtime_protocol_hash = hashlib.sha256(_canonical_bytes(runtime_contract)).hexdigest()
            workspace_contract = {
                "binding_type": "WORKSPACE_ONLY",
                "windows_workspace": verified.windows_workspace,
                "wsl_workspace": verified.wsl_workspace,
                "workspace_identity_sha256": verified.workspace_identity_sha256,
                "branch": verified.git_branch,
                "head": verified.git_head,
                "workspace_fingerprint_sha256": verified.git_status_sha256,
                "workspace_status_entry_count": verified.git_status_entry_count,
            }
            dispatch_envelope = {
                "envelope_version": "1",
                "handoff_id": handoff_id,
                "project": project,
                "route": {
                    "route_id": route["route_id"],
                    "handoff_type": route["handoff_type"],
                },
                "source_node": {
                    "node_id": state["source"]["node_id"],
                    "role": state["source"]["role"],
                    "transport_kind": state["source"]["transport_kind"],
                },
                "destination_node": {
                    "node_id": destination["node_id"],
                    "role": destination["role"],
                    "transport_kind": destination["transport_kind"],
                },
                "workspace": workspace_contract,
                "runtime_protocol": runtime_contract,
                "runtime_protocol_sha256": runtime_protocol_hash,
                "task_content_sha256": task_content_hash,
                "payload_sha256": payload_hash,
            }
            if source_handoff is not None:
                dispatch_envelope["source_handoff"] = source_handoff
            envelope_hash = hashlib.sha256(_canonical_bytes(dispatch_envelope)).hexdigest()
            destination_summary.update({
                "workspace": verified.windows_workspace,
                "windows_workspace": verified.windows_workspace,
                "wsl_workspace": verified.wsl_workspace,
                "workspace_identity_sha256": verified.workspace_identity_sha256,
            })
        artifact = {
            "schema_version": "1",
            "handoff_id": handoff_id,
            "project": project,
            "route_id": route_id,
            "task_content_sha256": task_content_hash,
            "payload_sha256": payload_hash,
            "envelope_sha256": envelope_hash,
            "dispatch_envelope": dispatch_envelope,
            "source_handoff": source_handoff,
            "destination": destination_summary,
            "rendered_message": rendered,
            "state": "PREPARED",
            "actual_send_count": 0,
            "created_at": _now(),
        }
        artifact_bytes = json.dumps(artifact, ensure_ascii=True, indent=2).encode("utf-8") + b"\n"
        artifact_hash = hashlib.sha256(artifact_bytes).hexdigest()
        with self._lock:
            ledger = self._ledger()
            if handoff_id in ledger["handoffs"]:
                raise ControlPlaneError("DUPLICATE_HANDOFF_BLOCKED")
            artifact_path = self.directory / f"{handoff_id}.json"
            if artifact_path.exists():
                raise ControlPlaneError("DUPLICATE_HANDOFF_BLOCKED")
            artifact_path.write_bytes(artifact_bytes)
            ledger["handoffs"][handoff_id] = {
                "project": project,
                "state": "PREPARED",
                "approval_state": "USER_APPROVAL_REQUIRED",
                "dispatch_status": "PREPARED",
                "task_content_sha256": task_content_hash,
                "payload_sha256": payload_hash,
                "envelope_sha256": envelope_hash,
                "artifact_sha256": artifact_hash,
                "destination_node_id": destination["node_id"],
                "actual_send_count": 0,
                "actual_send_locked": True,
                "created_at": artifact["created_at"],
            }
            self._write_ledger(ledger)
        return {**artifact, "artifact_sha256": artifact_hash}

    def prepare_smoke(
        self,
        *,
        handoff_id: str,
        project: str,
        message: str,
    ) -> dict[str, Any]:
        rendered = {
            "handoff_type": "TRANSPORT_SMOKE",
            "source_node_id": "developer-os-smoke",
            "destination_node_id": "scratch-codex-thread",
            "message": message,
        }
        payload_hash = hashlib.sha256(_canonical_bytes(rendered)).hexdigest()
        artifact = {
            "schema_version": "1",
            "handoff_id": handoff_id,
            "project": project,
            "route_id": "phase2b1-codex-smoke",
            "payload_sha256": payload_hash,
            "destination": {
                "node_id": "scratch-codex-thread",
                "transport_kind": "CODEX_THREAD",
                "binding_status": "UNBOUND",
                "thread_binding_sha256": None,
                "workspace": None,
            },
            "rendered_message": rendered,
            "state": "PREPARED",
            "actual_send_count": 0,
            "created_at": _now(),
        }
        artifact_bytes = json.dumps(artifact, ensure_ascii=True, indent=2).encode("utf-8") + b"\n"
        artifact_hash = hashlib.sha256(artifact_bytes).hexdigest()
        with self._lock:
            ledger = self._ledger()
            if handoff_id in ledger["handoffs"]:
                raise ControlPlaneError("DUPLICATE_HANDOFF_BLOCKED")
            path = self.directory / f"{handoff_id}.json"
            if path.exists():
                raise ControlPlaneError("DUPLICATE_HANDOFF_BLOCKED")
            path.write_bytes(artifact_bytes)
            ledger["handoffs"][handoff_id] = {
                "state": "PREPARED",
                "project": project,
                "payload_sha256": payload_hash,
                "artifact_sha256": artifact_hash,
                "destination_node_id": "scratch-codex-thread",
                "actual_send_count": 0,
                "created_at": artifact["created_at"],
            }
            self._write_ledger(ledger)
        return {**artifact, "artifact_sha256": artifact_hash}

    def bind(self, handoff_id: str, binding: CodexThreadBinding) -> dict[str, Any]:
        binding_artifact = {
            "schema_version": "1",
            "handoff_id": handoff_id,
            "thread_binding_sha256": hashlib.sha256(binding.thread_id.encode("utf-8")).hexdigest(),
            "workspace": binding.workspace,
            "bound_at": _now(),
        }
        binding_bytes = json.dumps(binding_artifact, ensure_ascii=True, indent=2).encode("utf-8") + b"\n"
        binding_hash = hashlib.sha256(binding_bytes).hexdigest()
        with self._lock:
            ledger = self._ledger()
            entry = ledger["handoffs"].get(handoff_id)
            if entry is None:
                raise ControlPlaneError("HANDOFF_NOT_FOUND")
            if entry["state"] != "PREPARED" or entry.get("binding_artifact_sha256"):
                raise ControlPlaneError("HANDOFF_BINDING_CONFLICT")
            path = self.directory / f"{handoff_id}-binding.json"
            if path.exists():
                raise ControlPlaneError("HANDOFF_BINDING_CONFLICT")
            path.write_bytes(binding_bytes)
            entry.update({
                "binding_artifact_sha256": binding_hash,
                "thread_binding_sha256": binding_artifact["thread_binding_sha256"],
                "workspace": binding.workspace,
                "binding_status": "BOUND",
                "updated_at": binding_artifact["bound_at"],
            })
            self._write_ledger(ledger)
            return dict(entry)

    def transition(self, handoff_id: str, state: str) -> dict[str, Any]:
        if state not in DISPATCH_STATES - {"PREPARED"}:
            raise ControlPlaneError("INVALID_DISPATCH_STATE")
        with self._lock:
            ledger = self._ledger()
            entry = ledger["handoffs"].get(handoff_id)
            if entry is None:
                raise ControlPlaneError("HANDOFF_NOT_FOUND")
            allowed = {
                "PREPARED": {"SENT", "FAILED"},
                "APPROVED": set(),
                "DISPATCHABLE": set(),
                "REJECTED": set(),
                "SENT": {"COMPLETED", "FAILED"},
                "COMPLETED": set(),
                "FAILED": set(),
            }
            if state not in allowed[entry["state"]]:
                raise ControlPlaneError("INVALID_DISPATCH_TRANSITION")
            entry["state"] = state
            entry["updated_at"] = _now()
            if state == "SENT":
                entry["actual_send_count"] += 1
                if entry["actual_send_count"] != 1:
                    raise ControlPlaneError("DUPLICATE_HANDOFF_BLOCKED")
            self._write_ledger(ledger)
            return dict(entry)

    @staticmethod
    def _response_text(result: dict[str, Any]) -> str:
        items = result.get("turn", {}).get("items", [])
        if not isinstance(items, list):
            return ""
        values = [
            item.get("text", "")
            for item in items
            if isinstance(item, dict) and item.get("type") == "agentMessage"
        ]
        return "\n".join(value for value in values if isinstance(value, str)).strip()

    def record_completion(self, handoff_id: str, result: dict[str, Any]) -> dict[str, Any]:
        if result.get("status") != "completed":
            raise ControlPlaneError("HANDOFF_NOT_COMPLETED")
        response_text = self._response_text(result)
        capture = {
            "schema_version": "1",
            "handoff_id": handoff_id,
            "status": "COMPLETED",
            "event_count": len(result.get("events", [])),
            "response_text": response_text,
            "transport_result": result,
            "captured_at": _now(),
        }
        capture_bytes = json.dumps(capture, ensure_ascii=True, indent=2).encode("utf-8") + b"\n"
        capture_hash = hashlib.sha256(capture_bytes).hexdigest()
        with self._lock:
            ledger = self._ledger()
            entry = ledger["handoffs"].get(handoff_id)
            if entry is None:
                raise ControlPlaneError("HANDOFF_NOT_FOUND")
            if entry["state"] != "SENT":
                raise ControlPlaneError("INVALID_DISPATCH_TRANSITION")
            path = self.directory / f"{handoff_id}-result.json"
            if path.exists():
                raise ControlPlaneError("DUPLICATE_HANDOFF_BLOCKED")
            path.write_bytes(capture_bytes)
            entry.update({
                "state": "COMPLETED",
                "dispatch_status": "COMPLETED",
                "completion_received": True,
                "event_count": capture["event_count"],
                "response_text": response_text,
                "result_artifact_sha256": capture_hash,
                "updated_at": capture["captured_at"],
            })
            self._write_ledger(ledger)
            return dict(entry)

    def record_failure(
        self,
        handoff_id: str,
        error_code: str,
        safe_error_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        failure = {
            "schema_version": "1",
            "handoff_id": handoff_id,
            "status": "FAILED",
            "error_code": error_code,
            "safe_error_metadata": safe_error_metadata or {},
            "captured_at": _now(),
        }
        failure_bytes = json.dumps(failure, ensure_ascii=True, indent=2).encode("utf-8") + b"\n"
        failure_hash = hashlib.sha256(failure_bytes).hexdigest()
        with self._lock:
            ledger = self._ledger()
            entry = ledger["handoffs"].get(handoff_id)
            if entry is None:
                raise ControlPlaneError("HANDOFF_NOT_FOUND")
            if entry["state"] not in {"PREPARED", "DISPATCHABLE", "SENT"}:
                raise ControlPlaneError("INVALID_DISPATCH_TRANSITION")
            path = self.directory / f"{handoff_id}-failure.json"
            if path.exists():
                raise ControlPlaneError("DUPLICATE_HANDOFF_BLOCKED")
            path.write_bytes(failure_bytes)
            entry.update({
                "state": "FAILED",
                "dispatch_status": "FAILED",
                "error_code": error_code,
                "failure_artifact_sha256": failure_hash,
                "updated_at": failure["captured_at"],
            })
            self._write_ledger(ledger)
            return dict(entry)

    def list_for_project(self, project: str) -> list[dict[str, Any]]:
        with self._lock:
            entries = self._ledger()["handoffs"]
        result = []
        for handoff_id, entry in entries.items():
            path = self.directory / f"{handoff_id}.json"
            if path.is_file():
                artifact = json.loads(path.read_text(encoding="utf-8"))
                if artifact.get("project") == project or entry.get("project") == project:
                    envelope = artifact.get("dispatch_envelope") or {}
                    workspace = envelope.get("workspace") or {}
                    message = str(artifact.get("rendered_message", {}).get("message") or "")
                    display_state = entry.get("state")
                    workspace_guard = (
                        "VERIFIED_AT_APPROVAL"
                        if entry.get("approval_state") == "APPROVED"
                        else "VERIFIED_AT_PREPARE" if workspace else None
                    )
                    if entry.get("state") in {"PREPARED", "DISPATCHABLE"} and workspace:
                        expected = WorkspaceBindingSeal(
                            project=project,
                            windows_workspace=str(workspace.get("windows_workspace") or ""),
                            wsl_workspace=str(workspace.get("wsl_workspace") or ""),
                            runtime=str(envelope.get("runtime_protocol", {}).get("runtime") or ""),
                            distro=str(envelope.get("runtime_protocol", {}).get("distro") or ""),
                            workspace_identity_sha256=str(workspace.get("workspace_identity_sha256") or ""),
                            git_branch=str(workspace.get("branch") or ""),
                            git_head=str(workspace.get("head") or ""),
                            git_status_sha256=str(workspace.get("workspace_fingerprint_sha256") or ""),
                            git_status_entry_count=int(workspace.get("workspace_status_entry_count") or 0),
                        )
                        try:
                            if self.workspace_verifier(expected) != expected:
                                raise WorkspaceGuardError("WORKSPACE_CHANGED_EXTERNALLY")
                        except (WorkspaceGuardError, OSError, ValueError):
                            display_state = "STALE_PREPARED_HANDOFF"
                            workspace_guard = "WORKSPACE_CHANGED_EXTERNALLY"
                    result.append({
                        "handoff_id": handoff_id,
                        **entry,
                        "display_state": display_state,
                        "task_summary": message.splitlines()[0][:160] if message else "",
                        "task_message": message,
                        "source_node_id": envelope.get("source_node", {}).get("node_id"),
                        "route_id": envelope.get("route", {}).get("route_id"),
                        "workspace_fingerprint_sha256": workspace.get("workspace_fingerprint_sha256"),
                        "workspace_status_entry_count": workspace.get("workspace_status_entry_count"),
                        "duplicate_send_status": "CONSUMED" if entry.get("actual_send_count") else "UNUSED",
                        "workspace": workspace.get("windows_workspace"),
                        "wsl_workspace": workspace.get("wsl_workspace"),
                        "branch": workspace.get("branch"),
                        "head": workspace.get("head"),
                        "workspace_guard": workspace_guard,
                        "runtime_protocol_sha256": envelope.get("runtime_protocol_sha256"),
                        "actual_send_locked": True,
                        "approve_and_send_allowed": display_state == "PREPARED",
                    })
        return sorted(result, key=lambda item: item["created_at"], reverse=True)
