from __future__ import annotations

import html
import json
from dataclasses import dataclass
from typing import Iterable

from .graph import GraphLink, GraphNode, SankeyGraph, build_graph
from .models import Statement


NODE_COLORS = {
    "revenue": "#5F6368",
    "profit": "#00A66A",
    "cost": "#D60B52",
}
LINK_COLORS = {
    "revenue": "rgba(95,99,104,0.42)",
    "profit": "rgba(0,166,106,0.48)",
    "cost": "rgba(214,11,82,0.43)",
}


@dataclass(slots=True)
class PlacedNode:
    node: GraphNode
    x: float
    y: float
    width: float
    height: float


def format_money(value: float) -> str:
    magnitude = abs(value)
    if magnitude >= 1_000_000_000_000:
        amount, suffix = value / 1_000_000_000_000, "T"
    elif magnitude >= 1_000_000_000:
        amount, suffix = value / 1_000_000_000, "B"
    elif magnitude >= 1_000_000:
        amount, suffix = value / 1_000_000, "M"
    elif magnitude >= 1_000:
        amount, suffix = value / 1_000, "K"
    else:
        amount, suffix = value, ""
    decimals = 0 if abs(amount) >= 100 else 1
    return f"${amount:,.{decimals}f}{suffix}"


def _effective_values(graph: SankeyGraph) -> dict[str, float]:
    incoming = {node.id: 0.0 for node in graph.nodes}
    outgoing = {node.id: 0.0 for node in graph.nodes}
    for link in graph.links:
        outgoing[link.source] = outgoing.get(link.source, 0.0) + link.value
        incoming[link.target] = incoming.get(link.target, 0.0) + link.value
    return {
        node.id: max(node.value, incoming.get(node.id, 0.0), outgoing.get(node.id, 0.0))
        for node in graph.nodes
    }


def _layout(
    graph: SankeyGraph,
    *,
    width: int,
    height: int,
) -> tuple[dict[str, PlacedNode], float]:
    # Reserve enough room for left-aligned segment labels and right-aligned outcomes.
    x_positions = [160, 314, 486, 658, 866, 1072]
    node_width = 18.0
    top = 105.0
    bottom = height - 105.0
    available = bottom - top
    values = _effective_values(graph)
    largest = max(values.values(), default=1.0)
    scale = min(180.0 / largest, available / (largest * 2.4))
    placed: dict[str, PlacedNode] = {}

    for column in range(6):
        column_nodes = sorted(
            (node for node in graph.nodes if node.column == column),
            key=lambda node: node.y_hint,
        )
        if not column_nodes:
            continue
        items: list[PlacedNode] = []
        for node in column_nodes:
            node_height = max(9.0, values[node.id] * scale)
            center = top + node.y_hint * available
            items.append(
                PlacedNode(
                    node=node,
                    x=x_positions[column],
                    y=max(top, min(bottom - node_height, center - node_height / 2)),
                    width=node_width,
                    height=node_height,
                )
            )

        gap = 20.0
        for index in range(1, len(items)):
            minimum = items[index - 1].y + items[index - 1].height + gap
            if items[index].y < minimum:
                items[index].y = minimum
        overflow = items[-1].y + items[-1].height - bottom
        if overflow > 0:
            for item in items:
                item.y -= overflow
        for index in range(len(items) - 2, -1, -1):
            maximum = items[index + 1].y - gap - items[index].height
            if items[index].y > maximum:
                items[index].y = maximum
        underflow = top - items[0].y
        if underflow > 0:
            for item in items:
                item.y += underflow
        placed.update({item.node.id: item for item in items})
    return placed, scale


