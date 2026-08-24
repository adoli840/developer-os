from __future__ import annotations

import copy
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Protocol

from .api_mainline import (
    API_MAINLINE_NODE_ID,
    MANAGED_API_MAINLINE_ROUTE_IDS,
    NATIVE_MAINLINE_NODE_ID,
    ApiMainlineError,
    api_mainline_output_schema,
    authority_node_id,
    audit_mainline_state,
    ensure_btest_api_mainline,
    public_mainline_state,
    sync_mainline_authority,
    validate_mainline_output,
    validate_mainline_state,
)


SCHEMA_VERSION = "1"
MODES = {"OFF", "SHADOW_REVIEW", "SEMI_AUTO"}
RESERVED_MODES = {"AUTO_SAFE_CONTINUE"}
STATUSES = {
    "DISABLED", "IDLE", "RUNNING", "WAITING_FOR_USER", "PAUSED",
    "BLOCKED", "STOPPED", "ERROR",
}
NODE_ROLES = {"MAINLINE", "FUTURE_DESIGN", "CODEX_WORKER", "REVIEWER", "USER"}
TRANSPORT_KINDS = {
    "CHATGPT_SESSION", "CODEX_THREAD", "OPENAI_RESPONSES",
    "USER_ASSISTED", "MOCK",
}
HANDOFF_TYPES = {"TASK", "REPORT", "REVIEW", "DECISION", "HANDOFF"}
IDENTIFIER = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")


class ControlPlaneError(ValueError):
    pass


@dataclass(frozen=True)
class TransportCapabilities:
    can_read: bool
    can_write: bool
    can_resume: bool
    capture_message: bool
    send_message: bool
    health: str
    status: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "can_read": self.can_read,
            "can_write": self.can_write,
            "can_resume": self.can_resume,
            "capture_message": self.capture_message,
            "send_message": self.send_message,
            "health": self.health,
            "status": self.status,
        }


class TransportAdapter(Protocol):
    @property
    def capabilities(self) -> TransportCapabilities: ...

    def capture_message(self, transport_ref: str) -> dict[str, Any]: ...

    def send_message(self, transport_ref: str, message: str) -> dict[str, Any]: ...


class DisabledTransportAdapter:
    def __init__(self, capabilities: TransportCapabilities) -> None:
        self._capabilities = capabilities

    @property
    def capabilities(self) -> TransportCapabilities:
        return self._capabilities

    def capture_message(self, transport_ref: str) -> dict[str, Any]:
        raise ControlPlaneError("TRANSPORT_CAPTURE_DISABLED")

    def send_message(self, transport_ref: str, message: str) -> dict[str, Any]:
        raise ControlPlaneError("TRANSPORT_SEND_DISABLED")


class MockTransportAdapter:
    def __init__(self) -> None:
        self.captured: list[dict[str, Any]] = []
        self.sent: list[dict[str, Any]] = []

    @property
    def capabilities(self) -> TransportCapabilities:
        return TransportCapabilities(True, True, True, True, True, "HEALTHY", "READY")

    def capture_message(self, transport_ref: str) -> dict[str, Any]:
        record = {"transport_ref": transport_ref, "operation": "capture", "network": False}
        self.captured.append(record)
        return copy.deepcopy(record)

    def send_message(self, transport_ref: str, message: str) -> dict[str, Any]:
        record = {
            "transport_ref": transport_ref,
            "operation": "send",
            "message": message,
            "network": False,
        }
        self.sent.append(record)
        return copy.deepcopy(record)


def transport_capabilities(kind: str) -> TransportCapabilities:
    values = {
        "CHATGPT_SESSION": TransportCapabilities(
            False, False, False, False, False, "DEGRADED", "REMOTE_READ_UNRELIABLE",
        ),
        "CODEX_THREAD": TransportCapabilities(
            False, False, False, False, False, "LOCKED", "AUTO_SEND_DISABLED",
        ),
        "OPENAI_RESPONSES": TransportCapabilities(
            False, False, False, False, False, "LOCKED", "LIVE_REVIEW_DISABLED",
        ),
        "USER_ASSISTED": TransportCapabilities(
            False, False, False, True, False, "AVAILABLE", "EXACT_CAPTURE_ONLY",
        ),
        "MOCK": MockTransportAdapter().capabilities,
    }
    try:
        return values[kind]
    except KeyError as error:
        raise ControlPlaneError("INVALID_TRANSPORT_KIND") from error


