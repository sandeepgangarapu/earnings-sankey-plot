from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}")
DISPLAY_RE = re.compile(r"display\s*:\s*([^;!]+)\s*(!important)?\s*;?")


class _ElementsById(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.elements: dict[str, dict[str, str | None]] = {}
        self.text: dict[str, str] = {}
        self.document_title = ""
        self.brand_attributes: dict[str, str | None] = {}
        self.brand_text = ""
        self.workspace_attributes: dict[str, str | None] = {}
        self._id_stack: list[str | None] = []
        self._in_title = False
        self._brand_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if tag == "title":
            self._in_title = True
        if tag == "a" and "brand" in (attributes.get("class") or "").split():
            self.brand_attributes = attributes
            self._brand_depth = 1
        elif self._brand_depth:
            self._brand_depth += 1
        if tag == "section" and "workspace" in (attributes.get("class") or "").split():
            self.workspace_attributes = attributes
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}:
            self._id_stack.append(element_id)
        if element_id:
            self.elements[element_id] = attributes
            self.text[element_id] = ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if self._brand_depth:
            self._brand_depth -= 1
        if self._id_stack:
            self._id_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.document_title += data
        if self._brand_depth:
            self.brand_text += data
        for element_id in reversed(self._id_stack):
            if element_id:
                self.text[element_id] += data
                return


def _matches(selector: str, attributes: dict[str, str | None]) -> bool:
    selector = selector.strip()
    if selector == "[hidden]":
        return "hidden" in attributes
    if selector.startswith(".") and selector.count(".") == 1:
        return selector[1:] in (attributes.get("class") or "").split()
    return False


def _computed_display(css: str, attributes: dict[str, str | None]) -> str:
    # Browsers supply a normal-priority `[hidden] { display: none; }` rule.
    # Author display rules outrank it unless the app explicitly protects the hidden state.
    candidates = [(False, 0, 0, "none")] if "hidden" in attributes else []
    for order, (selector_list, declarations) in enumerate(RULE_RE.findall(css), start=1):
        match = DISPLAY_RE.search(declarations)
        if not match:
            continue
        for selector in selector_list.split(","):
            if _matches(selector, attributes):
                candidates.append((bool(match.group(2)), 1, order, match.group(1).strip()))
    return max(candidates)[-1]


class WebStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = (ROOT / "web" / "index.html").read_text()
        self.parser = _ElementsById()
        self.parser.feed(self.html)

    def test_hidden_result_states_and_panels_are_not_displayed(self) -> None:
        css = (ROOT / "web" / "styles.css").read_text()

        for element_id in ("loading", "empty-state", "svg-panel", "json-panel", "share-menu", "download-menu"):
            self.assertIn(element_id, self.parser.elements)
            attributes = self.parser.elements[element_id]
            attributes["hidden"] = None
            with self.subTest(element_id=element_id):
                self.assertEqual(_computed_display(css, attributes), "none")

    def test_generator_and_result_regions_have_accessible_context(self) -> None:
        generator = self.parser.elements["generator-form"]
        self.assertEqual(generator.get("aria-labelledby"), "generator-title")
        self.assertIn("generator-title", self.parser.elements)

        company = self.parser.elements["company-search"]
        self.assertEqual(company.get("role"), "combobox")
        self.assertEqual(company.get("aria-controls"), "company-options")
        self.assertEqual(company.get("aria-expanded"), "false")
        self.assertEqual(company.get("aria-describedby"), "company-search-status")
        self.assertEqual(self.parser.elements["company-options"].get("role"), "listbox")

        result = self.parser.elements["result-workspace"]
        self.assertEqual(result["aria-label"], "Chart workspace")

        controller_ids = {
            "generator-form", "company-search", "company-options", "company-search-status",
            "empty-state", "loading", "error",
            "chart-shell", "result-views", "result-toolbar", "result-meta",
            "source-link", "notes-panel", "notes-list", "svg-source", "json-source",
        }
        self.assertTrue(controller_ids.issubset(self.parser.elements))

    def test_page_leads_with_the_user_benefit_and_one_action(self) -> None:
        self.assertEqual(
            self.parser.text["page-title"].strip(),
            "Understand how a company makes and spends its money.",
        )
        self.assertEqual(
            self.parser.text["hero-intro"].strip(),
            "Earnings Genie turns a company’s SEC filing into one intuitive "
            "visualization of its revenue, costs, and profit.",
        )
        self.assertEqual(self.parser.text["submit-label"].strip(), "Visualize earnings")
        self.assertNotIn("trust-note", self.html)

    def test_page_uses_earnings_genie_as_its_primary_brand(self) -> None:
        self.assertEqual(self.parser.document_title.strip(), "Earnings Genie")
        self.assertEqual(self.parser.brand_attributes.get("aria-label"), "Earnings Genie home")
        self.assertEqual(" ".join(self.parser.brand_text.split()), "G Earnings Genie")
        self.assertTrue(
            self.parser.text["hero-intro"].strip().startswith("Earnings Genie ")
        )
        self.assertEqual(self.parser.workspace_attributes.get("aria-label"), "Sankey generator")

    def test_generator_uses_alphabet_defaults_and_removes_advanced_inputs(self) -> None:
        self.assertEqual(
            self.parser.elements["company-search"].get("value"),
            "Alphabet Inc. (GOOGL)",
        )
        self.assertEqual(self.parser.elements["ticker"].get("value"), "GOOGL")
        self.assertIn("selected", self.parser.elements["fiscal-year-default"])
        self.assertIn("selected", self.parser.elements["period-q1"])
        for removed_id in ("sample-button", "user-agent", "override"):
            self.assertNotIn(removed_id, self.parser.elements)

    def test_method_links_the_official_edgar_search(self) -> None:
        self.assertEqual(
            self.parser.elements["edgar-link"].get("href"),
            "https://www.sec.gov/edgar/search/",
        )

    def test_result_modes_are_accessible_views_not_download_controls(self) -> None:
        self.assertIn("result-mode-tabs", self.parser.elements)
        self.assertEqual(self.parser.elements["result-mode-tabs"]["role"], "tablist")
        expected = {
            "mode-chart": ("chart", "chart-panel", "true"),
            "mode-svg": ("svg", "svg-panel", "false"),
            "mode-json": ("json", "json-panel", "false"),
        }
        for element_id, (mode, panel_id, selected) in expected.items():
            with self.subTest(element_id=element_id):
                self.assertIn(element_id, self.parser.elements)
                attributes = self.parser.elements[element_id]
                self.assertEqual(attributes["role"], "tab")
                self.assertEqual(attributes["data-result-mode"], mode)
                self.assertEqual(attributes["aria-controls"], panel_id)
                self.assertEqual(attributes["aria-selected"], selected)
                self.assertEqual(self.parser.text[element_id].strip().lower(), mode)

        for mode in ("chart", "svg", "json"):
            panel_id = f"{mode}-panel"
            self.assertIn(panel_id, self.parser.elements)
            attributes = self.parser.elements[panel_id]
            with self.subTest(panel_id=panel_id):
                self.assertEqual(attributes["role"], "tabpanel")
                self.assertEqual(attributes["data-result-panel"], mode)
                self.assertEqual(attributes["aria-labelledby"], f"mode-{mode}")
                self.assertEqual("hidden" in attributes, mode != "chart")

    def test_result_actions_name_their_outcomes_and_share_destinations(self) -> None:
        expected_labels = {
            "copy-image": "Copy image",
            "download-button": "Download",
            "download-png": "Download PNG",
            "download-svg-chart": "Download SVG",
            "download-html": "Download HTML",
            "share-button": "Share",
            "download-svg-source": "Download SVG",
            "copy-svg-source": "Copy SVG code",
            "download-json": "Download JSON",
            "copy-json": "Copy JSON",
            "native-share": "Share from device",
            "share-linkedin": "LinkedIn",
            "share-x": "X",
            "share-facebook": "Facebook",
        }
        for element_id, label in expected_labels.items():
            with self.subTest(element_id=element_id):
                self.assertIn(element_id, self.parser.text)
                self.assertEqual(self.parser.text[element_id].strip(), label)

        self.assertIn("share-button", self.parser.elements)
        share_button = self.parser.elements["share-button"]
        self.assertNotIn("aria-haspopup", share_button)
        self.assertEqual(share_button["aria-expanded"], "false")
        self.assertEqual(share_button["aria-controls"], "share-menu")
        share_options = self.parser.elements["share-menu"]
        self.assertNotIn("role", share_options)
        self.assertEqual(share_options["aria-label"], "Share options")
        self.assertIn("hidden", share_options)
        for element_id in ("native-share", "share-linkedin", "share-x", "share-facebook"):
            self.assertNotIn("role", self.parser.elements[element_id])

        self.assertIn("download-button", self.parser.elements)
        download_button = self.parser.elements["download-button"]
        self.assertEqual(download_button["aria-expanded"], "false")
        self.assertEqual(download_button["aria-controls"], "download-menu")
        download_options = self.parser.elements["download-menu"]
        self.assertEqual(download_options["aria-label"], "Download options")
        self.assertIn("hidden", download_options)


if __name__ == "__main__":
    unittest.main()