def _link_paths(
    graph: SankeyGraph,
    placed: dict[str, PlacedNode],
    scale: float,
) -> Iterable[str]:
    outgoing: dict[str, list[GraphLink]] = {node.id: [] for node in graph.nodes}
    incoming: dict[str, list[GraphLink]] = {node.id: [] for node in graph.nodes}
    for link in graph.links:
        outgoing.setdefault(link.source, []).append(link)
        incoming.setdefault(link.target, []).append(link)

    source_offsets: dict[tuple[str, str], float] = {}
    target_offsets: dict[tuple[str, str], float] = {}
    for node_id, links in outgoing.items():
        node = placed.get(node_id)
        if not node:
            continue
        links.sort(key=lambda link: placed[link.target].y)
        total = sum(max(1.0, link.value * scale) for link in links)
        cursor = node.y + max(0.0, (node.height - total) / 2)
        for link in links:
            source_offsets[(link.source, link.target)] = cursor
            cursor += max(1.0, link.value * scale)
    for node_id, links in incoming.items():
        node = placed.get(node_id)
        if not node:
            continue
        links.sort(key=lambda link: placed[link.source].y)
        total = sum(max(1.0, link.value * scale) for link in links)
        cursor = node.y + max(0.0, (node.height - total) / 2)
        for link in links:
            target_offsets[(link.source, link.target)] = cursor
            cursor += max(1.0, link.value * scale)

    for link in graph.links:
        source = placed[link.source]
        target = placed[link.target]
        thickness = max(1.0, link.value * scale)
        x0 = source.x + source.width
        x1 = target.x
        y0 = source_offsets[(link.source, link.target)]
        y1 = target_offsets[(link.source, link.target)]
        control = max(50.0, (x1 - x0) * 0.48)
        path = (
            f"M{x0:.2f},{y0:.2f} "
            f"C{x0 + control:.2f},{y0:.2f} {x1 - control:.2f},{y1:.2f} {x1:.2f},{y1:.2f} "
            f"L{x1:.2f},{y1 + thickness:.2f} "
            f"C{x1 - control:.2f},{y1 + thickness:.2f} "
            f"{x0 + control:.2f},{y0 + thickness:.2f} {x0:.2f},{y0 + thickness:.2f} Z"
        )
        yield (
            f'<path class="flow flow-{link.role}" d="{path}">'
            f"<title>{html.escape(format_money(link.value))}</title></path>"
        )


def _node_svg(item: PlacedNode) -> str:
    node = item.node
    color = NODE_COLORS[node.role]
    is_left_label = node.column == 0
    label_x = item.x - 9 if is_left_label else item.x + item.width + 9
    anchor = "end" if is_left_label else "start"
    label_y = item.y + item.height / 2 - 12
    yoy = ""
    if node.yoy_percent is not None:
        yoy = f'{node.yoy_percent:+.0f}% Y/Y'
    lines = [
        f'<tspan class="node-name" x="{label_x:.2f}" dy="0">{html.escape(node.label)}</tspan>',
        f'<tspan x="{label_x:.2f}" dy="17">{html.escape(format_money(node.value))}</tspan>',
    ]
    if yoy:
        lines.append(
            f'<tspan class="node-yoy" x="{label_x:.2f}" dy="16">{html.escape(yoy)}</tspan>'
        )
    return (
        f'<g class="node node-{node.role}">'
        f'<rect x="{item.x:.2f}" y="{item.y:.2f}" width="{item.width:.2f}" '
        f'height="{item.height:.2f}" rx="1.5" fill="{color}">'
        f"<title>{html.escape(node.label)}: {html.escape(format_money(node.value))}</title></rect>"
        f'<text x="{label_x:.2f}" y="{label_y:.2f}" text-anchor="{anchor}">'
        f"{''.join(lines)}</text></g>"
    )


