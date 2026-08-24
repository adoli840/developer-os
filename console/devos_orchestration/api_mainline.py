from __future__ import annotations

import copy
from typing import Any


API_MAINLINE_NODE_ID = "BTEST_MAINLINE_API"
NATIVE_MAINLINE_NODE_ID = "BTEST_MAINLINE"
NATIVE_MAINLINE_AUTHORITY = "NATIVE_MAINLINE"
MAINLINE_AUTHORITIES = {NATIVE_MAINLINE_AUTHORITY, API_MAINLINE_NODE_ID}
MAINLINE_ROUTING_ACTIONS = {
    "HANDOFF_CODEX",
    "USER_REQUIRED",
    "CONTINUE_USER_DIALOGUE",
    "BLOCKED",
    "STOP",
}
API_MAINLINE_CAPABILITIES = {
    "READ": "LOCKED_LIVE_API_OFF",
    "WRITE": "LOCKED_LIVE_API_OFF",
    "RESUME": "LOCKED_LIVE_API_OFF",
}
MANAGED_API_MAINLINE_ROUTE_IDS = {
    "BTEST_MAINLINE_API_TO_CODEX",
    "BTEST_CODEX_TO_MAINLINE_API",
}


class ApiMainlineError(ValueError):
    pass


def default_mainline_state() -> dict[str, Any]:
    return {
        "authority": NATIVE_MAINLINE_AUTHORITY,
        "canonical_state": {
            "current_purpose": None,
            "frozen_decisions": [],
            "scope": [],
            "authority": NATIVE_MAINLINE_AUTHORITY,
            "routing": {"latest_action": None, "current_destination": None},
            "user_decisions": [],
            "current_gate": None,
            "latest_relevant_handoff": None,
        },
        "openai_conversation_state": {
            "conversation_id": None,
            "previous_response_id": None,
            "model_interaction_history": [],
            "status": "NOT_INITIALIZED",
        },
    }


def api_mainline_node() -> dict[str, Any]:
    return {
        "node_id": API_MAINLINE_NODE_ID,
        "display_name": "bTest API Mainline",
        "role": "MAINLINE",
        "transport_kind": "OPENAI_RESPONSES",
        "transport_ref": "",
        "enabled": True,
        "allowed_sources": ["BTEST_CODEX_WORKER"],
        "allowed_destinations": ["BTEST_CODEX_WORKER"],
    }


def native_mainline_node() -> dict[str, Any]:
    return {
        "node_id": NATIVE_MAINLINE_NODE_ID,
        "display_name": "bTest Native Mainline",
        "role": "MAINLINE",
        "transport_kind": "CHATGPT_SESSION",
        "transport_ref": "",
        "enabled": True,
        "allowed_sources": ["BTEST_CODEX_WORKER"],
        "allowed_destinations": ["BTEST_CODEX_WORKER"],
    }


def ensure_btest_api_mainline(state: dict[str, Any]) -> None:
    if "mainline_state" not in state or state["mainline_state"] is None:
        state["mainline_state"] = default_mainline_state()

    nodes = state.setdefault("nodes", [])
    native_node = next((node for node in nodes if node.get("node_id") == NATIVE_MAINLINE_NODE_ID), None)
    if native_node is None:
        nodes.append(native_mainline_node())
    elif native_node.get("role") != "MAINLINE":
        raise ApiMainlineError("NATIVE_MAINLINE_NODE_CONFLICT")
    api_node = next((node for node in nodes if node.get("node_id") == API_MAINLINE_NODE_ID), None)
    if api_node is None:
        nodes.append(api_mainline_node())
    elif api_node.get("role") != "MAINLINE" or api_node.get("transport_kind") != "OPENAI_RESPONSES":
        raise ApiMainlineError("API_MAINLINE_NODE_CONFLICT")

    worker = next((node for node in nodes if node.get("node_id") == "BTEST_CODEX_WORKER"), None)
    if worker is not None:
        for field in ("allowed_sources", "allowed_destinations"):
            values = worker.setdefault(field, [])
            # An empty allowlist means unrestricted. Preserve that semantic
            # instead of turning a test or custom worker into API-only routing.
            if values and API_MAINLINE_NODE_ID not in values:
                values.append(API_MAINLINE_NODE_ID)
        _ensure_route(
            state,
            "BTEST_MAINLINE_API_TO_CODEX",
            API_MAINLINE_NODE_ID,
            "BTEST_CODEX_WORKER",
            "TASK",
        )
        _ensure_route(
            state,
            "BTEST_CODEX_TO_MAINLINE_API",
            "BTEST_CODEX_WORKER",
            API_MAINLINE_NODE_ID,
            "REPORT",
        )

    sync_mainline_authority(state)


