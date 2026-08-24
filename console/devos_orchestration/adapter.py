from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from .manifest import ApprovalManifestGuard
from .response_pipeline import capture_response, parse_response
from .schema import SchemaError


class LiveCallDisabled(RuntimeError):
    """Phase 1A never performs a live OpenAI request."""


@dataclass(frozen=True)
class MockResponse:
    response_id: str
    model: str
    status: str
    output: dict[str, Any]
    usage: dict[str, int]
    latency_ms: int


class MockReviewerAdapter:
    def __init__(self, response_factory: Callable[[dict[str, Any]], MockResponse]) -> None:
        self._response_factory = response_factory
        self.calls = 0

    def review(self, request: dict[str, Any]) -> MockResponse:
        self.calls += 1
        return self._response_factory(request)


def build_responses_request(
    *,
    model: str,
    prompt: str,
    schema_name: str,
    schema: dict[str, Any],
    max_output_tokens: int = 8192,
    reasoning_effort: str = "high",
    verbosity: str = "medium",
    project_id: str | None = None,
    reasoning_mode: str | None = None,
) -> dict[str, Any]:
    """Build the locked Phase 1A Responses request without performing I/O."""
    request: dict[str, Any] = {
        "model": model,
        "input": prompt,
        "store": False,
        "tools": [],
        "background": False,
        "max_output_tokens": max_output_tokens,
        "reasoning": {"effort": reasoning_effort},
        "text": {
            "verbosity": verbosity,
            "format": {"type": "json_schema", "name": schema_name, "strict": True, "schema": schema},
        },
    }
    if reasoning_mode is not None:
        if reasoning_mode != "pro":
            raise ValueError("only the explicitly approved pro reasoning mode may be sent")
        request["reasoning"]["mode"] = reasoning_mode
    if project_id:
        request["project"] = project_id
    return request


class OpenAIReviewerAdapter:
    endpoint = "https://api.openai.com/v1/responses"

    def __init__(
        self,
        *,
        model: str,
        schema_name: str,
        schema: dict[str, Any],
        api_key: str | None = None,
        project_id: str | None = None,
        transport: Callable[[str, dict[str, Any], str, float], Mapping[str, Any]] | None = None,
        allow_live: bool = False,
        timeout_seconds: float = 30.0,
        approval_manifest: dict[str, Any] | None = None,
        capture_directory: Path | None = None,
        expected_requirement_ids: set[str] | None = None,
    ) -> None:
        self.model = model
        self.schema_name = schema_name
        self.schema = schema
        self.api_key = api_key
        self.project_id = project_id
        self.transport = transport
        self.allow_live = allow_live
        self.timeout_seconds = timeout_seconds
        self.calls = 0
        self.manifest_guard = ApprovalManifestGuard(approval_manifest) if approval_manifest is not None else None
        self.capture_directory = capture_directory
        self.expected_requirement_ids = expected_requirement_ids

    def review(self, prompt: str, *, max_output_tokens: int = 8192, approval_manifest_hash: str | None = None) -> dict[str, Any]:
        if self.transport is None or not self.allow_live:
            raise LiveCallDisabled("Phase 1A live OpenAI calls are disabled.")
        if not self.api_key:
            raise PermissionError("OPENAI_ORCHESTRATION_API_KEY is required")
        if self.calls >= 1:
            raise RuntimeError("exactly one reviewer call is permitted")
        if self.manifest_guard is not None:
            if approval_manifest_hash is None:
                raise PermissionError("approval manifest is required")
            self.manifest_guard.validate(approval_manifest_hash)
        request = build_responses_request(
            model=self.model,
            prompt=prompt,
            schema_name=self.schema_name,
            schema=self.schema,
            max_output_tokens=max_output_tokens,
            project_id=self.project_id,
        )
        self.calls += 1
        if self.manifest_guard is not None:
            self.manifest_guard.consume(approval_manifest_hash or "")
        response = self.transport(self.endpoint, request, self.api_key, self.timeout_seconds)
        if self.capture_directory is not None:
            capture_response(response, self.capture_directory)
        pipeline = parse_response(
            response, expected_requirement_ids=self.expected_requirement_ids,
        )
        if pipeline.error is not None or pipeline.parsed_output is None:
            if pipeline.error and pipeline.error.get("code") == "STRUCTURED_SCHEMA_VALIDATION_ERROR":
                raise SchemaError(pipeline.error["message"])
            raise ValueError(pipeline.error or "response parsing failed")
        parsed = pipeline.parsed_output
        return {
            "response_id": response.get("id"),
            "request_id": response.get("request_id"),
            "model": response.get("model", self.model),
            "status": response.get("status"),
            "output": parsed,
            "usage": response.get("usage", {}),
        }