def render_svg(statement: Statement, *, width: int = 1280, height: int = 720) -> str:
    graph = build_graph(statement)
    placed, scale = _layout(graph, width=width, height=height)
    flow_svg = "".join(_link_paths(graph, placed, scale))
    node_svg = "".join(_node_svg(placed[node.id]) for node in graph.nodes)
    source = statement.source_url or "Bundled/manual data"
    escaped_title = html.escape(statement.title)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="chart-title chart-desc">
  <title id="chart-title">{escaped_title}</title>
  <desc id="chart-desc">Income statement flow from revenue through costs, operating profit, tax, and net income.</desc>
  <style>
    .chart-title {{ font: 700 31px Inter, ui-sans-serif, system-ui, -apple-system, sans-serif; fill: #143A52; }}
    .chart-subtitle {{ font: 500 13px Inter, ui-sans-serif, system-ui, sans-serif; fill: #657783; }}
    .flow {{ stroke: none; transition: opacity .15s ease; }}
    .flow:hover {{ opacity: .72; }}
    .flow-revenue {{ fill: {LINK_COLORS['revenue']}; }}
    .flow-profit {{ fill: {LINK_COLORS['profit']}; }}
    .flow-cost {{ fill: {LINK_COLORS['cost']}; }}
    .node text {{ font: 500 13px Inter, ui-sans-serif, system-ui, -apple-system, sans-serif; fill: #18262F; pointer-events: none; }}
    .node-name {{ font-weight: 700; }}
    .node-yoy {{ font-size: 11px; fill: #63717A; }}
    .legend {{ font: 600 12px Inter, ui-sans-serif, system-ui, sans-serif; fill: #4C5B64; }}
    .source {{ font: 500 11px Inter, ui-sans-serif, system-ui, sans-serif; fill: #7B8991; }}
  </style>
  <rect width="100%" height="100%" fill="#FBFCFA" rx="12"/>
  <text class="chart-title" x="36" y="48">{escaped_title}</text>
  <text class="chart-subtitle" x="36" y="72">Standardized from public filing data · values are proportional</text>
  <g transform="translate(955,43)">
    <rect x="0" y="-10" width="10" height="10" rx="2" fill="{NODE_COLORS['revenue']}"/><text class="legend" x="16" y="0">Revenue</text>
    <rect x="88" y="-10" width="10" height="10" rx="2" fill="{NODE_COLORS['profit']}"/><text class="legend" x="104" y="0">Profit</text>
    <rect x="158" y="-10" width="10" height="10" rx="2" fill="{NODE_COLORS['cost']}"/><text class="legend" x="174" y="0">Costs</text>
  </g>
  <g class="links">{flow_svg}</g>
  <g class="nodes">{node_svg}</g>
  <text class="source" x="36" y="{height - 26}">Source: {html.escape(source)}</text>
</svg>'''


def render_html(statement: Statement) -> str:
    svg = render_svg(statement)
    payload = html.escape(json.dumps(statement.to_dict(), indent=2))
    notes = "".join(f"<li>{html.escape(note)}</li>" for note in statement.notes)
    source_link = ""
    if statement.source_url:
        safe_url = html.escape(statement.source_url, quote=True)
        source_link = f'<a href="{safe_url}" target="_blank" rel="noreferrer">Open SEC filing source</a>'
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(statement.title)}</title>
  <style>
    :root {{ color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, -apple-system, sans-serif; color: #18262f; background: #eef2ee; }}
    body {{ margin: 0; padding: 28px; }}
    main {{ max-width: 1320px; margin: 0 auto; }}
    .chart {{ background: #fbfcfa; border: 1px solid #dce3de; border-radius: 14px; box-shadow: 0 12px 34px rgba(20,58,82,.08); overflow: auto; }}
    .chart svg {{ width: 100%; min-width: 1040px; height: auto; display: block; }}
    .toolbar {{ display: flex; gap: 12px; align-items: center; justify-content: flex-end; margin-bottom: 12px; }}
    button, a {{ font: inherit; }}
    button {{ border: 0; border-radius: 999px; background: #143a52; color: white; padding: 10px 18px; cursor: pointer; font-weight: 700; }}
    a {{ color: #0a6f51; font-weight: 700; text-decoration: none; }}
    details {{ margin-top: 18px; background: white; border: 1px solid #dce3de; border-radius: 10px; padding: 14px 18px; }}
    pre {{ white-space: pre-wrap; font-size: 12px; }}
    .notes {{ color: #53646e; }}
  </style>
</head>
<body>
  <main>
    <div class="toolbar">{source_link}<button id="download-svg">Download SVG</button></div>
    <div class="chart" id="chart">{svg}</div>
    {f'<details class="notes"><summary>Normalization notes</summary><ul>{notes}</ul></details>' if notes else ''}
    <details><summary>Normalized data</summary><pre>{payload}</pre></details>
  </main>
  <script>
    document.getElementById('download-svg').addEventListener('click', () => {{
      const text = document.querySelector('#chart svg').outerHTML;
      const blob = new Blob([text], {{type: 'image/svg+xml'}});
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = {json.dumps(f'{statement.ticker.lower()}-{statement.fiscal_year}-{statement.period.lower()}-sankey.svg')};
      link.click();
      URL.revokeObjectURL(link.href);
    }});
  </script>
</body>
</html>'''
