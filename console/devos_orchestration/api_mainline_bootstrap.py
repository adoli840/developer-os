from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from decimal import Decimal, ROUND_UP
from pathlib import Path
from typing import Any

from .api_mainline import API_MAINLINE_NODE_ID, default_mainline_state
from .fixtures import SECRET_PATTERNS
from .manifest import canonical_json, sha256_json
from .pricing import SOL_PROPOSAL_PRICING, estimate_cost, pricing_record_payload


BOOTSTRAP_PROMPT_VERSION = "2c.2a.1"
BOOTSTRAP_SCHEMA_VERSION = "2c.2a.1"
BOOTSTRAP_RUNTIME_VERSION = "2c.2a.1"
BOOTSTRAP_CANDIDATE_FILE = "phase2c-2a-api-mainline-bootstrap-candidate-manifest.json"
MODEL = SOL_PROPOSAL_PRICING.model
MAX_OUTPUT_TOKENS = 8_192
TIMEOUT_SECONDS = 600
USER_INPUT = (
    "Initialize the DeveloperOS-managed bTest Mainline from the supplied canonical state. "
    "Do not infer missing project work. Ask me for the first bTest objective or decision "
    "needed before creating any Codex handoff."
)

BOOTSTRAP_FROZEN_DECISIONS = [
    "Orchestration OFF uses NATIVE_MAINLINE; orchestration ON uses BTEST_MAINLINE_API.",
    "Only one Mainline authority may be canonical at a time.",
    "OpenAI conversation state is transport continuity, not canonical policy authority.",
    "Codex dispatch requires a separately sealed envelope and explicit user approval.",
]

ALLOWED_STATE_DELTA_FIELDS = {
    "current_purpose",
    "scope_append",
    "user_decisions_append",
    "current_gate",
    "latest_relevant_handoff",
}


class ApiMainlineBootstrapError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _nullable_string() -> dict[str, Any]:
    return {"type": ["string", "null"]}


def api_mainline_bootstrap_schema() -> dict[str, Any]:
    decision_packet = {
        "anyOf": [
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["question", "options"],
                "properties": {
                    "question": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}, "minItems": 2},
                },
            },
            {"type": "null"},
        ]
    }
    blocker = {
        "anyOf": [
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["reason", "required_action", "stop_reason"],
                "properties": {
                    "reason": _nullable_string(),
                    "required_action": _nullable_string(),
                    "stop_reason": _nullable_string(),
                },
            },
            {"type": "null"},
        ]
    }
    state_delta = {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(ALLOWED_STATE_DELTA_FIELDS),
        "properties": {
            "current_purpose": _nullable_string(),
            "scope_append": {"type": "array", "items": {"type": "string"}},
            "user_decisions_append": {"type": "array", "items": {"type": "string"}},
            "current_gate": {
                "type": ["string", "null"],
                "enum": ["SAFE_CONTINUE", "USER_REQUIRED", "BLOCKED", "STOP", None],
            },
            "latest_relevant_handoff": _nullable_string(),
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "action", "assistant_message", "gate", "destination", "handoff_message",
            "decision_packet", "blocker", "updated_state_delta",
        ],
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "HANDOFF_CODEX", "USER_REQUIRED", "CONTINUE_USER_DIALOGUE", "BLOCKED", "STOP",
                ],
            },
            "assistant_message": _nullable_string(),
            "gate": {
                "type": ["string", "null"],
                "enum": ["SAFE_CONTINUE", "USER_REQUIRED", "BLOCKED", "STOP", None],
            },
            "destination": {
                "type": ["string", "null"],
                "enum": ["CODEX_WORKER", "USER", None],
            },
            "handoff_message": _nullable_string(),
            "decision_packet": decision_packet,
            "blocker": blocker,
            "updated_state_delta": state_delta,
        },
    }


