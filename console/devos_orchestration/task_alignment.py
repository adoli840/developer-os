from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any


TASK_ALIGNMENT_CONTRACT_VERSION = "2.3"
TASK_ALIGNMENT_CONFLICT_INVARIANTS = (
    "EXPLICIT_REQUIREMENT_OMITTED",
    "NEXT_INSTRUCTION_UNRELATED_TO_UNRESOLVED_TASK",
    "SCOPE_EXPANSION_WITHOUT_BLOCKING_EVIDENCE",
    "UNPROVEN_PREREQUISITE_REPLACES_ORIGINAL_TASK",
    "PRIMARY_TASK_DOES_NOT_DIRECTLY_ADDRESS_UNRESOLVED_REQUIREMENT",
    "DEFERRED_REQUIREMENT_WITHOUT_EXACT_BLOCKER",
    "ADDED_SCOPE_PROMOTED_WITHOUT_EXACT_BLOCKER",
    "COMPLETED_TASK_ADVANCES_WITHOUT_CANONICAL_AUTHORITY",
    "NEXT_STEP_SOURCE_REFERENCE_INVENTED",
    "UNRESOLVED_TASK_REPLACED_BY_PLAN_ADVANCE",
)
TASK_TRANSITIONS = {
    "CONTINUE_CURRENT_TASK", "ADVANCE_AUTHORIZED_PLAN", "USER_DECISION_REQUIRED",
}
NEXT_STEP_BASES = {
    "UNRESOLVED_REQUIREMENT", "FROZEN_NEXT_STEP", "APPROVED_PLAN_ITEM",
    "USER_DECISION", "NONE",
}
_CANONICAL_NEXT_STEP_PREFIXES = {
    "frozen_decisions": {
        "FROZEN_NEXT_STEP:": "FROZEN_NEXT_STEP",
        "APPROVED_PLAN_ITEM:": "APPROVED_PLAN_ITEM",
    },
    "user_decisions": {
        "APPROVED_PLAN_ITEM:": "APPROVED_PLAN_ITEM",
        "FROZEN_NEXT_STEP:": "FROZEN_NEXT_STEP",
    },
}
_NUMBERED_HEADING = re.compile(r"^\s*\d+\.\s+\S")
_BRACKET_HEADING = re.compile(r"^\s*\[[^\]]+\]\s*$")


def extract_requirement_inventory(task_text: str) -> list[dict[str, Any]]:
    """Create stable task-section identities without inferring status or answers."""
    normalized = unicodedata.normalize(
        "NFC", task_text.replace("\r\n", "\n").replace("\r", "\n"),
    )
    lines = normalized.splitlines()
    starts = [
        index for index, line in enumerate(lines, 1)
        if _NUMBERED_HEADING.match(line) or _BRACKET_HEADING.match(line)
    ]
    inventory: list[dict[str, Any]] = []
    for offset, start in enumerate(starts):
        end = starts[offset + 1] - 1 if offset + 1 < len(starts) else len(lines)
        heading = lines[start - 1].strip()
        identity = hashlib.sha256(f"{start}:{end}:{heading}".encode("utf-8")).hexdigest()[:12]
        inventory.append({
            "requirement_id": f"TASK-L{start:04d}-{identity}",
            "source_ref": f"historical_codex_task:L{start}-L{end}",
            "heading": heading,
        })
    if not inventory:
        identity = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
        inventory.append({
            "requirement_id": f"TASK-L0001-{identity}",
            "source_ref": f"historical_codex_task:L1-L{max(1, len(lines))}",
            "heading": "Entire explicit task",
        })
    return inventory


def canonical_next_step_catalog(canonical_state: dict[str, Any]) -> list[dict[str, str]]:
    """Expose only explicitly marked next steps; never infer authority from prose."""
    catalog: list[dict[str, str]] = []
    for field, prefixes in _CANONICAL_NEXT_STEP_PREFIXES.items():
        values = canonical_state.get(field) or []
        if not isinstance(values, list):
            continue
        for index, value in enumerate(values):
            if not isinstance(value, str):
                continue
            stripped = value.strip()
            for prefix, basis in prefixes.items():
                if stripped.startswith(prefix) and stripped[len(prefix):].strip():
                    catalog.append({
                        "source_ref": f"canonical_state.{field}[{index}]",
                        "basis": basis,
                        "authorized_next_step": stripped[len(prefix):].strip(),
                    })
                    break
    return catalog
