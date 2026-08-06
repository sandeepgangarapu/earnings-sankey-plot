from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

from .models import LineItem, Statement
from .sec import CompanyIdentity, filing_url


class NormalizationError(ValueError):
    """Raised when an income statement cannot be normalized safely."""


CONCEPTS: dict[str, tuple[str, ...]] = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "SalesRevenueGoodsAndServicesNet",
        "OperatingRevenues",
    ),
    "gross_profit": ("GrossProfit",),
    "cost_of_revenue": (
        "CostOfRevenue",
        "CostOfGoodsAndServicesSold",
        "CostOfGoodsSold",
        "CostOfGoodsSoldDirectLabor",
    ),
    "operating_expenses": (
        "OperatingExpenses",
        "CostsAndExpenses",
        "CostAndExpenseExcludingInterest",
    ),
    "operating_income": ("OperatingIncomeLoss",),
    "pretax_income": (
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxes",
    ),
    "income_tax": ("IncomeTaxExpenseBenefit",),
    "net_income": (
        "NetIncomeLoss",
        "ProfitLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
    ),
}

EXPENSE_CONCEPTS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "research_development",
        "R&D",
        ("ResearchAndDevelopmentExpense", "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost"),
    ),
    (
        "selling_marketing",
        "Sales & marketing",
        ("SellingAndMarketingExpense", "MarketingExpense", "SellingExpense"),
    ),
    (
        "general_admin",
        "General & administrative",
        ("GeneralAndAdministrativeExpense",),
    ),
)

SGA_CONCEPTS = ("SellingGeneralAndAdministrativeExpense",)
SUPPORTED_PERIODS = ("Q1", "Q2", "Q3", "FY")


@dataclass(frozen=True, slots=True)
class SelectedFact:
    value: float
    concept: str
    label: str
    entry: dict[str, Any]


def _duration_days(entry: dict[str, Any]) -> int | None:
    try:
        return (date.fromisoformat(entry["end"]) - date.fromisoformat(entry["start"])).days
    except (KeyError, TypeError, ValueError):
        return None


def _filing_ordinal(entry: dict[str, Any]) -> int:
    try:
        return date.fromisoformat(str(entry.get("filed", ""))).toordinal()
    except ValueError:
        return 0


def _form_matches(form: str, period: str) -> bool:
    form = form.upper().removesuffix("/A")
    if period == "FY":
        return form in {"10-K", "20-F", "40-F"}
    return form in {"10-Q", "6-K"}


def _fact_candidates(
    companyfacts: dict[str, Any], concepts: Iterable[str]
) -> Iterable[tuple[int, str, dict[str, Any], dict[str, Any]]]:
    facts = companyfacts.get("facts", {})
    concept_order = {concept: index for index, concept in enumerate(concepts)}
    for taxonomy in ("us-gaap", "ifrs-full"):
        taxonomy_facts = facts.get(taxonomy, {})
        for concept, priority in concept_order.items():
            definition = taxonomy_facts.get(concept)
            if not definition:
                continue
            units = definition.get("units", {})
            entries = units.get("USD") or units.get("USD/shares") or []
            for entry in entries:
                yield priority, concept, definition, entry


def select_fact(
    companyfacts: dict[str, Any],
    concepts: Iterable[str],
    fiscal_year: int,
    period: str,
) -> SelectedFact | None:
    period = period.upper()
    if period not in SUPPORTED_PERIODS:
        raise ValueError(f"Period must be one of {', '.join(SUPPORTED_PERIODS)}.")
    target_duration = 365 if period == "FY" else 91
    maximum_delta = 100 if period == "FY" else 55
    matches: list[tuple[tuple[int, int, int], SelectedFact]] = []

    for priority, concept, definition, entry in _fact_candidates(companyfacts, concepts):
        try:
            entry_fy = int(entry.get("fy"))
            value = float(entry["val"])
        except (KeyError, TypeError, ValueError):
            continue
        if entry_fy != fiscal_year or str(entry.get("fp", "")).upper() != period:
            continue
        if not _form_matches(str(entry.get("form", "")), period):
            continue
        duration = _duration_days(entry)
        duration_delta = 999 if duration is None else abs(duration - target_duration)
        if duration_delta > maximum_delta:
            continue
        score = (duration_delta, priority, -_filing_ordinal(entry))
        matches.append(
            (
                score,
                SelectedFact(
                    value=value,
                    concept=concept,
                    label=str(definition.get("label") or concept),
                    entry=entry,
                ),
            )
        )
    return min(matches, key=lambda item: item[0])[1] if matches else None


