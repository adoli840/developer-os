from __future__ import annotations

import json
from typing import Any


class SchemaError(ValueError):
    """Raised when a strict orchestration document is invalid."""


def _type_ok(value: Any, expected: str) -> bool:
    if isinstance(expected, list):
        return any(_type_ok(value, item) for item in expected)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    return False


def validate_strict(value: Any, schema: dict[str, Any], path: str = "$", *, allow_null: bool = False) -> None:
    if value is None and (allow_null or schema.get("nullable") is True):
        return
    expected = schema.get("type")
    if expected and not _type_ok(value, expected):
        raise SchemaError(f"{path}: expected {expected}")
    if "enum" in schema and value not in schema["enum"]:
        raise SchemaError(f"{path}: invalid enum value")
    if isinstance(value, str):
        if len(value) > int(schema.get("maxLength", 120_000)):
            raise SchemaError(f"{path}: string is too long")
    if isinstance(value, list):
        if len(value) > int(schema.get("maxItems", 1_000)):
            raise SchemaError(f"{path}: too many items")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                validate_strict(item, item_schema, f"{path}[{index}]")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        missing = [name for name in required if name not in value]
        if missing:
            raise SchemaError(f"{path}: missing required field(s): {', '.join(missing)}")
        if schema.get("additionalProperties") is False:
            unknown = sorted(set(value) - set(properties))
            if unknown:
                raise SchemaError(f"{path}: unknown field(s): {', '.join(unknown)}")
        for name, child_schema in properties.items():
            if name in value:
                validate_strict(value[name], child_schema, f"{path}.{name}", allow_null=child_schema.get("type") == "null")


def evidence_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["source", "captured_at", "sha256", "line_numbered_content"],
        "properties": {
            "source": {"type": "string", "maxLength": 1_000},
            "captured_at": {"type": "string", "maxLength": 100},
            "sha256": {"type": "string", "maxLength": 64},
            "line_numbered_content": {"type": "string", "maxLength": 120_000},
        },
    }


def reviewer_output_schema_v1() -> dict[str, Any]:
    status = {"type": "string", "enum": ["PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE"]}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version", "review_id", "gate_decision", "executive_summary",
            "contract_assessment", "findings", "evidence_refs", "next_instruction",
            "user_decision_packet", "blocker_packet", "branch_assessment",
        ],
        "properties": {
            "schema_version": {"type": "string", "enum": ["1"]},
            "review_id": {"type": "string", "maxLength": 200},
            "gate_decision": {"type": "string", "enum": ["SAFE_CONTINUE", "USER_REQUIRED", "BLOCKED", "STOP"]},
            "executive_summary": {"type": "string", "maxLength": 12_000},
            "contract_assessment": {
                "type": "object", "additionalProperties": False,
                "required": ["purpose", "scope", "frozen_decisions", "semantic_contract", "authority", "routing", "safety", "test_evidence", "provenance", "report_completeness"],
                "properties": {name: status for name in ["purpose", "scope", "frozen_decisions", "semantic_contract", "authority", "routing", "safety", "test_evidence", "provenance", "report_completeness"]},
            },
            "findings": {
                "type": "array", "maxItems": 100,
                "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["finding_id", "severity", "category", "description", "evidence_refs", "consequence", "required_action", "user_decision_required"],
                    "properties": {
                        "finding_id": {"type": "string", "maxLength": 100},
                        "severity": {"type": "string", "enum": ["INFO", "WARNING", "BLOCKING", "STOP"]},
                        "category": {"type": "string", "maxLength": 100},
                        "description": {"type": "string", "maxLength": 5_000},
                        "evidence_refs": {"type": "array", "items": {"type": "string", "maxLength": 200}},
                        "consequence": {"type": "string", "maxLength": 5_000},
                        "required_action": {"type": "string", "maxLength": 5_000},
                        "user_decision_required": {"type": "boolean"},
                    },
                },
            },
            "evidence_refs": {"type": "array", "items": {"type": "string", "maxLength": 200}},
            "next_instruction": {"type": ["object", "null"], "additionalProperties": False, "required": ["title", "purpose", "frozen_decisions", "scope", "prohibited_actions", "tasks", "required_tests", "required_evidence", "result_report_format", "stop_conditions"], "properties": {name: {"type": "string", "maxLength": 12_000} for name in ["title", "purpose", "frozen_decisions", "scope", "prohibited_actions", "tasks", "required_tests", "required_evidence", "result_report_format", "stop_conditions"]}},
            "user_decision_packet": {"type": ["object", "null"], "additionalProperties": False, "required": ["decision_id", "question", "why_user_authority_is_required", "known_facts", "options", "tradeoffs", "reviewer_recommendation", "consequences_of_no_decision"], "properties": {name: {"type": "string", "maxLength": 12_000} for name in ["decision_id", "question", "why_user_authority_is_required", "known_facts", "options", "tradeoffs", "reviewer_recommendation", "consequences_of_no_decision"]}},
            "blocker_packet": {"type": ["object", "null"], "additionalProperties": False, "required": ["blocker", "evidence", "attempted_or_available_checks", "exact_unblocking_requirement"], "properties": {name: {"type": "string", "maxLength": 12_000} for name in ["blocker", "evidence", "attempted_or_available_checks", "exact_unblocking_requirement"]}},
            "branch_assessment": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["branch_id", "dependency_status", "rationale"], "properties": {"branch_id": {"type": "string", "maxLength": 200}, "dependency_status": {"type": "string", "enum": ["CONTINUE_CANDIDATE", "PAUSE_REQUIRED", "UNKNOWN"]}, "rationale": {"type": "string", "maxLength": 5_000}}}},
        },
    }


