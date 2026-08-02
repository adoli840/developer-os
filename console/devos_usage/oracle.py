from __future__ import annotations

import json
import os
import sys
from calendar import monthrange
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .snapshot import write_snapshot


INSTANCE_METADATA_URL = "http://169.254.169.254/opc/v2/instance/"
PUBLIC_PRICE_LIST_URL = "https://apexapps.oracle.com/pls/apex/cetools/api/v1/products/"
FREE_RESOURCE_SPECS = (
    ("a1_ocpu", "Ampere A1 OCPU", "B93297", "OCPU-hours", Decimal("3000")),
    ("a1_memory", "Ampere A1 memory", "B93298", "GB-hours", Decimal("18000")),
)


def _month_start(now: datetime) -> datetime:
    current = now.astimezone(timezone.utc)
    return current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _day_start(now: datetime) -> datetime:
    current = now.astimezone(timezone.utc)
    return current.replace(hour=0, minute=0, second=0, microsecond=0)


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def fetch_instance_metadata(opener: Callable[..., Any] = urlopen) -> dict[str, Any]:
    request = Request(
        INSTANCE_METADATA_URL,
        headers={"Authorization": "Bearer Oracle"},
    )
    with opener(request, timeout=5) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise RuntimeError("OCI instance metadata returned an unexpected response.")
    return payload


def fetch_free_resource_pricing(
    currency: str,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, dict[str, Decimal | None]]:
    pricing: dict[str, dict[str, Decimal | None]] = {}
    for _, _, sku, _, fallback_allowance in FREE_RESOURCE_SPECS:
        query = urlencode({"partNumber": sku, "currencyCode": currency.upper()})
        request = Request(
            f"{PUBLIC_PRICE_LIST_URL}?{query}",
            headers={"User-Agent": "DeveloperOS-Usage-Collector/1.0"},
        )
        with opener(request, timeout=10) as response:
            payload = json.load(response)
        items = payload.get("items") if isinstance(payload, dict) else None
        if isinstance(items, dict):
            items = [items]
        if not isinstance(items, list):
            raise RuntimeError("Oracle public price list returned an unexpected response.")
        item = next(
            (candidate for candidate in items if str(candidate.get("partNumber")) == sku),
            None,
        )
        localizations = item.get("currencyCodeLocalizations") if isinstance(item, dict) else None
        if not isinstance(localizations, list):
            raise RuntimeError(f"Oracle public price list did not return pricing for {sku}.")
        localization = next(
            (
                candidate
                for candidate in localizations
                if str(candidate.get("currencyCode", "")).upper() == currency.upper()
            ),
            None,
        )
        prices = localization.get("prices") if isinstance(localization, dict) else None
        if not isinstance(prices, list):
            raise RuntimeError(f"Oracle public price list did not return {currency} rates for {sku}.")
        free_ranges = [
            (_decimal(price.get("rangeMax")), _decimal(price.get("value")))
            for price in prices
            if isinstance(price, dict) and str(price.get("model")) == "PAY_AS_YOU_GO"
        ]
        free_allowance = max(
            (maximum for maximum, value in free_ranges if maximum is not None and value == 0),
            default=fallback_allowance,
        )
        overage_rate = next(
            (
                value
                for minimum, value in sorted(
                    (
                        (_decimal(price.get("rangeMin")), _decimal(price.get("value")))
                        for price in prices
                        if isinstance(price, dict) and str(price.get("model")) == "PAY_AS_YOU_GO"
                    ),
                    key=lambda entry: entry[0] if entry[0] is not None else Decimal("Infinity"),
                )
                if minimum is not None
                and minimum >= free_allowance
                and value is not None
                and value > 0
            ),
            None,
        )
        pricing[sku] = {
            "free_allowance": free_allowance,
            "overage_rate": overage_rate,
        }
    return pricing


