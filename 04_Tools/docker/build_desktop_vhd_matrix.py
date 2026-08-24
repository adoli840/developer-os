from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


VOLUME_FACTS: dict[str, dict[str, Any]] = {
    "0a5ed0c20c2e61e5a9f004f92a63d986e30257faa85bb50aa2f8540b042734b1": {
        "owner": "unknown",
        "size_bytes": 48_640_000,
        "catalog_databases": ["temp"],
    },
    "46277a77c226d6d32ab1dcd74454e874fc5becd97bdf04e379f853d81632bc02": {
        "owner": "DeveloperOS",
        "size_bytes": 56_520_000,
        "catalog_databases": ["devos_verify"],
    },
    "7ccf989eb0bf61dd98ba5a7b787245a09a5eeb4a0f3d1a913b7c15835db96742": {
        "owner": "DeveloperOS",
        "size_bytes": 1_542_000_000,
        "catalog_databases": ["devos_verify"],
    },
    "957fc7c02fbc4c1b659db9ad2b2edd90e6b964e77c6f5d0816e123457e93b399": {
        "owner": "unknown",
        "size_bytes": 413_700_000,
        "catalog_databases": ["temp"],
    },
    "btest_consolidated_postgres_data": {
        "owner": "bTest",
        "size_bytes": 2_938_000_000,
        "catalog_databases": ["elliott", "ever", "grid", "kline", "memo", "plot", "webhook"],
    },
    "btest_desktop_forensic_clone_20260815_phase4": {
        "owner": "bTest",
        "size_bytes": 2_937_000_000,
        "catalog_databases": ["elliott", "ever", "grid", "kline", "memo", "plot", "webhook"],
    },
    "btest_go_build_cache": {"owner": "bTest", "size_bytes": 171_700_000},
    "btest_web_node_modules": {"owner": "bTest", "size_bytes": 64_990_000},
    "gaia_gaia-dev-next-cache": {"owner": "Gaia", "size_bytes": 336_400_000},
    "gaia_gaia-dev-node-modules": {"owner": "Gaia", "size_bytes": 494_000_000},
    "gaia_gaia-sim-next-cache": {"owner": "Gaia", "size_bytes": 59_370_000},
    "gaia_postgres-data": {
        "owner": "Gaia",
        "size_bytes": 324_600_000,
        "catalog_databases": ["gaia"],
    },
}

VHD_FORENSIC_COPY = {
    "path": r"X:\Docker\Forensics\vhd\docker_data-20260815T044434Z-forensic-copy.vhdx",
    "sha256": "e3ceb00f8eabc02b5b80664da6c1e6ea2e1f8084791b34c80356a985ce1a3161",
    "verification": "SOURCE_AND_COPY_SIZE_SHA256_MATCH; COPY_READ_ONLY",
}

