from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_usage_snapshot(path: Path) -> dict[str, Any]:
    unavailable = {
        "status": "not_configured",
        "provider": "OpenAI",
        "cost_usd": None,
        "budget_usd": None,
        "remaining_usd": None,
        "updated_at": None,
        "message": "No local usage snapshot is configured. No API key is requested by this console.",
    }
    if not path.is_file():
        return unavailable
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {**unavailable, "status": "invalid_snapshot", "message": "The local usage snapshot could not be read."}
    if not isinstance(value, dict):
        return {**unavailable, "status": "invalid_snapshot", "message": "The local usage snapshot must be a JSON object."}
    cost = value.get("cost_usd")
    budget = value.get("budget_usd")
    remaining = None
    if isinstance(cost, (int, float)) and isinstance(budget, (int, float)):
        remaining = round(float(budget) - float(cost), 4)
    return {
        "status": "snapshot",
        "provider": "OpenAI",
        "cost_usd": cost if isinstance(cost, (int, float)) else None,
        "budget_usd": budget if isinstance(budget, (int, float)) else None,
        "remaining_usd": remaining,
        "updated_at": value.get("updated_at"),
        "period_start": value.get("period_start"),
        "period_end": value.get("period_end"),
        "message": "Values are read from a local snapshot; this console does not call the OpenAI API.",
    }