def reviewer_output_schema_v2() -> dict[str, Any]:
    status = {"type": "string", "enum": ["PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE"]}
    routing_assessment = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "resolution_kind", "safe_bounded_next_step_available",
            "evidence_collection_possible", "user_authority_required",
            "blocker_class", "blocker_detail",
        ],
        "properties": {
            "resolution_kind": {
                "type": "string",
                "enum": ["BOUNDED_TASK", "USER_DECISION", "MISSING_DEPENDENCY", "SAFETY_STOP", "NONE"],
            },
            "safe_bounded_next_step_available": {"type": "boolean"},
            "evidence_collection_possible": {"type": "boolean"},
            "user_authority_required": {"type": "boolean"},
            "blocker_class": {
                "type": "string",
                "enum": ["NONE", "ENVIRONMENT", "PERMISSION", "MISSING_ARTIFACT", "EXTERNAL_DEPENDENCY", "CREDENTIAL", "OTHER"],
            },
            "blocker_detail": {"type": ["string", "null"], "maxLength": 12_000},
        },
    }
    v1 = reviewer_output_schema_v1()
    properties = dict(v1["properties"])
    properties.pop("schema_version")
    properties.pop("gate_decision")
    properties.update({
        "schema_version": {"type": "string", "enum": ["2"]},
        "review_verdict": {"type": "string", "enum": ["PASS", "FAIL", "INCOMPLETE", "UNKNOWN"]},
        "orchestration_gate": {"type": "string", "enum": ["SAFE_CONTINUE", "USER_REQUIRED", "BLOCKED", "STOP"]},
        "routing_assessment": routing_assessment,
    })
    required = [
        "schema_version", "review_id", "review_verdict", "orchestration_gate",
        "routing_assessment", "executive_summary", "contract_assessment",
        "findings", "evidence_refs", "next_instruction", "user_decision_packet",
        "blocker_packet", "branch_assessment",
    ]
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


def reviewer_output_schema_v2_1() -> dict[str, Any]:
    schema = reviewer_output_schema_v2()
    properties = dict(schema["properties"])
    properties["schema_version"] = {"type": "string", "enum": ["2.1"]}
    instruction = dict(properties["next_instruction"])
    instruction_properties = dict(instruction["properties"])
    instruction_properties["addresses_requirement_ids"] = {
        "type": "array", "maxItems": 500,
        "items": {"type": "string", "maxLength": 200},
    }
    instruction["properties"] = instruction_properties
    instruction["required"] = [*instruction["required"], "addresses_requirement_ids"]
    properties["next_instruction"] = instruction
    properties["task_requirement_assessment"] = {
        "type": "array", "maxItems": 500,
        "items": {
            "type": "object", "additionalProperties": False,
            "required": ["requirement_id", "status", "evidence_refs", "unresolved_action"],
            "properties": {
                "requirement_id": {"type": "string", "maxLength": 200},
                "status": {
                    "type": "string",
                    "enum": ["SATISFIED", "UNRESOLVED", "BLOCKED", "NOT_APPLICABLE"],
                },
                "evidence_refs": {
                    "type": "array", "maxItems": 100,
                    "items": {"type": "string", "maxLength": 200},
                },
                "unresolved_action": {"type": ["string", "null"], "maxLength": 12_000},
            },
        },
    }
    properties["added_scope"] = {
        "type": "array", "maxItems": 100,
        "items": {
            "type": "object", "additionalProperties": False,
            "required": [
                "added_scope", "prerequisite_justification", "exact_blocking_evidence",
                "replaces_original_task", "related_requirement_ids",
            ],
            "properties": {
                "added_scope": {"type": "string", "maxLength": 12_000},
                "prerequisite_justification": {"type": "string", "maxLength": 12_000},
                "exact_blocking_evidence": {"type": ["string", "null"], "maxLength": 12_000},
                "replaces_original_task": {"type": "boolean"},
                "related_requirement_ids": {
                    "type": "array", "maxItems": 500,
                    "items": {"type": "string", "maxLength": 200},
                },
            },
        },
    }
    return {
        **schema,
        "required": [*schema["required"], "task_requirement_assessment", "added_scope"],
        "properties": properties,
    }


