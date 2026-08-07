# Company Search and Copy Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the technical, multi-control landing form with benefit-led copy, browser-side company search, useful defaults, and one “Visualize earnings” action.

**Architecture:** The Python server will own the SEC identity and expose a cached, compact company directory. A focused browser module will rank matches and validate selected or manually entered tickers; the existing controller will wire that module into an accessible combobox and keep result rendering unchanged.

**Tech Stack:** Python 3.12 standard library HTTP server, vanilla ES modules, HTML/CSS, Python `unittest`, Node.js `node:test`.

## Global Constraints

- Keep the current public product name; the later Earnings Genie branding plan supersedes the original Earnings Sankey copy in this plan.
- Headline: “Understand how a company makes and spends its money.”
- Introduction: “Earnings Genie turns a company’s SEC filing into one intuitive visualization of its revenue, costs, and profit.”
- Primary action label: “Visualize earnings.”
- Prefill Alphabet Inc. (`GOOGL`), fiscal year `2026`, and period `Q1`; do not automatically generate a chart.
- Load the company directory lazily and keep it in browser memory for the page session.
- Never expose `SEC_USER_AGENT` to browser HTML or JSON.
- Preserve CLI contact and JSON-override behavior.
- Keep the existing Sankey normalization, rendering, result modes, export, and share behavior.

---

### Task 1: Server-owned SEC access and compact company directory

**Files:**
- Modify: `src/earnings_sankey/sec.py`
- Modify: `src/earnings_sankey/server.py`
- Modify: `tests/test_sec.py`
- Create: `tests/test_server.py`

**Interfaces:**
- Produces: `SECClient.company_directory() -> list[dict[str, str]]`.
- Produces: `configured_sec_client(environ: Mapping[str, str] | None = None) -> SECClient`.
- Produces: `GET /api/companies` JSON array of `{ticker, name}` objects.
- Changes: `POST /api/generate` reads `SEC_USER_AGENT` from the server environment and consumes only `ticker`, `fiscal_year`, and `period` from the browser payload.

- [ ] **Step 1: Write failing SEC directory tests**

Add tests using a complete three-entry SEC ticker fixture and patch only `_get_json`:

```python
def test_company_directory_returns_only_browser_search_fields(self) -> None:
    client = SECClient("Test User test@example.com")
    payload = {
        "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
        "1": {"cik_str": 1652044, "ticker": "GOOGL", "title": "Alphabet Inc."},
        "2": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
    }
    with patch.object(client, "_get_json", return_value=payload):
        self.assertEqual(
            client.company_directory(),
            [
                {"ticker": "AAPL", "name": "Apple Inc."},
                {"ticker": "GOOGL", "name": "Alphabet Inc."},
                {"ticker": "MSFT", "name": "MICROSOFT CORP"},
            ],
        )
```

Also assert malformed entries without a ticker or title are skipped and a non-object SEC response raises `SECError`.

- [ ] **Step 2: Run the SEC tests and verify the new tests fail**

Run: `uv run python -m unittest tests.test_sec -v`

Expected: failure because `SECClient` has no `company_directory` method.

- [ ] **Step 3: Implement the compact directory method**

Fetch `TICKERS_URL`, validate it is a dictionary, preserve SEC order, strip ticker/title strings, skip incomplete rows, and return only `ticker` and `name`.

- [ ] **Step 4: Run the SEC tests and verify they pass**

Run: `uv run python -m unittest tests.test_sec -v`

Expected: all `tests.test_sec` cases pass.

- [ ] **Step 5: Write failing server configuration and route tests**

Test `configured_sec_client` directly with controlled mappings:

```python
def test_configured_client_uses_server_environment(self) -> None:
    client = configured_sec_client({"SEC_USER_AGENT": "Web App web@example.com"})
    self.assertEqual(client.user_agent, "Web App web@example.com")

def test_configured_client_explains_missing_server_identity(self) -> None:
    with self.assertRaisesRegex(ValueError, "not configured for SEC access"):
        configured_sec_client({})
```

Start `ThreadingHTTPServer(("127.0.0.1", 0), AppHandler)` in a test thread, patch `configured_sec_client` to return a fake client, request `/api/companies`, and assert HTTP 200 plus the literal compact array. For `/api/generate`, patch `configured_sec_client`, `available_periods`, `normalize_companyfacts`, and `_result`; send a body containing only `ticker`, `fiscal_year`, and `period`; assert the response succeeds and the fake client receives `GOOGL`.

- [ ] **Step 6: Run the server tests and verify the new tests fail**

Run: `uv run python -m unittest tests.test_server -v`

Expected: import or assertion failures because `configured_sec_client`, `/api/companies`, and server-owned generation are not implemented.

- [ ] **Step 7: Implement server configuration and routes**

