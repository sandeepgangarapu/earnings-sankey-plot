from __future__ import annotations

import unittest

from earnings_sankey.normalize import available_periods, normalize_companyfacts, select_fact
from earnings_sankey.sec import CompanyIdentity


def entry(
    value: float,
    *,
    fy: int,
    fp: str,
    start: str,
    end: str,
    filed: str,
) -> dict:
    return {
        "val": value,
        "fy": fy,
        "fp": fp,
        "form": "10-Q" if fp != "FY" else "10-K",
        "start": start,
        "end": end,
        "filed": filed,
        "accn": f"0000000000-{str(fy)[-2:]}-000001",
    }


def fact(label: str, entries: list[dict]) -> dict:
    return {"label": label, "units": {"USD": entries}}


class NormalizeTests(unittest.TestCase):
    def setUp(self) -> None:
        current = dict(fy=2025, fp="Q2", start="2025-04-01", end="2025-06-30", filed="2025-07-25")
        previous = dict(fy=2024, fp="Q2", start="2024-04-01", end="2024-06-30", filed="2024-07-25")
        self.companyfacts = {
            "entityName": "Example Corporation",
            "facts": {
                "us-gaap": {
                    "RevenueFromContractWithCustomerExcludingAssessedTax": fact(
                        "Revenue",
                        [
                            entry(120, **current),
                            entry(230, fy=2025, fp="Q2", start="2025-01-01", end="2025-06-30", filed="2025-07-25"),
                            entry(100, **previous),
                        ],
                    ),
                    "GrossProfit": fact("Gross profit", [entry(70, **current), entry(60, **previous)]),
                    "OperatingIncomeLoss": fact("Operating income", [entry(40, **current), entry(30, **previous)]),
                    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest": fact(
                        "Pretax income", [entry(42, **current), entry(32, **previous)]
                    ),
                    "IncomeTaxExpenseBenefit": fact("Tax", [entry(8, **current), entry(6, **previous)]),
                    "NetIncomeLoss": fact("Net income", [entry(34, **current), entry(26, **previous)]),
                    "ResearchAndDevelopmentExpense": fact("R&D", [entry(10, **current), entry(8, **previous)]),
                    "SellingAndMarketingExpense": fact("Sales", [entry(12, **current), entry(10, **previous)]),
                    "GeneralAndAdministrativeExpense": fact("G&A", [entry(8, **current), entry(12, **previous)]),
                }
            },
        }
        self.identity = CompanyIdentity("EXM", 123456, "Example Corporation")

    def test_selects_single_quarter_instead_of_year_to_date(self) -> None:
        selected = select_fact(
            self.companyfacts,
            ("RevenueFromContractWithCustomerExcludingAssessedTax",),
            2025,
            "Q2",
        )
        self.assertIsNotNone(selected)
        self.assertEqual(selected.value, 120)

    def test_normalizes_and_balances_statement(self) -> None:
        statement = normalize_companyfacts(self.companyfacts, self.identity, 2025, "Q2")
        self.assertEqual(statement.revenue, 120)
        self.assertEqual(statement.cost_of_revenue, 50)
        self.assertEqual(statement.gross_profit, 70)
        self.assertEqual(statement.operating_expenses_total, 30)
        self.assertEqual(statement.operating_income, 40)
        self.assertEqual(statement.other_income, 2)
        self.assertEqual(statement.pretax_income, 42)
        self.assertEqual(statement.income_tax, 8)
        self.assertEqual(statement.net_income, 34)
        self.assertAlmostEqual(statement.yoy["revenue"], 20)
        self.assertEqual([item.name for item in statement.operating_expenses], ["R&D", "Sales & marketing", "General & administrative"])

    def test_lists_only_usable_period_durations(self) -> None:
        periods = available_periods(self.companyfacts)
        self.assertEqual(periods[0]["fiscal_year"], 2025)
        self.assertEqual(periods[0]["period"], "Q2")
        self.assertEqual(len(periods), 2)


if __name__ == "__main__":
    unittest.main()

