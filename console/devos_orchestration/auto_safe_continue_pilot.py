from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from .auto_safe_continue import AutoAdvanceEvidence, evaluate_auto_advance
from .api_mainline_bootstrap import ApiMainlineBootstrapError
from .api_mainline_continuation import validate_auto_advance_evidence


PILOT_RUN_VERSION = "2c.auto-pilot-run.1"


class AutoSafeContinuePilotError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _atomic_json(path: Path, value: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    os.replace(temporary, path)
    return hashlib.sha256(data).hexdigest()


class AutoSafeContinuePilotStore:
    """Durably records an explicitly approved pilot before any live transport runs."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.ledger_path = directory / "ledger.json"

    def execute_preflight(
        self,
        *,
        project: str,
        source_result_path: Path,
        approved_cumulative_cap_usd: str,
        next_call_worst_case_usd: str,
        workspace_fingerprint_valid: bool,
    ) -> dict[str, Any]:
        if project != "btest":
            raise AutoSafeContinuePilotError("BTEST_PILOT_ONLY")
        cap = Decimal(approved_cumulative_cap_usd)
        if cap != Decimal("0.64"):
            raise AutoSafeContinuePilotError("PILOT_CAP_BINDING_MISMATCH")
        result_raw = source_result_path.read_bytes()
        result = json.loads(result_raw.decode("utf-8"))
        if result.get("status") != "COMPLETED" or result.get("gate") != "SAFE_CONTINUE":
            raise AutoSafeContinuePilotError("SAFE_CONTINUE_SOURCE_RESULT_REQUIRED")

        source_result_sha256 = hashlib.sha256(result_raw).hexdigest()
        run_id = f"auto-safe-pilot-{source_result_sha256[:16]}-cap064"
        ledger = self._read_ledger()
        if run_id in ledger["runs"]:
            raise AutoSafeContinuePilotError("PILOT_RUN_ALREADY_RECORDED")

        evidence_value = result.get("auto_advance_evidence")
        try:
            validated_evidence = validate_auto_advance_evidence(evidence_value)
        except ApiMainlineBootstrapError as error:
            reason = str(error)
            decision = {
                "decision": "STOP_AUTO_ADVANCE",
                "project_status": "WAITING_FOR_USER",
                "stop_reason": (
                    "AUTO_ADVANCE_VALIDATION_EVIDENCE_MISSING"
                    if evidence_value is None else reason
                ),
                "next_cycle": None,
                "codex_retry_count": 0,
                "mainline_retry_count": 0,
                "model_fallback_count": 0,
                "automatic_approval": False,
            }
        else:
            evidence = AutoAdvanceEvidence(
                gate=result["gate"],
                resolution_kind=validated_evidence["resolution_kind"],
                task_transition=validated_evidence["task_transition"],
                next_step_basis=validated_evidence["next_step_basis"],
                source_refs=tuple(validated_evidence["source_refs"]),
                deterministic_validation=validated_evidence["deterministic_validation"],
                task_alignment=validated_evidence["task_alignment"],
                evidence_sufficiency=validated_evidence["evidence_sufficiency"],
                user_required=bool(result.get("user_required", False)),
                blocker=result.get("blocker"),
                workspace_fingerprint_valid=workspace_fingerprint_valid,
                approval_input_required=False,
            )
            decision = evaluate_auto_advance(
                evidence,
                cycles_completed=0,
                cumulative_cost_usd="0",
                next_call_worst_case_usd=next_call_worst_case_usd,
                approved_cumulative_cap_usd=str(cap),
            )

        approval = {
            "record_type": "AUTO_SAFE_CONTINUE_PILOT_ONE_TIME_APPROVAL",
            "version": PILOT_RUN_VERSION,
            "run_id": run_id,
            "project": project,
            "source_result_sha256": source_result_sha256,
            "approved_max_cycles": 2,
            "approved_cumulative_cap_usd": str(cap),
            "retry_count": 0,
            "fallback_count": 0,
            "codex_auto_approval": False,
            "explicit_user_instruction": True,
            "approved_at": _now(),
        }
        approval_sha256 = _atomic_json(self.directory / f"{run_id}-approval.json", approval)
        terminal = {
            "record_type": "AUTO_SAFE_CONTINUE_PILOT_RESULT",
            "version": PILOT_RUN_VERSION,
            "run_id": run_id,
            "project": project,
            "approval_record_sha256": approval_sha256,
            "source_result_sha256": source_result_sha256,
            "status": "STOPPED" if decision["decision"] == "STOP_AUTO_ADVANCE" else "READY",
            "decision": decision,
            "cycles_completed": 0,
            "mainline_api_calls": 0,
            "codex_turns": 0,
            "dispatch_count": 0,
            "retry_count": 0,
            "fallback_count": 0,
            "cumulative_usage_based_cost_usd": "0",
            "workspace_fingerprint_valid": workspace_fingerprint_valid,
            "approval_input_required": False,
            "completed_at": _now(),
        }
        terminal["result_sha256"] = _sha256_json(terminal)
        result_file_sha256 = _atomic_json(self.directory / f"{run_id}-result.json", terminal)
        ledger["runs"][run_id] = {
            "project": project,
            "status": terminal["status"],
            "stop_reason": decision.get("stop_reason"),
            "cycles_completed": 0,
            "mainline_api_calls": 0,
            "codex_turns": 0,
            "approval_record_sha256": approval_sha256,
            "result_file_sha256": result_file_sha256,
            "completed_at": terminal["completed_at"],
        }
        _atomic_json(self.ledger_path, ledger)
        return terminal

    def _read_ledger(self) -> dict[str, Any]:
        if not self.ledger_path.is_file():
            return {"version": PILOT_RUN_VERSION, "runs": {}}
        value = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        if value.get("version") != PILOT_RUN_VERSION or not isinstance(value.get("runs"), dict):
            raise AutoSafeContinuePilotError("PILOT_LEDGER_INVALID")
        return value
