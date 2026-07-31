from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen


COSTS_ENDPOINT = "https://api.openai.com/v1/organization/costs"


def _month_bounds(now: datetime) -> tuple[datetime, datetime]:
    current = now.astimezone(timezone.utc)
    start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def fetch_monthly_cost(
    admin_key: str,
    *,
    now: datetime,
    opener: Callable[..., Any] = urlopen,
) -> Decimal:
    start, month_end = _month_bounds(now)
    query: dict[str, str | int] = {
        "start_time": int(start.timestamp()),
        "end_time": int(min(now.astimezone(timezone.utc), month_end).timestamp()) + 1,
        "bucket_width": "1d",
        "limit": 31,
    }
    total = Decimal("0")

    for _ in range(20):
        request = Request(
            f"{COSTS_ENDPOINT}?{urlencode(query)}",
            headers={
                "Authorization": f"Bearer {admin_key}",
                "Content-Type": "application/json",
            },
        )
        with opener(request, timeout=30) as response:
            payload = json.load(response)
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise RuntimeError("OpenAI Costs API returned an unexpected response.")

        for bucket in payload["data"]:
            if not isinstance(bucket, dict):
                continue
            for result in bucket.get("results", []):
                if not isinstance(result, dict):
                    continue
                amount = result.get("amount")
                if not isinstance(amount, dict):
                    continue
                currency = str(amount.get("currency", "")).lower()
                if currency != "usd":
                    continue
                try:
                    total += Decimal(str(amount.get("value", "0")))
                except InvalidOperation as exc:
                    raise RuntimeError("OpenAI Costs API returned an invalid amount.") from exc

        next_page = payload.get("next_page")
        if not payload.get("has_more") or not next_page:
            return total
        query["page"] = str(next_page)

    raise RuntimeError("OpenAI Costs API pagination exceeded the safety limit.")


def build_snapshot(*, cost: Decimal, budget: Decimal, now: datetime) -> dict[str, Any]:
    start, month_end = _month_bounds(now)
    return {
        "cost_usd": float(round(cost, 6)),
        "budget_usd": float(round(budget, 2)),
        "period_start": start.date().isoformat(),
        "period_end": (month_end.date() - timedelta(days=1)).isoformat(),
        "updated_at": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def write_snapshot(path: Path, snapshot: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def main() -> int:
    admin_key = os.getenv("OPENAI_ADMIN_API_KEY", "").strip()
    if not admin_key:
        print("OPENAI_ADMIN_API_KEY is required.", file=sys.stderr)
        return 1

    try:
        budget = Decimal(os.environ["OPENAI_MONTHLY_BUDGET_USD"].strip())
    except (KeyError, InvalidOperation):
        print("OPENAI_MONTHLY_BUDGET_USD must be a valid number.", file=sys.stderr)
        return 1
    if budget < 0:
        print("OPENAI_MONTHLY_BUDGET_USD must not be negative.", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc)
    snapshot_path = Path(
        os.getenv(
            "DEVOS_OPENAI_USAGE_SNAPSHOT",
            "/var/lib/developer-os-console/openai-usage.json",
        )
    )
    try:
        cost = fetch_monthly_cost(admin_key, now=now)
        write_snapshot(snapshot_path, build_snapshot(cost=cost, budget=budget, now=now))
    except Exception as exc:
        print(f"OpenAI cost refresh failed: {exc}", file=sys.stderr)
        return 1

    print("OpenAI usage snapshot refreshed.")
    return 0
