from __future__ import annotations

from dataclasses import dataclass, field

from .models import LineItem, Statement


@dataclass(slots=True)
class GraphNode:
    id: str
    label: str
    value: float
    role: str
    column: int
    y_hint: float
    yoy_percent: float | None = None


@dataclass(slots=True)
class GraphLink:
    source: str
    target: str
    value: float
    role: str


@dataclass(slots=True)
class SankeyGraph:
    nodes: list[GraphNode] = field(default_factory=list)
    links: list[GraphLink] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def add_node(
        self,
        node_id: str,
        label: str,
        value: float,
        role: str,
        column: int,
        y_hint: float,
        yoy_percent: float | None = None,
    ) -> None:
        if value <= 0:
            return
        self.nodes.append(
            GraphNode(node_id, label, value, role, column, y_hint, yoy_percent)
        )

    def add_link(self, source: str, target: str, value: float, role: str) -> None:
        if value > 0:
            self.links.append(GraphLink(source, target, value, role))


def _balanced_items(
    items: list[LineItem], total: float, fallback_label: str
) -> list[LineItem]:
    if total <= 0:
        return []
    positive = [item for item in items if item.value > 0]
    selected = sum(item.value for item in positive)
    tolerance = max(total * 0.015, 1.0)
    if selected > total + tolerance:
        return [LineItem(fallback_label, total)]
    if total - selected > tolerance:
        positive.append(LineItem(f"Other {fallback_label.lower()}", total - selected))
    return positive or [LineItem(fallback_label, total)]


