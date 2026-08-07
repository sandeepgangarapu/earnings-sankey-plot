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
        self._id_stack: list[str | None] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}:
            self._id_stack.append(element_id)
        if element_id:
            self.elements[element_id] = attributes
            self.text[element_id] = ""

    def handle_endtag(self, tag: str) -> None:
        if self._id_stack:
            self._id_stack.pop()

    def handle_data(self, data: str) -> None:
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
        self.parser = _ElementsById()
        self.parser.feed((ROOT / "web" / "index.html").read_text())

    def test_hidden_result_states_and_panels_are_not_displayed(self) -> None:
        css = (ROOT / "web" / "styles.css").read_text()

        for element_id in ("loading", "empty-state", "svg-panel", "json-panel", "share-menu"):
            attributes = self.parser.elements[element_id]
            attributes["hidden"] = None
            with self.subTest(element_id=element_id):
                self.assertEqual(_computed_display(css, attributes), "none")

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
            "download-svg-chart": "Download SVG",
            "download-html": "Download HTML",
            "copy-svg-chart": "Copy SVG",
            "share-button": "Share",
            "download-svg-source": "Download SVG",
            "copy-svg-source": "Copy SVG",
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
        self.assertEqual(share_button["aria-haspopup"], "menu")
        self.assertEqual(share_button["aria-expanded"], "false")
        self.assertEqual(share_button["aria-controls"], "share-menu")
        self.assertIn("hidden", self.parser.elements["share-menu"])


if __name__ == "__main__":
    unittest.main()
