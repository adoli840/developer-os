from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Mapping

from .manifest import build_canonical_token_request, canonical_json, sha256_bytes, sha256_json
from .schema import lint_structured_output_schema, reviewer_output_schema


SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"(?i)authorization\s*:\s*bearer\s+\S+"),
    re.compile(r"(?i)\b(?:password|passwd|secret|token)\s*[:=]\s*\S+"),
)


def sanitize_error_message(message: str, *, limit: int = 500) -> str:
    value = message
    for pattern in SECRET_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    value = re.sub(r"(?i)(postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s]+", "[REDACTED_CONNECTION_STRING]", value)
    value = "".join(char if char.isprintable() or char in "\n\t" else " " for char in value)
    return value[:limit]


def parse_error_metadata(*, http_status: int, headers: Mapping[str, str], body: bytes, captured_at: str | None = None) -> dict[str, Any]:
    request_id = next((value for key, value in headers.items() if key.lower() == "x-request-id"), None)
    content_type = next((value for key, value in headers.items() if key.lower() == "content-type"), None)
    metadata: dict[str, Any] = {
        "http_status": http_status, "x_request_id": request_id, "response_content_type": content_type,
        "response_body_bytes": len(body), "captured_at": captured_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        metadata.update({"error_body_parse_status": "NON_JSON", "error_type": None, "error_code": None, "error_param": None, "sanitized_error_message": None})
        return metadata
    error = payload.get("error", payload) if isinstance(payload, dict) else {}
    metadata.update({
        "error_body_parse_status": "JSON", "error_type": error.get("type"), "error_code": error.get("code"),
        "error_param": error.get("param"), "sanitized_error_message": sanitize_error_message(str(error.get("message", ""))),
    })
    return metadata


def content_fingerprint(content: Any) -> dict[str, Any]:
    serialized = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":")) if not isinstance(content, str) else content
    encoded = serialized.encode("utf-8")
    return {"content_type": type(content).__name__, "byte_length": len(encoded), "sha256": hashlib.sha256(encoded).hexdigest()}


def _wire_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_wire_request(canonical_request: dict[str, Any]) -> dict[str, Any]:
    """Build provider-shaped body; local manifest metadata never crosses the wire."""
    wire: dict[str, Any] = {
        "model": canonical_request["model"],
        "input": [{"role": item["role"], "content": _wire_content(item["content"])} for item in canonical_request["messages"]],
        "reasoning": canonical_request["reasoning"], "text": canonical_request["text"],
        "max_output_tokens": canonical_request["max_output_tokens"], "store": canonical_request["store"],
        "tools": canonical_request["tools"], "background": canonical_request["background"],
    }
    return wire


def audit_wire_request(canonical_request: dict[str, Any], wire_request: dict[str, Any]) -> dict[str, Any]:
    violations: list[dict[str, str]] = []
    if "verbosity" in wire_request:
        violations.append({"path": "$.verbosity", "rule": "verbosity must be nested under $.text"})
    if "format" in wire_request or "response_format" in wire_request:
        violations.append({"path": "$.format", "rule": "structured format must be nested under $.text.format"})
    if wire_request.get("reasoning", {}).get("mode") == "standard":
        violations.append({"path": "$.reasoning.mode", "rule": "standard mode must be omitted"})
    for index, item in enumerate(wire_request.get("input", [])):
        if not isinstance(item.get("content"), (str, list)):
            violations.append({"path": f"$.input[{index}].content", "rule": "message content must be string or content-part array"})
    return {
        "method": "POST", "endpoint_path": "/v1/responses", "top_level_keys": sorted(wire_request),
        "wire_body_utf8_bytes": len(canonical_json(wire_request)), "actual_wire_request_body_sha256": sha256_json(wire_request),
        "canonical_token_bearing_request_sha256": sha256_json(canonical_request),
        "canonical_wire_structure_diff": "DIFFERENT" if canonical_request != wire_request else "IDENTICAL",
        "violations": violations, "status": "FAIL" if violations else "PASS",
        "content_fingerprints": [{"role": item["role"], **content_fingerprint(item["content"])} for item in canonical_request.get("messages", [])],
    }


def audit_schema() -> dict[str, Any]:
    report = lint_structured_output_schema(reviewer_output_schema())
    report["structured_output_schema_sha256"] = sha256_json(reviewer_output_schema())
    return report
