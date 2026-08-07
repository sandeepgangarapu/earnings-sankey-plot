# Editorial Tool-First Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refresh the single-page Earnings Sankey interface with an approachable, editorial tool-first hierarchy while preserving all result behavior.

**Architecture:** Keep the existing dependency-free HTML/CSS/JavaScript app and stable DOM IDs. Reorganize the page copy and form markup in `web/index.html`, replace the visual system in `web/styles.css`, and make only the approved loading-language change in `web/app.js`.

**Tech Stack:** Semantic HTML, modern responsive CSS, vanilla JavaScript, Python `unittest`, Node test runner.

## Global Constraints

- Keep the generator above the fold and the result canvas beside it on desktop.
- Use approachable language while retaining financial credibility.
- Preserve the server API, SEC normalization, SVG rendering, result modes, downloads, copying, and sharing.
- Preserve stable element IDs and accessible tab/panel relationships.
- Build light-first and verify desktop and mobile output.

---

### Task 1: Copy and semantic hierarchy

**Files:**
- Modify: `tests/test_web.py`
- Modify: `web/index.html`
- Modify: `web/app.js`

**Interfaces:**
- Consumes: Existing DOM IDs queried by `web/app.js`.
- Produces: Revised page copy, form headings, helper text, and unchanged interactive element IDs.

- [ ] **Step 1: Write the failing tests**

Add assertions that the generator form is named by a visible `generator-title`, the SEC contact helper is connected with `aria-describedby`, and the primary result region retains its accessible label and every ID required by the controller.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run python -m unittest tests.test_web -v`
Expected: FAIL because the approved copy and hierarchy are absent.

- [ ] **Step 3: Implement the semantic HTML and loading copy**

Restructure the header, hero, form headings, empty state, method strip, and footer without changing the existing result-control IDs. Change the loading message to `Reading and organizing the SEC filing…`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run python -m unittest tests.test_web -v`
Expected: PASS.

### Task 2: Editorial Instrument visual system

**Files:**
- Modify: `web/styles.css`
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: The semantic classes introduced by Task 1.
- Produces: A responsive two-column tool workspace, compact mobile stack, warm neutral palette, deep-green action language, and readable result states.

- [ ] **Step 1: Implement the CSS system**

Replace the current large marketing hero and card-heavy styling with the approved compact editorial hierarchy, restrained bordered workspace, purposeful status/control pills, accessible focus styles, and responsive desktop/mobile layouts.

- [ ] **Step 2: Run all automated tests**

Run: `uv run python -m unittest discover -s tests -v && node --test tests/test_result_actions.mjs tests/test_app_controller.mjs`
Expected: PASS with zero failures.

- [ ] **Step 3: Verify in the browser**

Run the local server, inspect the empty and sample-result states at desktop and mobile viewport sizes, and fix any overflow, hierarchy, or legibility problems found.
