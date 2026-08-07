# Cached Permanent Results Design

## Goal

Give every generated company-period result a stable, shareable URL and make
repeat visits fast without introducing a database. This is the first release
in the approved product sequence: permanent results establish the foundation
for earnings-change stories, company comparisons, historical views, creator
exports, and discovery pages.

## Scope

This release adds:

- Canonical result routes shaped as `/company/{ticker}/{fiscal-year}/{period}`.
- Direct loading of those routes in a new browser session.
- A small file-backed server cache containing the complete generated JSON
  response: normalized statement plus rendered SVG.
- Automatic replacement of the generic page URL with the canonical result URL
  after a successful generation.
- A persistent Fly Volume for the production cache.

The existing form, result modes, downloads, clipboard actions, and social-share
actions remain available. Because they already use the current page URL,
updating the browser URL makes their links point to the selected result.

Personalized Open Graph images, server-rendered result markup, search-engine
index pages, an on-page result history, company comparisons, and earnings-story
analysis are later releases and are not part of this change.

## Canonical Identity

A permanent result is identified by three normalized fields:

1. Uppercase ticker, such as `GOOGL`.
2. Four-digit fiscal year, such as `2026`.
3. Uppercase fiscal period: `Q1`, `Q2`, `Q3`, or `FY`.

The canonical path is therefore `/company/GOOGL/2026/Q1`. The route always
names the resolved filing period. A form request for `Latest` may initially use
an unresolved request, but after generation the response statement supplies
the concrete year and period used to build the canonical path.

Route components are validated before any SEC request. Tickers must use the
SEC-style letters, digits, dots, or hyphens accepted by the company directory;
years must be four digits from 2009 through 2100; and periods must use the
supported set. Invalid browser routes return `404`. Invalid API parameters
return structured `400` responses. Extra path components and percent-encoded
separators are rejected rather than being interpreted as filesystem paths.

## Browser Flow

On ordinary form submission, the browser continues to call
`POST /api/generate`. After a successful response it:

1. Derives the canonical path from the returned statement.
2. Calls `history.pushState` with that path without reloading the document.
3. Renders the result through the existing result controller, which builds its
   sharing metadata from the now-canonical current URL.

When the server receives a browser request for a valid canonical company path,
it serves the application shell instead of looking for a static file at that
path. During initialization, the browser parses the path, updates the company,
year, and period controls, and requests
`GET /api/results/{ticker}/{fiscal-year}/{period}`. The response enters the same
loading, success, and error states as a form-generated result.

Browser back and forward navigation listens for `popstate`. Moving to a valid
company path loads that result; moving back to `/` restores the generator's
normal ungenerated state. A failed direct load retains the canonical URL and
shows the existing result-area error so the user can correct the inputs or
return home.

## Generation Service

The HTTP handler's current generation pipeline will be extracted into a small
server-side function that accepts ticker, optional fiscal year, and optional
period and returns the existing `{statement, svg}` payload. Both
`POST /api/generate` and the new explicit-period GET endpoint call this shared
function, preventing the two routes from drifting.

The explicit GET endpoint requires all three canonical identity fields. It is
safe to retry and returns the same structured result shape as the POST
endpoint. The POST endpoint remains responsible for resolving `Latest` and
other form requests that do not yet have a canonical period.

Successful generation responses include no user identity or secret fields.
The server-owned `SEC_USER_AGENT` continues to be used only for outbound SEC
requests and is never included in cache keys, cache contents, URLs, logs, or
browser responses.

## File Cache

A focused `ResultCache` component will own cache key creation, reads, writes,
freshness checks, and cleanup. The cache has no third-party dependency and uses
one JSON file per result.

The key is a SHA-256 digest of canonical JSON containing:

- A cache-format version.
- The uppercase ticker.
- The requested fiscal year or `null`.
- The requested period or `null`.

The stored envelope contains its creation timestamp, normalized request
identity, and the complete generated result. Keeping the cache-format version
in the key provides an explicit invalidation mechanism when normalization or
rendering behavior changes.

