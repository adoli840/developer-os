from __future__ import annotations

from typing import Any


REQUIREMENT_MATRIX: tuple[dict[str, str], ...] = (
    {"id": "STATE-01", "contract": "valid state/schema", "test": "test_state_contract_and_line_numbered_evidence", "status": "PASS"},
    {"id": "STATE-02", "contract": "unknown field rejection", "test": "test_state_rejects_unknown_top_level_field", "status": "PASS"},
    {"id": "GATE-01", "contract": "SAFE_CONTINUE requires next instruction", "test": "test_safe_continue_requires_instruction_and_no_other_packet", "status": "PASS"},
    {"id": "GATE-02", "contract": "USER_REQUIRED requires decision packet", "test": "test_user_required_contract", "status": "PASS"},
    {"id": "GATE-03", "contract": "BLOCKED requires blocker packet", "test": "test_gate_combinations_are_fail_closed", "status": "PASS"},
    {"id": "GATE-04", "contract": "STOP requires STOP finding", "test": "test_stop_requires_stop_finding", "status": "PASS"},
    {"id": "GATE-05", "contract": "contradictory packet rejected", "test": "test_contradictory_packets_are_rejected", "status": "PASS"},
    {"id": "AUTH-01", "contract": "manual baseline excluded from reviewer prompt", "test": "test_fixture_prompt_excludes_manual_baseline", "status": "PASS"},
    {"id": "CRED-01", "contract": "generic/admin key fallback prohibited", "test": "test_admin_or_legacy_key_never_fulfills_orchestration_readiness", "status": "PASS"},
    {"id": "ADAPTER-01", "contract": "request shape and standard mode omission", "test": "test_request_contract_omits_standard_mode", "status": "PASS"},
    {"id": "ADAPTER-02", "contract": "default live transport locked", "test": "test_live_adapter_is_disabled", "status": "PASS"},
    {"id": "ADAPTER-03", "contract": "exactly one injected call", "test": "test_injected_transport_is_single_call", "status": "PASS"},
    {"id": "ADAPTER-04", "contract": "refusal/incomplete/malformed output fail closed", "test": "test_adapter_rejects_unsafe_responses", "status": "PASS"},
    {"id": "COST-01", "contract": "Decimal pricing and budget block", "test": "test_pricing_uses_decimal_and_separates_cache_write", "status": "PASS"},
    {"id": "FIXTURE-01", "contract": "three-file fixture intake and hashes", "test": "test_fixture_import_records_integrity", "status": "PASS"},
    {"id": "FIXTURE-02", "contract": "secret scan blocks fixture", "test": "test_fixture_secret_scan_does_not_expose_value", "status": "PASS"},
    {"id": "SAFE-01", "contract": "no dispatch, commit, push, deploy in Phase 1A", "test": "test_default_run_is_local_only", "status": "PASS"},
)


def coverage_matrix() -> list[dict[str, str]]:
    return [dict(item) for item in REQUIREMENT_MATRIX]
