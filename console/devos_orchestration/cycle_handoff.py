from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .fixtures import SECRET_PATTERNS
from .state import line_numbered_content
from .task_alignment import extract_requirement_inventory


PACKET_VERSION = "1"
USER_ASSISTED_PACKET_VERSION = "2"
MAINLINE_LANE = "MAINLINE_CODEX_REVIEW"
DIRECT_EXACT_CAPTURE = "DIRECT_EXACT_RETRIEVAL"
USER_ASSISTED_EXACT_CAPTURE = "USER_ASSISTED_EXACT_CAPTURE"
REMOTE_SOURCE_BLOCKED = "REMOTE_SOURCE_BLOCKED"
ALLOWED_SOURCE_CONTEXTS = {"MAINLINE", "CODEX", "FUTURE_DESIGN", "OTHER"}
GENUINE_USER_DECISION_KINDS = {
    "SEMANTIC", "POLICY", "THRESHOLD", "AUTHORITY", "ARCHITECTURE", "SCOPE",
}


class CycleCaptureError(RuntimeError):
    pass


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _content_sha256(content: str) -> str:
    return _sha256(content.encode("utf-8"))


def _normalized_content_sha256(content: str) -> str:
    normalized = unicodedata.normalize(
        "NFC", content.replace("\r\n", "\n").replace("\r", "\n"),
    )
    return _content_sha256(normalized)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _message_index(messages: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for message in messages:
        required = {
            "session_identifier", "message_identifier", "role", "source_context",
            "cycle_id", "sequence", "content",
        }
        if set(message) != required:
            raise CycleCaptureError("INVALID_MESSAGE_SHAPE")
        identifier = message["message_identifier"]
        if not isinstance(identifier, str) or not identifier or identifier in index:
            raise CycleCaptureError("DUPLICATE_OR_INVALID_MESSAGE_IDENTIFIER")
        if not isinstance(message["session_identifier"], str) or not message["session_identifier"]:
            raise CycleCaptureError("INVALID_SESSION_IDENTIFIER")
        if message["role"] not in {"user", "assistant"}:
            raise CycleCaptureError("INVALID_MESSAGE_ROLE")
        if message["source_context"] not in ALLOWED_SOURCE_CONTEXTS:
            raise CycleCaptureError("INVALID_SOURCE_CONTEXT")
        if not isinstance(message["cycle_id"], str) or not message["cycle_id"]:
            raise CycleCaptureError("INVALID_CYCLE_IDENTIFIER")
        if not isinstance(message["sequence"], int) or message["sequence"] < 0:
            raise CycleCaptureError("INVALID_MESSAGE_SEQUENCE")
        if not isinstance(message["content"], str) or not message["content"]:
            raise CycleCaptureError("INVALID_MESSAGE_CONTENT")
        index[identifier] = dict(message)
    return index


def _selected_message(
    index: dict[str, dict[str, Any]], identifier: str, *, kind: str,
    expected_role: str, allowed_contexts: set[str], cycle_id: str,
) -> dict[str, Any]:
    message = index.get(identifier)
    if message is None:
        raise CycleCaptureError(f"MESSAGE_NOT_FOUND:{kind}")
    if message["cycle_id"] != cycle_id:
        raise CycleCaptureError("MULTIPLE_CYCLES_SELECTED")
    if message["role"] != expected_role:
        raise CycleCaptureError(f"INVALID_ROLE:{kind}")
    if message["source_context"] not in allowed_contexts:
        if message["source_context"] == "FUTURE_DESIGN":
            raise CycleCaptureError("FUTURE_DESIGN_CONTAMINATION")
        raise CycleCaptureError(f"INVALID_SOURCE_CONTEXT:{kind}")
    return {**message, "kind": kind}


def _capture_record(message: dict[str, Any], *, reviewer_input: bool, local_comparison: bool) -> dict[str, Any]:
    content = message["content"]
    raw = content.encode("utf-8")
    if any(pattern.search(raw) for pattern in SECRET_PATTERNS):
        raise CycleCaptureError("CYCLE_REDACTION_REQUIRED")
    return {
        "sequence": message["sequence"],
        "kind": message["kind"],
        "session_identifier": message["session_identifier"],
        "message_identifier": message["message_identifier"],
        "role": message["role"],
        "source_context": message["source_context"],
        "exact_content": content,
        "exact_content_sha256": _sha256(raw),
        "normalized_content_sha256": _normalized_content_sha256(content),
        "content_utf8_bytes": len(raw),
        "reviewer_input": reviewer_input,
        "local_comparison": local_comparison,
    }


def _packet_hash(packet: dict[str, Any]) -> str:
    payload = {key: value for key, value in packet.items() if key != "packet_sha256"}
    return _sha256(_canonical_json(payload))


def capture_cycle_handoff(
    messages: Iterable[dict[str, Any]], *, project: str, cycle_id: str,
    task_message_identifier: str, report_message_identifier: str,
    manual_review_message_identifier: str,
    intermediate_user_decision_identifiers: Iterable[str] = (),
    lane: str = MAINLINE_LANE, capture_timestamp: str | None = None,
    previous_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if lane != MAINLINE_LANE:
        raise CycleCaptureError("UNSUPPORTED_LANE")
    if not project or not cycle_id:
        raise CycleCaptureError("INVALID_CYCLE_IDENTITY")

    index = _message_index(messages)
    task = _selected_message(
        index, task_message_identifier, kind="task", expected_role="assistant",
        allowed_contexts={"MAINLINE"}, cycle_id=cycle_id,
    )
    report = _selected_message(
        index, report_message_identifier, kind="report", expected_role="assistant",
        allowed_contexts={"CODEX"}, cycle_id=cycle_id,
    )
    manual = _selected_message(
        index, manual_review_message_identifier, kind="manual_review",
        expected_role="assistant", allowed_contexts={"MAINLINE"}, cycle_id=cycle_id,
    )
    if task["session_identifier"] != manual["session_identifier"]:
        raise CycleCaptureError("MAINLINE_SESSION_MISMATCH")

    decision_ids = list(intermediate_user_decision_identifiers)
    if len(decision_ids) != len(set(decision_ids)):
        raise CycleCaptureError("DUPLICATE_USER_DECISION")
    decisions = [
        _selected_message(
            index, identifier, kind="intermediate_user_decision",
            expected_role="user", allowed_contexts={"MAINLINE", "CODEX"}, cycle_id=cycle_id,
        )
        for identifier in decision_ids
    ]

    unclassified_decisions = [
        message["message_identifier"]
        for message in index.values()
        if message["cycle_id"] == cycle_id
        and message["role"] == "user"
        and message["source_context"] in {"MAINLINE", "CODEX"}
        and task["sequence"] < message["sequence"] < report["sequence"]
        and message["message_identifier"] not in decision_ids
    ]
    if unclassified_decisions:
        raise CycleCaptureError("UNCLASSIFIED_INTERMEDIATE_USER_DECISION")

    selected = [task, *decisions, report, manual]
    sequences = [item["sequence"] for item in selected]
    if len(sequences) != len(set(sequences)) or sequences != sorted(sequences):
        raise CycleCaptureError("CYCLE_MESSAGE_ORDER_INVALID")
    if any(item["source_context"] == "FUTURE_DESIGN" for item in selected):
        raise CycleCaptureError("FUTURE_DESIGN_CONTAMINATION")

    captures = [
        _capture_record(
            item,
            reviewer_input=item["kind"] != "manual_review",
            local_comparison=item["kind"] == "manual_review",
        )
        for item in selected
    ]
    captures_by_kind = {item["kind"]: item for item in captures if item["kind"] != "intermediate_user_decision"}
    reviewer_ids = [item["message_identifier"] for item in captures if item["reviewer_input"]]
    comparison_ids = [item["message_identifier"] for item in captures if item["local_comparison"]]

    revision = 1
    supersedes = None
    if previous_packet is not None:
        verify_cycle_handoff_packet(previous_packet)
        if any(previous_packet[key] != value for key, value in {
            "lane": lane, "project": project, "cycle_id": cycle_id,
        }.items()):
            raise CycleCaptureError("PREVIOUS_PACKET_IDENTITY_MISMATCH")
        old_fingerprint = [
            (item["message_identifier"], item["exact_content_sha256"])
            for item in previous_packet["captured_messages"]
        ]
        new_fingerprint = [
            (item["message_identifier"], item["exact_content_sha256"])
            for item in captures
        ]
        if old_fingerprint == new_fingerprint:
            raise CycleCaptureError("CYCLE_CONTENT_UNCHANGED")
        revision = previous_packet["cycle_revision"] + 1
        supersedes = previous_packet["packet_sha256"]

    session_ids = list(dict.fromkeys(item["session_identifier"] for item in captures))
    packet = {
        "packet_version": PACKET_VERSION,
        "cycle_revision": revision,
        "lane": lane,
        "project": project,
        "cycle_id": cycle_id,
        "source_session_identifiers": session_ids,
        "task_message_identifier": task_message_identifier,
        "task_exact_content_sha256": captures_by_kind["task"]["exact_content_sha256"],
        "report_message_identifier": report_message_identifier,
        "report_exact_content_sha256": captures_by_kind["report"]["exact_content_sha256"],
        "manual_review_message_identifier": manual_review_message_identifier,
        "manual_review_exact_content_sha256": captures_by_kind["manual_review"]["exact_content_sha256"],
        "intermediate_user_decisions": [
            {
                "message_identifier": item["message_identifier"],
                "exact_content_sha256": item["exact_content_sha256"],
            }
            for item in captures if item["kind"] == "intermediate_user_decision"
        ],
        "capture_timestamp": capture_timestamp or _utc_now(),
        "ordered_message_manifest": [
            {
                "order": order,
                "kind": item["kind"],
                "session_identifier": item["session_identifier"],
                "message_identifier": item["message_identifier"],
                "role": item["role"],
                "source_context": item["source_context"],
                "exact_content_sha256": item["exact_content_sha256"],
                "content_utf8_bytes": item["content_utf8_bytes"],
                "reviewer_input": item["reviewer_input"],
                "local_comparison": item["local_comparison"],
            }
            for order, item in enumerate(captures, 1)
        ],
        "captured_messages": captures,
        "reviewer_input_message_identifiers": reviewer_ids,
        "local_comparison_message_identifiers": comparison_ids,
        "approved_for_external_api": False,
        "supersedes_packet_sha256": supersedes,
    }
    packet["packet_sha256"] = _packet_hash(packet)
    verify_cycle_handoff_packet(packet)
    return packet


def capture_legacy_fixture_cycle(
    task_path: Path, report_path: Path, manual_review_path: Path, *, project: str,
    cycle_id: str, capture_timestamp: str | None = None,
) -> dict[str, Any]:
    """Adapt the legacy three-file fallback without inventing platform IDs."""
    paths = {
        "task": task_path,
        "report": report_path,
        "manual_review": manual_review_path,
    }
    if not all(path.is_file() for path in paths.values()):
        raise CycleCaptureError("LEGACY_FIXTURE_FILE_MISSING")
    contents = {kind: path.read_text(encoding="utf-8") for kind, path in paths.items()}
    hashes = {kind: _content_sha256(content) for kind, content in contents.items()}
    messages = [
        {
            "session_identifier": f"legacy-file-mainline:{hashes['task'][:16]}",
            "message_identifier": f"legacy-file:task:{hashes['task']}",
            "role": "assistant", "source_context": "MAINLINE", "cycle_id": cycle_id,
            "sequence": 10, "content": contents["task"],
        },
        {
            "session_identifier": f"legacy-file-codex:{hashes['report'][:16]}",
            "message_identifier": f"legacy-file:report:{hashes['report']}",
            "role": "assistant", "source_context": "CODEX", "cycle_id": cycle_id,
            "sequence": 20, "content": contents["report"],
        },
        {
            "session_identifier": f"legacy-file-mainline:{hashes['task'][:16]}",
            "message_identifier": f"legacy-file:manual-review:{hashes['manual_review']}",
            "role": "assistant", "source_context": "MAINLINE", "cycle_id": cycle_id,
            "sequence": 30, "content": contents["manual_review"],
        },
    ]
    packet = capture_cycle_handoff(
        messages, project=project, cycle_id=cycle_id,
        task_message_identifier=messages[0]["message_identifier"],
        report_message_identifier=messages[1]["message_identifier"],
        manual_review_message_identifier=messages[2]["message_identifier"],
        capture_timestamp=capture_timestamp,
    )
    return packet


def capture_user_assisted_exact_cycle(
    messages: Iterable[dict[str, Any]], *, project: str, cycle_id: str,
    task_message_identifier: str, report_message_identifier: str,
    manual_review_exact_content: str, mainline_session_identifier: str,
    manual_review_sequence: int,
    intermediate_user_decision_identifiers: Iterable[str] = (),
    source_retrieval_status: str,
    capture_timestamp: str | None = None,
) -> dict[str, Any]:
    """Seal user-supplied exact review text only after remote retrieval is blocked."""
    if source_retrieval_status != REMOTE_SOURCE_BLOCKED:
        raise CycleCaptureError("USER_ASSISTED_CAPTURE_REQUIRES_REMOTE_SOURCE_BLOCKED")
    if not isinstance(manual_review_exact_content, str) or not manual_review_exact_content:
        raise CycleCaptureError("USER_ASSISTED_EXACT_CONTENT_REQUIRED")
    if not isinstance(mainline_session_identifier, str) or not mainline_session_identifier:
        raise CycleCaptureError("INVALID_SESSION_IDENTIFIER")
    if not isinstance(manual_review_sequence, int) or manual_review_sequence < 0:
        raise CycleCaptureError("INVALID_MESSAGE_SEQUENCE")

    source_messages = [dict(message) for message in messages]
    content_hash = _content_sha256(manual_review_exact_content)
    assisted_identifier = f"user-assisted:manual-review:{content_hash}"
    source_messages.append({
        "session_identifier": mainline_session_identifier,
        "message_identifier": assisted_identifier,
        "role": "assistant",
        "source_context": "MAINLINE",
        "cycle_id": cycle_id,
        "sequence": manual_review_sequence,
        "content": manual_review_exact_content,
    })
    packet = capture_cycle_handoff(
        source_messages, project=project, cycle_id=cycle_id,
        task_message_identifier=task_message_identifier,
        report_message_identifier=report_message_identifier,
        manual_review_message_identifier=assisted_identifier,
        intermediate_user_decision_identifiers=intermediate_user_decision_identifiers,
        capture_timestamp=capture_timestamp,
    )
    packet.update({
        "packet_version": USER_ASSISTED_PACKET_VERSION,
        "capture_mode": USER_ASSISTED_EXACT_CAPTURE,
        "source_retrieval_status": REMOTE_SOURCE_BLOCKED,
        "user_supplied_exact_content": True,
    })
    packet["packet_sha256"] = _packet_hash(packet)
    verify_cycle_handoff_packet(packet)
    return packet


def verify_cycle_handoff_packet(packet: dict[str, Any]) -> None:
    required = {
        "packet_version", "cycle_revision", "lane", "project", "cycle_id",
        "source_session_identifiers", "task_message_identifier", "task_exact_content_sha256",
        "report_message_identifier", "report_exact_content_sha256",
        "manual_review_message_identifier", "manual_review_exact_content_sha256",
        "intermediate_user_decisions", "capture_timestamp", "ordered_message_manifest",
        "captured_messages", "reviewer_input_message_identifiers",
        "local_comparison_message_identifiers", "approved_for_external_api",
        "supersedes_packet_sha256", "packet_sha256",
    }
    if packet.get("packet_version") == USER_ASSISTED_PACKET_VERSION:
        required |= {
            "capture_mode", "source_retrieval_status", "user_supplied_exact_content",
        }
    if set(packet) != required:
        raise CycleCaptureError("INVALID_PACKET_SHAPE")
    if packet["packet_version"] not in {PACKET_VERSION, USER_ASSISTED_PACKET_VERSION} or packet["lane"] != MAINLINE_LANE:
        raise CycleCaptureError("UNSUPPORTED_PACKET_VERSION_OR_LANE")
    if packet["packet_version"] == USER_ASSISTED_PACKET_VERSION:
        if packet["capture_mode"] != USER_ASSISTED_EXACT_CAPTURE:
            raise CycleCaptureError("INVALID_USER_ASSISTED_CAPTURE_MODE")
        if packet["source_retrieval_status"] != REMOTE_SOURCE_BLOCKED:
            raise CycleCaptureError("USER_ASSISTED_CAPTURE_REQUIRES_REMOTE_SOURCE_BLOCKED")
        if packet["user_supplied_exact_content"] is not True:
            raise CycleCaptureError("USER_ASSISTED_EXACT_CONTENT_NOT_CONFIRMED")
    if not isinstance(packet["cycle_revision"], int) or packet["cycle_revision"] < 1:
        raise CycleCaptureError("INVALID_CYCLE_REVISION")
    if packet["approved_for_external_api"] is not False:
        raise CycleCaptureError("EXTERNAL_API_APPROVAL_MUST_DEFAULT_FALSE")
    if packet["packet_sha256"] != _packet_hash(packet):
        raise CycleCaptureError("PACKET_HASH_MISMATCH")

    captures = packet["captured_messages"]
    manifest = packet["ordered_message_manifest"]
    if len(captures) != len(manifest) or len(captures) < 3:
        raise CycleCaptureError("MESSAGE_MANIFEST_MISMATCH")
    capture_keys = {
        "sequence", "kind", "session_identifier", "message_identifier", "role",
        "source_context", "exact_content", "exact_content_sha256",
        "normalized_content_sha256", "content_utf8_bytes", "reviewer_input",
        "local_comparison",
    }
    for order, (capture, entry) in enumerate(zip(captures, manifest), 1):
        if set(capture) != capture_keys:
            raise CycleCaptureError("INVALID_CAPTURED_MESSAGE_SHAPE")
        if capture["exact_content_sha256"] != _content_sha256(capture["exact_content"]):
            raise CycleCaptureError("MESSAGE_CONTENT_HASH_MISMATCH")
        if capture["normalized_content_sha256"] != _normalized_content_sha256(capture["exact_content"]):
            raise CycleCaptureError("NORMALIZED_CONTENT_HASH_MISMATCH")
        if capture["content_utf8_bytes"] != len(capture["exact_content"].encode("utf-8")):
            raise CycleCaptureError("MESSAGE_BYTE_LENGTH_MISMATCH")
        expected_entry = {
            "order": order,
            **{key: capture[key] for key in (
                "kind", "session_identifier", "message_identifier", "role",
                "source_context", "exact_content_sha256", "content_utf8_bytes",
                "reviewer_input", "local_comparison",
            )},
        }
        if entry != expected_entry:
            raise CycleCaptureError("ORDERED_MESSAGE_MANIFEST_MISMATCH")

    kinds = [item["kind"] for item in captures]
    if kinds.count("task") != 1 or kinds.count("report") != 1 or kinds.count("manual_review") != 1:
        raise CycleCaptureError("CYCLE_CARDINALITY_INVALID")
    if any(item["source_context"] == "FUTURE_DESIGN" for item in captures):
        raise CycleCaptureError("FUTURE_DESIGN_CONTAMINATION")
    if [item["sequence"] for item in captures] != sorted(item["sequence"] for item in captures):
        raise CycleCaptureError("CYCLE_MESSAGE_ORDER_INVALID")
    if kinds[0] != "task" or kinds[-2:] != ["report", "manual_review"]:
        raise CycleCaptureError("CYCLE_ROLE_ORDER_INVALID")
    if any(kind != "intermediate_user_decision" for kind in kinds[1:-2]):
        raise CycleCaptureError("CYCLE_ROLE_ORDER_INVALID")

    by_kind = {item["kind"]: item for item in captures if item["kind"] != "intermediate_user_decision"}
    for kind in ("task", "report", "manual_review"):
        if packet[f"{kind}_message_identifier"] != by_kind[kind]["message_identifier"]:
            raise CycleCaptureError("TOP_LEVEL_MESSAGE_IDENTIFIER_MISMATCH")
        if packet[f"{kind}_exact_content_sha256"] != by_kind[kind]["exact_content_sha256"]:
            raise CycleCaptureError("TOP_LEVEL_MESSAGE_HASH_MISMATCH")
    expected_decisions = [
        {
            "message_identifier": item["message_identifier"],
            "exact_content_sha256": item["exact_content_sha256"],
        }
        for item in captures if item["kind"] == "intermediate_user_decision"
    ]
    if packet["intermediate_user_decisions"] != expected_decisions:
        raise CycleCaptureError("USER_DECISION_MANIFEST_MISMATCH")
    expected_sessions = list(dict.fromkeys(item["session_identifier"] for item in captures))
    if packet["source_session_identifiers"] != expected_sessions:
        raise CycleCaptureError("SOURCE_SESSION_MANIFEST_MISMATCH")
    reviewer_ids = [item["message_identifier"] for item in captures if item["reviewer_input"]]
    comparison_ids = [item["message_identifier"] for item in captures if item["local_comparison"]]
    if reviewer_ids != packet["reviewer_input_message_identifiers"]:
        raise CycleCaptureError("REVIEWER_INPUT_MANIFEST_MISMATCH")
    if comparison_ids != [packet["manual_review_message_identifier"]] or comparison_ids != packet["local_comparison_message_identifiers"]:
        raise CycleCaptureError("MANUAL_REVIEW_ISOLATION_FAILURE")
    if packet["manual_review_message_identifier"] in reviewer_ids:
        raise CycleCaptureError("MANUAL_BASELINE_CONTAMINATION")
    if packet["packet_version"] == USER_ASSISTED_PACKET_VERSION:
        expected_identifier = (
            "user-assisted:manual-review:"
            + packet["manual_review_exact_content_sha256"]
        )
        if packet["manual_review_message_identifier"] != expected_identifier:
            raise CycleCaptureError("USER_ASSISTED_IDENTIFIER_HASH_MISMATCH")


def verify_user_assisted_remote_equivalence(
    packet: dict[str, Any], remote_message: dict[str, Any],
) -> dict[str, Any]:
    """Compare a later exact remote message without mutating the sealed packet."""
    verify_cycle_handoff_packet(packet)
    if packet.get("capture_mode") != USER_ASSISTED_EXACT_CAPTURE:
        raise CycleCaptureError("NOT_USER_ASSISTED_CAPTURE")
    required = {
        "session_identifier", "message_identifier", "role", "source_context",
        "cycle_id", "sequence", "content",
    }
    if set(remote_message) != required:
        raise CycleCaptureError("INVALID_MESSAGE_SHAPE")
    if remote_message["role"] != "assistant" or remote_message["source_context"] != "MAINLINE":
        raise CycleCaptureError("INVALID_REMOTE_MANUAL_REVIEW_SOURCE")
    if remote_message["cycle_id"] != packet["cycle_id"]:
        raise CycleCaptureError("MULTIPLE_CYCLES_SELECTED")
    task = next(
        item for item in packet["captured_messages"] if item["kind"] == "task"
    )
    if remote_message["session_identifier"] != task["session_identifier"]:
        raise CycleCaptureError("MAINLINE_SESSION_MISMATCH")
    report = next(
        item for item in packet["captured_messages"] if item["kind"] == "report"
    )
    if remote_message["sequence"] <= report["sequence"]:
        raise CycleCaptureError("CYCLE_MESSAGE_ORDER_INVALID")
    actual_hash = _content_sha256(remote_message["content"])
    equivalent = actual_hash == packet["manual_review_exact_content_sha256"]
    return {
        "status": (
            "USER_ASSISTED_REMOTE_EQUIVALENT"
            if equivalent else "USER_ASSISTED_REMOTE_MISMATCH"
        ),
        "equivalent": equivalent,
        "remote_message_identifier": remote_message["message_identifier"],
        "remote_exact_content_sha256": actual_hash,
        "packet_manual_review_exact_content_sha256": packet["manual_review_exact_content_sha256"],
        "packet_immutable": True,
    }


def build_cycle_reviewer_prompt(packet: dict[str, Any]) -> str:
    verify_cycle_handoff_packet(packet)
    allowed = set(packet["reviewer_input_message_identifiers"])
    sections = [
        "DeveloperOS Cycle Handoff reviewer evidence",
        f"Lane: {packet['lane']}",
        f"Project: {packet['project']}",
        f"Cycle: {packet['cycle_id']}",
        f"Packet SHA-256: {packet['packet_sha256']}",
    ]
    for message in packet["captured_messages"]:
        if message["message_identifier"] not in allowed:
            continue
        sections.append(
            f"[{message['kind']}:{message['message_identifier']}]\n"
            + line_numbered_content(message["exact_content"])
        )
    prompt = "\n\n".join(sections)
    manual = next(item for item in packet["captured_messages"] if item["kind"] == "manual_review")
    if manual["message_identifier"] in prompt or manual["exact_content"] in prompt:
        raise CycleCaptureError("MANUAL_BASELINE_CONTAMINATION")
    return prompt


def requirement_inventory_for_cycle_packet(packet: dict[str, Any]) -> list[dict[str, Any]]:
    verify_cycle_handoff_packet(packet)
    task = next(item for item in packet["captured_messages"] if item["kind"] == "task")
    return extract_requirement_inventory(task["exact_content"])


def compare_legacy_fixture(packet: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
    verify_cycle_handoff_packet(packet)
    files = {item["source_label"]: item for item in fixture.get("files", [])}
    labels = {
        "task": "historical_codex_task",
        "report": "historical_codex_report",
        "manual_review": "manual_review_baseline",
    }
    matches: dict[str, bool] = {}
    for kind, label in labels.items():
        message = next(item for item in packet["captured_messages"] if item["kind"] == kind)
        metadata = files.get(label)
        matches[kind] = bool(
            metadata
            and message["normalized_content_sha256"] == metadata.get("normalized_content_sha256")
        )
    decisions = packet["intermediate_user_decisions"]
    equivalent = all(matches.values()) and not decisions
    return {
        "status": "SEMANTIC_INPUT_EQUIVALENT" if equivalent else "SEMANTIC_INPUT_NOT_EQUIVALENT",
        "content_matches": matches,
        "intermediate_user_decision_count": len(decisions),
        "reviewer_input_equivalent": matches["task"] and matches["report"] and not decisions,
        "manual_comparison_equivalent": matches["manual_review"],
    }


def classify_genuine_user_required_candidate(
    packet: dict[str, Any], *, manual_review_gate: str,
    decision_kind: str | None, evidence_classification: str,
) -> dict[str, Any]:
    """Mark a real completed cycle for later approval without executing it."""
    verify_cycle_handoff_packet(packet)
    direct_capture = packet.get("capture_mode", DIRECT_EXACT_CAPTURE) == DIRECT_EXACT_CAPTURE and not any(
        item["message_identifier"].startswith(("legacy-file:", "synthetic:"))
        or item["session_identifier"].startswith(("legacy-file-", "synthetic:"))
        for item in packet["captured_messages"]
    )
    candidate = all((
        evidence_classification == "REAL_WORLD_EVIDENCE",
        direct_capture,
        manual_review_gate == "USER_REQUIRED",
        decision_kind in GENUINE_USER_DECISION_KINDS,
    ))
    return {
        "genuine_user_required_candidate": candidate,
        "evidence_classification": evidence_classification,
        "direct_session_capture": direct_capture,
        "manual_review_gate": manual_review_gate,
        "decision_kind": decision_kind,
        "automatic_api_execution": False,
        "user_approval_required_for_holdout": candidate,
        "reason": (
            "REAL_WORLD_USER_REQUIRED_CYCLE_READY_FOR_USER_APPROVAL"
            if candidate else "NOT_A_GENUINE_USER_REQUIRED_CANDIDATE"
        ),
    }


def write_cycle_handoff_packet(path: Path, packet: dict[str, Any]) -> None:
    verify_cycle_handoff_packet(packet)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(packet, ensure_ascii=True, indent=2) + "\n")
    except FileExistsError as error:
        raise CycleCaptureError("IMMUTABLE_PACKET_ALREADY_EXISTS") from error