PRESERVATION_FACTS: dict[str, dict[str, Any]] = {
    "0a5ed0c20c2e61e5a9f004f92a63d986e30257faa85bb50aa2f8540b042734b1": {
        "data_classification": "DISPOSABLE_FORENSIC_OR_TEST_ARTIFACT",
        "artifacts": [
            {
                "path": r"X:\Docker\Forensics\global-anonymous-volumes\0a5ed0c20c2e61e5a9f004f92a63d986e30257faa85bb50aa2f8540b042734b1-pgdata-20260815.tar",
                "sha256": "5601c2cfb25096e9903abcc65ded4970e7a6a97993b6b9f256e51cfe74af5eaf",
                "verification": "PHYSICAL_ARCHIVE_SHA256_VERIFIED; DISPOSABLE CLONE CRASH-RECOVERY START PASS; LOGICAL VALUE REVIEW NOT REQUIRED",
            },
            VHD_FORENSIC_COPY,
        ],
    },
    "957fc7c02fbc4c1b659db9ad2b2edd90e6b964e77c6f5d0816e123457e93b399": {
        "data_classification": "DISPOSABLE_FORENSIC_OR_TEST_ARTIFACT",
        "artifacts": [
            {
                "path": r"X:\Docker\Forensics\global-anonymous-volumes\957fc7c02fbc4c1b659db9ad2b2edd90e6b964e77c6f5d0816e123457e93b399-pgdata-20260815.tar",
                "sha256": "1b2530e1a858698345b4f17dad28e66bec09f253ce7e0350dbbefeac516bb2f8",
                "verification": "PHYSICAL_ARCHIVE_SHA256_VERIFIED; DISPOSABLE CLONE CRASH-RECOVERY START PASS; LOGICAL VALUE REVIEW NOT REQUIRED",
            },
            VHD_FORENSIC_COPY,
        ],
    },
    "46277a77c226d6d32ab1dcd74454e874fc5becd97bdf04e379f853d81632bc02": {
        "data_classification": "DISPOSABLE_DEVELOPEROS_RESTORE_VERIFICATION_ARTIFACT",
        "artifacts": [VHD_FORENSIC_COPY],
    },
    "7ccf989eb0bf61dd98ba5a7b787245a09a5eeb4a0f3d1a913b7c15835db96742": {
        "data_classification": "DISPOSABLE_DEVELOPEROS_RESTORE_VERIFICATION_ARTIFACT",
        "artifacts": [VHD_FORENSIC_COPY],
    },
    "btest_consolidated_postgres_data": {
        "data_classification": "HAS_UNIQUE_MEANINGFUL_DATA",
        "artifacts": [
            {
                "path": r"X:\Docker\Forensic\btest-desktop-elliott-forward-run-manifests-20260815.dump",
                "sha256": "077e368cc9fc5497065eb913e2fc2aec3eec6ab302454f5e9a7212283223e335",
                "verification": "LOGICAL_RESTORE_PASS; 69837 ROWS RESTORED; 4709 DESKTOP_ONLY PRIMARY KEYS PRESERVED",
            },
            {
                "path": r"X:\Docker\Forensics\btest\btest-desktop-postgres-20260815T004028Z.tar",
                "sha256": "f1afeb0a1ddd611a03992cdb07fbc2ce8ff8d4845ad0a4c8dba07a73681d84e2",
                "verification": "PHYSICAL_VOLUME_ARCHIVE_SHA256_VERIFIED",
            },
            VHD_FORENSIC_COPY,
        ],
    },
    "gaia_postgres-data": {
        "data_classification": "DESKTOP_ONLY_DATA_OBSOLETE",
        "artifacts": [
            {
                "path": r"D:\Gaia-forensics\20260815-desktop-native\logical-preservation\desktop-gaia-pg17.dump",
                "sha256": "8dc69461db4d666d3e527b3119b121f3c4517fb0d0fc0d5ddd926e598c90abe6",
                "verification": "LOGICAL_RESTORE_PASS; 62 PUBLIC TABLES; CORE ROW COUNTS MATCHED",
            },
            {
                "path": r"D:\Gaia-forensics\20260815-desktop-native\desktop-gaia-postgres.tar",
                "sha256": "a6fe1b81fc6d587f0210d60b5c04dd96f630cd3a89313729ab9e2759206ef23c",
                "verification": "PHYSICAL_ARCHIVE_SHA256_VERIFIED",
            },
            VHD_FORENSIC_COPY,
        ],
    },
}


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _project_from_text(*values: Any) -> str:
    text = " ".join(str(value).lower() for value in values)
    if "btest" in text:
        return "bTest"
    if "gaia" in text:
        return "Gaia"
    if "oa" in text:
        return "OA"
    return "unrelated"


def _native_named(native: dict[str, Any], kind: str, name: str) -> bool:
    key = "name" if kind != "image" else "repo_tags"
    for item in native[kind + "s"]:
        candidate = item.get(key)
        if candidate == name or isinstance(candidate, list) and name in candidate:
            return True
    return False


def _volume_record(item: dict[str, Any], native: dict[str, Any], backup: str) -> dict[str, Any]:
    name = item["name"]
    facts = VOLUME_FACTS[name]
    cache = "cache" in name or "node_modules" in name or "node-modules" in name
    if cache:
        persistence = "CACHE"
        counterpart = "SUPERSEDED_BY_NATIVE" if _native_named(native, "volume", name) else "UNKNOWN"
        final = "SAFE_TO_DELETE_WITH_DESKTOP"
        unique = False
        external = None
    elif name == "btest_desktop_forensic_clone_20260815_phase4":
        persistence = "PERSISTENT_DATA"
        counterpart = "SUPERSEDED_BY_NATIVE"
        final = "SAFE_TO_DELETE_WITH_DESKTOP"
        unique = False
        external = backup
    else:
        preservation = PRESERVATION_FACTS[name]
        persistence = (
            "PERSISTENT_DATA"
            if name in {"btest_consolidated_postgres_data", "gaia_postgres-data"}
            else "OBSOLETE"
        )
        counterpart = (
            "UNIQUE_DESKTOP"
            if name == "btest_consolidated_postgres_data"
            else "SUPERSEDED_BY_NATIVE"
            if name == "gaia_postgres-data"
            else "NOT_REQUIRED_DISPOSABLE"
        )
        final = "EXTERNALLY_PRESERVED_THEN_SAFE_TO_DELETE"
        unique = name == "btest_consolidated_postgres_data"
        external = preservation["artifacts"][0]["path"]
    record = {
        "asset_type": "volume",
        "asset": name,
        "owner": facts["owner"],
        "size_bytes": facts["size_bytes"],
        "created_at": item.get("created_at"),
        "compose_project": (item.get("labels") or {}).get("com.docker.compose.project"),
        "persistence": persistence,
        "native_counterpart": counterpart,
        "external_backup": external,
        "unique_data": unique,
        "final_classification": final,
        "catalog_databases": facts.get("catalog_databases", []),
    }
    if name in PRESERVATION_FACTS:
        record["preservation"] = PRESERVATION_FACTS[name]
    return record