def _ensure_route(
    state: dict[str, Any],
    route_id: str,
    source_node_id: str,
    destination_node_id: str,
    handoff_type: str,
) -> None:
    routes = state.setdefault("routes", [])
    existing = next((route for route in routes if route.get("route_id") == route_id), None)
    expected = {
        "route_id": route_id,
        "source_node_id": source_node_id,
        "destination_node_id": destination_node_id,
        "enabled": True,
        "handoff_type": handoff_type,
    }
    if existing is None:
        routes.append(expected)
    elif existing != expected:
        raise ApiMainlineError("API_MAINLINE_ROUTE_CONFLICT")


def sync_mainline_authority(state: dict[str, Any]) -> None:
    mainline = state.get("mainline_state")
    if mainline is None:
        return
    authority = API_MAINLINE_NODE_ID if state.get("orchestration_enabled") else NATIVE_MAINLINE_AUTHORITY
    mainline["authority"] = authority
    mainline["canonical_state"]["authority"] = authority


def validate_mainline_state(state: dict[str, Any]) -> None:
    mainline = state.get("mainline_state")
    if mainline is None:
        return
    if set(mainline) != {"authority", "canonical_state", "openai_conversation_state"}:
        raise ApiMainlineError("INVALID_MAINLINE_STATE")
    expected_authority = (
        API_MAINLINE_NODE_ID if state.get("orchestration_enabled") else NATIVE_MAINLINE_AUTHORITY
    )
    if mainline["authority"] != expected_authority:
        raise ApiMainlineError("DUAL_MAINLINE_AUTHORITY_CONFLICT")
    authority_node = authority_node_id(expected_authority)
    authority_nodes = [
        node for node in state.get("nodes", [])
        if node.get("node_id") == authority_node and node.get("role") == "MAINLINE"
    ]
    if len(authority_nodes) != 1 or not authority_nodes[0].get("enabled"):
        raise ApiMainlineError("MAINLINE_AUTHORITY_NODE_UNAVAILABLE")

    canonical = mainline["canonical_state"]
    if set(canonical) != {
        "current_purpose", "frozen_decisions", "scope", "authority", "routing",
        "user_decisions", "current_gate", "latest_relevant_handoff",
    }:
        raise ApiMainlineError("INVALID_CANONICAL_MAINLINE_STATE")
    if canonical["authority"] != expected_authority:
        raise ApiMainlineError("CANONICAL_AUTHORITY_CONFLICT")
    if not isinstance(canonical["frozen_decisions"], list) or not isinstance(canonical["scope"], list):
        raise ApiMainlineError("INVALID_CANONICAL_MAINLINE_STATE")
    if not isinstance(canonical["user_decisions"], list):
        raise ApiMainlineError("INVALID_CANONICAL_MAINLINE_STATE")
    if set(canonical["routing"]) != {"latest_action", "current_destination"}:
        raise ApiMainlineError("INVALID_CANONICAL_ROUTING_STATE")

    conversation = mainline["openai_conversation_state"]
    if set(conversation) != {
        "conversation_id", "previous_response_id", "model_interaction_history", "status",
    }:
        raise ApiMainlineError("INVALID_OPENAI_CONVERSATION_STATE")
    if not isinstance(conversation["model_interaction_history"], list):
        raise ApiMainlineError("INVALID_OPENAI_CONVERSATION_STATE")


def public_mainline_state(
    mainline: dict[str, Any] | None,
    bootstrap_candidate: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if mainline is None:
        return None
    canonical = copy.deepcopy(mainline["canonical_state"])
    conversation = mainline["openai_conversation_state"]
    return {
        "authority": mainline["authority"],
        "canonical_state": canonical,
        "api_mainline": {
            "node_id": API_MAINLINE_NODE_ID,
            "status": "LOCKED_LIVE_API_OFF",
            "conversation_initialized": conversation["conversation_id"] is not None,
            "interaction_count": len(conversation["model_interaction_history"]),
            "current_gate": canonical["current_gate"],
            "current_destination": canonical["routing"]["current_destination"],
            "capabilities": copy.deepcopy(API_MAINLINE_CAPABILITIES),
            "bootstrap_candidate": copy.deepcopy(bootstrap_candidate or {
                "status": "NOT_PREPARED",
                "model": None,
                "proposed_hard_cap_usd": None,
                "canonical_state_sha256": None,
            }),
        },
    }


def audit_mainline_state(mainline: dict[str, Any] | None) -> dict[str, Any] | None:
    if mainline is None:
        return None
    canonical = mainline["canonical_state"]
    conversation = mainline["openai_conversation_state"]
    return {
        "authority": mainline["authority"],
        "current_gate": canonical["current_gate"],
        "current_destination": canonical["routing"]["current_destination"],
        "conversation_initialized": conversation["conversation_id"] is not None,
        "interaction_count": len(conversation["model_interaction_history"]),
    }


def api_mainline_output_schema() -> dict[str, Any]:
    nullable_string = {"type": ["string", "null"]}
    nullable_decision = {
        "anyOf": [
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["question", "options"],
                "properties": {
                    "question": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}},
                },
            },
            {"type": "null"},
        ]
    }
    nullable_blocker = {
        "anyOf": [
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["blocker", "required_action"],
                "properties": {
                    "blocker": {"type": "string"},
                    "required_action": nullable_string,
                },
            },
            {"type": "null"},
        ]
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "action", "destination_node_id", "exact_message",
            "user_decision_packet", "blocker_packet", "stop_reason",
        ],
        "properties": {
            "action": {"type": "string", "enum": sorted(MAINLINE_ROUTING_ACTIONS)},
            "destination_node_id": nullable_string,
            "exact_message": nullable_string,
            "user_decision_packet": nullable_decision,
            "blocker_packet": nullable_blocker,
            "stop_reason": nullable_string,
        },
    }


