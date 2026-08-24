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
        "monthly_limit_usd": None,
        "credit_balance_usd": None,
        "credit_balance_status": "unsupported",
        "credit_balance_message": "CREDIT BALANCE: unavailable from supported API",
        "updated_at": None,
        "message": "The OpenAI cost collector has not produced a usage snapshot yet.",
    }
    value = _read_json(path)
    if value is None:
        return unavailable
    if not value:
        return {**unavailable, "status": "invalid_snapshot", "message": "The local usage snapshot could not be read."}
    cost = value.get("cost_usd")
    monthly_limit = value.get("monthly_limit_usd", value.get("budget_usd"))
    credit_balance = value.get("credit_balance_usd")
    credit_status = value.get("credit_balance_status") or "unsupported"
    credit_message = value.get("credit_balance_message") or "CREDIT BALANCE: unavailable from supported API"
    return {
        "status": "snapshot",
        "provider": "OpenAI",
        "cost_usd": cost if isinstance(cost, (int, float)) else None,
        "monthly_limit_usd": monthly_limit if isinstance(monthly_limit, (int, float)) else None,
        "credit_balance_usd": credit_balance if isinstance(credit_balance, (int, float)) else None,
        "credit_balance_status": credit_status,
        "credit_balance_message": credit_message,
        "updated_at": value.get("updated_at"),
        "period_start": value.get("period_start"),
        "period_end": value.get("period_end"),
        "message": "Cost and monthly limit come from the server-side collector; credit balance is not available from a supported API. The public console never receives the Admin key.",
    }


def read_oracle_usage_snapshot(path: Path) -> dict[str, Any]:
    unavailable = {
        "status": "not_configured",
        "provider": "Oracle Cloud",
        "cost": None,
        "currency": "USD",
        "budget": None,
        "remaining": None,
        "projected_cost": None,
        "completed_days": None,
        "days_in_month": None,
        "resources": [],
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
    resources = value.get("resources")
    if not isinstance(resources, list):
        resources = []
    service_costs = value.get("service_costs")
    projected_cost = value.get("projected_cost")
    completed_days = value.get("completed_days")
    days_in_month = value.get("days_in_month")
    return {
        "status": "snapshot",
        "provider": "Oracle Cloud",
        "cost": cost if isinstance(cost, (int, float)) else None,
        "currency": str(value.get("currency") or "USD").upper(),
        "budget": budget if isinstance(budget, (int, float)) else None,
        "remaining": remaining,
        "projected_cost": projected_cost if isinstance(projected_cost, (int, float)) else None,
        "completed_days": completed_days if isinstance(completed_days, int) else None,
        "days_in_month": days_in_month if isinstance(days_in_month, int) else None,
        "resources": resources,
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
