from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def read_usage_snapshot(path: Path) -> dict[str, Any]:
    unavailable = {
        "status": "not_configured",
        "provider": "OpenAI",
        "cost_usd": None,
        "budget_usd": None,
        "remaining_usd": None,
        "updated_at": None,
        "message": "The OpenAI cost collector has not produced a usage snapshot yet.",
    }
    value = _read_json(path)
    if value is None:
        return unavailable
    if not value:
        return {**unavailable, "status": "invalid_snapshot", "message": "The local usage snapshot could not be read."}
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
        "message": "Values come from the server-side OpenAI cost collector; the public console never receives the Admin key.",
    }


def read_oracle_usage_snapshot(path: Path) -> dict[str, Any]:
    unavailable = {
        "status": "not_configured",
        "provider": "Oracle Cloud",
        "cost": None,
        "currency": "USD",
        "budget": None,
        "remaining": None,
        "free_resources": [],
        "service_costs": [],
        "updated_at": None,
        "message": "Oracle Cloud collection is waiting for instance-principal access.",
    }
    value = _read_json(path)
    if value is None:
        return unavailable
    if not value:
        return {
            **unavailable,
            "status": "invalid_snapshot",
            "message": "The Oracle Cloud usage snapshot could not be read.",
        }

    cost = value.get("cost")
    budget = value.get("budget")
    remaining = None
    if isinstance(cost, (int, float)) and isinstance(budget, (int, float)):
        remaining = round(float(budget) - float(cost), 4)
    free_resources = value.get("free_resources")
    service_costs = value.get("service_costs")
    return {
        "status": "snapshot",
        "provider": "Oracle Cloud",
        "cost": cost if isinstance(cost, (int, float)) else None,
        "currency": str(value.get("currency") or "USD").upper(),
        "budget": budget if isinstance(budget, (int, float)) else None,
        "remaining": remaining,
        "free_resources": free_resources if isinstance(free_resources, list) else [],
        "service_costs": service_costs if isinstance(service_costs, list) else [],
        "updated_at": value.get("updated_at"),
        "period_start": value.get("period_start"),
        "period_end": value.get("period_end"),
        "message": "Values come from the server-side OCI collector; the public console receives no OCI credential.",
    }


def read_usage_snapshots(openai_path: Path, oracle_path: Path) -> dict[str, Any]:
    return {
        "providers": [
            read_usage_snapshot(openai_path),
            read_oracle_usage_snapshot(oracle_path),
        ]
    }