def validate_mainline_output(
    state: dict[str, Any],
    source_node_id: str,
    output: dict[str, Any],
) -> dict[str, Any]:
    mainline = state.get("mainline_state")
    if mainline is None:
        raise ApiMainlineError("API_MAINLINE_NOT_CONFIGURED")
    if source_node_id != authority_node_id(mainline["authority"]):
        raise ApiMainlineError("NON_CANONICAL_MAINLINE_SOURCE")
    required = {
        "action", "destination_node_id", "exact_message",
        "user_decision_packet", "blocker_packet", "stop_reason",
    }
    if not isinstance(output, dict) or set(output) != required:
        raise ApiMainlineError("INVALID_MAINLINE_OUTPUT_SHAPE")
    action = output["action"]
    if action not in MAINLINE_ROUTING_ACTIONS:
        raise ApiMainlineError("INVALID_MAINLINE_ROUTING_ACTION")

    destination = output["destination_node_id"]
    exact_message = output["exact_message"]
    decision = output["user_decision_packet"]
    blocker = output["blocker_packet"]
    stop_reason = output["stop_reason"]
    nodes = {node["node_id"]: node for node in state["nodes"]}

    if action == "HANDOFF_CODEX":
        node = nodes.get(destination)
        route_exists = any(
            route["enabled"]
            and route["source_node_id"] == source_node_id
            and route["destination_node_id"] == destination
            for route in state["routes"]
        )
        if (
            node is None or node["role"] != "CODEX_WORKER" or not node["enabled"]
            or not route_exists or not isinstance(exact_message, str) or not exact_message.strip()
            or decision is not None or blocker is not None or stop_reason is not None
        ):
            raise ApiMainlineError("INVALID_CODEX_HANDOFF_ACTION")
    elif action == "USER_REQUIRED":
        if (
            destination != "USER" or exact_message is not None
            or not _valid_decision_packet(decision)
            or blocker is not None or stop_reason is not None
        ):
            raise ApiMainlineError("INVALID_USER_REQUIRED_ACTION")
    elif action == "CONTINUE_USER_DIALOGUE":
        if (
            destination != "USER" or not isinstance(exact_message, str) or not exact_message.strip()
            or decision is not None or blocker is not None or stop_reason is not None
        ):
            raise ApiMainlineError("INVALID_USER_DIALOGUE_ACTION")
    elif action == "BLOCKED":
        if (
            destination is not None or exact_message is not None or decision is not None
            or not _valid_blocker_packet(blocker) or stop_reason is not None
        ):
            raise ApiMainlineError("INVALID_BLOCKED_ACTION")
    elif (
        destination is not None or exact_message is not None or decision is not None
        or blocker is not None or not isinstance(stop_reason, str) or not stop_reason.strip()
    ):
        raise ApiMainlineError("INVALID_STOP_ACTION")
    return copy.deepcopy(output)


def authority_node_id(authority: str) -> str:
    if authority == NATIVE_MAINLINE_AUTHORITY:
        return NATIVE_MAINLINE_NODE_ID
    if authority == API_MAINLINE_NODE_ID:
        return API_MAINLINE_NODE_ID
    raise ApiMainlineError("INVALID_MAINLINE_AUTHORITY")


def _valid_decision_packet(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"question", "options"}
        and isinstance(value["question"], str)
        and bool(value["question"].strip())
        and isinstance(value["options"], list)
        and len(value["options"]) >= 2
        and all(isinstance(item, str) and item.strip() for item in value["options"])
    )


def _valid_blocker_packet(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"blocker", "required_action"}
        and isinstance(value["blocker"], str)
        and bool(value["blocker"].strip())
        and (
            value["required_action"] is None
            or isinstance(value["required_action"], str)
        )
    )