Import `os` and `Mapping`, add `configured_sec_client`, allow `_json` to serialize arrays as well as objects, add the guarded `/api/companies` route, and replace the payload-derived contact in `do_POST` with `configured_sec_client()`. Remove web override parsing and application from `do_POST`; leave CLI code untouched.

- [ ] **Step 8: Run focused server and SEC tests**

Run: `uv run python -m unittest tests.test_sec tests.test_server -v`

Expected: all focused cases pass with no network requests.

### Task 2: Search ranking, ticker validation, and fiscal-year choices

**Files:**
- Create: `web/company-search.mjs`
- Create: `tests/test_company_search.mjs`

**Interfaces:**
- Produces: `formatCompany(company) -> string` formatted as `Name (TICKER)`.
- Produces: `rankCompanyMatches(companies, query, limit = 8) -> Company[]`.
- Produces: `resolveCompanyTicker(inputValue, selectedCompany) -> string | null`.
- Produces: `moveCompanySelection(activeIndex, key, resultCount) -> number`.
- Produces: `fiscalYearChoices(currentYear) -> number[]` from `currentYear + 1` through `2009`.

- [ ] **Step 1: Write failing pure behavior tests**

Cover literal outcomes:

```javascript
assert.deepEqual(
  rankCompanyMatches(companies, 'app').map(({ ticker }) => ticker),
  ['APP', 'AAPL'],
);
assert.equal(resolveCompanyTicker('Alphabet Inc. (GOOGL)', companies[0]), 'GOOGL');
assert.equal(resolveCompanyTicker(' aapl ', null), 'AAPL');
assert.equal(resolveCompanyTicker('Apple Incorporated', null), null);
assert.equal(moveCompanySelection(-1, 'ArrowDown', 3), 0);
assert.equal(moveCompanySelection(0, 'ArrowUp', 3), 2);
assert.deepEqual(fiscalYearChoices(2026).slice(0, 3), [2027, 2026, 2025]);
assert.equal(fiscalYearChoices(2026).at(-1), 2009);
```

Use fixtures that prove exact ticker, ticker prefix, name prefix, and substring ranking independently; assert results are capped at eight.

- [ ] **Step 2: Run the company-search tests and verify they fail**

Run: `node --test tests/test_company_search.mjs`

Expected: module-not-found failure for `web/company-search.mjs`.

- [ ] **Step 3: Implement the pure search module**

Normalize comparisons with trimmed lowercase strings. Assign ranking buckets in this order: exact ticker, ticker prefix, name prefix, ticker substring, name substring. Preserve SEC order within a bucket. Validate manual tickers with a bounded SEC-compatible ticker pattern and uppercase the return value. Implement wraparound keyboard indices and the descending year range.

- [ ] **Step 4: Run the company-search tests and verify they pass**

Run: `node --test tests/test_company_search.mjs`

Expected: all search, validation, keyboard-index, and year-range cases pass.

### Task 3: Simplified page, accessible combobox, and request controller

**Files:**
- Modify: `web/index.html`
- Modify: `web/styles.css`
- Modify: `web/app.js`
- Modify: `tests/test_web.py`
- Modify: `tests/test_app_controller.mjs`

**Interfaces:**
- Consumes: all exports from `web/company-search.mjs`.
- Consumes: `GET /api/companies` compact array.
- Produces: `POST /api/generate` body `{ticker: string, fiscal_year: number | null, period: string | null}`.

- [ ] **Step 1: Write failing HTML contract tests**

Update the page parser assertions to require:

```python
self.assertEqual(self.parser.text["page-title"].strip(), "Understand how a company makes and spends its money.")
self.assertEqual(self.parser.text["submit-label"].strip(), "Visualize earnings")
self.assertEqual(self.parser.elements["company-search"]["role"], "combobox")
self.assertEqual(self.parser.elements["company-search"]["aria-controls"], "company-options")
self.assertEqual(self.parser.elements["company-options"]["role"], "listbox")
self.assertIn("selected", self.parser.elements["fiscal-year-default"])
self.assertIn("selected", self.parser.elements["period-q1"])
```

Assert that `sample-button`, `user-agent`, `override`, and the trust sidebar IDs/classes no longer exist. Assert the SEC EDGAR link points to `https://www.sec.gov/edgar/search/`.

- [ ] **Step 2: Run the HTML tests and verify they fail**

Run: `uv run python -m unittest tests.test_web -v`

Expected: failures identify the old headline, missing combobox, old action, and controls that must be removed.

- [ ] **Step 3: Write failing controller tests**

Extend `FakeElement` only with DOM behavior the real controller uses (`className`, `type`, `removeAttribute`, and variadic `replaceChildren`). Replace sample-button result loading in existing tests with form submission. Add focused tests that:

