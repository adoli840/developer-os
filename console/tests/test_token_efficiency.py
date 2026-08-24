from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from console.devos_orchestration.token_efficiency import (
    EvaluationReuseStore,
    compact_canonical_context,
    deterministic_continuation_precheck,
    evaluation_identity_sha256,
)


class TokenEfficiencyTests(unittest.TestCase):
    @staticmethod
    def state() -> dict[str, object]:
        return {
            "current_purpose": "bounded task",
            "frozen_decisions": ["decision"],
            "scope": ["scope"],
            "authority": "BTEST_MAINLINE_API",
            "routing": {"destination": "CODEX_WORKER"},
            "user_decisions": [],
            "current_gate": "SAFE_CONTINUE",
            "latest_relevant_handoff": "handoff-1",
            "full_history": ["excluded"],
            "manual_review": "excluded baseline",
            "activity_timeline": ["excluded event"],
        }

    def test_compact_context_preserves_authority_and_excludes_history(self) -> None:
        compact = compact_canonical_context(self.state())
        self.assertEqual(compact["authority"], "BTEST_MAINLINE_API")
        self.assertEqual(compact["frozen_decisions"], ["decision"])
        self.assertEqual(compact["routing"], {"destination": "CODEX_WORKER"})
        self.assertNotIn("full_history", compact)
        self.assertNotIn("manual_review", compact)
        self.assertNotIn("activity_timeline", compact)

    def test_compact_context_fails_closed_when_authority_state_is_missing(self) -> None:
        state = self.state()
        state.pop("routing")
        with self.assertRaisesRegex(ValueError, "CANONICAL_STATE_INVALID"):
            compact_canonical_context(state)

    def test_evaluation_identity_is_exact_and_deterministic(self) -> None:
        arguments = {
            "canonical_state_sha256": "a" * 64,
            "task_sha256": "b" * 64,
            "report_sha256": "c" * 64,
            "protocol_version": "p1",
            "reviewer_schema_version": "s1",
        }
        first = evaluation_identity_sha256(**arguments)
        self.assertEqual(first, evaluation_identity_sha256(**arguments))
        self.assertNotEqual(first, evaluation_identity_sha256(**{**arguments, "report_sha256": "d" * 64}))

    def test_precheck_is_objective_and_fails_closed(self) -> None:
        binding = {
            "canonical_state_sha256": "a" * 64,
            "task_content_sha256": "b" * 64,
            "report_content_sha256": "c" * 64,
            "evaluation_identity_sha256": "d" * 64,
            "stable_prefix_sha256": "e" * 64,
            "dynamic_payload_sha256": "f" * 64,
        }
        candidate = {
            "binding": binding,
            "manifest": {"prompt_version": "v1", "schema_version": "v1"},
        }
        passed = deterministic_continuation_precheck(
            candidate,
            current_canonical_state_sha256="a" * 64,
            credential_available=True,
            already_consumed=False,
            route_binding_valid=True,
            workspace_binding_valid=True,
        )
        self.assertEqual(passed["status"], "PASS")
        self.assertFalse(passed["semantic_judgment_performed"])
        blocked = deterministic_continuation_precheck(
            candidate,
            current_canonical_state_sha256="0" * 64,
            credential_available=False,
            already_consumed=True,
            route_binding_valid=False,
            workspace_binding_valid=False,
        )
        self.assertEqual(blocked["status"], "BLOCKED")
        self.assertEqual(len(blocked["reasons"]), 5)

    def test_only_validated_exact_evaluations_are_reused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reuse.json"
            store = EvaluationReuseStore(path)
            self.assertIsNone(store.lookup("a" * 64))
            record = store.register_validated(
                "a" * 64,
                result_sha256="b" * 64,
                result_artifact="result.json",
                protocol_version="p1",
                reviewer_schema_version="s1",
            )
            self.assertEqual(store.lookup("a" * 64), record)
            serialized = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn("source_content", json.dumps(serialized))
            with self.assertRaisesRegex(ValueError, "IDENTITY_CONFLICT"):
                store.register_validated(
                    "a" * 64,
                    result_sha256="c" * 64,
                    result_artifact="other.json",
                    protocol_version="p1",
                    reviewer_schema_version="s1",
                )


if __name__ == "__main__":
    unittest.main()
