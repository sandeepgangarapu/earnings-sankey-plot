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

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id:
            self.elements[element_id] = attributes


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
    def test_completed_chart_hides_loading_and_empty_states(self) -> None:
        parser = _ElementsById()
        parser.feed((ROOT / "web" / "index.html").read_text())
        css = (ROOT / "web" / "styles.css").read_text()

        for element_id in ("loading", "empty-state"):
            attributes = parser.elements[element_id]
            attributes["hidden"] = None
            with self.subTest(element_id=element_id):
                self.assertEqual(_computed_display(css, attributes), "none")


if __name__ == "__main__":
    unittest.main()