- focus the company field and assert exactly one `/api/companies` fetch across repeated input;
- type `apple`, render ranked options, and select `AAPL` by click;
- use Arrow Down and Enter to select the active result, and Escape to close the list;
- submit a manual `MSFT` ticker and assert the exact three-key generation body;
- reject an unselected company name without calling `/api/generate`;
- assert the generated fiscal-year options retain `2026` as the selected default.

- [ ] **Step 4: Run the controller tests and verify they fail**

Run: `node --test tests/test_app_controller.mjs`

Expected: failures because the current controller still depends on sample/contact/override controls and has no company-search behavior.

- [ ] **Step 5: Implement the new HTML structure and copy**

Replace the hero copy exactly as specified, remove the trust sidebar, replace the ticker input with an accessible combobox wrapper (`company-search`, `company-options`, `company-search-status`, hidden `ticker`), change fiscal year to a select with a `2026` fallback option, select `Q1`, remove contact/sample/override markup, and label the primary button with a `submit-label` span. Update the method copy and link only the words “SEC EDGAR” to `https://www.sec.gov/edgar/search/`.

- [ ] **Step 6: Implement the controller behavior**

Import the search helpers. Populate fiscal years on startup. Fetch `/api/companies` once on first focus/input and cache the promise and result. Render up to eight option buttons with company name and ticker, maintain `aria-expanded`, `aria-activedescendant`, and `aria-selected`, and wire pointer plus Arrow Up/Down, Enter, and Escape behavior. Preserve manual ticker fallback. Submit only the three-key generation body and keep all existing result/export/share behavior.

- [ ] **Step 7: Apply the focused visual system**

Artifact type: front-end visualization app. Audience: people studying how public companies make and spend money. Primary job: choose a company and period, then create a chart. Visual mode: light, editorial utility with a compact form beside the visualization workspace.

Keep the existing forest/green/pink domain palette and serif/sans roles. Remove obsolete trust/contact/override/secondary-button selectors. Add a positioned combobox menu with a quiet border, compact rows, direct name/ticker hierarchy, visible active state, and a non-blocking status line. Keep the hero compact despite its longer headline. At tablet widths, let Company take the wider grid column and keep both selects aligned; at mobile widths, stack the fields and keep the options menu within the viewport.

- [ ] **Step 8: Run focused browser and HTML tests**

Run: `uv run python -m unittest tests.test_web -v`

Run: `node --test tests/test_company_search.mjs tests/test_app_controller.mjs`

Expected: all focused cases pass.

### Task 4: Documentation, regression verification, and visual QA

**Files:**
- Modify: `README.md`

**Interfaces:**
- Documents: server-side `SEC_USER_AGENT`, searchable company field, and current web workflow.

- [ ] **Step 1: Update the README**

Explain that the web server must be started with `SEC_USER_AGENT="Name email@example.com"`, that visitors search by company name or ticker, and that the contact stays server-side. Remove the instruction to enter an SEC identity in the page. Keep the CLI and JSON-override documentation because those capabilities remain supported.

- [ ] **Step 2: Run the complete automated verification**

Run: `uv run python -m unittest discover -s tests -v`

Run: `node --test tests/test_result_actions.mjs tests/test_company_search.mjs tests/test_app_controller.mjs`

Run: `git diff --check`

Expected: zero failures, zero errors, and no whitespace errors.

- [ ] **Step 3: Run the app with controlled SEC configuration**

Run: `SEC_USER_AGENT="Earnings Genie local@example.com" uv run earnings-sankey-server --host 127.0.0.1 --port 8000`

Expected: the server reports `Earnings Genie is running at http://127.0.0.1:8000`.

- [ ] **Step 4: Inspect desktop and mobile layouts**

Use the product-native preview to inspect the initial page around 1440px and 390px widths. Verify the benefit-led hero, Alphabet/2026/Q1 defaults, single action, company suggestions, keyboard focus, dropdown containment, three-step copy, and absence of the removed controls. Correct any visual defect and rerun the focused tests after each correction.

- [ ] **Step 5: Review the final diff against the spec**

Read `docs/superpowers/specs/2026-08-07-company-search-and-copy-design.md`, map every requirement to code or tests, and confirm CLI behavior and result actions were not unintentionally changed.

- [ ] **Step 6: Commit the implementation**

```bash
git add README.md src/earnings_sankey/sec.py src/earnings_sankey/server.py web/index.html web/styles.css web/app.js web/company-search.mjs tests/test_sec.py tests/test_server.py tests/test_web.py tests/test_company_search.mjs tests/test_app_controller.mjs docs/superpowers/plans/2026-08-07-company-search-and-copy-refresh.md
git commit -m "feat: simplify earnings generator and add company search"
```