def validate_bootstrap_output(output: dict[str, Any]) -> dict[str, Any]:
    required = set(api_mainline_bootstrap_schema()["required"])
    if not isinstance(output, dict) or set(output) != required:
        raise ApiMainlineBootstrapError("INVALID_BOOTSTRAP_OUTPUT_SHAPE")
    action = output["action"]
    destination = output["destination"]
    handoff = output["handoff_message"]
    decision = output["decision_packet"]
    blocker = output["blocker"]
    gate = output["gate"]
    assistant_message = output["assistant_message"]
    validate_state_delta(output["updated_state_delta"])
    if output["updated_state_delta"]["current_gate"] != gate:
        raise ApiMainlineBootstrapError("BOOTSTRAP_STATE_GATE_CONFLICT")

    if action == "HANDOFF_CODEX":
        valid = destination == "CODEX_WORKER" and gate == "SAFE_CONTINUE" and _nonempty(handoff)
        valid = valid and decision is None and blocker is None
    elif action == "USER_REQUIRED":
        valid = destination == "USER" and gate == "USER_REQUIRED" and _valid_decision(decision)
        valid = valid and handoff is None and blocker is None
    elif action == "CONTINUE_USER_DIALOGUE":
        valid = destination == "USER" and gate is None and _nonempty(assistant_message)
        valid = valid and handoff is None and decision is None and blocker is None
    elif action == "BLOCKED":
        valid = destination is None and gate == "BLOCKED" and _valid_blocker(blocker, stop=False)
        valid = valid and handoff is None and decision is None
    elif action == "STOP":
        valid = destination is None and gate == "STOP" and _valid_blocker(blocker, stop=True)
        valid = valid and handoff is None and decision is None
    else:
        valid = False
    if not valid:
        raise ApiMainlineBootstrapError("BOOTSTRAP_ROUTING_CONFLICT")
    return copy.deepcopy(output)


