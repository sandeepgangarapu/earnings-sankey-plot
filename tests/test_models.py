from __future__ import annotations

import unittest

from earnings_sankey.models import LineItem, Statement


class ModelTests(unittest.TestCase):
    def test_round_trip_and_override(self) -> None:
        statement = Statement(
            ticker="ABC",
            company="ABC Inc.",
            fiscal_year=2025,
            period="FY",
            revenue=100,
            cost_of_revenue=40,
            gross_profit=60,
            operating_expenses_total=20,
            operating_income=40,
            other_income=2,
            pretax_income=42,
            income_tax=8,
            net_income=34,
            revenue_streams=[LineItem("Products", 100)],
        )
        restored = Statement.from_dict(statement.to_dict())
        self.assertEqual(restored, statement)
        overridden = restored.with_override(
            {"revenue_streams": [{"name": "Services", "value": 100}]}
        )
        self.assertEqual(overridden.revenue_streams[0].name, "Services")
        self.assertEqual(statement.revenue_streams[0].name, "Products")


if __name__ == "__main__":
    unittest.main()