Entries expire after 24 hours. This keeps repeat browsing fast while allowing
SEC amendments and newly disseminated facts to appear without manual cache
management. The SEC states that Company Facts data is updated as filings are
disseminated, so a permanent URL identifies the company-period result rather
than promising that the bytes will never change.

Writes use a temporary file in the cache directory followed by `os.replace`,
so readers see either the old complete entry or the new complete entry. A
per-key in-process lock prevents concurrent identical requests from issuing
duplicate SEC fetches or racing to write the same file. Requests for different
keys may proceed independently.

After a successful write, cleanup retains at most 200 cache files by removing
the oldest excess entries. Cache files contain only reproducible public filing
data, so no backup or recovery workflow is required.

Cache read failures, malformed entries, and write failures fail open: the app
generates and returns a fresh result. A concise server warning may include the
cache key and exception class, but never request bodies or the SEC identity.

## Configuration and Hosting

The cache directory comes from `EARNINGS_SANKEY_CACHE_DIR`. Local development
and tests may use an operating-system temporary directory; production sets it
to `/data/generated`.

The Fly app remains a single Machine in `sjc`. A small Fly Volume named for the
generated cache is mounted at `/data`, allowing cached results to survive
Machine restarts and deployments. The volume is reconstructible and is not a
database or system of record. The existing scale-to-zero behavior remains
unchanged.

The deployment documentation will include the one-time volume creation step.
The application creates the `generated` subdirectory when needed. If the mount
is missing or unwritable, generation still works through fail-open cache
behavior, although results will not persist.

## HTTP and Cache Semantics

Application-shell and JSON responses retain the existing security headers.
The server-side result cache is independent of browser/proxy caching; this
release does not make generated responses publicly cacheable through HTTP
headers.

The API returns:

- `200` for a cached or freshly generated result.
- `400` for a syntactically valid request whose ticker or filing period cannot
  produce a result.
- `404` for unsupported application routes.

Whether a result was a cache hit is an implementation detail and is not added
to the user-facing payload.

## Testing

Unit tests for the cache will cover:

- Stable keys for normalized equivalent requests.
- Separation of different tickers, years, periods, and cache versions.
- Fresh hits and expired misses.
- Atomic replacement and malformed-entry recovery.
- The 200-entry cleanup limit.
- Concurrent same-key requests invoking the generator once.
- Fail-open behavior for unreadable or unwritable cache storage.

Server tests will cover:

- Shared generation behavior between POST and explicit GET routes.
- Cache hits avoiding the SEC and normalization pipeline.
- Valid canonical routes serving the application shell.
- Rejection of malformed canonical and API paths.
- Absence of `SEC_USER_AGENT` from cache keys, files, logs, and responses.

Browser tests will cover:

- Updating the URL after successful generation.
- Loading a canonical path on startup.
- Synchronizing the generator controls with the path.
- Back and forward navigation.
- Direct-load error handling.
- Share metadata using the canonical current URL.

The complete Python and Node suites will run after implementation. Production
verification will include a cold-start visit to a canonical result, a repeat
visit that does not call the SEC, and a restart/deployment check confirming
that the volume-backed entry remains usable.

## Success Criteria

- A visitor can copy `/company/GOOGL/2026/Q1`, open it in a fresh browser, and
  receive the same company-period result.
- Generating a result updates the address bar to its canonical URL without a
  page reload.
- Repeated identical requests within 24 hours do not re-fetch SEC Company
  Facts or re-render the SVG.
- Cached results survive Fly Machine restarts and deployments.
- Cache operation never persists or exposes the SEC contact identity.
- Missing or damaged cache storage cannot prevent fresh generation.
- Existing generation, company search, result modes, downloads, clipboard, and
  sharing behavior continue to work.

## Product Sequence After This Release

Once permanent results are verified, the approved roadmap continues in this
order:

1. Earnings-change story and profit bridge.
2. Two-company comparison normalized per $100 of revenue.
3. Historical company journey.
4. Creator-specific export formats and social previews.
5. Recent-earnings and discovery surfaces.

Each item will receive its own scoped design and implementation plan so the
product can ship useful increments without coupling unrelated data and UI
work.
