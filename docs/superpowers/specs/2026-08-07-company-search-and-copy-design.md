# Company Search and Copy Refresh Design

## Goal

Make Earnings Sankey immediately understandable to people who want to learn how a company earns and spends money, while reducing the generator to the few inputs needed to create a visualization.

## Product Copy

The hero will lead with the user benefit instead of the mechanics of reading an earnings report.

- Headline: “Understand how a company makes and spends its money.”
- Introduction: “Earnings Sankey turns a company’s SEC filing into one intuitive visualization of its revenue, costs, and profit.”
- Remove the “Comparable by design” sidebar and its accounting-tag explanation.
- Keep “Earnings Sankey” as the product name.

The primary action will be labeled “Visualize earnings.” There will be no separate Alphabet-example action.

## Generator Form

The form will contain three visible controls:

1. **Company:** A searchable combobox that accepts a company name or ticker and displays matching company names with their tickers. Selecting a result stores the ticker used by the generation API. The field is initially set to “Alphabet Inc. (GOOGL).”
2. **Fiscal year:** A select control initially set to `2026`. Browser code will populate a practical descending range from the next calendar year through 2009 so the control remains useful without another filing-data request.
3. **Period:** The existing select control, initially set to `Q1`, with `Latest`, `Q1`, `Q2`, `Q3`, and `FY` options.

The visible SEC contact field and optional segment-detail JSON panel will be removed. The browser generation request will send only `ticker`, `fiscal_year`, and `period`.

The form will begin with the Alphabet values, but it will not automatically build a chart. This preserves a clear user action and avoids an unsolicited SEC request on page load.

## Company Search Data Flow

The browser will lazily request the company directory the first time the Company combobox receives focus or search input. A new same-origin `GET /api/companies` endpoint will return a compact array of `{ticker, name}` objects derived from the official SEC company-ticker directory. The SEC client’s existing one-hour in-process cache will prevent repeated upstream downloads.

The browser will keep the returned directory in memory for the rest of the page session. It will perform case-insensitive prefix and substring matching locally and show a small, ranked result list. Exact ticker matches rank first, then ticker-prefix matches, company-name-prefix matches, and remaining substring matches. The list will be limited to eight visible suggestions.

The combobox will support pointer selection and standard keyboard behavior: Arrow Up/Down changes the active suggestion, Enter selects it, and Escape closes the list. Accessible combobox/listbox roles and active-descendant state will describe this interaction to assistive technology.

If the directory cannot load, the field will continue to accept a manually entered ticker and show a concise non-blocking message. Before submission, an unselected value that is already a plausible ticker will be normalized to uppercase. A company name that was not selected will produce a clear prompt to select a matching company or enter its ticker.

## SEC Identity

Web requests will use the server’s `SEC_USER_AGENT` environment variable. The server will validate that value only when an endpoint needs SEC data and will return a configuration-focused error if it is absent or invalid. The contact value will never be sent to or exposed in browser HTML or JSON.

CLI behavior remains unchanged: CLI users may continue to provide `SEC_USER_AGENT` and use JSON overrides. Removing segment detail applies only to the web form and web generation request.

## “How It Works” Copy

The section will remain a three-step explanation:

1. **Read the filing:** “Pull the company’s reported facts from SEC EDGAR.” The words “SEC EDGAR” will link to the official EDGAR search page.
2. **Organize the numbers:** “Bring revenue, costs, and profit into one clear view.”
3. **Trace the flow:** “Show what came in, what went out, and what remained.”

The section heading will emphasize clarity rather than normalization mechanics.

## Backend Compatibility

`POST /api/generate` will no longer accept a browser-provided `user_agent` or web override. It will obtain the SEC identity from server configuration and otherwise preserve the existing ticker, period selection, normalization, rendering, and response behavior.

`GET /api/sample` may remain for backward compatibility, but the refreshed page and controller will not call it.

## Error Handling

- Missing or invalid server SEC identity: explain that the service is not configured for SEC access.
- Company-directory request failure: preserve manual ticker entry and show a non-blocking search status.
- No company match: ask for a selected company or a valid ticker before submitting.
- Existing generation and filing errors continue to appear in the chart workspace.

## Testing

- Server tests will cover the compact company-directory response, server-owned SEC identity, missing configuration, and the simplified generation payload.
- Browser-controller tests will cover lazy directory loading, search ranking, company selection, keyboard operation, manual ticker fallback, default values, and the simplified request body.
- HTML/CSS tests will verify the new copy and accessible combobox structure, plus the absence of the removed contact, sample, sidebar, and override controls.
- The full Python and Node test suites will run after implementation.
- The page will be inspected at desktop and mobile widths to verify dropdown placement, focus states, responsive layout, and the simplified hero/form balance.

## Out of Scope

- Automatically loading a chart on page open.
- Fetching filing-specific available years before submission.
- Persisting the company directory across browser sessions.
- Changing the CLI override feature or the Sankey normalization and rendering model.
