# Result View, Export, and Sharing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ambiguous format/download controls with Chart, SVG, and JSON result modes containing explicit download, copy, and sharing actions.

**Architecture:** Keep the server payload unchanged. Add a dependency-free ES module for serialization, mode synchronization, clipboard behavior, and social URL construction; connect it to accessible HTML tabs and panels from the existing browser controller. Extend the existing light result workspace with compact action bars, a code-preview treatment, and an anchored share menu.

**Tech Stack:** Semantic HTML, modern browser JavaScript ES modules, CSS, Node's built-in test runner, Python `unittest`, and the dependency-free Python HTTP server.

## Global Constraints

- The result modes are exactly `Chart`, `SVG`, and `JSON`; switching modes never downloads a file.
- HTML remains a download from Chart mode and is not a source-preview mode.
- Copy actions copy raw SVG or pretty-printed normalized JSON and report success or failure truthfully.
- LinkedIn, X, and Facebook share the current page URL and prepared result text; native sharing includes the SVG file only when supported.
- The API response and financial normalization logic remain unchanged.
- Use inert `textContent` for source previews and retain the current server-produced SVG rendering path.

---

### Task 1: Result-action primitives

**Files:**
- Create: `web/result-actions.mjs`
- Create: `tests/test_result_actions.mjs`

**Interfaces:**
- Produces: `statementFilename(statement, extension) -> string`, `serializeStatement(statement) -> string`, `buildStandaloneHtml(result) -> string`, `buildShareMetadata(statement, pageUrl) -> {title, text, url}`, `buildSocialShareUrls(metadata) -> {linkedin, x, facebook}`, `selectResultMode(mode, tabs, panels) -> string`, and `copyText(text, environment) -> Promise<boolean>`.

- [ ] **Step 1: Write failing Node tests**

Cover literal filename/serialization output, safely escaped standalone HTML titles, encoded social URLs, actual tab/panel state mutation, Clipboard API success, selection fallback success, and total clipboard failure.

- [ ] **Step 2: Run tests and verify RED**

Run: `node --test tests/test_result_actions.mjs`

Expected: FAIL because `web/result-actions.mjs` does not exist.

- [ ] **Step 3: Implement the minimal module**

Use browser-native `URLSearchParams`, `Blob`/`File` consumers, and injected clipboard/document dependencies. The fallback must append a temporary textarea, select it, call `execCommand('copy')`, remove it, and return the real command result.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `node --test tests/test_result_actions.mjs`

Expected: all result-action tests PASS with no warnings.

- [ ] **Step 5: Commit**

```bash
git add web/result-actions.mjs tests/test_result_actions.mjs
git commit -m "Add tested result action helpers"
```

### Task 2: Accessible result modes and actions

**Files:**
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `tests/test_web.py`

**Interfaces:**
- Consumes: all exports from `web/result-actions.mjs`.
- Produces: `Chart / SVG / JSON` tablist, matching result panels, explicit per-panel action controls, accessible copy status, and share menu behavior.

- [ ] **Step 1: Write failing markup behavior tests**

Extend the HTML parser test support so tests assert three tab controls reference three panels, Chart is initially selected, non-Chart panels start hidden, each panel exposes only its specified verb-first actions, and the share menu contains native, LinkedIn, X, and Facebook options.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m unittest tests.test_web -v`

Expected: FAIL because the new tablist, panels, actions, and share menu are absent.

- [ ] **Step 3: Implement the markup and controller**

In `index.html`, replace the three immediate-download buttons with a `role="tablist"` mode switcher and three `role="tabpanel"` result sections. Add `Download SVG`, `Download HTML`, `Download JSON`, `Copy SVG`, `Copy JSON`, and Share controls in their relevant panels plus a polite copy/share status region.

In `app.js`, import the Task 1 helpers. Reset to Chart in `showResult`, populate SVG and JSON previews with `textContent`, synchronize tabs/panels on clicks and arrow keys, wire explicit downloads, show accurate copy feedback, construct social anchors, support native file share when possible, and close the share menu after actions, outside clicks, or Escape.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m unittest tests.test_web -v && node --test tests/test_result_actions.mjs`

Expected: all web and result-action tests PASS.

- [ ] **Step 5: Commit**

```bash
git add web/index.html web/app.js tests/test_web.py
git commit -m "Add result modes and export actions"
```

### Task 3: Responsive visual treatment and verification

**Files:**
- Modify: `web/styles.css`
- Modify: `README.md`

**Interfaces:**
- Consumes: semantic classes and state attributes added in Task 2.
- Produces: compact mode navigation, action bars, share menu, source previews, feedback state, and mobile wrapping consistent with the existing result surface.

- [ ] **Step 1: Add the focused CSS regression assertion**

Extend `tests/test_web.py` so hidden result panels and the hidden share menu still compute to `display: none` despite authored layout rules.

- [ ] **Step 2: Run the focused test and verify RED if a new layout selector overrides hidden state**

Run: `python -m unittest tests.test_web.WebStateTests -v`

Expected: hidden-state assertions remain protective; any conflicting display rule must fail before the CSS is finalized.

- [ ] **Step 3: Implement styling and documentation**

Style selected/unselected tabs as a compact segmented control; style action buttons as quiet verb-first controls; position the share menu under its trigger; format source previews in monospace with horizontal scrolling; retain the light navy/green visual language; and wrap controls below 680px. Update README feature copy to describe inspect, copy, download, and share behavior.

- [ ] **Step 4: Run all automated verification**

Run: `uv run python -m unittest discover -s tests -v && node --test tests/test_result_actions.mjs tests/test_app_controller.mjs && git diff --check`

Expected: all Python and Node tests PASS and the diff check is empty.

- [ ] **Step 5: Perform browser verification**

Start the local server, open the sample, inspect desktop and narrow layouts, switch all modes by click and keyboard, verify source scrolling, copy feedback, share-menu dismissal, and each download filename. Inspect the browser console for errors.

- [ ] **Step 6: Commit**

```bash
git add web/styles.css README.md tests/test_web.py
git commit -m "Polish result export and sharing interface"
```
