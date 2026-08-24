from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "build_desktop_vhd_matrix.py"
SPEC = importlib.util.spec_from_file_location("build_desktop_vhd_matrix", MODULE_PATH)
matrix_module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(matrix_module)


def test_image_names_do_not_assert_identical_native_data() -> None:
    inventory = {
        "desktop": {
            "containers": [],
            "volumes": [],
            "images": [{"id": "sha256:a", "repo_tags": ["oa:latest"], "labels": {}, "size": 1}],
            "networks": [],
            "build_cache": [],
        },
        "native": {"containers": [], "volumes": [], "images": [{"repo_tags": ["oa:latest"]}], "networks": []},
    }
    record = matrix_module.build_matrix(inventory, "backup")["records"][0]
    assert record["native_counterpart"] == "SUPERSEDED_BY_NATIVE"
    assert record["native_counterpart"] != "IDENTICAL_OR_EQUIVALENT_NATIVE"


def test_oa_unique_persistent_data_is_zero_without_oa_volume() -> None:
    inventory = {
        "desktop": {"containers": [], "volumes": [], "images": [], "networks": [], "build_cache": []},
        "native": {"containers": [], "volumes": [], "images": [], "networks": []},
    }
    assert matrix_module.build_matrix(inventory, "backup")["summary"]["oa_desktop_persistent_unique_data"] == 0


def test_hyphenated_node_modules_volume_is_cache() -> None:
    inventory = {
        "desktop": {
            "containers": [],
            "volumes": [{"name": "gaia_gaia-dev-node-modules", "labels": {}}],
            "images": [],
            "networks": [],
            "build_cache": [],
        },
        "native": {"containers": [], "volumes": [], "images": [], "networks": []},
    }
    record = matrix_module.build_matrix(inventory, "backup")["records"][0]
    assert record["persistence"] == "CACHE"
    assert record["final_classification"] == "SAFE_TO_DELETE_WITH_DESKTOP"


def test_generated_sidecar_hashes_exact_file_bytes(tmp_path, monkeypatch) -> None:
    inventory_path = tmp_path / "inventory.json"
    output_path = tmp_path / "matrix.json"
    inventory_path.write_text(
        json.dumps(
            {
                "desktop": {"containers": [], "volumes": [], "images": [], "networks": [], "build_cache": []},
                "native": {"containers": [], "volumes": [], "images": [], "networks": []},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        ["matrix", "--inventory", str(inventory_path), "--output", str(output_path), "--vhd-backup", "backup"],
    )
    assert matrix_module.main() == 0
    expected = hashlib.sha256(output_path.read_bytes()).hexdigest()
    assert output_path.with_suffix(".json.sha256").read_text().startswith(expected)


def test_six_preserved_volumes_have_closed_final_classification() -> None:
    names = tuple(matrix_module.PRESERVATION_FACTS)
    inventory = {
        "desktop": {
            "containers": [],
            "volumes": [{"name": name, "labels": {}} for name in names],
            "images": [],
            "networks": [],
            "build_cache": [],
        },
        "native": {"containers": [], "volumes": [], "images": [], "networks": []},
    }
    matrix = matrix_module.build_matrix(inventory, "backup")
    assert len(matrix["records"]) == 6
    assert all(
        record["final_classification"]
        == "EXTERNALLY_PRESERVED_THEN_SAFE_TO_DELETE"
        for record in matrix["records"]
    )
    assert matrix["summary"]["remaining_unknown_assets"] == 0
    assert matrix["summary"]["remaining_veto_assets"] == 0


def test_btest_unique_data_and_devos_verification_data_are_distinguished() -> None:
    names = (
        "btest_consolidated_postgres_data",
        "46277a77c226d6d32ab1dcd74454e874fc5becd97bdf04e379f853d81632bc02",
    )
    inventory = {
        "desktop": {
            "containers": [],
            "volumes": [{"name": name, "labels": {}} for name in names],
            "images": [],
            "networks": [],
            "build_cache": [],
        },
        "native": {"containers": [], "volumes": [], "images": [], "networks": []},
    }
    records = {record["asset"]: record for record in matrix_module.build_matrix(inventory, "backup")["records"]}
    assert records[names[0]]["unique_data"] is True
    assert records[names[0]]["native_counterpart"] == "UNIQUE_DESKTOP"
    assert records[names[1]]["persistence"] == "OBSOLETE"
    assert records[names[1]]["native_counterpart"] == "NOT_REQUIRED_DISPOSABLE"