def reviewer_output_schema_v2_2() -> dict[str, Any]:
    schema = reviewer_output_schema_v2_1()
    properties = dict(schema["properties"])
    properties["schema_version"] = {"type": "string", "enum": ["2.2"]}

    instruction = dict(properties["next_instruction"])
    instruction_properties = dict(instruction["properties"])
    instruction_properties["primary_requirement_ids"] = {
        "type": "array", "maxItems": 500,
        "items": {"type": "string", "maxLength": 200},
    }
    instruction["properties"] = instruction_properties
    instruction["required"] = [*instruction["required"], "primary_requirement_ids"]
    properties["next_instruction"] = instruction

    assessment = dict(properties["task_requirement_assessment"])
    assessment_item = dict(assessment["items"])
    assessment_properties = dict(assessment_item["properties"])
    assessment_properties.update({
        "defer_reason": {"type": ["string", "null"], "maxLength": 12_000},
        "exact_blocking_evidence": {"type": ["string", "null"], "maxLength": 12_000},
    })
    assessment_item["properties"] = assessment_properties
    assessment_item["required"] = [
        *assessment_item["required"], "defer_reason", "exact_blocking_evidence",
    ]
    assessment["items"] = assessment_item
    properties["task_requirement_assessment"] = assessment

    added_scope = dict(properties["added_scope"])
    added_scope_item = dict(added_scope["items"])
    added_scope_properties = dict(added_scope_item["properties"])
    added_scope_properties["is_prerequisite"] = {"type": "boolean"}
    added_scope_item["properties"] = added_scope_properties
    added_scope_item["required"] = [*added_scope_item["required"], "is_prerequisite"]
    added_scope["items"] = added_scope_item
    properties["added_scope"] = added_scope
    return {**schema, "properties": properties}


def reviewer_output_schema_v2_3() -> dict[str, Any]:
    schema = reviewer_output_schema_v2_2()
    properties = dict(schema["properties"])
    properties["schema_version"] = {"type": "string", "enum": ["2.3"]}
    assessment = dict(properties["task_requirement_assessment"])
    assessment_item = dict(assessment["items"])
    assessment_properties = dict(assessment_item["properties"])
    assessment_properties.update({
        "acceptance_criteria_status": {
            "type": "string",
            "enum": ["MET", "UNMET", "CONTRADICTED", "NOT_SPECIFIED"],
        },
        "unresolved_reason_kind": {
            "type": "string",
            "enum": ["NONE", "IMPLEMENTATION_WORK", "EVIDENCE_GAP", "OTHER"],
        },
        "mandatory_additional_evidence": {"type": "boolean"},
        "mandatory_evidence_basis": {
            "type": "string",
            "enum": [
                "NONE", "ACCEPTANCE_CRITERION_UNMET", "ACTUAL_CONTRADICTION",
                "EXPLICIT_PROVENANCE_CONTRACT", "SAFETY_AUTHORITY_REQUIREMENT",
            ],
        },
        "mandatory_evidence_refs": {
            "type": "array", "maxItems": 100,
            "items": {"type": "string", "maxLength": 200},
        },
        "optional_evidence_note": {"type": ["string", "null"], "maxLength": 12_000},
    })
    assessment_item["properties"] = assessment_properties
    assessment_item["required"] = [
        *assessment_item["required"], "acceptance_criteria_status",
        "unresolved_reason_kind", "mandatory_additional_evidence",
        "mandatory_evidence_basis", "mandatory_evidence_refs",
        "optional_evidence_note",
    ]
    assessment["items"] = assessment_item
    properties["task_requirement_assessment"] = assessment
    return {**schema, "properties": properties}