def transport_adapter(kind: str) -> TransportAdapter:
    if kind == "MOCK":
        return MockTransportAdapter()
    return DisabledTransportAdapter(transport_capabilities(kind))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _identifier(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not IDENTIFIER.fullmatch(text):
        raise ControlPlaneError(f"INVALID_{label.upper()}")
    return text


def _string_list(value: Any, label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ControlPlaneError(f"INVALID_{label.upper()}")
    result = [_identifier(item, label) for item in value]
    if len(result) != len(set(result)):
        raise ControlPlaneError(f"DUPLICATE_{label.upper()}")
    return result


def _default_project(project: str) -> dict[str, Any]:
    state = {
        "project": project,
        "orchestration_enabled": False,
        "mode": "OFF",
        "status": "DISABLED",
        "nodes": [],
        "routes": [],
        "current_cycle": None,
        "waiting_reason": None,
        "last_gate": None,
        "mainline_state": None,
        "updated_at": _now(),
    }
    if project == "btest":
        ensure_btest_api_mainline(state)
    return state


def _validate_node(node: dict[str, Any]) -> None:
    required = {
        "node_id", "display_name", "role", "transport_kind", "transport_ref",
        "enabled", "allowed_sources", "allowed_destinations",
    }
    if set(node) != required:
        raise ControlPlaneError("INVALID_NODE_SHAPE")
    _identifier(node["node_id"], "node_id")
    if (
        not isinstance(node["display_name"], str)
        or not node["display_name"].strip()
        or len(node["display_name"]) > 80
    ):
        raise ControlPlaneError("INVALID_NODE_DISPLAY_NAME")
    if node["role"] not in NODE_ROLES:
        raise ControlPlaneError("INVALID_NODE_ROLE")
    if node["transport_kind"] not in TRANSPORT_KINDS:
        raise ControlPlaneError("INVALID_TRANSPORT_KIND")
    if not isinstance(node["transport_ref"], str) or len(node["transport_ref"]) > 2048:
        raise ControlPlaneError("INVALID_TRANSPORT_REF")
    if not isinstance(node["enabled"], bool):
        raise ControlPlaneError("INVALID_NODE_ENABLED")
    _string_list(node["allowed_sources"], "allowed_sources")
    _string_list(node["allowed_destinations"], "allowed_destinations")


def _validate_project(state: dict[str, Any]) -> None:
    required = {
        "project", "orchestration_enabled", "mode", "status", "nodes", "routes",
        "current_cycle", "waiting_reason", "last_gate", "updated_at",
        "mainline_state",
    }
    if set(state) != required:
        raise ControlPlaneError("INVALID_PROJECT_ORCHESTRATION_SHAPE")
    if state["mode"] not in MODES or state["status"] not in STATUSES:
        raise ControlPlaneError("INVALID_MODE_OR_STATUS")
    if state["mode"] == "OFF" and (
        state["orchestration_enabled"] or state["status"] != "DISABLED"
    ):
        raise ControlPlaneError("OFF_MODE_CONFLICT")
    if not isinstance(state["nodes"], list) or not isinstance(state["routes"], list):
        raise ControlPlaneError("INVALID_GRAPH")
    try:
        validate_mainline_state(state)
    except ApiMainlineError as error:
        raise ControlPlaneError(str(error)) from error
    node_ids: set[str] = set()
    nodes: dict[str, dict[str, Any]] = {}
    for node in state["nodes"]:
        _validate_node(node)
        if node["node_id"] in node_ids:
            raise ControlPlaneError("DUPLICATE_NODE_ID")
        node_ids.add(node["node_id"])
        nodes[node["node_id"]] = node
    route_ids: set[str] = set()
    for route in state["routes"]:
        if set(route) != {
            "route_id", "source_node_id", "destination_node_id", "enabled", "handoff_type",
        }:
            raise ControlPlaneError("INVALID_ROUTE_SHAPE")
        route_id = _identifier(route["route_id"], "route_id")
        if route_id in route_ids:
            raise ControlPlaneError("DUPLICATE_ROUTE_ID")
        route_ids.add(route_id)
        source_id = route["source_node_id"]
        destination_id = route["destination_node_id"]
        if source_id not in nodes or destination_id not in nodes:
            raise ControlPlaneError("ROUTE_NODE_NOT_FOUND")
        if source_id == destination_id:
            raise ControlPlaneError("SELF_ROUTE_FORBIDDEN")
        if route["handoff_type"] not in HANDOFF_TYPES or not isinstance(route["enabled"], bool):
            raise ControlPlaneError("INVALID_ROUTE")
        if route["enabled"]:
            source = nodes[source_id]
            destination = nodes[destination_id]
            if not source["enabled"] or not destination["enabled"]:
                raise ControlPlaneError("DISABLED_NODE_ROUTE_FORBIDDEN")
            if source["allowed_destinations"] and destination_id not in source["allowed_destinations"]:
                raise ControlPlaneError("DESTINATION_NOT_ALLOWED")
            if destination["allowed_sources"] and source_id not in destination["allowed_sources"]:
                raise ControlPlaneError("SOURCE_NOT_ALLOWED")


def _public_state(
    state: dict[str, Any],
    capability_provider: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    bootstrap_candidate_provider: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    value = copy.deepcopy(state)
    bootstrap_candidate = (
        bootstrap_candidate_provider(state["project"])
        if bootstrap_candidate_provider is not None and state["project"] == "btest"
        else None
    )
    value["mainline_state"] = public_mainline_state(
        state["mainline_state"], bootstrap_candidate,
    )
    for index, node in enumerate(value["nodes"]):
        private_node = state["nodes"][index]
        node["transport_configured"] = bool(node.pop("transport_ref"))
        node["capabilities"] = transport_capabilities(node["transport_kind"]).as_dict()
        if node["transport_kind"] == "CODEX_THREAD" and capability_provider is not None:
            node["codex_transport"] = capability_provider(private_node)
        if node["role"] == "MAINLINE" and state["mainline_state"] is not None:
            node["authority_status"] = (
                "ACTIVE"
                if node["node_id"] == authority_node_id(state["mainline_state"]["authority"])
                else "INACTIVE"
            )
    return value


def _audit_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "orchestration_enabled": state["orchestration_enabled"],
        "mode": state["mode"],
        "status": state["status"],
        "nodes": [
            {
                "node_id": node["node_id"],
                "role": node["role"],
                "transport_kind": node["transport_kind"],
                "enabled": node["enabled"],
                "allowed_sources": node["allowed_sources"],
                "allowed_destinations": node["allowed_destinations"],
            }
            for node in state["nodes"]
        ],
        "routes": copy.deepcopy(state["routes"]),
        "current_cycle": state["current_cycle"],
        "waiting_reason": state["waiting_reason"],
        "last_gate": state["last_gate"],
        "mainline": audit_mainline_state(state["mainline_state"]),
    }


class OrchestrationControlStore:
    def __init__(
        self,
        path: Path,
        projects: list[str] | tuple[str, ...],
        audit: Any,
        capability_provider: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        bootstrap_candidate_provider: Callable[[str], dict[str, Any]] | None = None,
    ) -> None:
        self.path = path
        self.projects = tuple(projects)
        self.audit = audit
        self.capability_provider = capability_provider
        self.bootstrap_candidate_provider = bootstrap_candidate_provider
        self._lock = Lock()
        if len(self.projects) != len(set(self.projects)):
            raise ControlPlaneError("INVALID_PROJECT_REGISTRY")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {
                "schema_version": SCHEMA_VERSION,
                "projects": {project: _default_project(project) for project in self.projects},
            }
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
            raise ControlPlaneError("INVALID_CONTROL_PLANE_STATE")
        states = value.get("projects")
        if not isinstance(states, dict):
            raise ControlPlaneError("INVALID_CONTROL_PLANE_STATE")
        for project in self.projects:
            states.setdefault(project, _default_project(project))
        if set(states) != set(self.projects):
            raise ControlPlaneError("UNKNOWN_PROJECT_STATE")
        for state in states.values():
            state.setdefault("mainline_state", None)
            if state.get("project") == "btest":
                try:
                    ensure_btest_api_mainline(state)
                except ApiMainlineError as error:
                    raise ControlPlaneError(str(error)) from error
            _validate_project(state)
        return value

    def _write(self, value: dict[str, Any]) -> None:
        payload = json.dumps(value, ensure_ascii=True, indent=2) + "\n"
        temporary = self.path.with_name(f".{self.path.name}.tmp")
        temporary.write_text(payload, encoding="utf-8", newline="\n")
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, self.path)

    def _project(self, value: dict[str, Any], project: str) -> dict[str, Any]:
        if project not in self.projects:
            raise ControlPlaneError("UNKNOWN_PROJECT")
        return value["projects"][project]

    def _change(self, project: str, action_type: str, mutate: Any) -> dict[str, Any]:
        with self._lock:
            value = self._load()
            state = self._project(value, project)
            old_state = _audit_state(state)
            mutate(state)
            state["updated_at"] = _now()
            _validate_project(state)
            self._write(value)
            new_state = _audit_state(state)
        self.audit.write(
            "orchestration_change",
            timestamp=_now(),
            project=project,
            action_type=action_type,
            old_state=old_state,
            new_state=new_state,
        )
        return _public_state(
            state, self.capability_provider, self.bootstrap_candidate_provider,
        )

    def list_projects(self) -> dict[str, Any]:
        with self._lock:
            value = self._load()
        return {
            "schema_version": SCHEMA_VERSION,
            "selectable_modes": ["OFF", "SHADOW_REVIEW", "SEMI_AUTO"],
            "reserved_modes": [{
                "mode": "AUTO_SAFE_CONTINUE",
                "status": "PILOT_LOCKED_CAP_APPROVAL_REQUIRED",
                "selectable": False,
                "max_auto_cycles": 2,
                "background_execution": False,
            }],
            "background_execution": False,
            "dispatch_enabled": False,
            "api_mainline_network_enabled": False,
            "api_mainline_output_contract": {
                "version": "1",
                "schema": api_mainline_output_schema(),
            },
            "phase_1_contracts": [
                "SESSION_HANDOFF",
                "USER_ASSISTED_EXACT_CAPTURE",
                "GATE_CONTRACT_V2",
                "TASK_ALIGNMENT_2_2",
                "EVIDENCE_SUFFICIENCY",
                "IMMUTABLE_RUN_ARTIFACTS",
            ],
            "projects": [
                _public_state(
                    value["projects"][project], self.capability_provider,
                    self.bootstrap_candidate_provider,
                )
                for project in self.projects
            ],
        }

    def api_mainline_return_context(self, project: str) -> dict[str, Any]:
        """Return private continuation state without exposing provider IDs publicly."""
        with self._lock:
            value = self._load()
            state = self._project(value, project)
            mainline = state.get("mainline_state")
            if (
                project != "btest"
                or not state.get("orchestration_enabled")
                or mainline is None
                or mainline.get("authority") != API_MAINLINE_NODE_ID
            ):
                raise ControlPlaneError("API_MAINLINE_AUTHORITY_REQUIRED")
            conversation = mainline["openai_conversation_state"]
            if (
                conversation.get("status") != "INITIALIZED"
                or not conversation.get("previous_response_id")
            ):
                raise ControlPlaneError("API_MAINLINE_CONVERSATION_NOT_INITIALIZED")
            return {
                "canonical_state": copy.deepcopy(mainline["canonical_state"]),
                "previous_response_id": conversation["previous_response_id"],
                "conversation_status": conversation["status"],
            }

    def resolve_route(self, project: str, route_id: str) -> dict[str, Any]:
        with self._lock:
            value = self._load()
            state = self._project(value, project)
            route = next((item for item in state["routes"] if item["route_id"] == route_id), None)
            if route is None:
                raise ControlPlaneError("ROUTE_NOT_FOUND")
            if not route["enabled"]:
                raise ControlPlaneError("ROUTE_DISABLED")
            nodes = {node["node_id"]: node for node in state["nodes"]}
            source = nodes[route["source_node_id"]]
            destination = nodes[route["destination_node_id"]]
            if not source["enabled"] or not destination["enabled"]:
                raise ControlPlaneError("DISABLED_NODE_ROUTE_FORBIDDEN")
            mainline = state["mainline_state"]
            if mainline is not None:
                authority = authority_node_id(mainline["authority"])
                for node in (source, destination):
                    if node["role"] == "MAINLINE" and node["node_id"] != authority:
                        raise ControlPlaneError("INACTIVE_MAINLINE_AUTHORITY")
            return {
                "route": copy.deepcopy(route),
                "source": copy.deepcopy(source),
                "destination": copy.deepcopy(destination),
            }

    def transport_status(self, project: str, node_id: str) -> dict[str, Any] | None:
        with self._lock:
            value = self._load()
            state = self._project(value, project)
            node = next((item for item in state["nodes"] if item["node_id"] == node_id), None)
            if node is None:
                raise ControlPlaneError("NODE_NOT_FOUND")
            provider = self.capability_provider
            private_node = copy.deepcopy(node)
        if provider is None:
            return None
        return copy.deepcopy(provider(private_node))

    def set_mode(self, project: str, mode: str) -> dict[str, Any]:
        if mode in RESERVED_MODES:
            raise ControlPlaneError("AUTO_SAFE_CONTINUE_LOCKED")
        if mode not in MODES:
            raise ControlPlaneError("INVALID_MODE")

        def mutate(state: dict[str, Any]) -> None:
            state["mode"] = mode
            state["orchestration_enabled"] = mode != "OFF"
            state["status"] = "IDLE" if mode != "OFF" else "DISABLED"
            state["waiting_reason"] = None
            sync_mainline_authority(state)

        return self._change(project, "MODE_CHANGED", mutate)

    def control(self, project: str, action: str) -> dict[str, Any]:
        action = str(action or "").upper()

        def mutate(state: dict[str, Any]) -> None:
            if action == "ENABLE":
                if state["mode"] == "OFF":
                    state["mode"] = "SHADOW_REVIEW"
                state["orchestration_enabled"] = True
                state["status"] = "IDLE"
                state["waiting_reason"] = None
            elif action == "PAUSE":
                if not state["orchestration_enabled"] or state["status"] in {"DISABLED", "STOPPED"}:
                    raise ControlPlaneError("PAUSE_NOT_ALLOWED")
                state["status"] = "PAUSED"
                state["waiting_reason"] = "Paused by user"
            elif action == "RESUME":
                if state["status"] != "PAUSED":
                    raise ControlPlaneError("RESUME_NOT_ALLOWED")
                state["orchestration_enabled"] = True
                state["status"] = "IDLE"
                state["waiting_reason"] = None
            elif action == "STOP":
                if state["mode"] == "OFF" or state["status"] == "DISABLED":
                    raise ControlPlaneError("STOP_NOT_ALLOWED")
                state["orchestration_enabled"] = False
                state["status"] = "STOPPED"
                state["waiting_reason"] = "Stopped by user"
            else:
                raise ControlPlaneError("INVALID_CONTROL_ACTION")
            sync_mainline_authority(state)

        return self._change(project, action, mutate)

    def add_node(self, project: str, node: dict[str, Any]) -> dict[str, Any]:
        value = {
            "node_id": _identifier(node.get("node_id"), "node_id"),
            "display_name": str(node.get("display_name") or "").strip(),
            "role": str(node.get("role") or ""),
            "transport_kind": str(node.get("transport_kind") or ""),
            "transport_ref": str(node.get("transport_ref") or ""),
            "enabled": node.get("enabled", True),
            "allowed_sources": _string_list(node.get("allowed_sources"), "allowed_sources"),
            "allowed_destinations": _string_list(node.get("allowed_destinations"), "allowed_destinations"),
        }
        _validate_node(value)

        def mutate(state: dict[str, Any]) -> None:
            if any(item["node_id"] == value["node_id"] for item in state["nodes"]):
                raise ControlPlaneError("DUPLICATE_NODE_ID")
            state["nodes"].append(copy.deepcopy(value))

        return self._change(project, "NODE_ADDED", mutate)

    def update_node(self, project: str, node_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        node_id = _identifier(node_id, "node_id")
        if project == "btest" and node_id == API_MAINLINE_NODE_ID:
            raise ControlPlaneError("MANAGED_API_MAINLINE_NODE")
        allowed = {
            "display_name", "role", "transport_kind", "transport_ref", "enabled",
            "allowed_sources", "allowed_destinations",
        }
        if not changes or not set(changes).issubset(allowed):
            raise ControlPlaneError("INVALID_NODE_UPDATE")

        def mutate(state: dict[str, Any]) -> None:
            node = next((item for item in state["nodes"] if item["node_id"] == node_id), None)
            if node is None:
                raise ControlPlaneError("NODE_NOT_FOUND")
            for key, value in changes.items():
                if key in {"allowed_sources", "allowed_destinations"}:
                    node[key] = _string_list(value, key)
                elif key == "enabled":
                    if not isinstance(value, bool):
                        raise ControlPlaneError("INVALID_NODE_ENABLED")
                    node[key] = value
                else:
                    node[key] = str(value or "").strip()
            _validate_node(node)

        return self._change(project, "NODE_UPDATED", mutate)

    def delete_node(self, project: str, node_id: str) -> dict[str, Any]:
        node_id = _identifier(node_id, "node_id")
        if project == "btest" and node_id in {API_MAINLINE_NODE_ID, NATIVE_MAINLINE_NODE_ID}:
            raise ControlPlaneError("MANAGED_API_MAINLINE_NODE")

        def mutate(state: dict[str, Any]) -> None:
            if any(
                route["source_node_id"] == node_id or route["destination_node_id"] == node_id
                for route in state["routes"]
            ):
                raise ControlPlaneError("NODE_HAS_ROUTES")
            before = len(state["nodes"])
            state["nodes"] = [item for item in state["nodes"] if item["node_id"] != node_id]
            if len(state["nodes"]) == before:
                raise ControlPlaneError("NODE_NOT_FOUND")

        return self._change(project, "NODE_DELETED", mutate)

    def add_route(self, project: str, route: dict[str, Any]) -> dict[str, Any]:
        value = {
            "route_id": _identifier(route.get("route_id"), "route_id"),
            "source_node_id": _identifier(route.get("source_node_id"), "source_node_id"),
            "destination_node_id": _identifier(route.get("destination_node_id"), "destination_node_id"),
            "enabled": route.get("enabled", True),
            "handoff_type": str(route.get("handoff_type") or "HANDOFF"),
        }

        def mutate(state: dict[str, Any]) -> None:
            if any(item["route_id"] == value["route_id"] for item in state["routes"]):
                raise ControlPlaneError("DUPLICATE_ROUTE_ID")
            state["routes"].append(copy.deepcopy(value))

        return self._change(project, "ROUTE_ADDED", mutate)

    def update_route(self, project: str, route_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        route_id = _identifier(route_id, "route_id")
        if project == "btest" and route_id in MANAGED_API_MAINLINE_ROUTE_IDS:
            raise ControlPlaneError("MANAGED_API_MAINLINE_ROUTE")
        allowed = {"source_node_id", "destination_node_id", "enabled", "handoff_type"}
        if not changes or not set(changes).issubset(allowed):
            raise ControlPlaneError("INVALID_ROUTE_UPDATE")

        def mutate(state: dict[str, Any]) -> None:
            route = next((item for item in state["routes"] if item["route_id"] == route_id), None)
            if route is None:
                raise ControlPlaneError("ROUTE_NOT_FOUND")
            for key, value in changes.items():
                if key == "enabled":
                    if not isinstance(value, bool):
                        raise ControlPlaneError("INVALID_ROUTE_ENABLED")
                    route[key] = value
                elif key == "handoff_type":
                    route[key] = str(value or "")
                else:
                    route[key] = _identifier(value, key)

        return self._change(project, "ROUTE_UPDATED", mutate)

    def delete_route(self, project: str, route_id: str) -> dict[str, Any]:
        route_id = _identifier(route_id, "route_id")
        if project == "btest" and route_id in MANAGED_API_MAINLINE_ROUTE_IDS:
            raise ControlPlaneError("MANAGED_API_MAINLINE_ROUTE")

        def mutate(state: dict[str, Any]) -> None:
            before = len(state["routes"])
            state["routes"] = [item for item in state["routes"] if item["route_id"] != route_id]
            if len(state["routes"]) == before:
                raise ControlPlaneError("ROUTE_NOT_FOUND")

        return self._change(project, "ROUTE_DELETED", mutate)

    def record_mainline_output(
        self,
        project: str,
        source_node_id: str,
        output: dict[str, Any],
    ) -> dict[str, Any]:
        source_node_id = _identifier(source_node_id, "source_node_id")

        def mutate(state: dict[str, Any]) -> None:
            try:
                validated = validate_mainline_output(state, source_node_id, output)
            except ApiMainlineError as error:
                raise ControlPlaneError(str(error)) from error
            canonical = state["mainline_state"]["canonical_state"]
            action = validated["action"]
            canonical["routing"] = {
                "latest_action": action,
                "current_destination": validated["destination_node_id"],
            }
            if action in {"USER_REQUIRED", "BLOCKED", "STOP"}:
                canonical["current_gate"] = action

        return self._change(project, "MAINLINE_ROUTING_RECORDED", mutate)

    def record_dispatch_user_required(self, project: str, handoff_id: str) -> dict[str, Any]:
        handoff_id = str(handoff_id or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", handoff_id):
            raise ControlPlaneError("INVALID_HANDOFF_ID")

        def mutate(state: dict[str, Any]) -> None:
            state["status"] = "WAITING_FOR_USER"
            state["current_cycle"] = handoff_id
            state["last_gate"] = "USER_REQUIRED"
            state["waiting_reason"] = "Codex approval or input is required"

        return self._change(project, "CODEX_DISPATCH_USER_REQUIRED", mutate)

    def apply_api_mainline_turn(
        self,
        project: str,
        output: dict[str, Any],
        *,
        response_id: str,
        model: str,
        user_input_sha256: str,
        result_sha256: str,
        return_id: str | None = None,
    ) -> dict[str, Any]:
        """Apply only the validated API Mainline delta and safe linkage metadata."""

        def mutate(state: dict[str, Any]) -> None:
            mainline = state.get("mainline_state")
            if (
                project != "btest"
                or not state.get("orchestration_enabled")
                or mainline is None
                or mainline.get("authority") != API_MAINLINE_NODE_ID
            ):
                raise ControlPlaneError("API_MAINLINE_AUTHORITY_REQUIRED")
            canonical = mainline["canonical_state"]
            delta = output["updated_state_delta"]
            if delta["current_purpose"] is not None:
                canonical["current_purpose"] = delta["current_purpose"]
            for target, source in (
                ("scope", "scope_append"),
                ("user_decisions", "user_decisions_append"),
            ):
                canonical[target] = list(dict.fromkeys(canonical[target] + delta[source]))
            canonical["current_gate"] = delta["current_gate"]
            if delta["latest_relevant_handoff"] is not None:
                canonical["latest_relevant_handoff"] = delta["latest_relevant_handoff"]
            canonical["routing"] = {
                "latest_action": output["action"],
                "current_destination": output["destination"],
            }
            conversation = mainline["openai_conversation_state"]
            conversation["conversation_id"] = conversation["conversation_id"] or response_id
            conversation["previous_response_id"] = response_id
            conversation["model_interaction_history"].append({
                "response_id": response_id,
                "model": model,
                "user_input_sha256": user_input_sha256,
                "result_sha256": result_sha256,
            })
            conversation["status"] = "INITIALIZED"

            if return_id is not None:
                state["current_cycle"] = return_id
                state["last_gate"] = output["gate"]
                action = output["action"]
                if action == "BLOCKED":
                    state["status"] = "BLOCKED"
                    state["waiting_reason"] = "API Mainline reported an exact blocker"
                elif action == "STOP":
                    state["status"] = "STOPPED"
                    state["waiting_reason"] = "API Mainline stopped the cycle"
                elif action == "USER_REQUIRED":
                    state["status"] = "WAITING_FOR_USER"
                    state["waiting_reason"] = "API Mainline user decision required"
                elif action == "HANDOFF_CODEX":
                    state["status"] = "WAITING_FOR_USER"
                    state["waiting_reason"] = "Prepared Codex handoff requires approval"
                elif action == "CONTINUE_USER_DIALOGUE":
                    state["status"] = "WAITING_FOR_USER"
                    state["waiting_reason"] = "API Mainline is waiting for user dialogue"
                else:
                    raise ControlPlaneError("INVALID_API_MAINLINE_RETURN_ACTION")

        return self._change(project, "API_MAINLINE_TURN_APPLIED", mutate)
