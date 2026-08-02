from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

from .snapshot import write_snapshot


INSTANCE_METADATA_URL = "http://169.254.169.254/opc/v2/instance/"
ACCOUNT_RESOURCE_SPECS = (
    ("a1_ocpu", "Ampere A1 OCPU", "compute", "standard-a1-core-count", "OCPU"),
    ("a1_memory", "Ampere A1 memory", "compute", "standard-a1-memory-count", "GB"),
)


def _month_start(now: datetime) -> datetime:
    current = now.astimezone(timezone.utc)
    return current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def _number(value: Any) -> float | None:
    parsed = _decimal(value)
    return float(parsed) if parsed is not None else None


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


def fetch_monthly_costs(
    client: Any,
    tenant_id: str,
    *,
    now: datetime,
    details_factory: Callable[..., Any],
) -> tuple[Decimal, str, list[dict[str, Any]]]:
    details = details_factory(
        tenant_id=tenant_id,
        time_usage_started=_month_start(now),
        time_usage_ended=now.astimezone(timezone.utc),
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


def fetch_account_resources(
    client: Any,
    tenant_id: str,
    availability_domain: str,
) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    for key, label, service_name, limit_name, unit in ACCOUNT_RESOURCE_SPECS:
        response = client.get_resource_availability(
            service_name=service_name,
            limit_name=limit_name,
            compartment_id=tenant_id,
            availability_domain=availability_domain,
        )
        data = response.data
        used = _number(getattr(data, "fractional_usage", None))
        if used is None:
            used = _number(getattr(data, "used", None))
        available = _number(getattr(data, "fractional_availability", None))
        if available is None:
            available = _number(getattr(data, "available", None))
        account_limit = used + available if used is not None and available is not None else None
        resources.append(
            {
                "key": key,
                "label": label,
                "unit": unit,
                "used": used,
                "account_limit": account_limit,
                "available": available,
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
    return {
        "cost": float(round(cost, 6)),
        "currency": currency,
        "budget": float(round(budget, 2)) if budget is not None else None,
        "period_start": _month_start(current).date().isoformat(),
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
    availability_domain = os.getenv("OCI_AVAILABILITY_DOMAIN", "").strip() or str(
        metadata.get("availabilityDomain", "")
    )
    if not tenant_id or not region or not availability_domain:
        raise RuntimeError("OCI tenancy, region, and availability domain could not be resolved.")

    config = {"region": region}
    usage_client = oci.usage_api.UsageapiClient(config, signer=signer)
    limits_client = oci.limits.LimitsClient(config, signer=signer)
    now = datetime.now(timezone.utc)
    cost, currency, service_costs = fetch_monthly_costs(
        usage_client,
        tenant_id,
        now=now,
        details_factory=oci.usage_api.models.RequestSummarizedUsagesDetails,
    )
    resources = fetch_account_resources(
        limits_client,
        tenant_id,
        availability_domain,
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
