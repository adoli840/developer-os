from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .pricing import PricingRecord, estimate_cost


@dataclass(frozen=True)
class PreflightResult:
    serialized_input_bytes: int
    conservative_input_tokens: int
    max_output_tokens: int
    maximum_estimated_cost_usd: Decimal
    safety_margin_usd: Decimal
    worst_case_cost_usd: Decimal
    status: str

    def as_dict(self) -> dict[str, Any]:
        return {"serialized_input_bytes": self.serialized_input_bytes, "conservative_input_tokens": self.conservative_input_tokens, "max_output_tokens": self.max_output_tokens, "maximum_estimated_cost_usd": str(self.maximum_estimated_cost_usd), "safety_margin_usd": str(self.safety_margin_usd), "worst_case_cost_usd": str(self.worst_case_cost_usd), "status": self.status}


def run_preflight(payload: str, *, max_output_tokens: int, pricing: PricingRecord, hard_cap_usd: Decimal, safety_margin_usd: Decimal = Decimal("0")) -> PreflightResult:
    size = len(payload.encode("utf-8"))
    input_tokens = (size + 3) // 4
    input_cost = estimate_cost(pricing, uncached_input=input_tokens, cached_input=0, cache_write=0, output=0)
    output_cost = estimate_cost(pricing, uncached_input=0, cached_input=0, cache_write=0, output=max_output_tokens)
    worst = input_cost + output_cost + safety_margin_usd
    return PreflightResult(size, input_tokens, max_output_tokens, input_cost + output_cost, safety_margin_usd, worst, "BUDGET_BLOCKED" if worst > hard_cap_usd else "READY")
