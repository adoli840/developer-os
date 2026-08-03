from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from ..project_context import (
    ContextContractError,
    build_index,
    load_project_map,
    select_context,
    useful_file_token,
)


class ProjectContextTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self._write(
            "PROJECT_AREAS.json",
            json.dumps(
                {
                    "schema_version": 1,
                    "project": "Example",
                    "exclude_globs": ["outputs/**"],
                    "areas": [
                        {
                            "id": "payments",
                            "name": "Payments",
                            "description": "Payment API and persistence.",
                            "keywords": ["payment", "invoice"],
                            "path_globs": ["src/payments/**", "tests/payments/**", "docs/payments.md"],
                            "entrypoints": ["src/payments/service.py"],
                            "related_docs": ["docs/payments.md"],
                            "test_commands": ["python -m unittest tests.payments.test_service"],
                            "services": ["api"],
                            "data_stores": ["payments table"],
                            "risk_tags": ["database"],
                        },
                        {
                            "id": "accounts",
                            "name": "Accounts",
                            "description": "Account identity.",
                            "keywords": ["account", "identity"],
                            "path_globs": ["src/accounts/**"],
                            "entrypoints": ["src/accounts/model.py"],
                            "related_docs": [],
                            "test_commands": ["python -m unittest tests.accounts"],
                            "services": ["api"],
                            "data_stores": ["accounts table"],
                            "risk_tags": ["authentication"],
                        },
                    ],
                },
                indent=2,
            )
            + "\n",
        )
        self._write(".gitignore", ".developer-os/\noutputs/\n")
        self._write(
            "src/payments/service.py",
            "from decimal import Decimal\n\ndef create_invoice(total: Decimal):\n    return total\n",
        )
        self._write("tests/payments/test_service.py", "def test_create_invoice():\n    assert True\n")
        self._write("docs/payments.md", "# Payments\n\nPayment behavior.\n")
        self._write("src/accounts/model.py", "class Account:\n    pass\n")
        self._write("outputs/large.txt", "ignored\n")
        self._git("init")
        self._git("config", "user.email", "context@example.invalid")
        self._git("config", "user.name", "Context Test")
        self._git("add", ".")
        self._git("commit", "-m", "fixture")

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

    def test_index_reuses_clean_blobs_and_refreshes_dirty_file(self) -> None:
        project_map = load_project_map(self.root)
        first, first_stats = build_index(self.root, project_map)
        self.assertGreaterEqual(first_stats["refreshed"], 4)
        self.assertEqual(first_stats["reused"], 0)
        self.assertNotIn("outputs/large.txt", {item["path"] for item in first["files"]})
        self.assertNotIn("return total", json.dumps(first))

        second, second_stats = build_index(self.root, project_map)
        self.assertEqual(second_stats["refreshed"], 0)
        self.assertEqual(second_stats["reused"], len(second["files"]))

        self._write(
            "src/payments/service.py",
            "from decimal import Decimal\n\ndef create_invoice(total: Decimal):\n    return total * 2\n",
        )
        third, third_stats = build_index(self.root, project_map)
        self.assertEqual(third_stats["refreshed"], 1)
        self.assertEqual(third_stats["reused"], len(third["files"]) - 1)

    def test_task_selects_area_files_and_focused_verification(self) -> None:
        project_map = load_project_map(self.root)
        index, _ = build_index(self.root, project_map)
        selected = select_context(project_map, index, "repair payment invoice creation", limit=10)

        self.assertTrue(selected["matched"])
        self.assertEqual(selected["selected_areas"][0]["id"], "payments")
        self.assertIn("src/payments/service.py", selected["read_first"])
        self.assertIn(
            "python -m unittest tests.payments.test_service",
            selected["test_commands"],
        )
        self.assertIn("database", selected["risk_tags"])
        self.assertIn(
            "src/payments/service.py",
            {item["path"] for item in selected["relevant_files"]},
        )

    def test_invalid_duplicate_area_is_rejected(self) -> None:
        data = json.loads((self.root / "PROJECT_AREAS.json").read_text(encoding="utf-8"))
        data["areas"].append(dict(data["areas"][0]))
        self._write("PROJECT_AREAS.json", json.dumps(data))

        with self.assertRaisesRegex(ContextContractError, "Duplicate area id"):
            load_project_map(self.root)

    def test_missing_entrypoint_is_rejected(self) -> None:
        data = json.loads((self.root / "PROJECT_AREAS.json").read_text(encoding="utf-8"))
        data["areas"][0]["entrypoints"] = ["src/payments/missing.py"]
        self._write("PROJECT_AREAS.json", json.dumps(data))

        with self.assertRaisesRegex(ContextContractError, "missing entrypoint"):
            load_project_map(self.root)

    def test_absolute_area_path_is_rejected(self) -> None:
        data = json.loads((self.root / "PROJECT_AREAS.json").read_text(encoding="utf-8"))
        data["areas"][0]["path_globs"] = ["/outside/**"]
        self._write("PROJECT_AREAS.json", json.dumps(data))

        with self.assertRaisesRegex(ContextContractError, "project-relative"):
            load_project_map(self.root)

    def test_short_generic_file_tokens_do_not_expand_area_selection(self) -> None:
        self.assertFalse(useful_file_token("ui"))
        self.assertFalse(useful_file_token("api"))
        self.assertTrue(useful_file_token("game"))
        self.assertTrue(useful_file_token("\ub85c\ub4dc\ub9f5"))

    def test_cache_must_be_ignored(self) -> None:
        self._write(".gitignore", "outputs/\n")
        project_map = load_project_map(self.root)

        with self.assertRaisesRegex(ContextContractError, "not ignored by Git"):
            build_index(self.root, project_map)


if __name__ == "__main__":
    unittest.main()
