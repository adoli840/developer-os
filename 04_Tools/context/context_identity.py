#!/usr/bin/env python3
"""Project- and lane-isolated development context identity contracts."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import PurePosixPath
from typing import Any, Iterable, Mapping


DEVELOPMENT_CONTEXT_SEAL_VERSION = "DevelopmentContextSealV1"
DIRTY_TREE_SCOPE_MANIFEST_VERSION = "DirtyTreeScopeManifestV1"
AUTHORITY_STATUS = "NON_AUTHORITATIVE_DERIVED_INDEX"
SOURCE_WINS = "CANONICAL_SOURCE_WINS"

DIRTY_CLASSIFICATIONS = {
    "IN_SCOPE",
    "USER_OWNED_OUT_OF_SCOPE",
    "UNCLASSIFIED",
}
DIRTY_STATES = {
    "STAGED",
    "UNSTAGED",
    "UNTRACKED",
    "DELETED",
    "RENAMED",
}
IDENTITY_KINDS = {"GIT_BLOB", "CONTENT_SHA256", "ABSENT"}

MANIFEST_INVALIDATION_REASONS = {
    "MANIFEST_HASH_MISMATCH",
    "PROJECT_MISMATCH",
    "LANE_MISMATCH",
    "NAMESPACE_MISMATCH",
    "WORKSPACE_MISMATCH",
    "HEAD_DRIFT",
    "DIRTY_PATH_SET_DRIFT",
    "DIRTY_PATH_IDENTITY_DRIFT",
    "UNCLASSIFIED_DIRTY_PATH",
}

SEAL_INVALIDATION_REASONS = {
    "SEAL_HASH_MISMATCH",
    "PROJECT_MISMATCH",
    "LANE_MISMATCH",
    "NAMESPACE_MISMATCH",
    "WORKSPACE_MISMATCH",
    "BRANCH_DRIFT",
    "HEAD_DRIFT",
    "TASK_IDENTITY_DRIFT",
    "CANONICAL_STATE_DRIFT",
    "POLICY_REFERENCE_DRIFT",
    "CONTEXT_ENTRY_SET_DRIFT",
    "CONTEXT_ENTRY_IDENTITY_DRIFT",
    "DIRTY_MANIFEST_DRIFT",
    "DIRTY_MANIFEST_INVALID",
    "TOOL_VERSION_DRIFT",
    "PROTOCOL_VERSION_DRIFT",
}

_HEX_40_OR_64 = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


class ContextIdentityContractError(ValueError):
    """A context identity object violates its strict contract."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def namespace_sha256(project: str, lane: str) -> str:
    return sha256_json({"lane": _required(lane, "lane"), "project": _required(project, "project")})


def content_identity(kind: str, value: str | None = None) -> dict[str, str | None]:
    identity = {"kind": kind, "value": value}
    _validate_identity(identity, "content identity")
    return identity


def dirty_path_entry(
    *,
    path: str,
    states: Iterable[str],
    classification: str,
    pre_identity: Mapping[str, Any],
    current_identity: Mapping[str, Any],
    scope_basis: str | None,
    renamed_from: str | None = None,
) -> dict[str, Any]:
    entry = {
        "path": _relative_path(path),
        "states": sorted(set(states)),
        "classification": classification,
        "pre_identity": dict(pre_identity),
        "current_identity": dict(current_identity),
        "scope_basis": scope_basis,
        "renamed_from": _relative_path(renamed_from) if renamed_from is not None else None,
    }
    _validate_dirty_entry(entry)
    return entry


