from __future__ import annotations

import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from console.devos_usage.collector import build_snapshot, fetch_monthly_cost, write_snapshot


class UsageCollectorTests(unittest.TestCase):
    def test_costs_are_summed_and_query_covers_current_month(self) -> None:
        requests = []

        def opener(request, timeout):
            requests.append((request, timeout))
            payload = {
                "data": [
                    {
                        "results": [
                            {"amount": {"value": 1.25, "currency": "usd"}},
                            {"amount": {"value": "2.50", "currency": "usd"}},
                        ]
                    }
                ],
                "has_more": False,
                "next_page": None,
            }
            return io.BytesIO(json.dumps(payload).encode("utf-8"))

        now = datetime(2026, 7, 31, 12, 30, tzinfo=timezone.utc)
        total = fetch_monthly_cost("test-admin-key", now=now, opener=opener)

        self.assertEqual(total, Decimal("3.75"))
        self.assertEqual(requests[0][1], 30)
        query = parse_qs(urlparse(requests[0][0].full_url).query)
        self.assertEqual(query["start_time"], ["1782864000"])
        self.assertEqual(query["bucket_width"], ["1d"])
        self.assertTrue(requests[0][0].headers["Authorization"].startswith("Bearer "))

    def test_pagination_is_followed(self) -> None:
        responses = [
            {"data": [], "has_more": True, "next_page": "page-2"},
            {
                "data": [{"results": [{"amount": {"value": 4, "currency": "usd"}}]}],
                "has_more": False,
                "next_page": None,
            },
        ]
        urls = []

        def opener(request, timeout):
            urls.append(request.full_url)
            return io.BytesIO(json.dumps(responses.pop(0)).encode("utf-8"))

        total = fetch_monthly_cost(
            "test-admin-key",
            now=datetime(2026, 7, 15, tzinfo=timezone.utc),
            opener=opener,
        )

        self.assertEqual(total, Decimal("4"))
        self.assertIn("page=page-2", urls[1])

    def test_snapshot_is_written_atomically_without_credentials(self) -> None:
        now = datetime(2026, 7, 31, 12, 30, tzinfo=timezone.utc)
        snapshot = build_snapshot(cost=Decimal("7.125"), budget=Decimal("50"), now=now)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "openai-usage.json"
            write_snapshot(path, snapshot)
            stored = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(stored["cost_usd"], 7.125)
        self.assertEqual(stored["budget_usd"], 50.0)
        self.assertEqual(stored["period_start"], "2026-07-01")
        self.assertEqual(stored["period_end"], "2026-07-31")
        self.assertNotIn("key", stored)


if __name__ == "__main__":
    unittest.main()
