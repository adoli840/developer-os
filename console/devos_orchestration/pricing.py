from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class PricingRecord:
    model: str
    pricing_as_of: str
    uncached_input_per_million: Decimal
    cached_input_per_million: Decimal
    output_per_million: Decimal
    cache_write_multiplier: Decimal


SOL_PROPOSAL_PRICING = PricingRecord(
    model="gpt-5.6-sol", pricing_as_of="2026-08-12",
    uncached_input_per_million=Decimal("5.00"), cached_input_per_million=Decimal("0.50"),
    output_per_million=Decimal("30.00"), cache_write_multiplier=Decimal("1.25"),
)


def pricing_record_payload(pricing: PricingRecord) -> dict[str, str]:
    return {
        "model": pricing.model,
        "pricing_as_of": pricing.pricing_as_of,
        "uncached_input_per_million": str(pricing.uncached_input_per_million),
        "cached_input_per_million": str(pricing.cached_input_per_million),
        "output_per_million": str(pricing.output_per_million),
        "cache_write_multiplier": str(pricing.cache_write_multiplier),
    }


def pricing_record_sha256(pricing: PricingRecord) -> str:
    encoded = json.dumps(pricing_record_payload(pricing), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def estimate_cost(pricing: PricingRecord, *, uncached_input: int, cached_input: int, cache_write: int, output: int) -> Decimal:
    effective_cache_write = pricing.uncached_input_per_million * pricing.cache_write_multiplier
    return (
        Decimal(uncached_input) * pricing.uncached_input_per_million
        + Decimal(cached_input) * pricing.cached_input_per_million
        + Decimal(cache_write) * effective_cache_write
        + Decimal(output) * pricing.output_per_million
    ) / Decimal(1_000_000)


def estimate_usage_cost(
    pricing: PricingRecord, usage: dict[str, Any], *, expected_pricing_sha256: str | None = None,
) -> tuple[dict[str, int], Decimal]:
    """Price mutually exclusive input partitions from a Responses usage object."""
    if expected_pricing_sha256 is not None and pricing_record_sha256(pricing) != expected_pricing_sha256:
        raise ValueError("pricing record mismatch")
    input_tokens = int(usage.get("input_tokens", 0) or 0)
    details = usage.get("input_tokens_details") or {}
    cached = int(details.get("cached_tokens", 0) or 0)
    cache_write = int(details.get("cache_write_tokens", 0) or 0)
    output = int(usage.get("output_tokens", 0) or 0)
    reasoning = int((usage.get("output_tokens_details") or {}).get("reasoning_tokens", 0) or 0)
    total = int(usage.get("total_tokens", input_tokens + output) or 0)
    values = (input_tokens, cached, cache_write, output, reasoning, total)
    if any(value < 0 for value in values):
        raise ValueError("usage token counts must be non-negative")
    if cached + cache_write > input_tokens:
        raise ValueError("cached and cache-write input tokens exceed input tokens")
    if input_tokens + output != total:
        raise ValueError("total tokens do not equal input plus output tokens")
    ordinary = input_tokens - cached - cache_write
    cost = estimate_cost(pricing, uncached_input=ordinary, cached_input=cached, cache_write=cache_write, output=output)
    return {
        "input_tokens": input_tokens, "ordinary_uncached_input_tokens": ordinary,
        "cached_input_tokens": cached, "cache_write_tokens": cache_write,
        "output_tokens": output, "reasoning_tokens": reasoning, "total_tokens": total,
    }, cost
