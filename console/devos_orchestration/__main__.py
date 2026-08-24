from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path

from .credentials import DEFAULT_ENV_FILE, inspect_env_file
from .candidate import build_cycle_handoff_candidate, build_parser_bound_candidate, build_v2_calibration_candidate
from .cycle_handoff import (
    REMOTE_SOURCE_BLOCKED,
    capture_legacy_fixture_cycle,
    capture_user_assisted_exact_cycle,
    classify_genuine_user_required_candidate,
    capture_cycle_handoff,
    compare_legacy_fixture,
    verify_cycle_handoff_packet,
    write_cycle_handoff_packet,
)
from .fixtures import discover_fixture_pair, import_fixture, write_json
from .manifest import build_manifest_from_files
from .forensic import audit_schema, audit_wire_request, build_wire_request, parse_error_metadata
from .pricing import SOL_PROPOSAL_PRICING
from .preflight import run_preflight
from .state import build_initial_state, validate_state
from .synthetic_suite import run_synthetic_suite
from .api_mainline_bootstrap import build_bootstrap_candidate, load_control_plane_canonical_state


def main() -> int:
    parser = argparse.ArgumentParser(description="DeveloperOS local-only orchestration Phase 1A tools")
    sub = parser.add_subparsers(dest="command", required=True)
    state_parser = sub.add_parser("state")
    state_parser.add_argument("--run-id", required=True)
    state_parser.add_argument("--project", default="bTest")
    state_parser.add_argument("--purpose", required=True)
    fixture_parser = sub.add_parser("fixture-discover")
    fixture_parser.add_argument("--root", type=Path, required=True)
    import_parser = sub.add_parser("fixture-import")
    import_parser.add_argument("--task-file", type=Path, required=True)
    import_parser.add_argument("--report-file", type=Path, required=True)
    import_parser.add_argument("--baseline-file", type=Path, required=True)
    import_parser.add_argument("--project", required=True)
    import_parser.add_argument("--historical-date", required=True)
    import_parser.add_argument("--output", type=Path)
    cycle_parser = sub.add_parser("cycle-capture")
    cycle_parser.add_argument("--messages-file", type=Path, required=True)
    cycle_parser.add_argument("--project", required=True)
    cycle_parser.add_argument("--cycle-id", required=True)
    cycle_parser.add_argument("--task-message-id", required=True)
    cycle_parser.add_argument("--report-message-id", required=True)
    cycle_parser.add_argument("--manual-review-message-id", required=True)
    cycle_parser.add_argument("--user-decision-message-id", action="append", default=[])
    cycle_parser.add_argument("--capture-timestamp")
    cycle_parser.add_argument("--previous-packet", type=Path)
    cycle_parser.add_argument("--output", type=Path, required=True)
    cycle_legacy_parser = sub.add_parser("cycle-capture-legacy")
    cycle_legacy_parser.add_argument("--task-file", type=Path, required=True)
    cycle_legacy_parser.add_argument("--report-file", type=Path, required=True)
    cycle_legacy_parser.add_argument("--baseline-file", type=Path, required=True)
    cycle_legacy_parser.add_argument("--project", required=True)
    cycle_legacy_parser.add_argument("--cycle-id", required=True)
    cycle_legacy_parser.add_argument("--capture-timestamp")
    cycle_legacy_parser.add_argument("--output", type=Path, required=True)
    assisted_parser = sub.add_parser("cycle-capture-user-assisted")
    assisted_parser.add_argument("--messages-file", type=Path, required=True)
    assisted_parser.add_argument("--manual-review-file", type=Path, required=True)
    assisted_parser.add_argument("--project", required=True)
    assisted_parser.add_argument("--cycle-id", required=True)
    assisted_parser.add_argument("--task-message-id", required=True)
    assisted_parser.add_argument("--report-message-id", required=True)
    assisted_parser.add_argument("--mainline-session-id", required=True)
    assisted_parser.add_argument("--manual-review-sequence", type=int, required=True)
    assisted_parser.add_argument("--user-decision-message-id", action="append", default=[])
    assisted_parser.add_argument(
        "--source-retrieval-status", required=True, choices=[REMOTE_SOURCE_BLOCKED],
    )
    assisted_parser.add_argument("--capture-timestamp")
    assisted_parser.add_argument("--output", type=Path, required=True)
    cycle_verify_parser = sub.add_parser("cycle-verify")
    cycle_verify_parser.add_argument("--packet", type=Path, required=True)
    cycle_equivalence_parser = sub.add_parser("cycle-legacy-equivalence")
    cycle_equivalence_parser.add_argument("--packet", type=Path, required=True)
    cycle_equivalence_parser.add_argument("--task-file", type=Path, required=True)
    cycle_equivalence_parser.add_argument("--report-file", type=Path, required=True)
    cycle_equivalence_parser.add_argument("--baseline-file", type=Path, required=True)
    cycle_equivalence_parser.add_argument("--project", required=True)
    cycle_equivalence_parser.add_argument("--historical-date", required=True)
    cycle_candidate_parser = sub.add_parser("cycle-candidate")
    cycle_candidate_parser.add_argument("--packet", type=Path, required=True)
    cycle_candidate_parser.add_argument("--root", type=Path, default=Path("."))
    cycle_candidate_parser.add_argument("--output", type=Path, required=True)
    synthetic_parser = sub.add_parser("synthetic-routing-suite")
    synthetic_parser.add_argument(
        "--suite", type=Path,
        default=Path("console/devos_orchestration/synthetic_fixtures/user_required_suite.json"),
    )
    synthetic_parser.add_argument("--output", type=Path)
    genuine_parser = sub.add_parser("cycle-user-required-candidate")
    genuine_parser.add_argument("--packet", type=Path, required=True)
    genuine_parser.add_argument("--manual-review-gate", required=True)
    genuine_parser.add_argument("--decision-kind")
    genuine_parser.add_argument(
        "--evidence-classification", default="REAL_WORLD_EVIDENCE",
    )
    manifest_parser = sub.add_parser("manifest-preflight")
    manifest_parser.add_argument("--task-file", type=Path, required=True)
    manifest_parser.add_argument("--report-file", type=Path, required=True)
    manifest_parser.add_argument("--baseline-file", type=Path, required=True)
    manifest_parser.add_argument("--project", required=True)
    manifest_parser.add_argument("--historical-date", required=True)
    manifest_parser.add_argument("--run-id", required=True)
    manifest_parser.add_argument("--output", type=Path)
    forensic_parser = sub.add_parser("forensic-audit")
    forensic_parser.add_argument("--request-json", type=Path, required=True)
    forensic_parser.add_argument("--output", type=Path)
    credential_parser = sub.add_parser("credential-status")
    credential_parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    preflight_parser = sub.add_parser("preflight")
    preflight_parser.add_argument("--payload", required=True)
    preflight_parser.add_argument("--max-output-tokens", type=int, default=8192)
    preflight_parser.add_argument("--hard-cap-usd", default="0.75")
    candidate_parser = sub.add_parser("candidate-manifest")
    candidate_parser.add_argument("--root", type=Path, default=Path("."))
    candidate_parser.add_argument("--output", type=Path, default=Path(".console/orchestration/phase1b-r3-candidate-manifest.json"))
    v2_candidate_parser = sub.add_parser("v2-calibration-candidate")
    v2_candidate_parser.add_argument("--root", type=Path, default=Path("."))
    v2_candidate_parser.add_argument("--output", type=Path, default=Path(".console/orchestration/phase1c-r1-v2-candidate-manifest.json"))
    bootstrap_parser = sub.add_parser("api-mainline-bootstrap-candidate")
    bootstrap_parser.add_argument(
        "--output", type=Path,
        default=Path(".console/orchestration/phase2c-2a-api-mainline-bootstrap-candidate-manifest.json"),
    )
    bootstrap_parser.add_argument(
        "--control-state", type=Path,
        default=Path(".console/orchestration-control.json"),
    )
    args = parser.parse_args()
    if args.command == "state":
        value = build_initial_state(args.run_id, args.project, args.purpose)
        validate_state(value)
        print(json.dumps(value, ensure_ascii=True, indent=2))
        return 0
    if args.command == "fixture-discover":
        print(json.dumps(discover_fixture_pair(args.root), ensure_ascii=True, indent=2))
        return 0
    if args.command == "candidate-manifest":
        print(json.dumps(build_parser_bound_candidate(args.root, output=args.output), ensure_ascii=True, indent=2))
        return 0
    if args.command == "v2-calibration-candidate":
        candidate = build_v2_calibration_candidate(args.root, output=args.output)
        print(json.dumps(candidate, ensure_ascii=True, indent=2))
        return 0 if candidate["preflight"]["status"] == "READY" else 3
    if args.command == "api-mainline-bootstrap-candidate":
        candidate = build_bootstrap_candidate(
            args.output,
            canonical_state=load_control_plane_canonical_state(args.control_state),
        )
        print(json.dumps({
            "status": "API_MAINLINE_BOOTSTRAP_CANDIDATE_READY",
            "candidate": str(args.output),
            "approval_manifest_sha256": candidate["manifest"]["approval_manifest_sha256"],
            "approved_for_external_api": False,
            "network_calls": 0,
            "dispatch_count": 0,
        }, ensure_ascii=True, indent=2))
        return 0
    if args.command == "fixture-import":
        result = import_fixture(args.task_file, args.report_file, args.baseline_file, project=args.project, historical_date=args.historical_date)
        if args.output and result["status"] == "MATCHED_FIXTURE_REGISTERED":
            write_json(args.output, result)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0 if result["status"] == "MATCHED_FIXTURE_REGISTERED" else 2
    if args.command == "cycle-capture":
        source = json.loads(args.messages_file.read_text(encoding="utf-8"))
        messages = source["messages"] if isinstance(source, dict) else source
        previous = None
        if args.previous_packet:
            previous = json.loads(args.previous_packet.read_text(encoding="utf-8"))
        packet = capture_cycle_handoff(
            messages, project=args.project, cycle_id=args.cycle_id,
            task_message_identifier=args.task_message_id,
            report_message_identifier=args.report_message_id,
            manual_review_message_identifier=args.manual_review_message_id,
            intermediate_user_decision_identifiers=args.user_decision_message_id,
            capture_timestamp=args.capture_timestamp, previous_packet=previous,
        )
        write_cycle_handoff_packet(args.output, packet)
        print(json.dumps({
            "status": "CYCLE_HANDOFF_CAPTURED", "packet": str(args.output),
            "packet_sha256": packet["packet_sha256"],
            "approved_for_external_api": packet["approved_for_external_api"],
        }, ensure_ascii=True, indent=2))
        return 0
    if args.command == "cycle-capture-legacy":
        packet = capture_legacy_fixture_cycle(
            args.task_file, args.report_file, args.baseline_file,
            project=args.project, cycle_id=args.cycle_id,
            capture_timestamp=args.capture_timestamp,
        )
        write_cycle_handoff_packet(args.output, packet)
        print(json.dumps({
            "status": "CYCLE_HANDOFF_CAPTURED", "source_mode": "LEGACY_FILE_FALLBACK",
            "packet": str(args.output), "packet_sha256": packet["packet_sha256"],
            "approved_for_external_api": False,
        }, ensure_ascii=True, indent=2))
        return 0
    if args.command == "cycle-capture-user-assisted":
        source = json.loads(args.messages_file.read_text(encoding="utf-8"))
        messages = source["messages"] if isinstance(source, dict) else source
        packet = capture_user_assisted_exact_cycle(
            messages, project=args.project, cycle_id=args.cycle_id,
            task_message_identifier=args.task_message_id,
            report_message_identifier=args.report_message_id,
            manual_review_exact_content=args.manual_review_file.read_bytes().decode("utf-8"),
            mainline_session_identifier=args.mainline_session_id,
            manual_review_sequence=args.manual_review_sequence,
            intermediate_user_decision_identifiers=args.user_decision_message_id,
            source_retrieval_status=args.source_retrieval_status,
            capture_timestamp=args.capture_timestamp,
        )
        write_cycle_handoff_packet(args.output, packet)
        print(json.dumps({
            "status": "USER_ASSISTED_EXACT_CAPTURED",
            "capture_mode": packet["capture_mode"],
            "source_retrieval_status": packet["source_retrieval_status"],
            "packet": str(args.output), "packet_sha256": packet["packet_sha256"],
            "approved_for_external_api": False,
        }, ensure_ascii=True, indent=2))
        return 0
    if args.command == "cycle-verify":
        packet = json.loads(args.packet.read_text(encoding="utf-8"))
        verify_cycle_handoff_packet(packet)
        print(json.dumps({
            "status": "CYCLE_HANDOFF_VALID", "packet_sha256": packet["packet_sha256"],
            "approved_for_external_api": packet["approved_for_external_api"],
        }, ensure_ascii=True, indent=2))
        return 0
    if args.command == "cycle-legacy-equivalence":
        packet = json.loads(args.packet.read_text(encoding="utf-8"))
        fixture = import_fixture(
            args.task_file, args.report_file, args.baseline_file,
            project=args.project, historical_date=args.historical_date,
        )
        if fixture.get("status") != "MATCHED_FIXTURE_REGISTERED":
            print(json.dumps({"status": fixture["status"]}, ensure_ascii=True, indent=2))
            return 2
        result = compare_legacy_fixture(packet, fixture)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0 if result["status"] == "SEMANTIC_INPUT_EQUIVALENT" else 3
    if args.command == "cycle-candidate":
        packet = json.loads(args.packet.read_text(encoding="utf-8"))
        candidate = build_cycle_handoff_candidate(args.root, packet, output=args.output)
        print(json.dumps({
            "status": "NO_NETWORK_CANDIDATE_CREATED",
            "candidate": str(args.output),
            "approval_manifest_sha256": candidate["manifest"]["approval_manifest_sha256"],
            "approved_for_external_api": False, "network_calls": 0,
        }, ensure_ascii=True, indent=2))
        return 0
    if args.command == "synthetic-routing-suite":
        result = run_synthetic_suite(args.suite)
        if args.output:
            write_json(args.output, result)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    if args.command == "cycle-user-required-candidate":
        packet = json.loads(args.packet.read_text(encoding="utf-8"))
        result = classify_genuine_user_required_candidate(
            packet, manual_review_gate=args.manual_review_gate,
            decision_kind=args.decision_kind,
            evidence_classification=args.evidence_classification,
        )
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    if args.command == "manifest-preflight":
        try:
            manifest, details, preflight = build_manifest_from_files(args.task_file, args.report_file, args.baseline_file, project=args.project, historical_date=args.historical_date, run_id=args.run_id)
        except ValueError as error:
            print(json.dumps({"status": str(error)}, ensure_ascii=True, indent=2))
            return 2
        result = {"status": preflight["status"], "manifest": manifest, "preflight": {key: str(value) if isinstance(value, Decimal) else value for key, value in preflight.items()}, "network_calls": 0, "dispatch_count": 0, "retry_count": 0}
        if args.output:
            write_json(args.output, {"manifest": manifest, "preflight": result["preflight"], "network_calls": 0, "dispatch_count": 0, "retry_count": 0})
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0 if preflight["status"] == "READY" else 3
    if args.command == "forensic-audit":
        canonical = json.loads(args.request_json.read_text(encoding="utf-8"))
        result = {"wire_audit": audit_wire_request(canonical, build_wire_request(canonical)), "schema_audit": audit_schema(), "error_metadata": {"status": "NOT_RETAINED_IN_HISTORICAL_ARTIFACT"}}
        if args.output:
            write_json(args.output, result)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    if args.command == "credential-status":
        readiness = inspect_env_file(args.env_file)
        print(json.dumps({"orchestration_key_present": readiness.orchestration_key_present, "project_id_present": readiness.project_id_present, "admin_key_present": readiness.admin_key_present, "legacy_key_present": readiness.legacy_key_present, "ready_for_model_call": readiness.ready_for_model_call}, ensure_ascii=True, indent=2))
        return 0
    payload = Path(args.payload).read_text(encoding="utf-8")
    result = run_preflight(payload, max_output_tokens=args.max_output_tokens, pricing=SOL_PROPOSAL_PRICING, hard_cap_usd=Decimal(args.hard_cap_usd))
    print(json.dumps(result.as_dict(), ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