def build_dirty_tree_scope_manifest_v1(
    *,
    project: str,
    lane: str,
    workspace: str,
    base_head: str,
    entries: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    manifest_entries = [copy.deepcopy(dict(item)) for item in entries]
    manifest_entries.sort(key=lambda item: item.get("path", ""))
    manifest = {
        "contract_version": DIRTY_TREE_SCOPE_MANIFEST_VERSION,
        "project": _required(project, "project"),
        "lane": _required(lane, "lane"),
        "namespace_sha256": namespace_sha256(project, lane),
        "workspace": _required(workspace, "workspace"),
        "base_head": _git_object_id(base_head, "base_head"),
        "entries": manifest_entries,
        "manifest_sha256": "PENDING",
    }
    _validate_dirty_manifest_shape(manifest, verify_hash=False)
    manifest["manifest_sha256"] = sha256_json(_without_hash(manifest, "manifest_sha256"))
    return manifest


def validate_dirty_tree_scope_manifest_v1(
    manifest: Mapping[str, Any],
    *,
    expected_project: str,
    expected_lane: str,
    expected_workspace: str,
    expected_base_head: str,
    observed_entries: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    value = copy.deepcopy(dict(manifest))
    _validate_dirty_manifest_shape(value, verify_hash=False)
    reasons: set[str] = set()
    if value["manifest_sha256"] != sha256_json(_without_hash(value, "manifest_sha256")):
        reasons.add("MANIFEST_HASH_MISMATCH")
    if value["project"] != expected_project:
        reasons.add("PROJECT_MISMATCH")
    if value["lane"] != expected_lane:
        reasons.add("LANE_MISMATCH")
    if value["namespace_sha256"] != namespace_sha256(expected_project, expected_lane):
        reasons.add("NAMESPACE_MISMATCH")
    if value["workspace"] != expected_workspace:
        reasons.add("WORKSPACE_MISMATCH")
    if value["base_head"] != expected_base_head:
        reasons.add("HEAD_DRIFT")
    if any(item["classification"] == "UNCLASSIFIED" for item in value["entries"]):
        reasons.add("UNCLASSIFIED_DIRTY_PATH")

    if observed_entries is not None:
        observed = [copy.deepcopy(dict(item)) for item in observed_entries]
        for item in observed:
            _validate_dirty_entry(item)
        sealed_by_path = {item["path"]: item for item in value["entries"]}
        observed_by_path = {item["path"]: item for item in observed}
        if set(sealed_by_path) != set(observed_by_path):
            reasons.add("DIRTY_PATH_SET_DRIFT")
        for path in set(sealed_by_path).intersection(observed_by_path):
            if sealed_by_path[path]["current_identity"] != observed_by_path[path]["current_identity"]:
                reasons.add("DIRTY_PATH_IDENTITY_DRIFT")

    unknown = reasons - MANIFEST_INVALIDATION_REASONS
    if unknown:
        raise ContextIdentityContractError(f"unknown manifest invalidation reasons: {sorted(unknown)}")
    reusable = not reasons
    return {
        "contract_version": DIRTY_TREE_SCOPE_MANIFEST_VERSION,
        "status": "VALID" if reusable else "INVALID",
        "invalidation_reasons": sorted(reasons),
        "namespace_sha256": value["namespace_sha256"],
        "manifest_sha256": value["manifest_sha256"],
        "cache_reuse_eligible": reusable,
        "auto_advance_eligible": reusable,
        "authority_resolution": SOURCE_WINS,
    }


def context_entry(
    *,
    path: str,
    identity: Mapping[str, Any],
    inclusion_reason: str,
    byte_size: int,
) -> dict[str, Any]:
    entry = {
        "path": _relative_path(path),
        "identity": dict(identity),
        "inclusion_reason": _required(inclusion_reason, "inclusion_reason"),
        "byte_size": byte_size,
    }
    _validate_context_entry(entry)
    return entry


def policy_reference(reference_id: str, identity_sha256: str) -> dict[str, str]:
    value = {
        "reference_id": _required(reference_id, "reference_id"),
        "identity_sha256": _sha256(identity_sha256, "reference identity"),
    }
    return value


def build_development_context_seal_v1(
    *,
    project: str,
    lane: str,
    workspace: str,
    branch: str,
    head: str,
    task_identity: str,
    canonical_state_sha256: str,
    active_references: Iterable[Mapping[str, Any]],
    context_entries: Iterable[Mapping[str, Any]],
    dirty_manifest: Mapping[str, Any],
    tool_version: str,
    protocol_version: str,
) -> dict[str, Any]:
    dirty = copy.deepcopy(dict(dirty_manifest))
    _validate_dirty_manifest_shape(dirty, verify_hash=True)
    project_value = _required(project, "project")
    lane_value = _required(lane, "lane")
    namespace = namespace_sha256(project_value, lane_value)
    if dirty["project"] != project_value or dirty["lane"] != lane_value:
        raise ContextIdentityContractError("dirty manifest crosses project or lane namespace")
    if dirty["namespace_sha256"] != namespace or dirty["workspace"] != workspace:
        raise ContextIdentityContractError("dirty manifest namespace or workspace mismatch")
    if dirty["base_head"] != head:
        raise ContextIdentityContractError("dirty manifest HEAD does not match context seal")

    references = [copy.deepcopy(dict(item)) for item in active_references]
    references.sort(key=lambda item: item.get("reference_id", ""))
    entries = [copy.deepcopy(dict(item)) for item in context_entries]
    entries.sort(key=lambda item: item.get("path", ""))
    for item in references:
        _validate_reference(item)
    for item in entries:
        _validate_context_entry(item)
    _require_unique(references, "reference_id", "active reference")
    _require_unique(entries, "path", "context entry")

    valid_if = {
        "project": project_value,
        "lane": lane_value,
        "namespace_sha256": namespace,
        "workspace": _required(workspace, "workspace"),
        "branch": _required(branch, "branch"),
        "head": _git_object_id(head, "head"),
        "task_identity": _sha256(task_identity, "task identity"),
        "canonical_state_sha256": _sha256(canonical_state_sha256, "canonical state hash"),
        "active_references_sha256": sha256_json(references),
        "context_entries_sha256": sha256_json(entries),
        "dirty_manifest_sha256": dirty["manifest_sha256"],
        "tool_version": _required(tool_version, "tool_version"),
        "protocol_version": _required(protocol_version, "protocol_version"),
    }
    seal = {
        "contract_version": DEVELOPMENT_CONTEXT_SEAL_VERSION,
        "authority_status": AUTHORITY_STATUS,
        "project": project_value,
        "lane": lane_value,
        "namespace_sha256": namespace,
        "workspace": valid_if["workspace"],
        "branch": valid_if["branch"],
        "head": valid_if["head"],
        "task_identity": valid_if["task_identity"],
        "canonical_state_sha256": valid_if["canonical_state_sha256"],
        "active_references": references,
        "context_entries": entries,
        "dirty_manifest_sha256": dirty["manifest_sha256"],
        "tool_version": valid_if["tool_version"],
        "protocol_version": valid_if["protocol_version"],
        "valid_if": valid_if,
        "seal_sha256": "PENDING",
    }
    _validate_seal_shape(seal, verify_hash=False)
    seal["seal_sha256"] = sha256_json(_without_hash(seal, "seal_sha256"))
    return seal


def validate_development_context_seal_v1(
    seal: Mapping[str, Any],
    *,
    expected_project: str,
    expected_lane: str,
    expected_workspace: str,
    expected_branch: str,
    expected_head: str,
    expected_task_identity: str,
    expected_canonical_state_sha256: str,
    observed_active_references: Iterable[Mapping[str, Any]],
    observed_context_entries: Iterable[Mapping[str, Any]],
    dirty_manifest: Mapping[str, Any],
    expected_tool_version: str,
    expected_protocol_version: str,
) -> dict[str, Any]:
    value = copy.deepcopy(dict(seal))
    _validate_seal_shape(value, verify_hash=False)
    dirty_validation = validate_dirty_tree_scope_manifest_v1(
        dirty_manifest,
        expected_project=expected_project,
        expected_lane=expected_lane,
        expected_workspace=expected_workspace,
        expected_base_head=expected_head,
    )
    references = [copy.deepcopy(dict(item)) for item in observed_active_references]
    entries = [copy.deepcopy(dict(item)) for item in observed_context_entries]
    references.sort(key=lambda item: item.get("reference_id", ""))
    entries.sort(key=lambda item: item.get("path", ""))
    for item in references:
        _validate_reference(item)
    for item in entries:
        _validate_context_entry(item)

    reasons: set[str] = set()
    if value["seal_sha256"] != sha256_json(_without_hash(value, "seal_sha256")):
        reasons.add("SEAL_HASH_MISMATCH")
    if value["project"] != expected_project:
        reasons.add("PROJECT_MISMATCH")
    if value["lane"] != expected_lane:
        reasons.add("LANE_MISMATCH")
    if value["namespace_sha256"] != namespace_sha256(expected_project, expected_lane):
        reasons.add("NAMESPACE_MISMATCH")
    if value["workspace"] != expected_workspace:
        reasons.add("WORKSPACE_MISMATCH")
    if value["branch"] != expected_branch:
        reasons.add("BRANCH_DRIFT")
    if value["head"] != expected_head:
        reasons.add("HEAD_DRIFT")
    if value["task_identity"] != expected_task_identity:
        reasons.add("TASK_IDENTITY_DRIFT")
    if value["canonical_state_sha256"] != expected_canonical_state_sha256:
        reasons.add("CANONICAL_STATE_DRIFT")
    if value["active_references"] != references:
        reasons.add("POLICY_REFERENCE_DRIFT")
    sealed_entries = {item["path"]: item for item in value["context_entries"]}
    observed_by_path = {item["path"]: item for item in entries}
    if set(sealed_entries) != set(observed_by_path):
        reasons.add("CONTEXT_ENTRY_SET_DRIFT")
    for path in set(sealed_entries).intersection(observed_by_path):
        if sealed_entries[path]["identity"] != observed_by_path[path]["identity"]:
            reasons.add("CONTEXT_ENTRY_IDENTITY_DRIFT")
    if value["dirty_manifest_sha256"] != dirty_manifest.get("manifest_sha256"):
        reasons.add("DIRTY_MANIFEST_DRIFT")
    if dirty_validation["status"] != "VALID":
        reasons.add("DIRTY_MANIFEST_INVALID")
    if value["tool_version"] != expected_tool_version:
        reasons.add("TOOL_VERSION_DRIFT")
    if value["protocol_version"] != expected_protocol_version:
        reasons.add("PROTOCOL_VERSION_DRIFT")

    unknown = reasons - SEAL_INVALIDATION_REASONS
    if unknown:
        raise ContextIdentityContractError(f"unknown seal invalidation reasons: {sorted(unknown)}")
    valid = not reasons
    return {
        "contract_version": DEVELOPMENT_CONTEXT_SEAL_VERSION,
        "status": "VALID" if valid else "INVALID",
        "invalidation_reasons": sorted(reasons),
        "namespace_sha256": value["namespace_sha256"],
        "seal_sha256": value["seal_sha256"],
        "cache_reuse_eligible": valid,
        "auto_advance_eligible": valid,
        "authority_resolution": SOURCE_WINS,
        "seal_authority": AUTHORITY_STATUS,
    }


def _validate_dirty_manifest_shape(value: Mapping[str, Any], *, verify_hash: bool) -> None:
    _exact_keys(
        value,
        {
            "contract_version", "project", "lane", "namespace_sha256", "workspace",
            "base_head", "entries", "manifest_sha256",
        },
        "dirty-tree manifest",
    )
    if value["contract_version"] != DIRTY_TREE_SCOPE_MANIFEST_VERSION:
        raise ContextIdentityContractError("unsupported dirty-tree manifest version")
    _required(value["project"], "project")
    _required(value["lane"], "lane")
    _sha256(value["namespace_sha256"], "namespace")
    if value["namespace_sha256"] != namespace_sha256(value["project"], value["lane"]):
        raise ContextIdentityContractError("dirty-tree namespace identity mismatch")
    _required(value["workspace"], "workspace")
    _git_object_id(value["base_head"], "base_head")
    if not isinstance(value["entries"], list):
        raise ContextIdentityContractError("dirty-tree entries must be an array")
    for item in value["entries"]:
        _validate_dirty_entry(item)
    _require_unique(value["entries"], "path", "dirty path")
    if value["entries"] != sorted(value["entries"], key=lambda item: item["path"]):
        raise ContextIdentityContractError("dirty-tree entries must be ordered by path")
    if verify_hash and value["manifest_sha256"] != sha256_json(_without_hash(value, "manifest_sha256")):
        raise ContextIdentityContractError("dirty-tree manifest hash mismatch")


def _validate_dirty_entry(value: Mapping[str, Any]) -> None:
    _exact_keys(
        value,
        {
            "path", "states", "classification", "pre_identity", "current_identity",
            "scope_basis", "renamed_from",
        },
        "dirty path",
    )
    _relative_path(value["path"])
    states = value["states"]
    if not isinstance(states, list) or not states or states != sorted(set(states)):
        raise ContextIdentityContractError("dirty path states must be a sorted unique array")
    if not set(states) <= DIRTY_STATES:
        raise ContextIdentityContractError("unsupported dirty path state")
    if value["classification"] not in DIRTY_CLASSIFICATIONS:
        raise ContextIdentityContractError("unsupported dirty path classification")
    _validate_identity(value["pre_identity"], "pre identity")
    _validate_identity(value["current_identity"], "current identity")
    scope_basis = value["scope_basis"]
    if value["classification"] == "UNCLASSIFIED":
        if scope_basis is not None:
            raise ContextIdentityContractError("unclassified dirty path cannot claim scope basis")
    elif not isinstance(scope_basis, str) or not scope_basis.strip():
        raise ContextIdentityContractError("classified dirty path requires scope basis")
    if "UNTRACKED" in states and value["pre_identity"]["kind"] != "ABSENT":
        raise ContextIdentityContractError("untracked path must have absent pre identity")
    if "DELETED" in states and value["current_identity"]["kind"] != "ABSENT":
        raise ContextIdentityContractError("deleted path must have absent current identity")
    if "RENAMED" in states:
        if value["renamed_from"] is None:
            raise ContextIdentityContractError("renamed path requires renamed_from")
        _relative_path(value["renamed_from"])
    elif value["renamed_from"] is not None:
        raise ContextIdentityContractError("renamed_from requires RENAMED state")


def _validate_seal_shape(value: Mapping[str, Any], *, verify_hash: bool) -> None:
    _exact_keys(
        value,
        {
            "contract_version", "authority_status", "project", "lane", "namespace_sha256",
            "workspace", "branch", "head", "task_identity", "canonical_state_sha256",
            "active_references", "context_entries", "dirty_manifest_sha256", "tool_version",
            "protocol_version", "valid_if", "seal_sha256",
        },
        "development context seal",
    )
    if value["contract_version"] != DEVELOPMENT_CONTEXT_SEAL_VERSION:
        raise ContextIdentityContractError("unsupported development context seal version")
    if value["authority_status"] != AUTHORITY_STATUS:
        raise ContextIdentityContractError("development context seal cannot claim authority")
    _required(value["project"], "project")
    _required(value["lane"], "lane")
    if value["namespace_sha256"] != namespace_sha256(value["project"], value["lane"]):
        raise ContextIdentityContractError("development context namespace mismatch")
    _required(value["workspace"], "workspace")
    _required(value["branch"], "branch")
    _git_object_id(value["head"], "head")
    _sha256(value["task_identity"], "task identity")
    _sha256(value["canonical_state_sha256"], "canonical state hash")
    _sha256(value["dirty_manifest_sha256"], "dirty manifest hash")
    _required(value["tool_version"], "tool_version")
    _required(value["protocol_version"], "protocol_version")
    if not isinstance(value["active_references"], list):
        raise ContextIdentityContractError("active references must be an array")
    if not isinstance(value["context_entries"], list):
        raise ContextIdentityContractError("context entries must be an array")
    for item in value["active_references"]:
        _validate_reference(item)
    for item in value["context_entries"]:
        _validate_context_entry(item)
    _require_unique(value["active_references"], "reference_id", "active reference")
    _require_unique(value["context_entries"], "path", "context entry")
    if value["active_references"] != sorted(
        value["active_references"], key=lambda item: item["reference_id"],
    ):
        raise ContextIdentityContractError("active references must be ordered")
    if value["context_entries"] != sorted(value["context_entries"], key=lambda item: item["path"]):
        raise ContextIdentityContractError("context entries must be ordered")
    expected_valid_if = {
        "project": value["project"],
        "lane": value["lane"],
        "namespace_sha256": value["namespace_sha256"],
        "workspace": value["workspace"],
        "branch": value["branch"],
        "head": value["head"],
        "task_identity": value["task_identity"],
        "canonical_state_sha256": value["canonical_state_sha256"],
        "active_references_sha256": sha256_json(value["active_references"]),
        "context_entries_sha256": sha256_json(value["context_entries"]),
        "dirty_manifest_sha256": value["dirty_manifest_sha256"],
        "tool_version": value["tool_version"],
        "protocol_version": value["protocol_version"],
    }
    if value["valid_if"] != expected_valid_if:
        raise ContextIdentityContractError("development context valid_if mismatch")
    if verify_hash and value["seal_sha256"] != sha256_json(_without_hash(value, "seal_sha256")):
        raise ContextIdentityContractError("development context seal hash mismatch")


def _validate_context_entry(value: Mapping[str, Any]) -> None:
    _exact_keys(value, {"path", "identity", "inclusion_reason", "byte_size"}, "context entry")
    _relative_path(value["path"])
    _validate_identity(value["identity"], "context entry identity")
    if value["identity"]["kind"] == "ABSENT":
        raise ContextIdentityContractError("selected context entry cannot be absent")
    _required(value["inclusion_reason"], "inclusion_reason")
    if not isinstance(value["byte_size"], int) or isinstance(value["byte_size"], bool) or value["byte_size"] < 0:
        raise ContextIdentityContractError("context entry byte_size must be a non-negative integer")


def _validate_reference(value: Mapping[str, Any]) -> None:
    _exact_keys(value, {"reference_id", "identity_sha256"}, "active reference")
    _required(value["reference_id"], "reference_id")
    _sha256(value["identity_sha256"], "reference identity")


def _validate_identity(value: Mapping[str, Any], field: str) -> None:
    _exact_keys(value, {"kind", "value"}, field)
    kind = value["kind"]
    identity = value["value"]
    if kind not in IDENTITY_KINDS:
        raise ContextIdentityContractError(f"unsupported {field} kind")
    if kind == "ABSENT":
        if identity is not None:
            raise ContextIdentityContractError(f"{field} ABSENT value must be null")
    elif kind == "GIT_BLOB":
        _git_object_id(identity, field)
    else:
        _sha256(identity, field)


def _without_hash(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    return {key: copy.deepcopy(item) for key, item in value.items() if key != field}


def _required(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContextIdentityContractError(f"{field} is required")
    return value.strip()


def _relative_path(value: Any) -> str:
    normalized = _required(value, "path").replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or normalized.startswith("./") or re.match(r"^[A-Za-z]:", normalized):
        raise ContextIdentityContractError("path must be normalized and project-relative")
    return path.as_posix()


def _git_object_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _HEX_40_OR_64.fullmatch(value):
        raise ContextIdentityContractError(f"{field} must be a Git object identity")
    return value


def _sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _HEX_64.fullmatch(value):
        raise ContextIdentityContractError(f"{field} must be SHA-256")
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], field: str) -> None:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ContextIdentityContractError(f"{field} fields are invalid")


def _require_unique(values: Iterable[Mapping[str, Any]], field: str, label: str) -> None:
    identities = [item[field] for item in values]
    if len(identities) != len(set(identities)):
        raise ContextIdentityContractError(f"duplicate {label} identity")
