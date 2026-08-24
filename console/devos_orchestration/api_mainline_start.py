from __future__ import annotations

import copy
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from .api_mainline import API_MAINLINE_NODE_ID
from .api_mainline_bootstrap import (
    ApiMainlineBootstrapError,
    build_bootstrap_candidate,
    verify_bootstrap_candidate,
)
from .manifest import sha256_json


START_LEDGER_VERSION = "2c.2b.1"
MAX_INITIAL_REQUEST_BYTES = 131_072


class ApiMainlineStartError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


class ApiMainlineStartStore:
    """Append-only no-network candidates for user-initiated API Mainline turns."""

    def __init__(self, directory: Path, control_plane: Any) -> None:
        self.directory = directory
        self.control_plane = control_plane
        self.ledger_path = directory / "ledger.json"
        self._lock = Lock()
        self.directory.mkdir(parents=True, exist_ok=True)

    def _project(self, project: str) -> dict[str, Any]:
        if project != "btest":
            raise ApiMainlineStartError("API_MAINLINE_START_BTEST_ONLY")
        projects = self.control_plane.list_projects().get("projects", [])
        value = next((item for item in projects if item.get("project") == project), None)
        if value is None:
            raise ApiMainlineStartError("UNKNOWN_PROJECT")
        mainline = value.get("mainline_state") or {}
        if (
            value.get("orchestration_enabled") is not True
            or mainline.get("authority") != API_MAINLINE_NODE_ID
            or (mainline.get("canonical_state") or {}).get("authority") != API_MAINLINE_NODE_ID
        ):
            raise ApiMainlineStartError("API_MAINLINE_AUTHORITY_REQUIRED")
        return value

    def _load_ledger(self) -> dict[str, Any]:
        if not self.ledger_path.is_file():
            return {"version": START_LEDGER_VERSION, "records": []}
        try:
            value = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ApiMainlineStartError("INVALID_API_MAINLINE_START_LEDGER") from error
        if value.get("version") != START_LEDGER_VERSION or not isinstance(value.get("records"), list):
            raise ApiMainlineStartError("INVALID_API_MAINLINE_START_LEDGER")
        return value

    def _write_ledger(self, value: dict[str, Any]) -> None:
        temporary = self.ledger_path.with_name(f".{self.ledger_path.name}.tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, self.ledger_path)

    def prepare(self, project: str, initial_request: str) -> dict[str, Any]:
        if not isinstance(initial_request, str) or not initial_request.strip():
            raise ApiMainlineStartError("INITIAL_REQUEST_REQUIRED")
        encoded = initial_request.encode("utf-8")
        if len(encoded) > MAX_INITIAL_REQUEST_BYTES:
            raise ApiMainlineStartError("INITIAL_REQUEST_TOO_LARGE")

        with self._lock:
            project_state = self._project(project)
            canonical_state = copy.deepcopy(project_state["mainline_state"]["canonical_state"])
            input_sha256 = _sha256_bytes(encoded)
            ledger = self._load_ledger()
            if any(item.get("status") in {"DECIDING", "SENDING"} for item in ledger["records"]):
                raise ApiMainlineStartError("API_MAINLINE_START_IN_FLIGHT")
            current = next(
                (item for item in reversed(ledger["records"]) if item["status"] == "READY"),
                None,
            )
            if current and current["user_input_sha256"] == input_sha256:
                candidate_path = self.directory / current["candidate_file"]
                if candidate_path.is_file():
                    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
                    verify_bootstrap_candidate(candidate)
                    if candidate["canonical_state"] == canonical_state:
                        return self._public(current)

            for record in ledger["records"]:
                if record["status"] == "READY":
                    record["status"] = "STALE"
                    record["approval_state"] = "STALE"
                    record["stale_reason"] = "USER_INPUT_OR_CANONICAL_STATE_CHANGED"
                    record["stale_at"] = _now()

            provisional = self.directory / ".candidate.tmp.json"
            candidate = build_bootstrap_candidate(
                provisional,
                canonical_state=canonical_state,
                user_input=initial_request,
                candidate_type="API_MAINLINE_USER_START",
                preserve_canonical_state=True,
            )
            approval_sha256 = candidate["manifest"]["approval_manifest_sha256"]
            candidate_file = f"api-mainline-user-start-{approval_sha256}.json"
            candidate_path = self.directory / candidate_file
            if candidate_path.exists():
                provisional.unlink(missing_ok=True)
                raise ApiMainlineStartError("API_MAINLINE_START_CANDIDATE_ALREADY_EXISTS")
            os.replace(provisional, candidate_path)
            record = {
                "record_version": START_LEDGER_VERSION,
                "project": project,
                "candidate_file": candidate_file,
                "candidate_file_sha256": _file_sha256(candidate_path),
                "approval_manifest_sha256": approval_sha256,
                "canonical_state_sha256": candidate["manifest"]["canonical_state_sha256"],
                "user_input_sha256": input_sha256,
                "model": candidate["manifest"]["model"],
                "proposed_hard_cap_usd": candidate["manifest"]["proposed_single_call_cap_usd"],
                "request_utf8_bytes": candidate["manifest"]["request_utf8_bytes"],
                "hard_input_token_upper_bound": candidate["manifest"]["hard_input_token_upper_bound"],
                "status": "READY",
                "approval_state": "USER_APPROVAL_REQUIRED",
                "approval_record": False,
                "attempt_record": False,
                "result_record": False,
                "network_calls": 0,
                "dispatch_count": 0,
                "created_at": _now(),
            }
            ledger["records"].append(record)
            self._write_ledger(ledger)
            return self._public(record)

    def claim_for_decision(
        self,
        project: str,
        candidate_file_sha256: str,
        approval_manifest_sha256: str,
    ) -> dict[str, Any]:
        """Atomically revalidate and reserve the exact candidate for one decision."""
        with self._lock:
            project_state = self._project(project)
            ledger = self._load_ledger()
            record = next(
                (item for item in reversed(ledger["records"]) if item.get("status") == "READY"),
                None,
            )
            if record is None:
                raise ApiMainlineStartError("API_MAINLINE_CANDIDATE_NOT_READY")
            if (
                record["candidate_file_sha256"] != candidate_file_sha256
                or record["approval_manifest_sha256"] != approval_manifest_sha256
            ):
                raise ApiMainlineStartError("API_MAINLINE_APPROVAL_BINDING_MISMATCH")
            path = self.directory / record["candidate_file"]
            candidate = json.loads(path.read_text(encoding="utf-8"))
            verify_bootstrap_candidate(candidate)
            if (
                _file_sha256(path) != candidate_file_sha256
                or candidate["manifest"]["approval_manifest_sha256"] != approval_manifest_sha256
                or sha256_json(project_state["mainline_state"]["canonical_state"])
                != record["canonical_state_sha256"]
            ):
                raise ApiMainlineStartError("API_MAINLINE_APPROVAL_BINDING_MISMATCH")
            record["status"] = "DECIDING"
            record["approval_state"] = "DECISION_IN_PROGRESS"
            record["decision_started_at"] = _now()
            self._write_ledger(ledger)
            return copy.deepcopy(record)

    def status(self, project: str) -> dict[str, Any]:
        if project != "btest":
            return self._empty("UNAVAILABLE_FOR_PROJECT")
        with self._lock:
            ledger = self._load_ledger()
            current = next(
                (item for item in reversed(ledger["records"]) if item["status"] == "READY"),
                None,
            )
            if current is None:
                return self._empty("NOT_PREPARED")
            candidate_path = self.directory / current["candidate_file"]
            try:
                candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
                verify_bootstrap_candidate(candidate)
                if (
                    _file_sha256(candidate_path) != current["candidate_file_sha256"]
                    or candidate["manifest"]["approval_manifest_sha256"]
                    != current["approval_manifest_sha256"]
                ):
                    raise ApiMainlineStartError("API_MAINLINE_START_BINDING_MISMATCH")
            except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
                value = self._public(current)
                value["status"] = "INVALID_CANDIDATE"
                value["approval_state"] = "BLOCKED"
                return value
            try:
                project_state = self._project(project)
            except ApiMainlineStartError:
                value = self._public(current)
                value["status"] = "STALE_AUTHORITY_CHANGED"
                value["approval_state"] = "STALE"
                return value
            current_state = project_state["mainline_state"]["canonical_state"]
            if sha256_json(current_state) != current["canonical_state_sha256"]:
                value = self._public(current)
                value["status"] = "STALE_CANONICAL_STATE_CHANGED"
                value["approval_state"] = "STALE"
                return value
            return self._public(current)

    @staticmethod
    def _empty(status: str) -> dict[str, Any]:
        return {
            "status": status,
            "authority_required": API_MAINLINE_NODE_ID,
            "model": None,
            "proposed_hard_cap_usd": None,
            "canonical_state_sha256": None,
            "user_input_sha256": None,
            "candidate_file_sha256": None,
            "approval_manifest_sha256": None,
            "approval_state": "NONE",
            "network_calls": 0,
            "dispatch_count": 0,
        }

    @staticmethod
    def _public(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": record["status"],
            "authority_required": API_MAINLINE_NODE_ID,
            "model": record["model"],
            "proposed_hard_cap_usd": record["proposed_hard_cap_usd"],
            "canonical_state_sha256": record["canonical_state_sha256"],
            "user_input_sha256": record["user_input_sha256"],
            "candidate_file_sha256": record["candidate_file_sha256"],
            "approval_manifest_sha256": record["approval_manifest_sha256"],
            "approval_state": record["approval_state"],
            "network_calls": record["network_calls"],
            "dispatch_count": record["dispatch_count"],
        }