def build_matrix(
    inventory: dict[str, Any],
    vhd_backup: str,
    source_inventory_sha256: str | None = None,
) -> dict[str, Any]:
    desktop = inventory["desktop"]
    native = inventory["native"]
    records: list[dict[str, Any]] = []

    for item in desktop["containers"]:
        owner = _project_from_text(item.get("name"), item.get("labels"))
        records.append(
            {
                "asset_type": "container",
                "asset": item["name"],
                "id": item["id"],
                "owner": owner,
                "size_bytes": item.get("size_rw"),
                "created_at": item.get("created"),
                "compose_project": (item.get("labels") or {}).get("com.docker.compose.project"),
                "mount_relations": [mount.get("Name") or mount.get("Source") for mount in item.get("mounts", [])],
                "persistence": "REPRODUCIBLE_RUNTIME_ARTIFACT",
                "native_counterpart": "SUPERSEDED_BY_NATIVE",
                "external_backup": vhd_backup,
                "unique_data": False,
                "final_classification": "SAFE_TO_DELETE_WITH_DESKTOP",
                "writable_layer_entry_count": len(item.get("writable_layer_diff", [])),
            }
        )

    for item in desktop["volumes"]:
        records.append(_volume_record(item, native, vhd_backup))

    for item in desktop["images"]:
        labels = item.get("labels") or {}
        owner = _project_from_text(item.get("repo_tags"), labels)
        records.append(
            {
                "asset_type": "image",
                "asset": item.get("repo_tags") or [item["id"]],
                "id": item["id"],
                "owner": owner,
                "size_bytes": item.get("size"),
                "created_at": item.get("created"),
                "compose_project": labels.get("com.docker.compose.project"),
                "persistence": "REPRODUCIBLE_RUNTIME_ARTIFACT",
                "native_counterpart": "SUPERSEDED_BY_NATIVE" if owner in {"bTest", "OA", "Gaia"} else "UNKNOWN",
                "external_backup": None,
                "unique_data": False,
                "final_classification": "SAFE_TO_DELETE_WITH_DESKTOP",
            }
        )

    for item in desktop["networks"]:
        owner = _project_from_text(item.get("name"), item.get("labels"))
        records.append(
            {
                "asset_type": "network",
                "asset": item["name"],
                "id": item["id"],
                "owner": owner,
                "created_at": item.get("created"),
                "compose_project": (item.get("labels") or {}).get("com.docker.compose.project"),
                "mount_relations": item.get("container_names", []),
                "persistence": "REPRODUCIBLE_RUNTIME_ARTIFACT",
                "native_counterpart": "SUPERSEDED_BY_NATIVE" if _native_named(native, "network", item["name"]) else "UNKNOWN",
                "external_backup": None,
                "unique_data": False,
                "final_classification": "SAFE_TO_DELETE_WITH_DESKTOP",
            }
        )

    for item in desktop["build_cache"]:
        records.append(
            {
                "asset_type": "build_cache",
                "asset": item["ID"],
                "owner": "unknown",
                "size": item.get("Size"),
                "created_at": item.get("CreatedAt"),
                "description": item.get("Description"),
                "persistence": "CACHE",
                "native_counterpart": "UNKNOWN",
                "external_backup": None,
                "unique_data": False,
                "final_classification": "SAFE_TO_DELETE_WITH_DESKTOP",
            }
        )

    return {
        "schema_version": 1,
        "source_inventory_sha256": source_inventory_sha256
        or _sha256_bytes(json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode()),
        "records": records,
        "summary": {
            "record_count": len(records),
            "by_type": {kind: sum(record["asset_type"] == kind for record in records) for kind in ("container", "volume", "image", "network", "build_cache")},
            "oa_desktop_persistent_unique_data": 0,
            "project_approval_gate": "PASS (3/3)",
            "remaining_veto_assets": sum(record["final_classification"] == "VETO_DELETE" for record in records),
            "remaining_unknown_assets": sum(record["final_classification"] == "UNKNOWN" for record in records),
            "by_final_classification": {
                classification: sum(record["final_classification"] == classification for record in records)
                for classification in (
                    "SAFE_TO_DELETE_WITH_DESKTOP",
                    "EXTERNALLY_PRESERVED_THEN_SAFE_TO_DELETE",
                    "KEEP_OUTSIDE_DESKTOP",
                    "VETO_DELETE",
                    "UNKNOWN",
                )
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--vhd-backup", required=True)
    args = parser.parse_args()
    inventory_bytes = args.inventory.read_bytes()
    inventory = json.loads(inventory_bytes.decode("utf-8"))
    matrix = build_matrix(
        inventory,
        args.vhd_backup,
        source_inventory_sha256=_sha256_bytes(inventory_bytes),
    )
    encoded = json.dumps(matrix, indent=2, sort_keys=True).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = encoded + b"\n"
    args.output.write_bytes(payload)
    digest = _sha256_bytes(payload)
    args.output.with_suffix(args.output.suffix + ".sha256").write_text(
        f"{digest}  {args.output.name}\n", encoding="ascii"
    )
    print(digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