def validate_state_delta(delta: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(delta, dict) or set(delta) != ALLOWED_STATE_DELTA_FIELDS:
        raise ApiMainlineBootstrapError("CANONICAL_STATE_DELTA_FORBIDDEN")
    if any(field in delta for field in ("frozen_decisions", "authority", "routing")):
        raise ApiMainlineBootstrapError("CANONICAL_STATE_DELTA_FORBIDDEN")
    for field in ("scope_append", "user_decisions_append"):
        if not isinstance(delta[field], list) or not all(_nonempty(item) for item in delta[field]):
            raise ApiMainlineBootstrapError("INVALID_CANONICAL_STATE_DELTA")
    for field in ("current_purpose", "latest_relevant_handoff"):
        if delta[field] is not None and not _nonempty(delta[field]):
            raise ApiMainlineBootstrapError("INVALID_CANONICAL_STATE_DELTA")
    if delta["current_gate"] not in {None, "SAFE_CONTINUE", "USER_REQUIRED", "BLOCKED", "STOP"}:
        raise ApiMainlineBootstrapError("INVALID_CANONICAL_STATE_DELTA")
    return copy.deepcopy(delta)


def build_bootstrap_canonical_state(existing: dict[str, Any] | None = None) -> dict[str, Any]:
    source = copy.deepcopy(existing or default_mainline_state()["canonical_state"])
    expected = {
        "current_purpose", "frozen_decisions", "scope", "authority", "routing",
        "user_decisions", "current_gate", "latest_relevant_handoff",
    }
    if set(source) != expected:
        raise ApiMainlineBootstrapError("INVALID_BOOTSTRAP_CANONICAL_STATE")
    source["authority"] = API_MAINLINE_NODE_ID
    source["current_purpose"] = source.get("current_purpose") or (
        "Initialize the managed bTest Mainline without inferring an unprovided project objective."
    )
    source["frozen_decisions"] = list(dict.fromkeys(
        list(source.get("frozen_decisions") or []) + BOOTSTRAP_FROZEN_DECISIONS
    ))
    source["scope"] = list(dict.fromkeys(
        list(source.get("scope") or [])
        + ["First API Mainline user turn and structured routing action only."]
    ))
    source["routing"] = {"latest_action": None, "current_destination": None}
    source["current_gate"] = None
    return source


def validate_user_start_canonical_state(existing: dict[str, Any]) -> dict[str, Any]:
    source = copy.deepcopy(existing)
    expected = {
        "current_purpose", "frozen_decisions", "scope", "authority", "routing",
        "user_decisions", "current_gate", "latest_relevant_handoff",
    }
    if set(source) != expected:
        raise ApiMainlineBootstrapError("INVALID_BOOTSTRAP_CANONICAL_STATE")
    if source["authority"] != API_MAINLINE_NODE_ID:
        raise ApiMainlineBootstrapError("API_MAINLINE_AUTHORITY_REQUIRED")
    return source


def load_control_plane_canonical_state(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        mainline = value["projects"]["btest"].get("mainline_state")
        if mainline is None:
            return None
        canonical = mainline["canonical_state"]
        if not isinstance(canonical, dict):
            raise TypeError
        return copy.deepcopy(canonical)
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ApiMainlineBootstrapError("INVALID_CONTROL_PLANE_CANONICAL_STATE") from error


def _developer_prompt(canonical_state: dict[str, Any]) -> str:
    return "\n".join([
        "You are BTEST_MAINLINE_API, the sole managed Mainline authority for this proposed turn.",
        "Use only the supplied canonical state and user input. Do not infer missing project history.",
        "Return exactly one strict structured routing action.",
        "HANDOFF_CODEX requires CODEX_WORKER and an exact handoff message.",
        "USER_REQUIRED requires a decision packet. CONTINUE_USER_DIALOGUE must not create a handoff.",
        "BLOCKED requires an exact blocker. STOP requires an explicit stop reason.",
        "Propose only updated_state_delta. Never rewrite frozen decisions, authority, or routing.",
        "No tool use, network side effect, Codex dispatch, or automatic next cycle is permitted.",
        "Canonical state:\n" + json.dumps(canonical_state, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    ])


def _runtime_protocol() -> dict[str, Any]:
    return {
        "version": BOOTSTRAP_RUNTIME_VERSION,
        "endpoint": "/v1/responses",
        "conversation_mode": "NEW_CONVERSATION",
        "timeout_seconds": TIMEOUT_SECONDS,
        "retry_count": 0,
        "fallback_count": 0,
        "dispatch_count": 0,
        "capture_before_parse": True,
        "credential_variable": "OPENAI_ORCHESTRATION_API_KEY",
        "forbidden_credential_fallbacks": ["OPENAI_API_KEY", "OPENAI_ADMIN_API_KEY"],
    }


def build_bootstrap_request(canonical_state: dict[str, Any], user_input: str = USER_INPUT) -> tuple[dict[str, Any], str]:
    if not _nonempty(user_input):
        raise ApiMainlineBootstrapError("USER_INPUT_REQUIRED")
    developer_prompt = _developer_prompt(canonical_state)
    request = {
        "model": MODEL,
        "input": [
            {"role": "developer", "content": developer_prompt},
            {"role": "user", "content": user_input},
        ],
        "reasoning": {"effort": "high"},
        "text": {
            "verbosity": "medium",
            "format": {
                "type": "json_schema",
                "name": "developer_os_api_mainline_bootstrap",
                "strict": True,
                "schema": api_mainline_bootstrap_schema(),
            },
        },
        "tools": [],
        "store": False,
        "background": False,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
    }
    return request, developer_prompt


def _cost_preflight(request: dict[str, Any]) -> dict[str, Any]:
    request_bytes = len(canonical_json(request))
    hard_input_tokens = math.ceil(request_bytes * 1.10) + 2048
    max_output_tokens = int(request.get("max_output_tokens", MAX_OUTPUT_TOKENS))
    input_cost = estimate_cost(
        SOL_PROPOSAL_PRICING, uncached_input=0, cached_input=0,
        cache_write=hard_input_tokens, output=0,
    )
    output_cost = estimate_cost(
        SOL_PROPOSAL_PRICING, uncached_input=0, cached_input=0,
        cache_write=0, output=max_output_tokens,
    )
    subtotal = input_cost + output_cost
    safety_margin = max(Decimal("0.02"), subtotal * Decimal("0.10"))
    worst = subtotal + safety_margin
    proposed_cap = worst.quantize(Decimal("0.01"), rounding=ROUND_UP)
    return {
        "request_utf8_bytes": request_bytes,
        "hard_input_token_upper_bound": hard_input_tokens,
        "hard_input_cost_usd": str(input_cost),
        "hard_output_cost_usd": str(output_cost),
        "safety_margin_usd": str(safety_margin),
        "hard_worst_case_cost_usd": str(worst),
        "proposed_single_call_cap_usd": str(proposed_cap),
        "status": "READY",
    }


def build_bootstrap_candidate(
    output: Path,
    *,
    canonical_state: dict[str, Any] | None = None,
    user_input: str = USER_INPUT,
    candidate_type: str = "API_MAINLINE_BOOTSTRAP",
    preserve_canonical_state: bool = False,
) -> dict[str, Any]:
    if candidate_type not in {"API_MAINLINE_BOOTSTRAP", "API_MAINLINE_USER_START"}:
        raise ApiMainlineBootstrapError("INVALID_BOOTSTRAP_CANDIDATE")
    state = (
        validate_user_start_canonical_state(canonical_state or {})
        if preserve_canonical_state
        else build_bootstrap_canonical_state(canonical_state)
    )
    request, prompt = build_bootstrap_request(state, user_input)
    serialized_request = canonical_json(request)
    if any(pattern.search(serialized_request) for pattern in SECRET_PATTERNS):
        raise ApiMainlineBootstrapError("BOOTSTRAP_SECRET_SCAN_FAILED")
    preflight = _cost_preflight(request)
    runtime = _runtime_protocol()
    pricing = pricing_record_payload(SOL_PROPOSAL_PRICING)
    binding = {
        "conversation_mode": "NEW_CONVERSATION",
        "model": MODEL,
        "prompt_version": BOOTSTRAP_PROMPT_VERSION,
        "schema_version": BOOTSTRAP_SCHEMA_VERSION,
        "canonical_state_sha256": sha256_json(state),
        "user_input_sha256": _sha256_bytes(user_input.encode("utf-8")),
        "request_sha256": _sha256_bytes(serialized_request),
        "prompt_sha256": _sha256_bytes(prompt.encode("utf-8")),
        "structured_output_schema_sha256": sha256_json(request["text"]["format"]["schema"]),
        "runtime_protocol_sha256": sha256_json(runtime),
        "pricing_record_sha256": sha256_json(pricing),
    }
    manifest = {
        "manifest_version": "2c.2a.1",
        "candidate_type": candidate_type,
        **binding,
        "reasoning_effort": "high",
        "reasoning_mode": None,
        "text_verbosity": "medium",
        "tools": [],
        "store": False,
        "background": False,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "timeout_seconds": TIMEOUT_SECONDS,
        "retry_count": 0,
        "fallback_count": 0,
        "planned_response_call_count": 1,
        **preflight,
        "approved_for_external_api": False,
        "created_at": _now(),
    }
    manifest["approval_manifest_sha256"] = sha256_json(manifest)
    candidate = {
        "candidate_type": candidate_type,
        "manifest": manifest,
        "request_binding": binding,
        "canonical_state": state,
        "user_input": user_input,
        "request": request,
        "runtime_protocol": runtime,
        "preflight": preflight,
        "state_delta_policy": {
            "allowed_fields": sorted(ALLOWED_STATE_DELTA_FIELDS),
            "forbidden_fields": ["frozen_decisions", "authority", "routing"],
            "automatic_apply": False,
        },
        "approved_for_external_api": False,
        "approval_record": False,
        "attempt_record": False,
        "result_record": False,
        "network_calls": 0,
        "dispatch_count": 0,
    }
    verify_bootstrap_candidate(candidate)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    temporary.write_text(json.dumps(candidate, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, output)
    return candidate


def read_public_bootstrap_summary(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "status": "NOT_PREPARED", "model": None, "proposed_hard_cap_usd": None,
            "canonical_state_sha256": None,
        }
    try:
        candidate = json.loads(path.read_text(encoding="utf-8"))
        verify_bootstrap_candidate(candidate)
        manifest = candidate["manifest"]
        disposition_path = path.parent / f"disposition-{manifest['approval_manifest_sha256']}.json"
        status = (
            "DO_NOT_EXECUTE / SAFE_BOOTSTRAP_FALLBACK"
            if candidate.get("candidate_type") == "API_MAINLINE_BOOTSTRAP"
            and candidate.get("user_input") == USER_INPUT
            else "READY"
        )
        if disposition_path.is_file():
            disposition = json.loads(disposition_path.read_text(encoding="utf-8"))
            if (
                disposition.get("approval_manifest_sha256") == manifest["approval_manifest_sha256"]
                and disposition.get("candidate_file_sha256") == _sha256_bytes(path.read_bytes())
                and disposition.get("decision") == "DO_NOT_EXECUTE"
            ):
                status = "DO_NOT_EXECUTE / SAFE_BOOTSTRAP_FALLBACK"
        return {
            "status": status,
            "model": manifest["model"],
            "proposed_hard_cap_usd": manifest["proposed_single_call_cap_usd"],
            "canonical_state_sha256": manifest["canonical_state_sha256"],
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return {
            "status": "INVALID", "model": None, "proposed_hard_cap_usd": None,
            "canonical_state_sha256": None,
        }


def verify_bootstrap_candidate(candidate: dict[str, Any]) -> None:
    if candidate.get("candidate_type") not in {
        "API_MAINLINE_BOOTSTRAP", "API_MAINLINE_USER_START",
    }:
        raise ApiMainlineBootstrapError("INVALID_BOOTSTRAP_CANDIDATE")
    if any(candidate.get(name) is not False for name in (
        "approved_for_external_api", "approval_record", "attempt_record", "result_record",
    )):
        raise ApiMainlineBootstrapError("BOOTSTRAP_CANDIDATE_NOT_PRISTINE")
    if candidate.get("network_calls") != 0 or candidate.get("dispatch_count") != 0:
        raise ApiMainlineBootstrapError("BOOTSTRAP_EXECUTION_ALREADY_STARTED")

    manifest = candidate["manifest"]
    if manifest.get("candidate_type") != candidate["candidate_type"]:
        raise ApiMainlineBootstrapError("BOOTSTRAP_CANDIDATE_TYPE_MISMATCH")
    unsigned = dict(manifest)
    supplied = unsigned.pop("approval_manifest_sha256")
    if supplied != sha256_json(unsigned):
        raise ApiMainlineBootstrapError("APPROVAL_MANIFEST_HASH_MISMATCH")
    if manifest.get("approved_for_external_api") is not False:
        raise ApiMainlineBootstrapError("BOOTSTRAP_CANDIDATE_NOT_PRISTINE")

    state = candidate["canonical_state"]
    user_input = candidate["user_input"]
    request = candidate["request"]
    runtime = candidate["runtime_protocol"]
    if any(pattern.search(canonical_json(request)) for pattern in SECRET_PATTERNS):
        raise ApiMainlineBootstrapError("BOOTSTRAP_SECRET_SCAN_FAILED")
    expected_binding = {
        "conversation_mode": "NEW_CONVERSATION",
        "model": MODEL,
        "prompt_version": BOOTSTRAP_PROMPT_VERSION,
        "schema_version": BOOTSTRAP_SCHEMA_VERSION,
        "canonical_state_sha256": sha256_json(state),
        "user_input_sha256": _sha256_bytes(user_input.encode("utf-8")),
        "request_sha256": _sha256_bytes(canonical_json(request)),
        "prompt_sha256": _sha256_bytes(request["input"][0]["content"].encode("utf-8")),
        "structured_output_schema_sha256": sha256_json(request["text"]["format"]["schema"]),
        "runtime_protocol_sha256": sha256_json(runtime),
        "pricing_record_sha256": sha256_json(pricing_record_payload(SOL_PROPOSAL_PRICING)),
    }
    if candidate.get("request_binding") != expected_binding:
        raise ApiMainlineBootstrapError("BOOTSTRAP_REQUEST_BINDING_MISMATCH")
    if any(manifest.get(key) != value for key, value in expected_binding.items()):
        raise ApiMainlineBootstrapError("BOOTSTRAP_MANIFEST_BINDING_MISMATCH")
    if candidate.get("preflight") != _cost_preflight(request):
        raise ApiMainlineBootstrapError("BOOTSTRAP_COST_PREFLIGHT_MISMATCH")
    if any(manifest.get(key) != value for key, value in candidate["preflight"].items()):
        raise ApiMainlineBootstrapError("BOOTSTRAP_MANIFEST_COST_MISMATCH")
    if request.get("reasoning") != {"effort": "high"}:
        raise ApiMainlineBootstrapError("BOOTSTRAP_REASONING_CONTRACT_MISMATCH")
    if request.get("tools") != [] or request.get("store") is not False or request.get("background") is not False:
        raise ApiMainlineBootstrapError("BOOTSTRAP_REQUEST_SAFETY_MISMATCH")


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_decision(value: Any) -> bool:
    return (
        isinstance(value, dict) and set(value) == {"question", "options"}
        and _nonempty(value["question"]) and isinstance(value["options"], list)
        and len(value["options"]) >= 2 and all(_nonempty(item) for item in value["options"])
    )


def _valid_blocker(value: Any, *, stop: bool) -> bool:
    if not isinstance(value, dict) or set(value) != {"reason", "required_action", "stop_reason"}:
        return False
    if not _nonempty(value["stop_reason"] if stop else value["reason"]):
        return False
    return all(item is None or isinstance(item, str) for item in value.values())