def fetch_monthly_costs(
    client: Any,
    tenant_id: str,
    *,
    now: datetime,
    details_factory: Callable[..., Any],
) -> tuple[Decimal, str, list[dict[str, Any]]]:
    period_start = _month_start(now)
    period_end = _day_start(now)
    if period_end <= period_start:
        return Decimal("0"), "USD", []
    details = details_factory(
        tenant_id=tenant_id,
        time_usage_started=period_start,
        time_usage_ended=period_end,
        granularity="DAILY",
        query_type="COST",
        group_by=["service", "currency"],
        is_aggregate_by_time=True,
    )
    currency_totals: dict[str, Decimal] = {}
    service_totals: dict[tuple[str, str], Decimal] = {}
    page: str | None = None

    for _ in range(20):
        arguments: dict[str, Any] = {"request_summarized_usages_details": details}
        if page:
            arguments["page"] = page
        response = client.request_summarized_usages(**arguments)
        data = getattr(response, "data", None)
        items = getattr(data, "items", data if isinstance(data, list) else None)
        if not isinstance(items, list):
            raise RuntimeError("OCI Usage API returned an unexpected response.")

        for item in items:
            amount = _decimal(getattr(item, "computed_amount", None))
            if amount is None:
                continue
            currency = str(getattr(item, "currency", None) or "USD").upper()
            service = str(getattr(item, "service", None) or "Other")
            currency_totals[currency] = currency_totals.get(currency, Decimal("0")) + amount
            key = (service, currency)
            service_totals[key] = service_totals.get(key, Decimal("0")) + amount

        headers = getattr(response, "headers", {}) or {}
        page = headers.get("opc-next-page") or headers.get("opc-next-page".title())
        if not page:
            break
    else:
        raise RuntimeError("OCI Usage API pagination exceeded the safety limit.")

    if len(currency_totals) > 1:
        raise RuntimeError("OCI Usage API returned more than one billing currency.")
    currency = next(iter(currency_totals), "USD")
    total = currency_totals.get(currency, Decimal("0"))
    services = [
        {"name": service, "cost": float(round(amount, 6)), "currency": item_currency}
        for (service, item_currency), amount in sorted(
            service_totals.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    ]
    return total, currency, services


def fetch_free_resource_usage(
    client: Any,
    tenant_id: str,
    *,
    now: datetime,
    details_factory: Callable[..., Any],
    pricing: dict[str, dict[str, Decimal | None]] | None = None,
) -> list[dict[str, Any]]:
    period_start = _month_start(now)
    period_end = _day_start(now)
    completed_days = (period_end - period_start).days
    days_in_month = monthrange(period_start.year, period_start.month)[1]
    usage_by_sku: dict[str, Decimal] = {}

    if completed_days > 0:
        details = details_factory(
            tenant_id=tenant_id,
            time_usage_started=period_start,
            time_usage_ended=period_end,
            granularity="DAILY",
            query_type="USAGE",
            group_by=["service", "skuName", "skuPartNumber", "unit"],
            is_aggregate_by_time=True,
        )
        page: str | None = None
        for _ in range(20):
            arguments: dict[str, Any] = {"request_summarized_usages_details": details}
            if page:
                arguments["page"] = page
            response = client.request_summarized_usages(**arguments)
            data = getattr(response, "data", None)
            items = getattr(data, "items", data if isinstance(data, list) else None)
            if not isinstance(items, list):
                raise RuntimeError("OCI Usage API returned an unexpected response.")
            for item in items:
                sku = str(getattr(item, "sku_part_number", None) or "")
                quantity = _decimal(getattr(item, "computed_quantity", None))
                if sku and quantity is not None:
                    usage_by_sku[sku] = usage_by_sku.get(sku, Decimal("0")) + quantity
            headers = getattr(response, "headers", {}) or {}
            page = headers.get("opc-next-page") or headers.get("opc-next-page".title())
            if not page:
                break
        else:
            raise RuntimeError("OCI Usage API pagination exceeded the safety limit.")

    resources: list[dict[str, Any]] = []
    for key, label, sku, unit, fallback_allowance in FREE_RESOURCE_SPECS:
        sku_pricing = (pricing or {}).get(sku, {})
        free_allowance = sku_pricing.get("free_allowance", fallback_allowance)
        overage_rate = sku_pricing.get("overage_rate")
        used = usage_by_sku.get(sku, Decimal("0"))
        free_remaining = max(free_allowance - used, Decimal("0"))
        projected_usage = None
        projected_overage = None
        if completed_days > 0:
            projected_usage = used * Decimal(days_in_month) / Decimal(completed_days)
            projected_overage = max(projected_usage - free_allowance, Decimal("0"))
        resources.append(
            {
                "key": key,
                "label": label,
                "unit": unit,
                "used": float(round(used, 6)),
                "free_allowance": float(free_allowance),
                "free_remaining": float(round(free_remaining, 6)),
                "projected_month_usage": (
                    float(round(projected_usage, 6)) if projected_usage is not None else None
                ),
                "projected_overage": (
                    float(round(projected_overage, 6)) if projected_overage is not None else None
                ),
                "overage_rate": float(overage_rate) if overage_rate is not None else None,
            }
        )
    return resources


def build_oracle_snapshot(
    *,
    cost: Decimal,
    currency: str,
    budget: Decimal | None,
    resources: list[dict[str, Any]],
    service_costs: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    current = now.astimezone(timezone.utc)
    period_start = _month_start(current)
    completed_days = (_day_start(current) - period_start).days
    days_in_month = monthrange(period_start.year, period_start.month)[1]
    projected_cost = None
    if completed_days > 0:
        projected_cost = cost * Decimal(days_in_month) / Decimal(completed_days)
        projected_a1_cost = Decimal("0")
        for resource in resources:
            overage = _decimal(resource.get("projected_overage")) or Decimal("0")
            rate = _decimal(resource.get("overage_rate"))
            if overage > 0 and rate is None:
                projected_a1_cost = None
                break
            if rate is not None:
                projected_a1_cost += overage * rate
        if projected_a1_cost is not None:
            projected_cost = max(projected_cost, projected_a1_cost)
    return {
        "cost": float(round(cost, 6)),
        "currency": currency,
        "budget": float(round(budget, 2)) if budget is not None else None,
        "projected_cost": float(round(projected_cost, 6)) if projected_cost is not None else None,
        "completed_days": completed_days,
        "days_in_month": days_in_month,
        "projection_method": "linear_completed_utc_days",
        "period_start": period_start.date().isoformat(),
        "period_end": current.date().isoformat(),
        "resources": resources,
        "service_costs": service_costs,
        "updated_at": current.isoformat().replace("+00:00", "Z"),
    }


def _optional_non_negative_decimal(name: str) -> Decimal | None:
    value = os.getenv(name, "").strip()
    if not value:
        return None
    parsed = _decimal(value)
    if parsed is None or parsed < 0:
        raise RuntimeError(f"{name} must be a non-negative number.")
    return parsed


def collect_from_environment() -> bool:
    if os.getenv("DEVOS_OCI_ENABLED", "").strip().lower() not in {"1", "true", "yes", "on"}:
        print("Oracle Cloud usage collection is not enabled; skipped.")
        return False

    try:
        import oci
    except ImportError as exc:
        raise RuntimeError("The OCI Python SDK is required when DEVOS_OCI_ENABLED=1.") from exc

    metadata = fetch_instance_metadata()
    signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
    tenant_id = os.getenv("OCI_TENANCY_OCID", "").strip() or str(
        getattr(signer, "tenancy_id", "") or metadata.get("tenantId", "")
    )
    region = os.getenv("OCI_REGION", "").strip() or str(
        getattr(signer, "region", "") or metadata.get("region", "")
    )
    if not tenant_id or not region:
        raise RuntimeError("OCI tenancy and region could not be resolved.")

    config = {"region": region}
    usage_client = oci.usage_api.UsageapiClient(config, signer=signer)
    now = datetime.now(timezone.utc)
    cost, currency, service_costs = fetch_monthly_costs(
        usage_client,
        tenant_id,
        now=now,
        details_factory=oci.usage_api.models.RequestSummarizedUsagesDetails,
    )
    try:
        pricing = fetch_free_resource_pricing(currency)
    except Exception as exc:
        print(f"Oracle public price lookup failed; using documented allowances: {exc}", file=sys.stderr)
        pricing = {}
    resources = fetch_free_resource_usage(
        usage_client,
        tenant_id,
        now=now,
        details_factory=oci.usage_api.models.RequestSummarizedUsagesDetails,
        pricing=pricing,
    )
    budget = _optional_non_negative_decimal("OCI_MONTHLY_BUDGET")
    snapshot_path = Path(
        os.getenv(
            "DEVOS_ORACLE_USAGE_SNAPSHOT",
            "/var/lib/developer-os-console/oracle-usage.json",
        )
    )
    write_snapshot(
        snapshot_path,
        build_oracle_snapshot(
            cost=cost,
            currency=currency,
            budget=budget,
            resources=resources,
            service_costs=service_costs,
            now=now,
        ),
    )
    print("Oracle Cloud usage snapshot refreshed.")
    return True


def main() -> int:
    try:
        collect_from_environment()
    except Exception as exc:
        print(f"Oracle Cloud usage refresh failed: {exc}", file=sys.stderr)
        return 1
    return 0
