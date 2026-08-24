from __future__ import annotations

import hashlib
import json
import os
import time
from decimal import Decimal
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from .api_mainline import API_MAINLINE_NODE_ID
from .api_mainline_bootstrap import (
    MODEL,
    TIMEOUT_SECONDS,
    _cost_preflight,
)
from .api_mainline_run import HttpResult, Transport, _load_named_secret, default_transport
from .control_plane import ControlPlaneError, OrchestrationControlStore
from .credentials import DEFAULT_ENV_FILE
from .fixtures import SECRET_PATTERNS
from .forensic import parse_error_metadata, sanitize_error_message
from .manifest import canonical_json, sha256_json
from .pricing import SOL_PROPOSAL_PRICING, estimate_usage_cost, pricing_record_payload
from .response_pipeline import capture_response_bytes, extract_output_text
from .api_mainline_continuation import (
    CONTINUATION_MAX_OUTPUT_TOKENS,
    CONTINUATION_PROMPT_VERSION,
    CONTINUATION_RUNTIME_VERSION,
    CONTINUATION_SCHEMA_VERSION,
    REVIEWER_SCHEMA_VERSION,
    build_continuation_request,
    validate_continuation_output,
    validation_provenance,
)
from .task_alignment import canonical_next_step_catalog
from .token_efficiency import (
    TOKEN_EFFICIENCY_POLICY_VERSION,
    EvaluationReuseStore,
    deterministic_continuation_precheck,
    evaluation_identity_sha256,
)


RETURN_RUNTIME_VERSION = "2b.5.2"
RETURN_LEDGER_VERSION = "2b.4.1"
RETURN_STATES = {"PREPARED", "SENT", "COMPLETED", "FAILED"}


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


