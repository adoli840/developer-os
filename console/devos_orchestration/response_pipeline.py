from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .forensic import sanitize_error_message, sha256_bytes
from .gate import validate_review_output


class ResponsePipelineError(ValueError):
    """A provider response could not pass a named local pipeline stage."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class PipelineResult:
    stages: dict[str, str]
    output_text_sha256: str | None
    parsed_output: dict[str, Any] | None
    error: dict[str, Any] | None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def capture_response_bytes(body: bytes, directory: Path, *, request_id: str | None = None) -> dict[str, Any]:
    """Persist exact response bytes before decoding or parsing."""
    raw_path = directory / "provider-response.raw.json"
    envelope_path = directory / "provider-response-envelope.json"
    _atomic_bytes(raw_path, body)
    response = json.loads(body.decode("utf-8"))
    if not isinstance(response, dict):
        raise ResponsePipelineError("HTTP_JSON_DECODE_ERROR", "provider response root is not an object")

    output = response.get("output") if isinstance(response.get("output"), list) else []
    content_types = [
        content.get("type")
        for item in output
        if isinstance(item, dict)
        for content in item.get("content", [])
        if isinstance(content, dict)
    ]
    output_text = extract_output_text(response, allow_missing=True)
    envelope = {
        "response_id": response.get("id"),
        "requested_model": response.get("requested_model"),
        "returned_model": response.get("model"),
        "response_status": response.get("status"),
        "incomplete_details": response.get("incomplete_details"),
        "output_item_types": [item.get("type") for item in output if isinstance(item, dict)],
        "content_item_types": content_types,
        "output_text_byte_length": len(output_text.encode("utf-8")) if output_text is not None else None,
        "output_text_sha256": sha256_bytes(output_text.encode("utf-8")) if output_text is not None else None,
        "refusal_present": bool(response.get("refusal")) or "refusal" in content_types,
        "usage": response.get("usage", {}),
        "request_id": request_id or response.get("request_id"),
        "captured_at": _now(),
    }
    _atomic_bytes(envelope_path, (json.dumps(envelope, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return {"raw_path": str(raw_path), "envelope_path": str(envelope_path), **envelope}


def capture_response(response: Mapping[str, Any], directory: Path, *, request_id: str | None = None) -> dict[str, Any]:
    """Capture a decoded response for injected transports and local replay tests."""
    raw = json.dumps(response, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return capture_response_bytes(raw, directory, request_id=request_id)


def extract_output_text(response: Mapping[str, Any], *, allow_missing: bool = False) -> str | None:
    output = response.get("output")
    if not isinstance(output, list):
        if allow_missing:
            return None
        raise ResponsePipelineError("OUTPUT_TEXT_MISSING", "response output is not a list")
    texts: list[str] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            if content.get("type") == "refusal":
                raise ResponsePipelineError("REFUSAL", "provider returned a refusal content item")
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                texts.append(content["text"])
    if not texts:
        if allow_missing:
            return None
        raise ResponsePipelineError("OUTPUT_TEXT_MISSING", "no output_text content item")
    if len(texts) != 1:
        raise ResponsePipelineError("AMBIGUOUS_MULTIPLE_OUTPUT_TEXT", "more than one output_text content item")
    return texts[0]


def parse_response(
    response: Mapping[str, Any], *, expected_requirement_ids: set[str] | None = None,
) -> PipelineResult:
    stages = {
        "HTTP_RECEIVED": "PASS",
        "PROVIDER_STATUS": "NOT_RUN",
        "OUTPUT_EXTRACTION": "NOT_RUN",
        "JSON_DECODE": "NOT_RUN",
        "SCHEMA_VALIDATION": "NOT_RUN",
        "INTERNAL_MODEL_VALIDATION": "NOT_RUN",
        "GATE_VALIDATION": "NOT_RUN",
    }
    status = response.get("status")
    if status == "incomplete":
        stages["PROVIDER_STATUS"] = "FAIL"
        return PipelineResult(stages, None, None, {"code": "INCOMPLETE", "message": "provider response is incomplete"})
    if status in {"refused", "failed"} or response.get("refusal"):
        stages["PROVIDER_STATUS"] = "FAIL"
        return PipelineResult(stages, None, None, {"code": "REFUSAL", "message": "provider response was refused or failed"})
    stages["PROVIDER_STATUS"] = "PASS"
    try:
        text = extract_output_text(response)
        stages["OUTPUT_EXTRACTION"] = "PASS"
    except ResponsePipelineError as error:
        stages["OUTPUT_EXTRACTION"] = "FAIL"
        return PipelineResult(stages, None, None, {"code": error.code, "message": sanitize_error_message(str(error))})
    try:
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("structured output root is not an object")
        stages["JSON_DECODE"] = "PASS"
    except (json.JSONDecodeError, ValueError) as error:
        stages["JSON_DECODE"] = "FAIL"
        return PipelineResult(stages, sha256_bytes(text.encode("utf-8")), None, {"code": "JSON_DECODE_ERROR", "message": sanitize_error_message(str(error))})
    try:
        validate_review_output(parsed, expected_requirement_ids=expected_requirement_ids)
        stages["SCHEMA_VALIDATION"] = "PASS"
        stages["INTERNAL_MODEL_VALIDATION"] = "PASS"
    except Exception as error:
        stages["SCHEMA_VALIDATION"] = "FAIL"
        return PipelineResult(stages, sha256_bytes(text.encode("utf-8")), parsed, {"code": "STRUCTURED_SCHEMA_VALIDATION_ERROR", "message": sanitize_error_message(str(error))})
    stages["GATE_VALIDATION"] = "PASS"
    return PipelineResult(stages, sha256_bytes(text.encode("utf-8")), parsed, None)


def provider_status_record(response: Mapping[str, Any], pipeline: PipelineResult) -> dict[str, Any]:
    """Keep provider status distinct from local parser and Gate outcomes."""
    return {
        "http_status": 200,
        "provider_response_status": response.get("status"),
        "incomplete_details": response.get("incomplete_details"),
        "refusal_present": bool(response.get("refusal")),
        "pipeline_stages": pipeline.stages,
        "manual_comparison": "NOT_RUN",
    }
