from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class LineItem:
    name: str
    value: float
    yoy_percent: float | None = None
    concept: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "LineItem":
        return cls(
            name=str(value["name"]),
            value=float(value["value"]),
            yoy_percent=(
                None
                if value.get("yoy_percent") is None
                else float(value["yoy_percent"])
            ),
            concept=value.get("concept"),
        )


@dataclass(slots=True)
class Statement:
    ticker: str
    company: str
    fiscal_year: int
    period: str
    revenue: float
    operating_income: float
    pretax_income: float
    net_income: float
    cost_of_revenue: float | None = None
    gross_profit: float | None = None
    operating_expenses_total: float | None = None
    other_income: float = 0.0
    income_tax: float = 0.0
    filed_date: str | None = None
    accession: str | None = None
    source_url: str | None = None
    revenue_streams: list[LineItem] = field(default_factory=list)
    cost_of_revenue_items: list[LineItem] = field(default_factory=list)
    operating_expenses: list[LineItem] = field(default_factory=list)
    yoy: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def title(self) -> str:
        return f"{self.company} {self.period} FY{self.fiscal_year} Income Statement"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Statement":
        item_fields = {
            "revenue_streams",
            "cost_of_revenue_items",
            "operating_expenses",
        }
        payload = {key: item for key, item in value.items() if key not in item_fields}
        for key in item_fields:
            payload[key] = [LineItem.from_dict(item) for item in value.get(key, [])]
        payload["ticker"] = str(payload["ticker"]).upper()
        payload["fiscal_year"] = int(payload["fiscal_year"])
        payload["period"] = str(payload["period"]).upper()
        for key in (
            "revenue",
            "operating_income",
            "pretax_income",
            "net_income",
            "other_income",
            "income_tax",
        ):
            payload[key] = float(payload.get(key, 0.0))
        for key in ("cost_of_revenue", "gross_profit", "operating_expenses_total"):
            if payload.get(key) is not None:
                payload[key] = float(payload[key])
        payload["yoy"] = {
            str(key): float(item) for key, item in payload.get("yoy", {}).items()
        }
        payload["notes"] = [str(item) for item in payload.get("notes", [])]
        return cls(**payload)

    def with_override(self, override: dict[str, Any]) -> "Statement":
        """Return a copy with manually curated fields layered on top."""
        payload = self.to_dict()
        for key, value in override.items():
            if key in payload and value is not None:
                payload[key] = value
        return Statement.from_dict(payload)