class ApiMainlineReturnStore:
    """Prepare exact Codex results for a separately approved API Mainline turn."""

    def __init__(
        self,
        directory: Path,
        return_directory: Path,
        control: OrchestrationControlStore,
        *,
        dispatch_directory: Path | None = None,
        env_file: Path = DEFAULT_ENV_FILE,
        transport: Transport = default_transport,
    ) -> None:
        self.directory = directory
        self.return_directory = return_directory
        self.dispatch_directory = dispatch_directory or return_directory.parent / "dispatch-previews"
        self.control = control
        self.env_file = env_file
        self.transport = transport
        self.ledger_path = directory / "ledger.json"
        self._lock = Lock()
        directory.mkdir(parents=True, exist_ok=True)

    def _ledger(self) -> dict[str, Any]:
        if not self.ledger_path.is_file():
            return {"version": RETURN_LEDGER_VERSION, "returns": {}}
        value = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        if value.get("version") != RETURN_LEDGER_VERSION or not isinstance(value.get("returns"), dict):
            raise ControlPlaneError("INVALID_API_MAINLINE_RETURN_LEDGER")
        return value

    def _verified_return(self, project: str, return_id: str) -> tuple[dict[str, Any], str]:
        ledger_path = self.return_directory / "return-ledger.json"
        artifact_path = self.return_directory / f"{return_id}.json"
        if not ledger_path.is_file() or not artifact_path.is_file():
            raise ControlPlaneError("RETURN_HANDOFF_ARTIFACT_MISSING")
        return_ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        entry = return_ledger.get("returns", {}).get(return_id)
        raw = artifact_path.read_bytes()
        artifact = json.loads(raw.decode("utf-8"))
        if (
            not isinstance(entry, dict)
            or entry.get("project") != project
            or entry.get("artifact_sha256") != _sha256_bytes(raw)
            or artifact.get("return_envelope_sha256") != entry.get("return_envelope_sha256")
            or artifact.get("destination_node", {}).get("node_id") != API_MAINLINE_NODE_ID
            or artifact.get("destination_node", {}).get("transport_kind") != "OPENAI_RESPONSES"
            or artifact.get("state") != "PREPARED"
            or artifact.get("actual_mainline_send_count") != 0
        ):
            raise ControlPlaneError("API_MAINLINE_RETURN_HANDOFF_CHANGED")
        exact_result = artifact.get("result_content")
        if (
            not isinstance(exact_result, str)
            or not exact_result
            or _sha256_bytes(exact_result.encode("utf-8")) != artifact.get("result_content_sha256")
        ):
            raise ControlPlaneError("API_MAINLINE_RETURN_CONTENT_CHANGED")
        return artifact, _sha256_bytes(raw)

    def prepare(self, project: str, return_id: str) -> dict[str, Any]:
        artifact, artifact_sha256 = self._verified_return(project, return_id)
        context = self.control.api_mainline_return_context(project)
        exact_result = artifact["result_content"]
        dispatch_path = self.dispatch_directory / f"{artifact['source_dispatch_id']}.json"
        if not dispatch_path.is_file():
            raise ControlPlaneError("SOURCE_DISPATCH_TASK_MISSING")
        dispatch_raw = dispatch_path.read_bytes()
        dispatch = json.loads(dispatch_raw.decode("utf-8"))
        task_text = (dispatch.get("rendered_message") or {}).get("message")
        if (
            not isinstance(task_text, str)
            or not task_text
            or _sha256_bytes(task_text.encode("utf-8")) != artifact.get("originating_task_sha256")
        ):
            raise ControlPlaneError("SOURCE_DISPATCH_TASK_CHANGED")
        request, prompt, requirement_inventory = build_continuation_request(
            context["canonical_state"], task_text, exact_result,
        )
        # store=false requests remain stateless; local canonical state is replayed each turn.
        serialized_request = canonical_json(request)
        if any(pattern.search(serialized_request) for pattern in SECRET_PATTERNS):
            raise ControlPlaneError("API_MAINLINE_RETURN_SECRET_SCAN_FAILED")
        runtime = {
            "version": CONTINUATION_RUNTIME_VERSION,
            "endpoint": "/v1/responses",
            "conversation_mode": "STATELESS_CANONICAL_CONTINUATION",
            "provider_previous_response_id_transmitted": False,
            "timeout_seconds": TIMEOUT_SECONDS,
            "retry_count": 0,
            "fallback_count": 0,
            "dispatch_count": 0,
            "capture_before_parse": True,
            "live_api_locked": True,
            "credential_variable": "OPENAI_ORCHESTRATION_API_KEY",
            "forbidden_credential_fallbacks": ["OPENAI_API_KEY", "OPENAI_ADMIN_API_KEY"],
        }
        preflight = _cost_preflight(request)
        result_sha256 = artifact["result_content_sha256"]
        binding = {
            "return_id": return_id,
            "return_envelope_sha256": artifact["return_envelope_sha256"],
            "return_artifact_sha256": artifact_sha256,
            "source_dispatch_id": artifact["source_dispatch_id"],
            "exact_result_sha256": result_sha256,
            "report_content_sha256": result_sha256,
            "canonical_state_sha256": sha256_json(context["canonical_state"]),
            "next_step_catalog_sha256": sha256_json(
                canonical_next_step_catalog(context["canonical_state"]),
            ),
            "source_previous_response_id_sha256": _sha256_bytes(context["previous_response_id"].encode("utf-8")),
            "request_sha256": _sha256_bytes(serialized_request),
            "prompt_sha256": _sha256_bytes(prompt.encode("utf-8")),
            "stable_prefix_sha256": _sha256_bytes(prompt.encode("utf-8")),
            "dynamic_payload_sha256": _sha256_bytes(
                request["input"][1]["content"].encode("utf-8"),
            ),
            "structured_output_schema_sha256": sha256_json(request["text"]["format"]["schema"]),
            "runtime_protocol_sha256": sha256_json(runtime),
            "pricing_record_sha256": sha256_json(pricing_record_payload(SOL_PROPOSAL_PRICING)),
            "originating_task_sha256": artifact["originating_task_sha256"],
            "task_content_sha256": artifact["originating_task_sha256"],
            "requirement_inventory_sha256": sha256_json(requirement_inventory),
            "validation_provenance_sha256": validation_provenance()["provenance_sha256"],
            "token_efficiency_policy_version": TOKEN_EFFICIENCY_POLICY_VERSION,
        }
        binding["evaluation_identity_sha256"] = evaluation_identity_sha256(
            canonical_state_sha256=binding["canonical_state_sha256"],
            task_sha256=binding["task_content_sha256"],
            report_sha256=binding["report_content_sha256"],
            protocol_version=CONTINUATION_SCHEMA_VERSION,
            reviewer_schema_version=REVIEWER_SCHEMA_VERSION,
        )
        manifest = {
            "manifest_version": RETURN_RUNTIME_VERSION,
            "candidate_type": "API_MAINLINE_CODEX_RETURN",
            "conversation_mode": runtime["conversation_mode"],
            "model": MODEL,
            "prompt_version": CONTINUATION_PROMPT_VERSION,
            "schema_version": CONTINUATION_SCHEMA_VERSION,
            **binding,
            "max_output_tokens": CONTINUATION_MAX_OUTPUT_TOKENS,
            "timeout_seconds": TIMEOUT_SECONDS,
            "retry_count": 0,
            "fallback_count": 0,
            "planned_response_call_count": 1,
            **preflight,
            "approved_for_external_api": False,
        }
        manifest["approval_manifest_sha256"] = sha256_json(manifest)
        candidate = {
            "candidate_type": "API_MAINLINE_CODEX_RETURN",
            "manifest": manifest,
            "request_binding": binding,
            "canonical_state": context["canonical_state"],
            "exact_result": exact_result,
            "originating_task": task_text,
            "requirement_inventory": requirement_inventory,
            "validation_provenance": validation_provenance(),
            "request": request,
            "runtime_protocol": runtime,
            "preflight": preflight,
            "state": "PREPARED",
            "approved_for_external_api": False,
            "approval_record": False,
            "attempt_record": False,
            "result_record": False,
            "network_calls": 0,
            "dispatch_count": 0,
        }
        candidate_hash = sha256_json(candidate)
        candidate["candidate_sha256"] = candidate_hash
        self.verify(candidate)
        candidate_path = self.directory / f"{return_id}.json"
        with self._lock:
            ledger = self._ledger()
            if return_id in ledger["returns"] or candidate_path.exists() or any(
                entry.get("return_envelope_sha256") == artifact["return_envelope_sha256"]
                for entry in ledger["returns"].values()
            ):
                raise ControlPlaneError("DUPLICATE_API_MAINLINE_RETURN_BLOCKED")
            file_sha256 = _atomic_json(candidate_path, candidate)
            ledger["returns"][return_id] = {
                "project": project,
                "source_dispatch_id": artifact["source_dispatch_id"],
                "return_envelope_sha256": artifact["return_envelope_sha256"],
                "exact_result_sha256": result_sha256,
                "candidate_sha256": candidate_hash,
                "candidate_file_sha256": file_sha256,
                "approval_manifest_sha256": manifest["approval_manifest_sha256"],
                "state": "PREPARED",
                "transport_capability": "PREVIEW_READY_LIVE_API_LOCKED",
                "duplicate_status": "UNCONSUMED",
                "approval_state": "USER_APPROVAL_REQUIRED",
                "approved_for_external_api": False,
                "approval_record": False,
                "attempt_record": False,
                "result_record": False,
                "actual_mainline_send_count": 0,
                "network_calls": 0,
            }
            _atomic_json(self.ledger_path, ledger)
        return self.list_for_project(project)[-1]

    def _candidate(
        self,
        project: str,
        return_id: str,
        expected_candidate_sha256: str,
        expected_manifest_sha256: str,
    ) -> tuple[dict[str, Any], dict[str, Any], Path]:
        artifact, artifact_sha256 = self._verified_return(project, return_id)
        path = self.directory / f"{return_id}.json"
        if not path.is_file():
            raise ControlPlaneError("API_MAINLINE_RETURN_CANDIDATE_MISSING")
        raw = path.read_bytes()
        candidate = json.loads(raw.decode("utf-8"))
        self.verify(candidate)
        with self._lock:
            entry = self._ledger()["returns"].get(return_id)
        if (
            not isinstance(entry, dict)
            or entry.get("project") != project
            or entry.get("state") != "PREPARED"
            or entry.get("duplicate_status") != "UNCONSUMED"
            or entry.get("actual_mainline_send_count") != 0
            or entry.get("candidate_file_sha256") != _sha256_bytes(raw)
            or entry.get("candidate_sha256") != expected_candidate_sha256
            or entry.get("approval_manifest_sha256") != expected_manifest_sha256
            or candidate.get("candidate_sha256") != expected_candidate_sha256
            or candidate["manifest"].get("approval_manifest_sha256") != expected_manifest_sha256
            or candidate["request_binding"].get("return_artifact_sha256") != artifact_sha256
            or candidate["request_binding"].get("return_envelope_sha256")
            != artifact.get("return_envelope_sha256")
            or candidate["request_binding"].get("exact_result_sha256")
            != artifact.get("result_content_sha256")
        ):
            raise ControlPlaneError("API_MAINLINE_RETURN_APPROVAL_BINDING_MISMATCH")
        context = self.control.api_mainline_return_context(project)
        if sha256_json(context["canonical_state"]) != candidate["manifest"]["canonical_state_sha256"]:
            raise ControlPlaneError("API_MAINLINE_RETURN_CANONICAL_STATE_CHANGED")
        return candidate, entry, path

    def approve_and_execute(
        self,
        project: str,
        return_id: str,
        candidate_sha256: str,
        manifest_sha256: str,
    ) -> dict[str, Any]:
        candidate, _entry, _path = self._candidate(
            project, return_id, candidate_sha256, manifest_sha256,
        )
        reuse = EvaluationReuseStore(
            self.directory.parent / "orchestration-evaluation-reuse.json",
        ).lookup(candidate["request_binding"]["evaluation_identity_sha256"])
        if reuse is not None:
            raise ControlPlaneError("DUPLICATE_VALIDATED_EVALUATION_BLOCKED")
        api_key = _load_named_secret(self.env_file, "OPENAI_ORCHESTRATION_API_KEY")
        current_state_sha256 = sha256_json(
            self.control.api_mainline_return_context(project)["canonical_state"],
        )
        precheck = deterministic_continuation_precheck(
            candidate,
            current_canonical_state_sha256=current_state_sha256,
            credential_available=bool(api_key),
            already_consumed=False,
            route_binding_valid=(candidate["manifest"].get("return_id") == return_id),
            workspace_binding_valid=True,
        )
        if precheck["status"] != "PASS":
            raise ControlPlaneError(
                "API_MAINLINE_RETURN_DETERMINISTIC_PRECHECK_BLOCKED:"
                + ",".join(precheck["reasons"])
            )

        approval = {
            "record_type": "API_MAINLINE_RETURN_ONE_TIME_APPROVAL",
            "project": project,
            "return_id": return_id,
            "candidate_sha256": candidate_sha256,
            "approval_manifest_sha256": manifest_sha256,
            "return_envelope_sha256": candidate["manifest"]["return_envelope_sha256"],
            "exact_result_sha256": candidate["manifest"]["exact_result_sha256"],
            "canonical_state_sha256": candidate["manifest"]["canonical_state_sha256"],
            "approved_cost_cap_usd": candidate["manifest"]["proposed_single_call_cap_usd"],
            "explicit_user_action": True,
            "approved_at": _now(),
        }
        with self._lock:
            ledger = self._ledger()
            entry = ledger["returns"].get(return_id)
            if (
                not isinstance(entry, dict)
                or entry.get("state") != "PREPARED"
                or entry.get("duplicate_status") != "UNCONSUMED"
                or entry.get("approval_record") is not False
                or entry.get("attempt_record") is not False
                or entry.get("result_record") is not False
            ):
                raise ControlPlaneError("API_MAINLINE_RETURN_ALREADY_CONSUMED")
            approval_hash = _atomic_json(self.directory / f"{return_id}-approval.json", approval)
            attempt = {
                "record_type": "ATTEMPT_STARTED",
                "status": "SENT",
                "project": project,
                "return_id": return_id,
                "approval_manifest_sha256": manifest_sha256,
                "approval_record_sha256": approval_hash,
                "attempt_count": 1,
                "network_calls": 0,
                "retry_count": 0,
                "fallback_count": 0,
                "dispatch_count": 0,
                "started_at": _now(),
            }
            attempt_hash = _atomic_json(self.directory / f"{return_id}-attempt.json", attempt)
            entry.update({
                "state": "SENT",
                "transport_capability": "OPENAI_RESPONSES_IN_PROGRESS",
                "duplicate_status": "CONSUMED",
                "approval_record": True,
                "attempt_record": True,
                "attempt_record_sha256": attempt_hash,
                "approval_state": "APPROVED",
            })
            _atomic_json(self.ledger_path, ledger)

        run_dir = self.directory / return_id
        started = time.monotonic()
        network_calls = 0
        try:
            network_calls = 1
            http = self.transport(
                candidate["request"], api_key, float(candidate["manifest"]["timeout_seconds"]),
            )
            latency_ms = round((time.monotonic() - started) * 1000)
            capture = capture_response_bytes(
                http.body, run_dir, request_id=http.headers.get("x-request-id"),
            )
            if http.status != 200:
                metadata = parse_error_metadata(
                    http_status=http.status, headers=http.headers, body=http.body,
                )
                raise ControlPlaneError(json.dumps(metadata, ensure_ascii=True))
            response = json.loads(http.body.decode("utf-8"))
            output = json.loads(extract_output_text(response) or "")
            expected_requirement_ids = {
                item["requirement_id"] for item in candidate["requirement_inventory"]
            }
            validated, auto_advance_evidence = validate_continuation_output(
                output, expected_requirement_ids, candidate["canonical_state"],
            )
            tokens, estimated = estimate_usage_cost(
                SOL_PROPOSAL_PRICING,
                response.get("usage") or {},
                expected_pricing_sha256=candidate["manifest"]["pricing_record_sha256"],
            )
            response_id = str(response.get("id") or "")
            if not response_id:
                raise ControlPlaneError("OPENAI_RESPONSE_ID_MISSING")
            result_core = {
                "status": "COMPLETED",
                "http_status": http.status,
                "provider_status": response.get("status"),
                "response_id": response_id,
                "model": response.get("model") or candidate["manifest"]["model"],
                "latency_ms": latency_ms,
                "parsed_action": validated["action"],
                "gate": validated["gate"],
                "destination": validated["destination"],
                "state_delta": validated["updated_state_delta"],
                "decision_packet": validated["decision_packet"],
                "blocker": validated["blocker"],
                "auto_advance_evidence": auto_advance_evidence,
                "next_handoff": self._prepared_handoff(validated, candidate),
                "token_usage": tokens,
                "usage_based_estimated_cost_usd": str(estimated),
                "actual_cost_usd": None,
                "actual_cost_status": "NOT_RECONCILED",
                "capture": capture,
                "retry_count": 0,
                "fallback_count": 0,
                "dispatch_count": 0,
                "codex_turn_count": 0,
                "network_calls": network_calls,
            }
            result_hash = sha256_json(result_core)
            self.control.apply_api_mainline_turn(
                project,
                validated,
                response_id=response_id,
                model=result_core["model"],
                user_input_sha256=candidate["manifest"]["exact_result_sha256"],
                result_sha256=result_hash,
                return_id=return_id,
            )
            result = {
                **result_core,
                "canonical_state_delta_applied": True,
                "result_sha256": result_hash,
                "completed_at": _now(),
            }
            result_path = self.directory / f"{return_id}-result.json"
            _atomic_json(result_path, result)
            EvaluationReuseStore(
                self.directory.parent / "orchestration-evaluation-reuse.json",
            ).register_validated(
                candidate["request_binding"]["evaluation_identity_sha256"],
                result_sha256=result_hash,
                result_artifact=str(result_path),
                protocol_version=candidate["manifest"]["schema_version"],
                reviewer_schema_version=validation_provenance()["reviewer_schema_version"],
            )
            self._finish(return_id, result)
            return self._public(result)
        except Exception as error:
            failure = {
                "status": "FAILED",
                "error": sanitize_error_message(str(error)),
                "latency_ms": round((time.monotonic() - started) * 1000),
                "network_calls": network_calls,
                "retry_count": 0,
                "fallback_count": 0,
                "dispatch_count": 0,
                "codex_turn_count": 0,
                "failed_at": _now(),
            }
            _atomic_json(self.directory / f"{return_id}-failure.json", failure)
            self._finish(return_id, failure)
            raise ControlPlaneError(failure["error"]) from error

    def _prepared_handoff(
        self, output: dict[str, Any], candidate: dict[str, Any],
    ) -> dict[str, Any] | None:
        if output["action"] != "HANDOFF_CODEX":
            return None
        message = output["handoff_message"]
        return {
            "status": "PREPARED",
            "destination_node_id": "BTEST_CODEX_WORKER",
            "originating_return_id": candidate["manifest"]["return_id"],
            "originating_result_sha256": candidate["manifest"]["exact_result_sha256"],
            "exact_message_sha256": _sha256_bytes(message.encode("utf-8")),
            "exact_message": message,
            "approval_record": False,
            "attempt_record": False,
            "dispatch_count": 0,
        }

    def _finish(self, return_id: str, terminal: dict[str, Any]) -> None:
        with self._lock:
            ledger = self._ledger()
            entry = ledger["returns"][return_id]
            entry.update({
                "state": terminal["status"],
                "transport_capability": "CONSUMED",
                "duplicate_status": "CONSUMED",
                "result_record": True,
                "actual_mainline_send_count": terminal["network_calls"],
                "network_calls": terminal["network_calls"],
                "parsed_action": terminal.get("parsed_action"),
                "gate": terminal.get("gate"),
                "destination": terminal.get("destination"),
                "next_handoff_state": (terminal.get("next_handoff") or {}).get("status"),
                "decision_packet_state": (
                    "PREPARED" if terminal.get("decision_packet") is not None else None
                ),
                "error": terminal.get("error"),
                "terminal_at": _now(),
            })
            _atomic_json(self.ledger_path, ledger)

    @staticmethod
    def _public(record: dict[str, Any]) -> dict[str, Any]:
        return {key: record.get(key) for key in (
            "status", "http_status", "provider_status", "response_id", "model", "latency_ms",
            "parsed_action", "gate", "destination", "canonical_state_delta_applied",
            "decision_packet", "blocker", "next_handoff", "token_usage",
            "auto_advance_evidence",
            "usage_based_estimated_cost_usd", "actual_cost_status", "network_calls",
            "retry_count", "fallback_count", "dispatch_count", "codex_turn_count",
        )}

    @staticmethod
    def verify(candidate: dict[str, Any]) -> None:
        if (
            candidate.get("state") not in RETURN_STATES
            or candidate.get("state") != "PREPARED"
            or candidate.get("approved_for_external_api") is not False
            or candidate.get("approval_record") is not False
            or candidate.get("attempt_record") is not False
            or candidate.get("result_record") is not False
            or candidate.get("network_calls") != 0
            or candidate.get("dispatch_count") != 0
        ):
            raise ControlPlaneError("API_MAINLINE_RETURN_NOT_PRISTINE")
        unsigned = dict(candidate)
        supplied_candidate_hash = unsigned.pop("candidate_sha256", None)
        if supplied_candidate_hash != sha256_json(unsigned):
            raise ControlPlaneError("API_MAINLINE_RETURN_CANDIDATE_HASH_MISMATCH")
        manifest = candidate["manifest"]
        unsigned_manifest = dict(manifest)
        supplied_manifest_hash = unsigned_manifest.pop("approval_manifest_sha256", None)
        if supplied_manifest_hash != sha256_json(unsigned_manifest):
            raise ControlPlaneError("API_MAINLINE_RETURN_MANIFEST_HASH_MISMATCH")
        binding = candidate["request_binding"]
        request = candidate["request"]
        runtime = candidate["runtime_protocol"]
        exact_result = candidate["exact_result"]
        expected = {
            "exact_result_sha256": _sha256_bytes(exact_result.encode("utf-8")),
            "canonical_state_sha256": sha256_json(candidate["canonical_state"]),
            "next_step_catalog_sha256": sha256_json(
                canonical_next_step_catalog(candidate["canonical_state"]),
            ),
            "request_sha256": _sha256_bytes(canonical_json(request)),
            "prompt_sha256": _sha256_bytes(request["input"][0]["content"].encode("utf-8")),
            "stable_prefix_sha256": _sha256_bytes(
                request["input"][0]["content"].encode("utf-8"),
            ),
            "dynamic_payload_sha256": _sha256_bytes(
                request["input"][1]["content"].encode("utf-8"),
            ),
            "structured_output_schema_sha256": sha256_json(request["text"]["format"]["schema"]),
            "runtime_protocol_sha256": sha256_json(runtime),
            "pricing_record_sha256": sha256_json(pricing_record_payload(SOL_PROPOSAL_PRICING)),
            "token_efficiency_policy_version": TOKEN_EFFICIENCY_POLICY_VERSION,
        }
        expected["evaluation_identity_sha256"] = evaluation_identity_sha256(
            canonical_state_sha256=expected["canonical_state_sha256"],
            task_sha256=binding["task_content_sha256"],
            report_sha256=binding["report_content_sha256"],
            protocol_version=manifest["schema_version"],
            reviewer_schema_version=validation_provenance()["reviewer_schema_version"],
        )
        if any(binding.get(key) != value for key, value in expected.items()):
            raise ControlPlaneError("API_MAINLINE_RETURN_BINDING_MISMATCH")
        if any(manifest.get(key) != value for key, value in binding.items()):
            raise ControlPlaneError("API_MAINLINE_RETURN_MANIFEST_BINDING_MISMATCH")
        if candidate["preflight"] != _cost_preflight(request):
            raise ControlPlaneError("API_MAINLINE_RETURN_COST_PREFLIGHT_MISMATCH")
        if any(manifest.get(key) != value for key, value in candidate["preflight"].items()):
            raise ControlPlaneError("API_MAINLINE_RETURN_MANIFEST_COST_MISMATCH")
        if Decimal(manifest["hard_worst_case_cost_usd"]) > Decimal(
            manifest["proposed_single_call_cap_usd"]
        ):
            raise ControlPlaneError("API_MAINLINE_RETURN_BUDGET_BLOCKED")
        try:
            dynamic_payload = json.loads(candidate["request"]["input"][1]["content"])
        except (TypeError, json.JSONDecodeError) as error:
            raise ControlPlaneError("API_MAINLINE_RETURN_DYNAMIC_PAYLOAD_INVALID") from error
        if dynamic_payload.get("latest_codex_report") != candidate["exact_result"]:
            raise ControlPlaneError("API_MAINLINE_RETURN_EXACT_PAYLOAD_MISMATCH")
        if "previous_response_id" in candidate["request"]:
            raise ControlPlaneError("API_MAINLINE_RETURN_STATEFUL_REQUEST_FORBIDDEN")
        if candidate["runtime_protocol"].get("live_api_locked") is not True:
            raise ControlPlaneError("API_MAINLINE_RETURN_LIVE_LOCK_MISSING")
        if candidate.get("manifest", {}).get("schema_version") == CONTINUATION_SCHEMA_VERSION:
            inventory = candidate.get("requirement_inventory")
            provenance = candidate.get("validation_provenance")
            if (
                not isinstance(inventory, list)
                or binding.get("originating_task_sha256")
                != _sha256_bytes(str(candidate.get("originating_task") or "").encode("utf-8"))
                or binding.get("requirement_inventory_sha256") != sha256_json(inventory)
                or provenance != validation_provenance()
                or binding.get("validation_provenance_sha256") != provenance["provenance_sha256"]
            ):
                raise ControlPlaneError("API_MAINLINE_RETURN_VALIDATION_BINDING_MISMATCH")

    def list_for_project(self, project: str) -> list[dict[str, Any]]:
        with self._lock:
            entries = self._ledger()["returns"]
        values = []
        for return_id, entry in entries.items():
            if entry.get("project") != project:
                continue
            value = {"return_id": return_id, **entry}
            if value.get("state") == "PREPARED" and value.get("duplicate_status") == "UNCONSUMED":
                if not value.get("approval_state"):
                    value["approval_state"] = "USER_APPROVAL_REQUIRED"
            values.append(value)
        return values

    def latest_sealed_cost_preflight(self, project: str) -> dict[str, Any] | None:
        """Return the newest integrity-checked cost basis without exposing request content."""
        with self._lock:
            entries = list(self._ledger()["returns"].items())
        for return_id, entry in reversed(entries):
            if entry.get("project") != project:
                continue
            path = self.directory / f"{return_id}.json"
            if not path.is_file():
                continue
            raw = path.read_bytes()
            if entry.get("candidate_file_sha256") != _sha256_bytes(raw):
                raise ControlPlaneError("API_MAINLINE_RETURN_CANDIDATE_FILE_CHANGED")
            candidate = json.loads(raw.decode("utf-8"))
            self.verify(candidate)
            return {
                "return_id": return_id,
                "candidate_sha256": candidate["candidate_sha256"],
                **candidate["preflight"],
            }
        return None
