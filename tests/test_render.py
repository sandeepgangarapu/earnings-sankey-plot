from __future__ import annotations

import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from earnings_sankey.graph import build_graph
from earnings_sankey.models import Statement
from earnings_sankey.render import render_html, render_svg


ROOT = Path(__file__).resolve().parents[1]


class RenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.statement = Statement.from_dict(
            json.loads((ROOT / "examples" / "alphabet_q1_fy26.json").read_text())
        )

    def test_svg_is_well_formed_and_accessible(self) -> None:
        svg = render_svg(self.statement)
        root = ET.fromstring(svg)
        self.assertTrue(root.tag.endswith("svg"))
        self.assertEqual(root.attrib["role"], "img")
        self.assertIn("Alphabet Q1 FY2026", svg)

    def test_graph_has_standard_accounting_stages(self) -> None:
        graph = build_graph(self.statement)
        node_ids = {node.id for node in graph.nodes}
        self.assertTrue(
            {"revenue", "gross_profit", "operating_income", "pretax_income", "net_income"}
            <= node_ids
        )
        self.assertTrue(all(link.value > 0 for link in graph.links))

    def test_html_is_self_contained(self) -> None:
        output = render_html(self.statement)
        self.assertIn("<!doctype html>", output)
        self.assertIn("Download SVG", output)
        self.assertNotIn("<script src=", output)


if __name__ == "__main__":
    unittest.main()

