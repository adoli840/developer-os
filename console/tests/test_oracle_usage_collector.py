from __future__ import annotations

import io
import json
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from console.devos_usage.oracle import (
    build_oracle_snapshot,
    fetch_account_resources,
    fetch_instance_metadata,
    fetch_monthly_costs,
)


class OracleUsageCollectorTests(unittest.TestCase):
    def test_instance_metadata_uses_required_authorization_header(self) -> None:
        requests = []

        def opener(request, timeout):
            requests.append((request, timeout))
            return io.BytesIO(
                json.dumps(
                    {
                        "tenantId": "ocid1.tenancy.example",
                        "region": "ap-seoul-1",
                        "availabilityDomain": "example:AP-SEOUL-1-AD-1",
                    }
                ).encode("utf-8")
            )

        result = fetch_instance_metadata(opener)

        self.assertEqual(result["region"], "ap-seoul-1")
        self.assertEqual(requests[0][1], 5)
        self.assertEqual(requests[0][0].headers["Authorization"], "Bearer Oracle")

    def test_costs_are_grouped_by_service_and_paginated(self) -> None:
        responses = [
            SimpleNamespace(
                data=SimpleNamespace(
                    items=[SimpleNamespace(computed_amount="1.25", currency="USD", service="Compute")]
                ),
                headers={"opc-next-page": "page-2"},
            ),
            SimpleNamespace(
                data=SimpleNamespace(
                    items=[SimpleNamespace(computed_amount=2.5, currency="USD", service="Block Storage")]
                ),
                headers={},
            ),
        ]
        calls = []

        class Client:
            def request_summarized_usages(self, **kwargs):
                calls.append(kwargs)
                return responses.pop(0)

        now = datetime(2026, 8, 2, 12, tzinfo=timezone.utc)
        total, currency, services = fetch_monthly_costs(
            Client(),
            "ocid1.tenancy.example",
            now=now,
            details_factory=lambda **kwargs: kwargs,
        )

        self.assertEqual(total, Decimal("3.75"))
        self.assertEqual(currency, "USD")
        self.assertEqual(services[0]["name"], "Block Storage")
        self.assertEqual(calls[1]["page"], "page-2")
        details = calls[0]["request_summarized_usages_details"]
        self.assertEqual(details["query_type"], "COST")
        self.assertEqual(details["group_by"], ["service", "currency"])
        self.assertEqual(details["granularity"], "DAILY")
        self.assertEqual(
            details["time_usage_started"],
            datetime(2026, 8, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(
            details["time_usage_ended"],
            datetime(2026, 8, 2, tzinfo=timezone.utc),
        )

    def test_first_day_of_month_skips_an_empty_cost_period(self) -> None:
        class Client:
            def request_summarized_usages(self, **kwargs):
                raise AssertionError("Usage API should not be called for an empty period.")

        result = fetch_monthly_costs(
            Client(),
            "ocid1.tenancy.example",
            now=datetime(2026, 8, 1, 12, tzinfo=timezone.utc),
            details_factory=lambda **kwargs: kwargs,
        )

        self.assertEqual(result, (Decimal("0"), "USD", []))

    def test_account_resources_use_provider_reported_capacity(self) -> None:
        values = [
            SimpleNamespace(fractional_usage=4.0, used=4, fractional_availability=12.0, available=12),
            SimpleNamespace(fractional_usage=24.0, used=24, fractional_availability=72.0, available=72),
        ]

        class Client:
            def get_resource_availability(self, **kwargs):
                self.last_arguments = kwargs
                return SimpleNamespace(data=values.pop(0))

        result = fetch_account_resources(
            Client(),
            "ocid1.tenancy.example",
            "example:AP-SEOUL-1-AD-1",
        )

        self.assertEqual(result[0]["used"], 4.0)
        self.assertEqual(result[0]["account_limit"], 16.0)
        self.assertEqual(result[0]["available"], 12.0)
        self.assertEqual(result[1]["account_limit"], 96.0)
        self.assertEqual(result[1]["available"], 72.0)

    def test_snapshot_contains_only_derived_values(self) -> None:
        snapshot = build_oracle_snapshot(
            cost=Decimal("1.5"),
            currency="USD",
            budget=Decimal("10"),
            resources=[],
            service_costs=[],
            now=datetime(2026, 8, 2, 12, tzinfo=timezone.utc),
        )

        self.assertEqual(snapshot["cost"], 1.5)
        self.assertEqual(snapshot["budget"], 10.0)
        self.assertEqual(snapshot["period_start"], "2026-08-01")
        self.assertNotIn("tenancy", snapshot)
        self.assertNotIn("key", snapshot)


if __name__ == "__main__":
    unittest.main()