def _percent_change(current: float, previous: float) -> float | None:
    if abs(previous) < 1e-9:
        return None
    return (current - previous) / abs(previous) * 100.0


def _close(left: float, right: float, *, reference: float) -> bool:
    return abs(left - right) <= max(abs(reference) * 0.02, 1_000_000.0)


def _expense_breakdown(
    companyfacts: dict[str, Any],
    fiscal_year: int,
    period: str,
    total: float,
    revenue: float,
) -> list[LineItem]:
    items: list[LineItem] = []
    for _, label, concepts in EXPENSE_CONCEPTS:
        fact = select_fact(companyfacts, concepts, fiscal_year, period)
        if fact and fact.value > 0:
            items.append(LineItem(label, abs(fact.value), concept=fact.concept))

    has_sales_or_ga = any(item.name in {"Sales & marketing", "General & administrative"} for item in items)
    if not has_sales_or_ga:
        sga = select_fact(companyfacts, SGA_CONCEPTS, fiscal_year, period)
        if sga and sga.value > 0:
            items.append(LineItem("SG&A", abs(sga.value), concept=sga.concept))

    selected_total = sum(item.value for item in items)
    tolerance = max(revenue * 0.01, 1_000_000.0)
    if selected_total > total + tolerance:
        return [LineItem("Operating expenses", max(total, 0.0))]
    remainder = total - selected_total
    if remainder > tolerance:
        items.append(LineItem("Other operating expenses", remainder))
    if not items and total > 0:
        items.append(LineItem("Operating expenses", total))
    return items


def _normalize_base(
    companyfacts: dict[str, Any],
    identity: CompanyIdentity,
    fiscal_year: int,
    period: str,
) -> Statement:
    period = period.upper()
    notes: list[str] = []
    selected: dict[str, SelectedFact | None] = {
        name: select_fact(companyfacts, concepts, fiscal_year, period)
        for name, concepts in CONCEPTS.items()
    }

    revenue_fact = selected["revenue"]
    if revenue_fact is None or revenue_fact.value <= 0:
        raise NormalizationError(
            f"Could not find positive revenue for {identity.ticker} {period} FY{fiscal_year}."
        )
    revenue = revenue_fact.value
    gross_fact = selected["gross_profit"]
    cost_fact = selected["cost_of_revenue"]
    gross_profit = gross_fact.value if gross_fact else None
    cost_of_revenue = abs(cost_fact.value) if cost_fact else None

    if gross_profit is not None:
        balanced_cost = revenue - gross_profit
        if balanced_cost < 0:
            raise NormalizationError("Gross profit is greater than revenue in the selected SEC facts.")
        if cost_of_revenue is None or not _close(cost_of_revenue, balanced_cost, reference=revenue):
            cost_of_revenue = balanced_cost
            notes.append("Cost of revenue was derived from revenue minus gross profit.")
    elif cost_of_revenue is not None:
        gross_profit = revenue - cost_of_revenue
        notes.append("Gross profit was derived from revenue minus cost of revenue.")

    operating_fact = selected["operating_income"]
    if operating_fact is None:
        expense_fact = selected["operating_expenses"]
        base = gross_profit if gross_profit is not None else revenue
        if expense_fact is None:
            raise NormalizationError("Could not find operating income or operating expenses.")
        operating_income = base - abs(expense_fact.value)
        notes.append("Operating income was derived from the available expense total.")
    else:
        operating_income = operating_fact.value

    operating_base = gross_profit if gross_profit is not None else revenue
    operating_expenses_total = operating_base - operating_income
    if operating_expenses_total < 0:
        raise NormalizationError("Operating income is greater than its available operating base.")

    pretax_fact = selected["pretax_income"]
    if pretax_fact is None:
        raise NormalizationError("Could not find income before tax in the selected SEC facts.")
    pretax_income = pretax_fact.value

    net_fact = selected["net_income"]
    if net_fact is None:
        raise NormalizationError("Could not find net income in the selected SEC facts.")
    net_income = net_fact.value

    other_income = pretax_income - operating_income
    balanced_tax = pretax_income - net_income
    tax_fact = selected["income_tax"]
    income_tax = tax_fact.value if tax_fact else balanced_tax
    if tax_fact is None or not _close(income_tax, balanced_tax, reference=pretax_income):
        income_tax = balanced_tax
        notes.append("Income tax was derived from pretax income minus net income.")

    expenses = _expense_breakdown(
        companyfacts,
        fiscal_year,
        period,
        operating_expenses_total,
        revenue,
    )
    anchor = revenue_fact.entry
    accession = anchor.get("accn")
    return Statement(
        ticker=identity.ticker,
        company=str(companyfacts.get("entityName") or identity.name),
        fiscal_year=fiscal_year,
        period=period,
        revenue=revenue,
        cost_of_revenue=cost_of_revenue,
        gross_profit=gross_profit,
        operating_expenses_total=operating_expenses_total,
        operating_income=operating_income,
        other_income=other_income,
        pretax_income=pretax_income,
        income_tax=income_tax,
        net_income=net_income,
        operating_expenses=expenses,
        filed_date=anchor.get("filed"),
        accession=accession,
        source_url=filing_url(identity.cik, accession),
        notes=notes,
    )