def reviewer_output_schema_v2_4() -> dict[str, Any]:
    schema = reviewer_output_schema_v2_3()
    properties = dict(schema["properties"])
    properties["schema_version"] = {"type": "string", "enum": ["2.4"]}
    properties["next_step_authority"] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["task_transition", "next_step_basis", "source_refs"],
        "properties": {
            "task_transition": {
                "type": "string",
                "enum": [
                    "CONTINUE_CURRENT_TASK", "ADVANCE_AUTHORIZED_PLAN",
                    "USER_DECISION_REQUIRED",
                ],
            },
            "next_step_basis": {
                "type": "string",
                "enum": [
                    "UNRESOLVED_REQUIREMENT", "FROZEN_NEXT_STEP",
                    "APPROVED_PLAN_ITEM", "USER_DECISION", "NONE",
                ],
            },
            "source_refs": {
                "type": "array",
                "maxItems": 500,
                "items": {"type": "string", "maxLength": 500},
            },
        },
    }
    return {
        **schema,
        "required": [*schema["required"], "next_step_authority"],
        "properties": properties,
    }


def reviewer_output_schema(version: str = "1") -> dict[str, Any]:
    if version == "1":
        return reviewer_output_schema_v1()
    if version == "2":
        return reviewer_output_schema_v2()
    if version == "2.1":
        return reviewer_output_schema_v2_1()
    if version == "2.2":
        return reviewer_output_schema_v2_2()
    if version == "2.3":
        return reviewer_output_schema_v2_3()
    if version == "2.4":
        return reviewer_output_schema_v2_4()
    raise ValueError(f"unsupported reviewer schema version: {version}")


UNSUPPORTED_STRUCTURED_KEYWORDS = {"allOf", "not", "dependentRequired", "dependentSchemas", "if", "then", "else", "nullable"}


def lint_structured_output_schema(schema: dict[str, Any]) -> dict[str, Any]:
    unsupported: list[str] = []
    missing_required: list[str] = []
    missing_additional: list[str] = []
    max_depth = 0
    object_count = 0
    property_count = 0
    enum_count = 0
    enum_values = 0
    string_total = 0

    def walk(node: Any, path: str, depth: int) -> None:
        nonlocal max_depth, object_count, property_count, enum_count, enum_values, string_total
        if not isinstance(node, dict):
            return
        max_depth = max(max_depth, depth)
        for key, value in node.items():
            if key in UNSUPPORTED_STRUCTURED_KEYWORDS:
                unsupported.append(f"{path}.{key}")
            if isinstance(value, str):
                string_total += len(value)
            if key == "enum" and isinstance(value, list):
                enum_count += 1
                enum_values += len(value)
        if node.get("type") == "object" or node.get("type") == ["object", "null"]:
            object_count += 1
            properties = node.get("properties", {})
            property_count += len(properties)
            required = set(node.get("required", []))
            if set(properties) != required:
                missing_required.append(path)
            if node.get("additionalProperties") is not False:
                missing_additional.append(path)
            for name, child in properties.items():
                walk(child, f"{path}.properties.{name}", depth + 1)
        if isinstance(node.get("items"), dict):
            walk(node["items"], f"{path}.items", depth + 1)
        for key in ("anyOf", "oneOf"):
            for index, child in enumerate(node.get(key, []) if isinstance(node.get(key), list) else []):
                walk(child, f"{path}.{key}[{index}]", depth + 1)

    walk(schema, "$", 0)
    if schema.get("type") != "object":
        unsupported.append("$:root_type_not_object")
    if "anyOf" in schema:
        unsupported.append("$:root_anyOf")
    return {
        "root_type": schema.get("type"), "root_required_count": len(schema.get("required", [])),
        "root_property_count": len(schema.get("properties", {})), "object_count": object_count,
        "property_count": property_count, "maximum_nesting_depth": max_depth,
        "enum_count": enum_count, "enum_value_count": enum_values, "unsupported_keywords": sorted(set(unsupported)),
        "missing_required_property_paths": missing_required, "missing_additionalProperties_false_paths": missing_additional,
        "schema_utf8_bytes": len(json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")),
        "status": "PASS" if not unsupported and not missing_required and not missing_additional and max_depth <= 10 and property_count <= 5000 and string_total <= 120000 and enum_values <= 1000 else "FAIL",
    }
