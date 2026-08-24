from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from .api_mainline_continuation import (
    validate_auto_advance_evidence,
    validate_continuation_output,
    validation_stage_status,
)
from .api_mainline_run import _load_named_secret, default_transport
from .auto_safe_continue import AutoAdvanceEvidence, evaluate_auto_advance
from .auto_safe_continue_retry import verify_retry_candidate
from .control_plane import ControlPlaneError
from .credentials import DEFAULT_ENV_FILE
from .forensic import parse_error_metadata, sanitize_error_message
from .manifest import sha256_json
from .pricing import SOL_PROPOSAL_PRICING, estimate_usage_cost
from .response_pipeline import capture_response_bytes, extract_output_text
from .workspace_guard import capture_workspace_binding
from .token_efficiency import (
    EvaluationReuseStore,
    deterministic_continuation_precheck,
)


LIVE_RUN_VERSION = "2c.auto-pilot-live.2"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _atomic_json(path: Path, value: dict[str, Any]) -> str:
    data = (json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    os.replace(temporary, path)
    return hashlib.sha256(data).hexdigest()


class AutoSafeContinueLiveRunner:
    def __init__(self, application: Any, runtime_dir: Path, workspace: Path) -> None:
        self.app = application
        self.runtime_dir = runtime_dir
        self.workspace = workspace
        self.directory = runtime_dir / "auto-safe-continue"

    def run(
        self,
        candidate_path: Path,
        *,
        expected_candidate_sha256: str,
        expected_manifest_sha256: str,
        approved_cap_usd: str,
        explicit_user_instruction_at: str,
    ) -> dict[str, Any]:
        raw = candidate_path.read_bytes()
        candidate = json.loads(raw.decode("utf-8"))
        verify_retry_candidate(candidate)
        manifest = candidate["manifest"]
        if (
            candidate["candidate_sha256"] != expected_candidate_sha256
            or manifest["approval_manifest_sha256"] != expected_manifest_sha256
            or Decimal(manifest["cumulative_hard_worst_case_usd"]) > Decimal(approved_cap_usd)
        ):
            raise ControlPlaneError("AUTO_SAFE_CONTINUE_RETRY_APPROVAL_MISMATCH")
        current_context = self.app.orchestration.api_mainline_return_context("btest")
        current_state_sha256 = sha256_json(current_context["canonical_state"])
        run_id = f"auto-safe-retry-{expected_manifest_sha256[:20]}"
        approval_path = self.directory / f"{run_id}-approval.json"
        attempt_path = self.directory / f"{run_id}-attempt.json"
        result_path = self.directory / f"{run_id}-result.json"
        if approval_path.exists() or attempt_path.exists() or result_path.exists():
            raise ControlPlaneError("AUTO_SAFE_CONTINUE_RETRY_ALREADY_CONSUMED")
        api_key = _load_named_secret(DEFAULT_ENV_FILE, "OPENAI_ORCHESTRATION_API_KEY")
        workspace = capture_workspace_binding("btest", self.workspace, distro="Ubuntu")
        precheck = deterministic_continuation_precheck(
            candidate,
            current_canonical_state_sha256=current_state_sha256,
            credential_available=bool(api_key),
            already_consumed=False,
            route_binding_valid=(
                candidate.get("candidate_type") == "AUTO_SAFE_CONTINUE_RETRY_PREFLIGHT"
            ),
            workspace_binding_valid=(
                candidate["binding"].get("workspace_fingerprint_sha256")
                == workspace.git_status_sha256
            ),
        )
        if precheck["status"] != "PASS":
            raise ControlPlaneError(
                "AUTO_SAFE_CONTINUE_DETERMINISTIC_PRECHECK_BLOCKED:"
                + ",".join(precheck["reasons"])
            )
        reuse_store = EvaluationReuseStore(
            self.runtime_dir / "orchestration-evaluation-reuse.json",
        )
        if reuse_store.lookup(candidate["binding"]["evaluation_identity_sha256"]):
            raise ControlPlaneError("DUPLICATE_VALIDATED_EVALUATION_BLOCKED")

        approval = {
            "record_type": "AUTO_SAFE_CONTINUE_RETRY_ONE_TIME_APPROVAL",
            "version": LIVE_RUN_VERSION,
            "run_id": run_id,
            "project": "btest",
            "candidate_sha256": expected_candidate_sha256,
            "approval_manifest_sha256": expected_manifest_sha256,
            "approved_cumulative_cap_usd": approved_cap_usd,
            "max_auto_cycles": 2,
            "retry_count": 0,
            "fallback_count": 0,
            "codex_auto_approval": False,
            "explicit_user_instruction_at": explicit_user_instruction_at,
            "recorded_at": _now(),
        }
        approval_hash = _atomic_json(approval_path, approval)
        attempt = {
            "record_type": "ATTEMPT_STARTED",
            "version": LIVE_RUN_VERSION,
            "run_id": run_id,
            "approval_record_sha256": approval_hash,
            "status": "RUNNING",
            "mainline_api_calls": 0,
            "codex_turns": 0,
            "retry_count": 0,
            "fallback_count": 0,
            "started_at": _now(),
        }
        _atomic_json(attempt_path, attempt)

        state: dict[str, Any] = {
            "run_id": run_id, "status": "RUNNING", "cycles": [],
            "cycles_completed": 0, "mainline_api_calls": 0, "codex_turns": 0,
            "dispatch_count": 0, "retry_count": 0, "fallback_count": 0,
            "cumulative_usage_based_cost_usd": "0", "stop_reason": None,
            "user_required": False, "codex_approval_required": False,
            "workspace_changed_externally": False,
        }
        try:
            state["mainline_api_calls"] = 1
            first = self._execute_first_mainline(candidate, api_key, run_id)
            reuse_store.register_validated(
                candidate["binding"]["evaluation_identity_sha256"],
                result_sha256=first["result_sha256"],
                result_artifact=str(self.directory / run_id / "mainline-1-result.json"),
                protocol_version=candidate["manifest"]["schema_version"],
                reviewer_schema_version=candidate["validation_provenance"]["reviewer_schema_version"],
            )
            state["cumulative_usage_based_cost_usd"] = first["usage_based_estimated_cost_usd"]
            source = self._source_handoff_from_first(candidate, first)
            if not self._advance_and_dispatch(state, first, source, cycle_number=1, approved_cap=approved_cap_usd):
                return self._finish(result_path, state)

            returned = self.app.return_handoffs.create(
                "btest", state["cycles"][-1]["handoff_id"],
                return_route_id="BTEST_CODEX_TO_MAINLINE_API",
            )
            prepared = self.app.api_mainline_returns.prepare("btest", returned["return_id"])
            return_candidate_path = self.app.api_mainline_returns.directory / f"{returned['return_id']}.json"
            return_candidate = json.loads(return_candidate_path.read_text(encoding="utf-8"))
            projected = Decimal(state["cumulative_usage_based_cost_usd"]) + Decimal(
                return_candidate["preflight"]["hard_worst_case_cost_usd"],
            )
            if projected > Decimal(approved_cap_usd):
                state["stop_reason"] = "CUMULATIVE_COST_CAP_EXCEEDED"
                return self._finish(result_path, state)
            state["mainline_api_calls"] = 2
            second = self.app.api_mainline_returns.approve_and_execute(
                "btest", returned["return_id"], prepared["candidate_sha256"],
                prepared["approval_manifest_sha256"],
            )
            state["cumulative_usage_based_cost_usd"] = str(
                Decimal(state["cumulative_usage_based_cost_usd"])
                + Decimal(second["usage_based_estimated_cost_usd"]),
            )
            full_second = json.loads(
                (self.app.api_mainline_returns.directory / f"{returned['return_id']}-result.json").read_text(encoding="utf-8"),
            )
            source = self._source_handoff_from_return(return_candidate, full_second)
            self._advance_and_dispatch(state, full_second, source, cycle_number=2, approved_cap=approved_cap_usd)
            if state["cycles_completed"] >= 2:
                state["stop_reason"] = "AUTO_CYCLE_LIMIT_REACHED"
                state["status"] = "COMPLETED"
            return self._finish(result_path, state)
        except Exception as error:
            state["status"] = "STOPPED"
            state["stop_reason"] = sanitize_error_message(str(error))
            state["validation_stages"] = validation_stage_status(error)
            state["codex_approval_required"] = "CODEX_APPROVAL" in state["stop_reason"]
            state["workspace_changed_externally"] = (
                "WORKSPACE_CHANGED_EXTERNALLY" in state["stop_reason"]
            )
            return self._finish(result_path, state)

    def _execute_first_mainline(self, candidate: dict[str, Any], api_key: str, run_id: str) -> dict[str, Any]:
        started = time.monotonic()
        http = default_transport(candidate["request"], api_key, float(candidate["manifest"]["timeout_seconds"]))
        capture = capture_response_bytes(
            http.body, self.directory / run_id / "mainline-1",
            request_id=http.headers.get("x-request-id"),
        )
        if http.status != 200:
            raise ControlPlaneError(json.dumps(parse_error_metadata(
                http_status=http.status, headers=http.headers, body=http.body,
            ), ensure_ascii=True))
        response = json.loads(http.body.decode("utf-8"))
        output = json.loads(extract_output_text(response) or "")
        expected = {item["requirement_id"] for item in candidate["requirement_inventory"]}
        canonical_state = self.app.orchestration.api_mainline_return_context("btest")["canonical_state"]
        validated, evidence = validate_continuation_output(output, expected, canonical_state)
        tokens, estimated = estimate_usage_cost(SOL_PROPOSAL_PRICING, response.get("usage") or {})
        result = {
            "status": "COMPLETED", "http_status": http.status,
            "provider_status": response.get("status"), "response_id": response.get("id"),
            "model": response.get("model"), "latency_ms": round((time.monotonic() - started) * 1000),
            "parsed_action": validated["action"], "gate": validated["gate"],
            "destination": validated["destination"], "handoff_message": validated["handoff_message"],
            "decision_packet": validated["decision_packet"], "blocker": validated["blocker"],
            "state_delta": validated["updated_state_delta"], "auto_advance_evidence": evidence,
            "token_usage": tokens, "usage_based_estimated_cost_usd": str(estimated),
            "capture": capture, "network_calls": 1, "retry_count": 0, "fallback_count": 0,
        }
        result["result_sha256"] = sha256_json(result)
        result["result_artifact_sha256"] = _atomic_json(
            self.directory / run_id / "mainline-1-result.json", result,
        )
        self.app.orchestration.apply_api_mainline_turn(
            "btest", validated, response_id=str(response.get("id") or ""),
            model=str(response.get("model") or ""),
            user_input_sha256=candidate["binding"]["report_content_sha256"],
            result_sha256=result["result_sha256"], return_id=run_id,
        )
        return result

    def _advance_and_dispatch(
        self, state: dict[str, Any], mainline: dict[str, Any], source: dict[str, Any],
        *, cycle_number: int, approved_cap: str,
    ) -> bool:
        evidence = validate_auto_advance_evidence(mainline.get("auto_advance_evidence"))
        seal = capture_workspace_binding("btest", self.workspace, distro="Ubuntu")
        self.app.orchestration.update_node(
            "btest", "BTEST_CODEX_WORKER", {"transport_ref": seal.as_transport_ref()},
        )
        decision = evaluate_auto_advance(
            AutoAdvanceEvidence(
                gate=mainline["gate"], resolution_kind=evidence["resolution_kind"],
                task_transition=evidence["task_transition"],
                next_step_basis=evidence["next_step_basis"],
                source_refs=tuple(evidence["source_refs"]),
                deterministic_validation=evidence["deterministic_validation"],
                task_alignment=evidence["task_alignment"],
                evidence_sufficiency=evidence["evidence_sufficiency"],
                user_required=mainline["gate"] == "USER_REQUIRED",
                blocker=mainline.get("blocker"), workspace_fingerprint_valid=True,
                approval_input_required=False,
            ),
            cycles_completed=cycle_number - 1,
            cumulative_cost_usd=state["cumulative_usage_based_cost_usd"],
            next_call_worst_case_usd="0.000000001",
            approved_cumulative_cap_usd=approved_cap,
        )
        cycle = {
            "cycle": cycle_number, "mainline_action": mainline["parsed_action"],
            "gate": mainline["gate"], "auto_advance_evidence": evidence,
            "mainline_latency_ms": mainline.get("latency_ms"),
            "mainline_token_usage": mainline.get("token_usage"),
            "mainline_cost_usd": mainline.get("usage_based_estimated_cost_usd"),
            "workspace_before": {
                "branch": seal.git_branch, "head": seal.git_head,
                "status_sha256": seal.git_status_sha256,
            },
        }
        state["cycles"].append(cycle)
        if decision["decision"] != "ALLOW_AUTO_ADVANCE":
            state["status"] = "STOPPED"
            state["stop_reason"] = decision["stop_reason"]
            state["user_required"] = decision["stop_reason"] == "USER_REQUIRED"
            return False
        preview = self.app.dispatch_previews.prepare_mainline_handoff("btest", source)
        completed = self.app.semi_auto_dispatch.approve_and_send(
            "btest", preview["handoff_id"], preview["envelope_sha256"],
        )
        cycle.update({
            "handoff_id": preview["handoff_id"], "dispatch_state": completed["state"],
            "codex_latency_seconds": completed.get("latency_seconds"),
            "codex_response_sha256": completed.get("response_text_sha256"),
        })
        state["cycles_completed"] += 1
        state["codex_turns"] += 1
        state["dispatch_count"] += 1
        return True

    @staticmethod
    def _source_handoff_from_first(candidate: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        message = result["handoff_message"]
        return {
            "approval_manifest_sha256": candidate["manifest"]["approval_manifest_sha256"],
            "result_artifact_sha256": result["result_artifact_sha256"],
            "result_sha256": result["result_sha256"],
            "originating_user_input_sha256": candidate["binding"]["report_content_sha256"],
            "exact_message_sha256": hashlib.sha256(message.encode()).hexdigest(),
            "exact_message": message, "destination_node_id": "BTEST_CODEX_WORKER",
        }

    @staticmethod
    def _source_handoff_from_return(candidate: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        message = result["next_handoff"]["exact_message"]
        return {
            "approval_manifest_sha256": candidate["manifest"]["approval_manifest_sha256"],
            "result_artifact_sha256": hashlib.sha256(
                (json.dumps(result, ensure_ascii=True, indent=2) + "\n").encode(),
            ).hexdigest(),
            "result_sha256": result["result_sha256"],
            "originating_user_input_sha256": candidate["manifest"]["exact_result_sha256"],
            "exact_message_sha256": hashlib.sha256(message.encode()).hexdigest(),
            "exact_message": message, "destination_node_id": "BTEST_CODEX_WORKER",
        }

    def _finish(self, result_path: Path, state: dict[str, Any]) -> dict[str, Any]:
        if state["status"] == "RUNNING":
            state["status"] = "STOPPED"
        state["completed_at"] = _now()
        state["result_sha256"] = sha256_json(state)
        _atomic_json(result_path, state)
        return state