def normalize_companyfacts(
    companyfacts: dict[str, Any],
    identity: CompanyIdentity,
    fiscal_year: int,
    period: str,
) -> Statement:
    """Normalize company-specific XBRL tags into a common Sankey schema."""
    current = _normalize_base(companyfacts, identity, fiscal_year, period)
    try:
        previous = _normalize_base(companyfacts, identity, fiscal_year - 1, period)
    except NormalizationError:
        previous = None

    if previous:
        for key in (
            "revenue",
            "cost_of_revenue",
            "gross_profit",
            "operating_expenses_total",
            "operating_income",
            "other_income",
            "pretax_income",
            "income_tax",
            "net_income",
        ):
            current_value = getattr(current, key)
            previous_value = getattr(previous, key)
            if current_value is not None and previous_value is not None:
                yoy = _percent_change(float(current_value), float(previous_value))
                if yoy is not None:
                    current.yoy[key] = yoy
        previous_expenses = {item.name: item.value for item in previous.operating_expenses}
        for item in current.operating_expenses:
            if item.name in previous_expenses:
                item.yoy_percent = _percent_change(item.value, previous_expenses[item.name])
    return current


def available_periods(companyfacts: dict[str, Any]) -> list[dict[str, Any]]:
    """Return fiscal periods for which a usable revenue duration exists."""
    found: dict[tuple[int, str], str] = {}
    for _, _, _, entry in _fact_candidates(companyfacts, CONCEPTS["revenue"]):
        try:
            fy = int(entry["fy"])
        except (KeyError, TypeError, ValueError):
            continue
        period = str(entry.get("fp", "")).upper()
        if period not in SUPPORTED_PERIODS or not _form_matches(str(entry.get("form", "")), period):
            continue
        duration = _duration_days(entry)
        target = 365 if period == "FY" else 91
        maximum_delta = 100 if period == "FY" else 55
        if duration is None or abs(duration - target) > maximum_delta:
            continue
        filed = str(entry.get("filed") or "")
        key = (fy, period)
        found[key] = max(found.get(key, ""), filed)
    return [
        {"fiscal_year": fy, "period": period, "filed_date": filed}
        for (fy, period), filed in sorted(
            found.items(), key=lambda item: (item[1], item[0][0], item[0][1]), reverse=True
        )
    ]
