from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Mapping

from .api_mainline import API_MAINLINE_NODE_ID
from .api_mainline_bootstrap import validate_bootstrap_output, verify_bootstrap_candidate
from .api_mainline_start import ApiMainlineStartError, ApiMainlineStartStore
from .credentials import DEFAULT_ENV_FILE
from .forensic import parse_error_metadata, sanitize_error_message
from .manifest import canonical_json, sha256_json
from .pricing import SOL_PROPOSAL_PRICING, estimate_usage_cost, pricing_record_sha256
from .response_pipeline import capture_response_bytes, extract_output_text


RUN_LEDGER_VERSION = "2c.2c.1"


class ApiMainlineRunError(RuntimeError):
    pass


@dataclass(frozen=True)
class HttpResult:
    status: int
    headers: Mapping[str, str]
    body: bytes


Transport = Callable[[dict[str, Any], str, float], HttpResult]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _atomic_json(path: Path, value: dict[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=True, indent=2).encode("utf-8") + b"\n"
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(payload)
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    os.replace(temporary, path)
    return _sha256_bytes(payload)


def _load_named_secret(path: Path, name: str) -> str | None:
    value = os.getenv(name, "").strip()
    if value:
        return value
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, candidate = line.partition("=")
        if separator and key.strip() == name and candidate.strip():
            return candidate.strip()
    return None


def default_transport(request_body: dict[str, Any], api_key: str, timeout: float) -> HttpResult:
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=canonical_json(request_body),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return HttpResult(response.status, dict(response.headers.items()), response.read())
    except urllib.error.HTTPError as error:
        return HttpResult(error.code, dict(error.headers.items()), error.read())


class ApiMainlineRunStore:
    """Exactly-once approval and execution ledger for API Mainline user starts."""

    def __init__(
        self,
        directory: Path,
        starts: ApiMainlineStartStore,
        control_plane: Any,
        *,
        env_file: Path = DEFAULT_ENV_FILE,
        transport: Transport = default_transport,
    ) -> None:
        self.directory = directory
        self.starts = starts
        self.control_plane = control_plane
        self.env_file = env_file
        self.transport = transport
        self.ledger_path = directory / "ledger.json"
        self._lock = Lock()
        directory.mkdir(parents=True, exist_ok=True)

    def _ledger(self) -> dict[str, Any]:
        if not self.ledger_path.is_file():
            return {"version": RUN_LEDGER_VERSION, "runs": {}}
        value = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        if value.get("version") != RUN_LEDGER_VERSION or not isinstance(value.get("runs"), dict):
            raise ApiMainlineRunError("INVALID_API_MAINLINE_RUN_LEDGER")
        return value

    def _write_ledger(self, value: dict[str, Any]) -> None:
        _atomic_json(self.ledger_path, value)

    def _candidate(self, project: str, expected_candidate: str, expected_manifest: str) -> tuple[dict[str, Any], dict[str, Any], Path]:
        status = self.starts.status(project)
        if status.get("status") != "READY" or status.get("approval_state") != "USER_APPROVAL_REQUIRED":
            raise ApiMainlineRunError("API_MAINLINE_CANDIDATE_NOT_READY")
        if status.get("candidate_file_sha256") != expected_candidate or status.get("approval_manifest_sha256") != expected_manifest:
            raise ApiMainlineRunError("API_MAINLINE_APPROVAL_BINDING_MISMATCH")
        ledger = self.starts._load_ledger()
        start = next((item for item in reversed(ledger["records"]) if item.get("status") == "READY"), None)
        if start is None:
            raise ApiMainlineRunError("API_MAINLINE_CANDIDATE_NOT_READY")
        path = self.starts.directory / start["candidate_file"]
        candidate = json.loads(path.read_text(encoding="utf-8"))
        verify_bootstrap_candidate(candidate)
        if _sha256_bytes(path.read_bytes()) != expected_candidate:
            raise ApiMainlineRunError("API_MAINLINE_CANDIDATE_HASH_MISMATCH")
        if candidate["manifest"]["approval_manifest_sha256"] != expected_manifest:
            raise ApiMainlineRunError("API_MAINLINE_MANIFEST_HASH_MISMATCH")
        if Decimal(candidate["preflight"]["hard_worst_case_cost_usd"]) > Decimal(candidate["manifest"]["proposed_single_call_cap_usd"]):
            raise ApiMainlineRunError("API_MAINLINE_BUDGET_BLOCKED")
        return start, candidate, path

    def cancel(self, project: str, candidate_sha256: str, manifest_sha256: str) -> dict[str, Any]:
        self._candidate(project, candidate_sha256, manifest_sha256)
        start = self.starts.claim_for_decision(project, candidate_sha256, manifest_sha256)
        with self._lock:
            ledger = self._ledger()
            if manifest_sha256 in ledger["runs"]:
                raise ApiMainlineRunError("API_MAINLINE_CANDIDATE_ALREADY_DECIDED")
            record = {
                "status": "CANCELLED", "project": project,
                "candidate_file_sha256": candidate_sha256,
                "approval_manifest_sha256": manifest_sha256,
                "cancelled_at": _now(), "network_calls": 0,
                "retry_count": 0, "fallback_count": 0, "dispatch_count": 0,
            }
            _atomic_json(self.directory / f"{manifest_sha256}-cancellation.json", record)
            ledger["runs"][manifest_sha256] = record
            self._write_ledger(ledger)
        self._mark_start(start, "CANCELLED", approval_state="CANCELLED")
        return self._public(record)

    def status(self, project: str) -> dict[str, Any] | None:
        with self._lock:
            ledger = self._ledger()
            records = [
                (manifest_sha256, value)
                for manifest_sha256, value in ledger["runs"].items()
                if value.get("project") == project
            ]
        if not records:
            return None
        manifest_sha256, record = records[-1]
        if record.get("status") == "COMPLETED" and record.get("result_record"):
            result_path = self.directory / f"{manifest_sha256}-result.json"
            if result_path.is_file():
                result = json.loads(result_path.read_text(encoding="utf-8"))
                if isinstance(result, dict):
                    return self._public(result)
        return self._public(record)

    def prepared_handoff(self, project: str) -> dict[str, Any]:
        with self._lock:
            records = [
                (manifest_sha256, value)
                for manifest_sha256, value in self._ledger()["runs"].items()
                if value.get("project") == project
            ]
        for manifest_sha256, record in reversed(records):
            if record.get("status") != "COMPLETED" or not record.get("result_record"):
                continue
            result_path = self.directory / f"{manifest_sha256}-result.json"
            if not result_path.is_file():
                continue
            result_bytes = result_path.read_bytes()
            try:
                result = json.loads(result_bytes.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError) as error:
                raise ApiMainlineRunError("API_MAINLINE_RESULT_INVALID") from error
            handoff = result.get("handoff")
            if (
                result.get("status") != "COMPLETED"
                or result.get("parsed_action") != "HANDOFF_CODEX"
                or result.get("destination") != "CODEX_WORKER"
                or not isinstance(handoff, dict)
                or handoff.get("status") != "PREPARED"
                or handoff.get("destination_node_id") != "BTEST_CODEX_WORKER"
                or handoff.get("dispatch_count") != 0
            ):
                continue
            exact_message = handoff.get("exact_message")
            if not isinstance(exact_message, str) or not exact_message.strip():
                raise ApiMainlineRunError("API_MAINLINE_HANDOFF_INVALID")
            exact_hash = _sha256_bytes(exact_message.encode("utf-8"))
            if exact_hash != handoff.get("exact_message_sha256"):
                raise ApiMainlineRunError("API_MAINLINE_HANDOFF_CHANGED")
            return {
                "approval_manifest_sha256": manifest_sha256,
                "result_artifact_sha256": _sha256_bytes(result_bytes),
                "result_sha256": result.get("result_sha256"),
                "originating_user_input_sha256": handoff.get("originating_user_input_sha256"),
                "exact_message_sha256": exact_hash,
                "exact_message": exact_message,
                "destination_node_id": handoff["destination_node_id"],
            }
        raise ApiMainlineRunError("API_MAINLINE_PREPARED_HANDOFF_REQUIRED")

    def approve_and_execute(self, project: str, candidate_sha256: str, manifest_sha256: str) -> dict[str, Any]:
        start, candidate, _path = self._candidate(project, candidate_sha256, manifest_sha256)
        api_key = _load_named_secret(self.env_file, "OPENAI_ORCHESTRATION_API_KEY")
        if not api_key:
            raise ApiMainlineRunError("OPENAI_ORCHESTRATION_API_KEY_REQUIRED")
        start = self.starts.claim_for_decision(project, candidate_sha256, manifest_sha256)
        approved_at = _now()
        approval = {
            "record_type": "API_MAINLINE_ONE_TIME_APPROVAL",
            "project": project,
            "candidate_file_sha256": candidate_sha256,
            "approval_manifest_sha256": manifest_sha256,
            "user_input_sha256": candidate["manifest"]["user_input_sha256"],
            "canonical_state_sha256": candidate["manifest"]["canonical_state_sha256"],
            "authority": API_MAINLINE_NODE_ID,
            "approved_cost_cap_usd": candidate["manifest"]["proposed_single_call_cap_usd"],
            "explicit_user_action": True,
            "approved_at": approved_at,
        }
        with self._lock:
            ledger = self._ledger()
            if manifest_sha256 in ledger["runs"]:
                raise ApiMainlineRunError("API_MAINLINE_CANDIDATE_ALREADY_CONSUMED")
            approval_hash = _atomic_json(self.directory / f"{manifest_sha256}-approval.json", approval)
            attempt = {
                "record_type": "ATTEMPT_STARTED", "status": "SENDING",
                "project": project, "approval_manifest_sha256": manifest_sha256,
                "approval_record_sha256": approval_hash, "attempt_count": 1,
                "network_calls": 0, "retry_count": 0, "fallback_count": 0,
                "dispatch_count": 0, "started_at": _now(),
            }
            attempt_hash = _atomic_json(self.directory / f"{manifest_sha256}-attempt.json", attempt)
            record = {**attempt, "attempt_record_sha256": attempt_hash}
            ledger["runs"][manifest_sha256] = record
            self._write_ledger(ledger)
        self._mark_start(start, "SENDING", approval_state="APPROVED", approval_record=True, attempt_record=True)

        run_dir = self.directory / manifest_sha256
        started = time.monotonic()
        try:
            http = self.transport(candidate["request"], api_key, float(candidate["manifest"]["timeout_seconds"]))
            latency_ms = round((time.monotonic() - started) * 1000)
            capture = capture_response_bytes(http.body, run_dir, request_id=http.headers.get("x-request-id"))
            if http.status != 200:
                raise ApiMainlineRunError(json.dumps(parse_error_metadata(http_status=http.status, headers=http.headers, body=http.body), ensure_ascii=True))
            response = json.loads(http.body.decode("utf-8"))
            output = json.loads(extract_output_text(response) or "")
            validated = validate_bootstrap_output(output)
            tokens, estimated = estimate_usage_cost(
                SOL_PROPOSAL_PRICING,
                response.get("usage") or {},
                expected_pricing_sha256=candidate["manifest"]["pricing_record_sha256"],
            )
            response_id = str(response.get("id") or "")
            if not response_id:
                raise ApiMainlineRunError("OPENAI_RESPONSE_ID_MISSING")
            result_core = {
                "status": "COMPLETED", "http_status": http.status,
                "provider_status": response.get("status"), "response_id": response_id,
                "model": response.get("model") or candidate["manifest"]["model"],
                "latency_ms": latency_ms, "parsed_action": validated["action"],
                "gate": validated["gate"], "destination": validated["destination"],
                "state_delta": validated["updated_state_delta"],
                "token_usage": tokens, "usage_based_estimated_cost_usd": str(estimated),
                "actual_cost_usd": None, "actual_cost_status": "NOT_RECONCILED",
                "handoff": self._prepared_handoff(validated, candidate),
                "capture": capture, "retry_count": 0, "fallback_count": 0,
                "dispatch_count": 0, "network_calls": 1,
            }
            result_hash = sha256_json(result_core)
            self.control_plane.apply_api_mainline_turn(
                project, validated, response_id=response_id,
                model=result_core["model"], user_input_sha256=candidate["manifest"]["user_input_sha256"],
                result_sha256=result_hash,
            )
            result = {**result_core, "canonical_state_delta_applied": True, "result_sha256": result_hash, "completed_at": _now()}
            _atomic_json(self.directory / f"{manifest_sha256}-result.json", result)
            self._finish(manifest_sha256, result)
            self._mark_start(start, "COMPLETED", approval_state="APPROVED", approval_record=True, attempt_record=True, result_record=True, network_calls=1)
            return self._public(result)
        except Exception as error:
            failure = {
                "status": "FAILED", "error": sanitize_error_message(str(error)),
                "latency_ms": round((time.monotonic() - started) * 1000),
                "network_calls": 1, "retry_count": 0, "fallback_count": 0,
                "dispatch_count": 0, "failed_at": _now(),
            }
            _atomic_json(self.directory / f"{manifest_sha256}-failure.json", failure)
            self._finish(manifest_sha256, failure)
            self._mark_start(start, "FAILED", approval_state="APPROVED", approval_record=True, attempt_record=True, result_record=True, network_calls=1)
            raise ApiMainlineRunError(failure["error"]) from error

    def _prepared_handoff(self, output: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any] | None:
        if output["action"] != "HANDOFF_CODEX":
            return None
        message = output["handoff_message"]
        return {
            "status": "PREPARED", "destination_node_id": "BTEST_CODEX_WORKER",
            "originating_user_input_sha256": candidate["manifest"]["user_input_sha256"],
            "exact_message_sha256": _sha256_bytes(message.encode("utf-8")),
            "exact_message": message, "dispatch_count": 0,
        }

    def _finish(self, manifest_sha256: str, terminal: dict[str, Any]) -> None:
        with self._lock:
            ledger = self._ledger()
            record = ledger["runs"][manifest_sha256]
            record.update({
                "status": terminal["status"], "network_calls": terminal["network_calls"],
                "result_record": True, "terminal_at": _now(),
            })
            self._write_ledger(ledger)

    def _mark_start(self, start: dict[str, Any], status: str, **changes: Any) -> None:
        with self.starts._lock:
            ledger = self.starts._load_ledger()
            record = next(item for item in ledger["records"] if item["approval_manifest_sha256"] == start["approval_manifest_sha256"])
            record.update({"status": status, **changes})
            self.starts._write_ledger(ledger)

    @staticmethod
    def _public(record: dict[str, Any]) -> dict[str, Any]:
        return {key: record.get(key) for key in (
            "status", "http_status", "provider_status", "response_id", "model", "latency_ms",
            "parsed_action", "gate", "destination", "canonical_state_delta_applied",
            "token_usage", "usage_based_estimated_cost_usd", "actual_cost_status", "handoff",
            "network_calls", "retry_count", "fallback_count", "dispatch_count",
        )}
