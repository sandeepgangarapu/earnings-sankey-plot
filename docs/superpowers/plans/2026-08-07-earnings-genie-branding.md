# Earnings Genie Branding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make “Earnings Genie” the primary user-facing product name without renaming stable technical identifiers or removing accurate Sankey terminology.

**Architecture:** Apply a copy-only rename at the public presentation boundary: the static web shell, README introduction, and local server command messaging. Preserve the Python package, CLI commands, deployment configuration, repository URL, output filenames, and chart/share terminology.

**Tech Stack:** Static HTML, Python 3.10+, `unittest`

## Global Constraints

- Use “Earnings Genie” as the product name.
- Keep “Sankey” when it identifies the visualization type.
- Keep `earnings-sankey`, `earnings_sankey`, repository URLs, Fly app IDs, output filenames, and internal class/function names unchanged.
- Do not change layout or behavior beyond replacing the existing brand-mark initial from `S` to `G`.

---

### Task 1: Rebrand public presentation surfaces

**Files:**
- Modify: `tests/test_web.py`
- Modify: `tests/test_server.py`
- Modify: `web/index.html`
- Modify: `README.md`
- Modify: `src/earnings_sankey/server.py`

**Interfaces:**
- Consumes: the existing static page, README, and `server.main()` command output
- Produces: a consistent “Earnings Genie” public identity while retaining technical Sankey names

- [x] **Step 1: Write the failing web branding test**

Add assertions that the parsed page title, brand link accessible name, brand mark, brand text, and hero introduction present “Earnings Genie.” The test should continue to require “Sankey generator” as chart terminology.

Add command-surface tests that exercise `build_parser().format_help()` and `main()` output so the local server also presents the new product brand.

- [x] **Step 2: Run the branding test to verify it fails**

Run: `uv run python -m unittest tests.test_web.WebStateTests.test_page_uses_earnings_genie_as_its_primary_brand -v`

Expected: FAIL because the current page title and header say “Earnings Sankey.”

- [x] **Step 3: Apply the minimal public-facing rename**

In `web/index.html`, use `Earnings Genie` for the document title, header accessible name/text, and hero product reference; change the existing brand mark to `G`. In `README.md`, use `Earnings Genie` for the title and opening product sentence while keeping the Sankey diagram description and technical commands. In `server.py`, change only the argparse description and startup message to `Earnings Genie`.

- [x] **Step 4: Run targeted and full verification**

Run the branding test, then the full Python suite and browser-controller suite. Confirm that user-facing `Earnings Sankey` references are gone while approved technical references remain.