def build_graph(statement: Statement) -> SankeyGraph:
    graph = SankeyGraph(notes=list(statement.notes))
    if statement.revenue <= 0:
        raise ValueError("Revenue must be positive to render a Sankey diagram.")

    revenue_streams = _balanced_items(
        statement.revenue_streams, statement.revenue, "Revenue"
    ) if statement.revenue_streams else []
    if revenue_streams:
        count = len(revenue_streams)
        for index, item in enumerate(revenue_streams):
            node_id = f"revenue_stream_{index}"
            y_hint = 0.14 + (0.66 * index / max(count - 1, 1))
            graph.add_node(
                node_id,
                item.name,
                item.value,
                "revenue",
                0,
                y_hint,
                item.yoy_percent,
            )
            graph.add_link(node_id, "revenue", item.value, "revenue")

    graph.add_node(
        "revenue",
        "Revenue",
        statement.revenue,
        "revenue",
        1,
        0.42,
        statement.yoy.get("revenue"),
    )

    operating_base_id = "revenue"
    operating_base = statement.revenue
    if (
        statement.gross_profit is not None
        and statement.gross_profit > 0
        and statement.cost_of_revenue is not None
        and statement.cost_of_revenue >= 0
    ):
        graph.add_node(
            "gross_profit",
            "Gross profit",
            statement.gross_profit,
            "profit",
            2,
            0.33,
            statement.yoy.get("gross_profit"),
        )
        graph.add_node(
            "cost_of_revenue",
            "Cost of revenue",
            statement.cost_of_revenue,
            "cost",
            2,
            0.73,
            statement.yoy.get("cost_of_revenue"),
        )
        graph.add_link("revenue", "gross_profit", statement.gross_profit, "profit")
        graph.add_link("revenue", "cost_of_revenue", statement.cost_of_revenue, "cost")
        operating_base_id = "gross_profit"
        operating_base = statement.gross_profit

        cost_items = _balanced_items(
            statement.cost_of_revenue_items,
            statement.cost_of_revenue,
            "Cost of revenue",
        ) if statement.cost_of_revenue_items else []
        for index, item in enumerate(cost_items):
            node_id = f"cost_item_{index}"
            graph.add_node(
                node_id,
                item.name,
                item.value,
                "cost",
                3,
                0.76 + index * 0.10,
                item.yoy_percent,
            )
            graph.add_link("cost_of_revenue", node_id, item.value, "cost")

    operating_expenses = statement.operating_expenses_total
    if operating_expenses is None:
        operating_expenses = operating_base - statement.operating_income

    if statement.operating_income >= 0:
        graph.add_node(
            "operating_income",
            "Operating profit",
            statement.operating_income,
            "profit",
            3,
            0.25,
            statement.yoy.get("operating_income"),
        )
        graph.add_link(
            operating_base_id, "operating_income", statement.operating_income, "profit"
        )
    else:
        graph.add_node(
            "operating_loss",
            "Operating loss",
            abs(statement.operating_income),
            "cost",
            3,
            0.25,
            statement.yoy.get("operating_income"),
        )
        graph.add_link(
            operating_base_id,
            "operating_loss",
            min(operating_base, abs(statement.operating_income)),
            "cost",
        )
        graph.notes.append(
            "Loss-making statements are shown as magnitude flows; accounting stages may not balance visually."
        )

    if operating_expenses > 0:
        graph.add_node(
            "operating_expenses",
            "Operating expenses",
            operating_expenses,
            "cost",
            3,
            0.54,
            statement.yoy.get("operating_expenses_total"),
        )
        graph.add_link(
            operating_base_id,
            "operating_expenses",
            min(operating_base, operating_expenses),
            "cost",
        )
        expense_items = _balanced_items(
            statement.operating_expenses,
            operating_expenses,
            "Operating expenses",
        )
        count = len(expense_items)
        for index, item in enumerate(expense_items):
            node_id = f"operating_expense_{index}"
            y_hint = 0.48 + (0.44 * index / max(count - 1, 1))
            graph.add_node(
                node_id,
                item.name,
                item.value,
                "cost",
                4,
                y_hint,
                item.yoy_percent,
            )
            graph.add_link("operating_expenses", node_id, item.value, "cost")

    if statement.pretax_income >= 0 and statement.operating_income >= 0:
        graph.add_node(
            "pretax_income",
            "Pre-tax profit",
            statement.pretax_income,
            "profit",
            4,
            0.18,
            statement.yoy.get("pretax_income"),
        )
        if statement.other_income >= 0:
            graph.add_node(
                "other_income",
                "Other income",
                statement.other_income,
                "profit",
                2,
                0.08,
                statement.yoy.get("other_income"),
            )
            graph.add_link(
                "operating_income", "pretax_income", statement.operating_income, "profit"
            )
            graph.add_link("other_income", "pretax_income", statement.other_income, "profit")
        else:
            other_expense = abs(statement.other_income)
            graph.add_node(
                "other_expense",
                "Other expense",
                other_expense,
                "cost",
                4,
                0.38,
                statement.yoy.get("other_income"),
            )
            graph.add_link("operating_income", "pretax_income", statement.pretax_income, "profit")
            graph.add_link("operating_income", "other_expense", other_expense, "cost")

        if statement.net_income >= 0 and statement.income_tax >= 0:
            graph.add_node(
                "net_income",
                "Net income",
                statement.net_income,
                "profit",
                5,
                0.10,
                statement.yoy.get("net_income"),
            )
            graph.add_node(
                "income_tax",
                "Income tax",
                statement.income_tax,
                "cost",
                5,
                0.34,
                statement.yoy.get("income_tax"),
            )
            graph.add_link("pretax_income", "net_income", statement.net_income, "profit")
            graph.add_link("pretax_income", "income_tax", statement.income_tax, "cost")
        elif statement.net_income >= 0 and statement.income_tax < 0:
            benefit = abs(statement.income_tax)
            graph.add_node("tax_benefit", "Tax benefit", benefit, "profit", 4, 0.02)
            graph.add_node(
                "net_income",
                "Net income",
                statement.net_income,
                "profit",
                5,
                0.10,
                statement.yoy.get("net_income"),
            )
            graph.add_link("pretax_income", "net_income", statement.pretax_income, "profit")
            graph.add_link("tax_benefit", "net_income", benefit, "profit")
    else:
        loss = abs(statement.pretax_income)
        graph.add_node(
            "pretax_loss",
            "Pre-tax loss",
            loss,
            "cost",
            4,
            0.18,
            statement.yoy.get("pretax_income"),
        )
        graph.add_node(
            "net_loss",
            "Net loss",
            abs(statement.net_income),
            "cost",
            5,
            0.10,
            statement.yoy.get("net_income"),
        )
        graph.add_link("pretax_loss", "net_loss", min(loss, abs(statement.net_income)), "cost")

    return graph
