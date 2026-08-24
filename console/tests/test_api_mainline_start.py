from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from console.devos_orchestration.api_mainline import API_MAINLINE_NODE_ID, default_mainline_state
from console.devos_orchestration.api_mainline_start import (
    ApiMainlineStartError,
    ApiMainlineStartStore,
)


class FakeControlPlane:
    def __init__(self) -> None:
        mainline = default_mainline_state()
        mainline["authority"] = API_MAINLINE_NODE_ID
        mainline["canonical_state"]["authority"] = API_MAINLINE_NODE_ID
        self.enabled = True
        self.canonical = mainline["canonical_state"]

    def list_projects(self) -> dict[str, object]:
        return {"projects": [{
            "project": "btest",
            "orchestration_enabled": self.enabled,
            "mainline_state": {
                "authority": API_MAINLINE_NODE_ID if self.enabled else "NATIVE_MAINLINE",
                "canonical_state": dict(
                    self.canonical,
                    authority=API_MAINLINE_NODE_ID if self.enabled else "NATIVE_MAINLINE",
                ),
            },
        }]}


class ApiMainlineStartTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.control = FakeControlPlane()
        self.store = ApiMainlineStartStore(Path(self.temporary.name), self.control)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_exact_input_is_sealed_in_immutable_pristine_candidate(self) -> None:
        request = "Audit the current bTest purpose, then prepare the next bounded task."
        public = self.store.prepare("btest", request)
        ledger = json.loads(self.store.ledger_path.read_text(encoding="utf-8"))
        record = ledger["records"][0]
        candidate = json.loads((self.store.directory / record["candidate_file"]).read_text(encoding="utf-8"))

        self.assertEqual(candidate["candidate_type"], "API_MAINLINE_USER_START")
        self.assertEqual(candidate["user_input"], request)
        self.assertEqual(candidate["manifest"]["user_input_sha256"], public["user_input_sha256"])
        self.assertEqual(candidate["canonical_state"], self.control.canonical)
        self.assertFalse(candidate["approved_for_external_api"])
        self.assertFalse(candidate["approval_record"])
        self.assertFalse(candidate["attempt_record"])
        self.assertFalse(candidate["result_record"])
        self.assertEqual(candidate["network_calls"], 0)
        self.assertEqual(candidate["dispatch_count"], 0)
        self.assertNotIn(request, json.dumps(public))

    def test_same_input_and_state_reuses_current_candidate_without_rewriting(self) -> None:
        first = self.store.prepare("btest", "Exact first request")
        path = next(self.store.directory.glob("api-mainline-user-start-*.json"))
        before = path.read_bytes()
        second = self.store.prepare("btest", "Exact first request")
        self.assertEqual(first, second)
        self.assertEqual(path.read_bytes(), before)
        ledger = json.loads(self.store.ledger_path.read_text(encoding="utf-8"))
        self.assertEqual(len(ledger["records"]), 1)

    def test_input_change_marks_previous_candidate_stale_and_creates_new_candidate(self) -> None:
        first = self.store.prepare("btest", "First exact request")
        second = self.store.prepare("btest", "Second exact request")
        ledger = json.loads(self.store.ledger_path.read_text(encoding="utf-8"))

        self.assertNotEqual(first["candidate_file_sha256"], second["candidate_file_sha256"])
        self.assertNotEqual(first["approval_manifest_sha256"], second["approval_manifest_sha256"])
        self.assertEqual([item["status"] for item in ledger["records"]], ["STALE", "READY"])
        self.assertEqual(ledger["records"][0]["approval_state"], "STALE")
        self.assertEqual(
            ledger["records"][0]["stale_reason"],
            "USER_INPUT_OR_CANONICAL_STATE_CHANGED",
        )
        self.assertFalse(ledger["records"][0]["approval_record"])

    def test_canonical_state_change_invalidates_previous_candidate(self) -> None:
        first = self.store.prepare("btest", "Same request")
        self.control.canonical["current_purpose"] = "Changed purpose"
        self.assertEqual(
            self.store.status("btest")["status"],
            "STALE_CANONICAL_STATE_CHANGED",
        )
        second = self.store.prepare("btest", "Same request")
        self.assertNotEqual(first["canonical_state_sha256"], second["canonical_state_sha256"])

    def test_tampered_candidate_is_blocked(self) -> None:
        self.store.prepare("btest", "Immutable request")
        path = next(self.store.directory.glob("api-mainline-user-start-*.json"))
        candidate = json.loads(path.read_text(encoding="utf-8"))
        candidate["user_input"] = "tampered"
        path.write_text(json.dumps(candidate), encoding="utf-8")
        status = self.store.status("btest")
        self.assertEqual(status["status"], "INVALID_CANDIDATE")
        self.assertEqual(status["approval_state"], "BLOCKED")

    def test_inactive_authority_fails_closed_without_candidate(self) -> None:
        self.control.enabled = False
        with self.assertRaisesRegex(ApiMainlineStartError, "API_MAINLINE_AUTHORITY_REQUIRED"):
            self.store.prepare("btest", "Do not prepare while OFF")
        self.assertEqual(list(self.store.directory.glob("api-mainline-user-start-*.json")), [])

    def test_blank_or_oversized_input_is_rejected(self) -> None:
        with self.assertRaisesRegex(ApiMainlineStartError, "INITIAL_REQUEST_REQUIRED"):
            self.store.prepare("btest", "  ")
        with self.assertRaisesRegex(ApiMainlineStartError, "INITIAL_REQUEST_TOO_LARGE"):
            self.store.prepare("btest", "a" * 131_073)

    def test_status_becomes_stale_when_authority_turns_off(self) -> None:
        self.store.prepare("btest", "Prepare only")
        self.control.enabled = False
        status = self.store.status("btest")
        self.assertEqual(status["status"], "STALE_AUTHORITY_CHANGED")
        self.assertEqual(status["approval_state"], "STALE")
        self.assertEqual(status["network_calls"], 0)

    def test_claim_revalidates_and_blocks_candidate_replacement(self) -> None:
        prepared = self.store.prepare("btest", "Exact approved request")
        claimed = self.store.claim_for_decision(
            "btest", prepared["candidate_file_sha256"], prepared["approval_manifest_sha256"],
        )
        self.assertEqual(claimed["status"], "DECIDING")
        with self.assertRaisesRegex(ApiMainlineStartError, "IN_FLIGHT"):
            self.store.prepare("btest", "Replacement while approval is in flight")


if __name__ == "__main__":
    unittest.main()
