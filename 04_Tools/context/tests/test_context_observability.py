from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from ..context_observability import (
    ContextObservabilityError,
    build_context_efficiency_snapshot_v1,
    validate_context_efficiency_snapshot_v1,
)
from ..project_context import build_index, load_project_map, select_context


class ContextObservabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self._write(
            "PROJECT_AREAS.json",
            json.dumps(
                {
                    "schema_version": 1,
                    "project": "Example",
                    "exclude_globs": [],
                    "areas": [
                        {
                            "id": "payments",
                            "name": "Payments",
                            "description": "Payment handling.",
                            "keywords": ["payment", "invoice"],
                            "path_globs": ["src/**", "docs/**", "scripts/**"],
                            "entrypoints": ["src/service.py", "scripts/context.mk"],
                            "related_docs": ["docs/payments.md"],
                            "test_commands": ["python -m unittest tests"],
                            "services": ["api"],
                            "data_stores": ["payments"],
                            "risk_tags": ["money"],
                        }
                    ],
                }
            )
            + "\n",
        )
        self._write(".gitignore", ".developer-os/\n")
        self._write("src/service.py", "def invoice():\n    return 1\n")
        self._write("scripts/context.mk", "context:\n\t@echo context\n")
        self._write("docs/payments.md", "# Payments\n\nExact evidence.\n")
        self._git("init")
        self._git("config", "user.email", "context@example.invalid")
        self._git("config", "user.name", "Context Test")
        self._git("add", ".")
        self._git("commit", "-m", "fixture")
        project_map = load_project_map(self.root)
        build_index(self.root, project_map)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write(self, relative: str, content: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _git(self, *arguments: str) -> None:
        subprocess.run(
            ["git", "-C", str(self.root), *arguments],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def _observe(self, **overrides):
        arguments = {
            "project_root": self.root,
            "lane": "MAINLINE_CODEX_REVIEW",
            "task": "repair payment invoice",
        }
        arguments.update(overrides)
        return build_context_efficiency_snapshot_v1(**arguments)

    def test_observer_preserves_exact_selection_and_order(self) -> None:
        project_map = load_project_map(self.root)
        index, _ = build_index(self.root, project_map, persist_cache=False)
        expected = select_context(project_map, index, "repair payment invoice")

        snapshot, observed, _ = self._observe()

        self.assertEqual(observed, expected)
        self.assertEqual(
            [item["path"] for item in observed["relevant_files"]],
            [item["path"] for item in expected["relevant_files"]],
        )
        self.assertGreater(snapshot["selection"]["selected_total_bytes"], 0)
        self.assertGreater(snapshot["selection"]["selected_total_lines"], 0)

    def test_observer_does_not_rewrite_context_cache(self) -> None:
        cache = self.root / ".developer-os/context-index.json"
        before = cache.read_bytes()

        self._observe()

        self.assertEqual(cache.read_bytes(), before)

    def test_snapshot_contains_metrics_but_not_source_or_task_content(self) -> None:
        snapshot, _, _ = self._observe()
        encoded = json.dumps(snapshot, ensure_ascii=False)

        self.assertNotIn("repair payment invoice", encoded)
        self.assertNotIn("Exact evidence", encoded)
        self.assertIsNone(snapshot["actual_api_usage"])
        self.assertEqual(snapshot["expansion"]["expansion_count"], 0)
        self.assertEqual(snapshot["expansion"]["stage_count"], 1)

    def test_repeated_selection_is_measured(self) -> None:
        snapshot, selection, _ = self._observe()
        expected_repeated = set(selection["read_first"]).intersection(
            item["path"] for item in selection["relevant_files"]
        )

        self.assertEqual(
            {item["path"] for item in snapshot["repeated_selection"]["sources"]},
            expected_repeated,
        )
        self.assertEqual(
            snapshot["repeated_selection"]["repeated_occurrence_count"],
            len(expected_repeated),
        )

    def test_dirty_full_scan_is_reported_without_cache_write(self) -> None:
        self._write("src/service.py", "def invoice():\n    return 2\n")
        snapshot, _, _ = self._observe()

        self.assertTrue(snapshot["dirty_scan"]["dirty_full_scan"])
        self.assertEqual(snapshot["dirty_scan"]["dirty_indexed_path_count"], 1)
        self.assertGreaterEqual(snapshot["identity_reuse"]["index_refreshed_file_count"], 1)

    def test_project_lane_namespace_is_fail_closed(self) -> None:
        snapshot, _, _ = self._observe()

        with self.assertRaisesRegex(ContextObservabilityError, "lane mismatch"):
            validate_context_efficiency_snapshot_v1(
                snapshot,
                expected_project="Example",
                expected_lane="FUTURE_DESIGN",
            )

    def test_snapshot_hash_detects_metric_tampering(self) -> None:
        snapshot, _, _ = self._observe()
        snapshot["selection"]["selected_total_bytes"] += 1

        with self.assertRaisesRegex(ContextObservabilityError, "hash mismatch"):
            validate_context_efficiency_snapshot_v1(snapshot)

    def test_only_provider_actual_api_usage_is_accepted(self) -> None:
        with self.assertRaisesRegex(ContextObservabilityError, "provider-reported"):
            self._observe(actual_api_usage={"measurement": "ESTIMATED"})

        usage = {
            "measurement": "PROVIDER_ACTUAL",
            "input_tokens": 10,
            "cached_input_tokens": 2,
            "output_tokens": 3,
            "reasoning_tokens": 1,
            "total_tokens": 13,
        }
        snapshot, _, _ = self._observe(actual_api_usage=usage)
        self.assertEqual(snapshot["actual_api_usage"], usage)

    def test_identity_validation_status_is_explicit(self) -> None:
        snapshot, _, _ = self._observe(
            seal_validation_status="VALID",
            dirty_manifest_validation_status="INVALID",
        )

        self.assertEqual(
            snapshot["identity_validation"],
            {
                "development_context_seal": "VALID",
                "dirty_tree_scope_manifest": "INVALID",
            },
        )


if __name__ == "__main__":
    unittest.main()
