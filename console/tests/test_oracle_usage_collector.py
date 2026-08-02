from __future__ import annotations

import io
import json
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from console.devos_usage.oracle import (
    build_oracle_snapshot,
    fetch_free_resource_usage,
    fetch_free_resource_pricing,
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

    def test_public_price_list_supplies_free_ranges_and_overage_rates(self) -> None:
        payloads = {
            "B93297": {
                "items": [
                    {
                        "partNumber": "B93297",
                        "currencyCodeLocalizations": [
                            {
                                "currencyCode": "SGD",
                                "prices": [
                                    {"model": "PAY_AS_YOU_GO", "value": 0, "rangeMin": 0, "rangeMax": 3000},
                                    {"model": "PAY_AS_YOU_GO", "value": 0.013819, "rangeMin": 3000},
                                ],
                            }
                        ],
                    }
                ]
            },
            "B93298": {
                "items": [
                    {
                        "partNumber": "B93298",
                        "currencyCodeLocalizations": [
                            {
                                "currencyCode": "SGD",
                                "prices": [
                                    {"model": "PAY_AS_YOU_GO", "value": 0, "rangeMin": 0, "rangeMax": 18000},
                                    {"model": "PAY_AS_YOU_GO", "value": 0.00207285, "rangeMin": 18000},
                                ],
                            }
                        ],
                    }
                ]
            },
        }

        def opener(request, timeout):
            sku = next(sku for sku in payloads if sku in request.full_url)
            self.assertEqual(timeout, 10)
            return io.BytesIO(json.dumps(payloads[sku]).encode("utf-8"))

        result = fetch_free_resource_pricing("SGD", opener)

        self.assertEqual(result["B93297"]["free_allowance"], Decimal("3000"))
        self.assertEqual(result["B93297"]["overage_rate"], Decimal("0.013819"))
        self.assertEqual(result["B93298"]["free_allowance"], Decimal("18000"))

    def test_free_resources_use_actual_usage_and_project_to_month_end(self) -> None:
        responses = [
            SimpleNamespace(
                data=SimpleNamespace(
                    items=[
                        SimpleNamespace(sku_part_number="B93297", computed_quantity="96"),
                        SimpleNamespace(sku_part_number="B93298", computed_quantity="576"),
                        SimpleNamespace(sku_part_number="B91444", computed_quantity="24"),
                    ]
                ),
                headers={},
            )
        ]
        calls = []

        class Client:
            def request_summarized_usages(self, **kwargs):
                calls.append(kwargs)
                return responses.pop(0)

        result = fetch_free_resource_usage(
            Client(),
            "ocid1.tenancy.example",
            now=datetime(2026, 8, 2, 12, tzinfo=timezone.utc),
            details_factory=lambda **kwargs: kwargs,
        )

        self.assertEqual(result[0]["used"], 96.0)
        self.assertEqual(result[0]["free_allowance"], 3000.0)
        self.assertEqual(result[0]["free_remaining"], 2904.0)
        self.assertEqual(result[0]["projected_month_usage"], 2976.0)
        self.assertEqual(result[0]["projected_overage"], 0.0)
        self.assertEqual(result[1]["used"], 576.0)
        self.assertEqual(result[1]["free_remaining"], 17424.0)
        self.assertEqual(result[1]["projected_month_usage"], 17856.0)
        details = calls[0]["request_summarized_usages_details"]
        self.assertEqual(details["query_type"], "USAGE")
        self.assertEqual(details["group_by"], ["service", "skuName", "skuPartNumber", "unit"])

    def test_first_day_has_zero_free_usage_without_a_projection(self) -> None:
        class Client:
            def request_summarized_usages(self, **kwargs):
                raise AssertionError("Usage API should not be called for an empty period.")

        result = fetch_free_resource_usage(
            Client(),
            "ocid1.tenancy.example",
            now=datetime(2026, 8, 1, 12, tzinfo=timezone.utc),
            details_factory=lambda **kwargs: kwargs,
        )

        self.assertEqual(result[0]["used"], 0.0)
        self.assertEqual(result[0]["free_remaining"], 3000.0)
        self.assertIsNone(result[0]["projected_month_usage"])

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
        self.assertEqual(snapshot["projected_cost"], 46.5)
        self.assertEqual(snapshot["completed_days"], 1)
        self.assertEqual(snapshot["days_in_month"], 31)
        self.assertEqual(snapshot["period_start"], "2026-08-01")
        self.assertNotIn("tenancy", snapshot)
        self.assertNotIn("key", snapshot)

    def test_snapshot_forecast_includes_projected_free_tier_overage(self) -> None:
        snapshot = build_oracle_snapshot(
            cost=Decimal("0"),
            currency="SGD",
            budget=None,
            resources=[
                {
                    "projected_overage": 100,
                    "overage_rate": 0.013819,
                }
            ],
            service_costs=[],
            now=datetime(2026, 8, 2, 12, tzinfo=timezone.utc),
        )

        self.assertEqual(snapshot["projected_cost"], 1.3819)


if __name__ == "__main__":
    unittest.main()
