from __future__ import annotations

import copy
import hashlib
import unittest

from ..context_identity import (
    AUTHORITY_STATUS,
    DEVELOPMENT_CONTEXT_SEAL_VERSION,
    DIRTY_TREE_SCOPE_MANIFEST_VERSION,
    SOURCE_WINS,
    build_development_context_seal_v1,
    build_dirty_tree_scope_manifest_v1,
    content_identity,
    context_entry,
    dirty_path_entry,
    policy_reference,
    validate_development_context_seal_v1,
    validate_dirty_tree_scope_manifest_v1,
)


HEAD = "1" * 40
OTHER_HEAD = "2" * 40


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class ContextIdentityContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = "example"
        self.lane = "MAINLINE_CODEX_REVIEW"
        self.workspace = "X:/Projects/example"
        self.task_identity = digest("task")
        self.canonical_state = digest("canonical-state")
        self.references = [
            policy_reference("DeveloperOS.BOOT", digest("boot")),
            policy_reference("project.rules", digest("rules")),
        ]
        self.entries = [
            context_entry(
                path="PROJECT_RULES.md",
                identity=content_identity("GIT_BLOB", "a" * 40),
                inclusion_reason="project authority",
                byte_size=120,
            ),
            context_entry(
                path="src/service.py",
                identity=content_identity("CONTENT_SHA256", digest("service")),
                inclusion_reason="selected entrypoint",
                byte_size=240,
            ),
        ]
        self.dirty_entries = [
            dirty_path_entry(
                path="src/service.py",
                states=["UNSTAGED"],
                classification="IN_SCOPE",
                pre_identity=content_identity("GIT_BLOB", "b" * 40),
                current_identity=content_identity("CONTENT_SHA256", digest("service-dirty")),
                scope_basis="task:TASK-1",
            ),
            dirty_path_entry(
                path="notes/local.txt",
                states=["UNTRACKED"],
                classification="USER_OWNED_OUT_OF_SCOPE",
                pre_identity=content_identity("ABSENT"),
                current_identity=content_identity("CONTENT_SHA256", digest("notes")),
                scope_basis="pre-existing user work",
            ),
        ]
        self.manifest = self._manifest(self.dirty_entries)
        self.seal = self._seal(self.manifest)

    def _manifest(self, entries, *, project=None, lane=None, head=HEAD):
        return build_dirty_tree_scope_manifest_v1(
            project=project or self.project,
            lane=lane or self.lane,
            workspace=self.workspace,
            base_head=head,
            entries=entries,
        )

    def _seal(self, manifest, *, project=None, lane=None, head=HEAD):
        return build_development_context_seal_v1(
            project=project or self.project,
            lane=lane or self.lane,
            workspace=self.workspace,
            branch="main",
            head=head,
            task_identity=self.task_identity,
            canonical_state_sha256=self.canonical_state,
            active_references=self.references,
            context_entries=self.entries,
            dirty_manifest=manifest,
            tool_version="context-identity/1",
            protocol_version="context-protocol/1",
        )

    def _validate_manifest(self, manifest=None, **overrides):
        values = {
            "expected_project": self.project,
            "expected_lane": self.lane,
            "expected_workspace": self.workspace,
            "expected_base_head": HEAD,
            "observed_entries": self.dirty_entries,
        }
        values.update(overrides)
        return validate_dirty_tree_scope_manifest_v1(manifest or self.manifest, **values)

    def _validate_seal(self, seal=None, manifest=None, **overrides):
        values = {
            "expected_project": self.project,
            "expected_lane": self.lane,
            "expected_workspace": self.workspace,
            "expected_branch": "main",
            "expected_head": HEAD,
            "expected_task_identity": self.task_identity,
            "expected_canonical_state_sha256": self.canonical_state,
            "observed_active_references": self.references,
            "observed_context_entries": self.entries,
            "dirty_manifest": manifest or self.manifest,
            "expected_tool_version": "context-identity/1",
            "expected_protocol_version": "context-protocol/1",
        }
        values.update(overrides)
        return validate_development_context_seal_v1(seal or self.seal, **values)

    def test_valid_seal_and_manifest(self) -> None:
        manifest = self._validate_manifest()
        seal = self._validate_seal()

        self.assertEqual(self.manifest["contract_version"], DIRTY_TREE_SCOPE_MANIFEST_VERSION)
        self.assertEqual(self.seal["contract_version"], DEVELOPMENT_CONTEXT_SEAL_VERSION)
        self.assertEqual(self.seal["authority_status"], AUTHORITY_STATUS)
        self.assertEqual(manifest["status"], "VALID")
        self.assertEqual(seal["status"], "VALID")
        self.assertTrue(seal["cache_reuse_eligible"])

    def test_context_content_drift_invalidates_seal(self) -> None:
        changed = copy.deepcopy(self.entries)
        changed[1]["identity"] = content_identity("CONTENT_SHA256", digest("changed"))

        result = self._validate_seal(observed_context_entries=changed)

        self.assertEqual(result["status"], "INVALID")
        self.assertIn("CONTEXT_ENTRY_IDENTITY_DRIFT", result["invalidation_reasons"])
        self.assertFalse(result["auto_advance_eligible"])

    def test_head_drift_invalidates_manifest_and_seal(self) -> None:
        manifest = self._validate_manifest(expected_base_head=OTHER_HEAD)
        seal = self._validate_seal(expected_head=OTHER_HEAD)

        self.assertIn("HEAD_DRIFT", manifest["invalidation_reasons"])
        self.assertIn("HEAD_DRIFT", seal["invalidation_reasons"])
        self.assertIn("DIRTY_MANIFEST_INVALID", seal["invalidation_reasons"])

    def test_canonical_state_drift_invalidates_seal(self) -> None:
        result = self._validate_seal(expected_canonical_state_sha256=digest("new-state"))

        self.assertEqual(result["status"], "INVALID")
        self.assertEqual(result["invalidation_reasons"], ["CANONICAL_STATE_DRIFT"])

    def test_policy_reference_drift_invalidates_seal(self) -> None:
        changed = copy.deepcopy(self.references)
        changed[0]["identity_sha256"] = digest("changed-policy")

        result = self._validate_seal(observed_active_references=changed)

        self.assertIn("POLICY_REFERENCE_DRIFT", result["invalidation_reasons"])
        self.assertFalse(result["cache_reuse_eligible"])

    def test_dirty_path_classification_is_preserved(self) -> None:
        classifications = {
            item["path"]: item["classification"] for item in self.manifest["entries"]
        }

        self.assertEqual(classifications["src/service.py"], "IN_SCOPE")
        self.assertEqual(classifications["notes/local.txt"], "USER_OWNED_OUT_OF_SCOPE")

    def test_unclassified_dirty_path_fails_closed(self) -> None:
        entry = dirty_path_entry(
            path="mystery.txt",
            states=["UNTRACKED"],
            classification="UNCLASSIFIED",
            pre_identity=content_identity("ABSENT"),
            current_identity=content_identity("CONTENT_SHA256", digest("mystery")),
            scope_basis=None,
        )
        manifest = self._manifest([entry])

        result = self._validate_manifest(manifest, observed_entries=[entry])

        self.assertIn("UNCLASSIFIED_DIRTY_PATH", result["invalidation_reasons"])
        self.assertFalse(result["cache_reuse_eligible"])
        self.assertFalse(result["auto_advance_eligible"])

    def test_dirty_identity_drift_fails_closed(self) -> None:
        observed = copy.deepcopy(self.dirty_entries)
        observed[0]["current_identity"] = content_identity("CONTENT_SHA256", digest("later"))

        result = self._validate_manifest(observed_entries=observed)

        self.assertIn("DIRTY_PATH_IDENTITY_DRIFT", result["invalidation_reasons"])
        self.assertFalse(result["cache_reuse_eligible"])

    def test_cross_project_and_lane_reuse_is_blocked(self) -> None:
        project_result = self._validate_seal(expected_project="other-project")
        lane_result = self._validate_seal(expected_lane="FUTURE_DESIGN")

        self.assertIn("PROJECT_MISMATCH", project_result["invalidation_reasons"])
        self.assertIn("NAMESPACE_MISMATCH", project_result["invalidation_reasons"])
        self.assertIn("LANE_MISMATCH", lane_result["invalidation_reasons"])
        self.assertIn("NAMESPACE_MISMATCH", lane_result["invalidation_reasons"])

    def test_hashes_are_deterministic_for_reordered_inputs(self) -> None:
        manifest = self._manifest(reversed(self.dirty_entries))
        seal = build_development_context_seal_v1(
            project=self.project,
            lane=self.lane,
            workspace=self.workspace,
            branch="main",
            head=HEAD,
            task_identity=self.task_identity,
            canonical_state_sha256=self.canonical_state,
            active_references=reversed(self.references),
            context_entries=reversed(self.entries),
            dirty_manifest=manifest,
            tool_version="context-identity/1",
            protocol_version="context-protocol/1",
        )

        self.assertEqual(manifest["manifest_sha256"], self.manifest["manifest_sha256"])
        self.assertEqual(seal["seal_sha256"], self.seal["seal_sha256"])

    def test_source_wins_invariant_is_explicit(self) -> None:
        result = self._validate_seal(expected_branch="release")

        self.assertEqual(result["status"], "INVALID")
        self.assertEqual(result["authority_resolution"], SOURCE_WINS)
        self.assertEqual(result["seal_authority"], AUTHORITY_STATUS)
        self.assertIn("BRANCH_DRIFT", result["invalidation_reasons"])


if __name__ == "__main__":
    unittest.main()
