# Fly.io Subdomain Hosting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the live Earnings Sankey application at `https://earnings.sandeepgangarapu.com` on a scale-to-zero Fly.io Machine.

**Architecture:** Package the existing dependency-free Python server and browser assets in one container. Fly Proxy terminates HTTPS, starts and stops one San Jose Machine, and routes both static and API traffic; GitHub Actions deploys tested `main` commits. A process-wide request gate prevents concurrent users from bypassing SEC pacing.

**Tech Stack:** Python 3.12, `uv`, `unittest`, Docker, Fly.io Machines, GitHub Actions, DNS, TLS.

## Global Constraints

- Public hostname: `earnings.sandeepgangarapu.com`.
- Fly app: `sandeep-earnings-sankey`; primary region: San Jose (`sjc`).
- One `shared-cpu-1x` Machine with 512 MB RAM, automatic stop/start, and zero minimum running Machines.
- No database or persistent volume; the SEC response cache remains in memory.
- Keep request bodies and the user-provided SEC identity out of logs.
- Preserve the existing 30-second SEC timeout and one-megabyte inbound request limit.
- Do not modify the separate Hugo repository.
- Preserve unrelated user changes in the main checkout.

---

### Task 1: Process-wide SEC request pacing

**Files:**
- Create: `tests/test_sec.py`
- Modify: `src/earnings_sankey/sec.py`

**Interfaces:**
- Consumes: `SECClient(user_agent, min_request_interval=...)` and `SECClient._get_json(url)`.
- Produces: one class-level outbound request lock and timestamp shared by every `SECClient` instance in the process.

- [ ] **Step 1: Write the failing concurrency-boundary test**

Create a test that replaces only the external `urllib.request.urlopen` boundary with a real context-manager response containing `{}`. Construct two clients with a 50 ms minimum interval, request two unique URLs sequentially, record when the fake upstream boundary is entered, and assert that the two entries are at least 40 ms apart. Reset the shared cache and pacing timestamp in `setUp` so the test is independent.

- [ ] **Step 2: Run the new test and confirm the expected failure**

Run: `uv run python -m unittest tests.test_sec.SECClientPacingTests.test_separate_clients_share_request_pacing -v`

Expected: FAIL because the current per-instance timestamps allow both upstream calls without a shared delay.

- [ ] **Step 3: Implement the minimum shared pacing state**

Move `_request_lock` and `_last_request` to class attributes beside `_cache_lock`. Remove their instance initialization. In `_get_json`, take `type(self)._request_lock`, calculate the delay from `type(self)._last_request`, and update the class timestamp in `finally`. Keep caching and error translation unchanged.

- [ ] **Step 4: Verify the focused and full Python suites**

Run:

```bash
uv run python -m unittest tests.test_sec -v
uv run python -m unittest discover -s tests -v
```

Expected: the pacing test passes and all existing Python tests remain green.

- [ ] **Step 5: Commit the pacing safeguard**

```bash
git add tests/test_sec.py src/earnings_sankey/sec.py
git commit -m "Share SEC request pacing across clients"
```

### Task 2: Production container and Fly Machine configuration

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `fly.toml`

**Interfaces:**
- Consumes: the `earnings-sankey-server` console entry point and `/healthz` route.
- Produces: an OCI image listening on `0.0.0.0:8080` and a Fly service definition routing HTTPS traffic to port 8080.

- [ ] **Step 1: Add the container definition**

Use `python:3.12-slim` plus the pinned `uv` binary image, set `PYTHONUNBUFFERED=1`, `UV_COMPILE_BYTECODE=1`, `UV_LINK_MODE=copy`, and put `/app/.venv/bin` on `PATH`. Copy `pyproject.toml` and `uv.lock`, install locked non-development dependencies, copy `src`, `web`, `examples`, and `README.md`, install the project, expose port 8080, and run:

```dockerfile
CMD ["earnings-sankey-server", "--host", "0.0.0.0", "--port", "8080"]
```

- [ ] **Step 2: Exclude non-runtime files from the build context**

Ignore `.git`, `.github`, `.venv`, `.worktrees`, `.superpowers`, Python and test caches, `docs`, `tests`, `output`, `dist`, and `build`. Do not exclude `src`, `web`, `examples`, `pyproject.toml`, `uv.lock`, or `README.md`.

- [ ] **Step 3: Add the Fly service definition**

Configure app `sandeep-earnings-sankey`, region `sjc`, internal port `8080`, forced HTTPS, `auto_stop_machines = "stop"`, `auto_start_machines = true`, `min_machines_running = 0`, request concurrency soft/hard limits of 10/20, a 30-second `/healthz` check with a 10-second grace period and 5-second timeout, and a 1x shared CPU VM with 512 MB RAM.

- [ ] **Step 4: Build and exercise the real container**

Run:

```bash
docker build -t earnings-sankey:local .
docker run --rm -d --name earnings-sankey-local -p 18080:8080 earnings-sankey:local
curl --fail --retry 10 --retry-delay 1 http://127.0.0.1:18080/healthz
curl --fail http://127.0.0.1:18080/api/sample > /tmp/earnings-sankey-sample.json
docker stop earnings-sankey-local
```

Expected: health returns `{"ok": true}`, the sample response contains `statement` and `svg`, and the container stops cleanly.

- [ ] **Step 5: Validate Fly configuration and commit**

Run `flyctl config validate --config fly.toml` and expect a valid configuration. Then commit:

```bash
git add Dockerfile .dockerignore fly.toml
git commit -m "Add scale-to-zero Fly deployment"
```

### Task 3: Tested-main deployment automation and documentation

**Files:**
- Create: `.github/workflows/fly-deploy.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: successful completion of the existing `test` workflow for a push to `main`, the workflow run's exact `head_sha`, and the `FLY_API_TOKEN` GitHub secret.
- Produces: a remote Fly deployment of the tested commit and user-facing public/deployment documentation.

- [ ] **Step 1: Add the gated deployment workflow**

Trigger on completed runs of workflow `test`. Run the deploy job only when the conclusion is `success`, the source event is `push`, and `head_branch` is `main`. Give the workflow read-only contents permission, check out `github.event.workflow_run.head_sha`, install `flyctl`, and run `flyctl deploy --remote-only --ha=false` with `FLY_API_TOKEN` from repository secrets. Add a deployment concurrency group that cancels superseded runs.

- [ ] **Step 2: Document the public service and operator flow**

Add `https://earnings.sandeepgangarapu.com` near the top of the README. Add a deployment section naming `fly.toml`, the scale-to-zero cold-start behavior, `/healthz`, and the required `FLY_API_TOKEN` repository secret without exposing any token value.

- [ ] **Step 3: Verify the repository suites and workflow syntax**

Run:

```bash
uv run python -m unittest discover -s tests -v
node --test tests/test_result_actions.mjs tests/test_app_controller.mjs
ruby -e 'require "yaml"; YAML.load_file(".github/workflows/fly-deploy.yml", aliases: true); puts "workflow yaml ok"'
git diff --check
```

Expected: all tests pass, YAML parses, and no whitespace errors are reported.

- [ ] **Step 4: Commit automation and documentation**

```bash
git add .github/workflows/fly-deploy.yml README.md
git commit -m "Deploy tested main commits to Fly"
```

### Task 4: Create and publish the Fly application

**Files:**
- No repository file changes expected.

**Interfaces:**
- Consumes: authenticated Fly.io and GitHub accounts, the committed container configuration, and repository `sandeepgangarapu/earnings-sankey-plot`.
- Produces: live app `sandeep-earnings-sankey`, a scoped deploy token stored as GitHub secret `FLY_API_TOKEN`, and a healthy `*.fly.dev` release.

- [ ] **Step 1: Authenticate and create the app if absent**

Run `flyctl auth whoami`. If authentication is absent, complete `flyctl auth login`. Check `flyctl status -a sandeep-earnings-sankey`; if the app does not exist, run `flyctl apps create sandeep-earnings-sankey`.

- [ ] **Step 2: Deploy the branch and verify Fly health**

Run `flyctl deploy --remote-only --ha=false`, then `flyctl status`, `flyctl checks list`, and `curl --fail https://sandeep-earnings-sankey.fly.dev/healthz`. Confirm exactly one Machine is configured.

- [ ] **Step 3: Install the scoped deploy token**

Create a deploy-scoped token for `sandeep-earnings-sankey` and pipe it directly into `gh secret set FLY_API_TOKEN --repo sandeepgangarapu/earnings-sankey-plot` so the token is never written to the repository or printed in logs. Confirm only the secret name with `gh secret list`.

### Task 5: Custom hostname, TLS, and public verification

**Files:**
- No repository file changes expected.

**Interfaces:**
- Consumes: the live Fly application and authenticated control of DNS for `sandeepgangarapu.com`.
- Produces: a healthy Fly certificate and public DNS for `earnings.sandeepgangarapu.com`.

- [ ] **Step 1: Request the custom-domain certificate**

Run `flyctl certs add earnings.sandeepgangarapu.com -a sandeep-earnings-sankey`, then inspect `flyctl certs show` to obtain the exact DNS target and ownership verification records.

- [ ] **Step 2: Add the required DNS records**

Use the domain provider that serves the current Google Domains nameservers to add the exact Fly-provided CNAME/A/AAAA and ownership record combination. Do not alter apex or `www` records used by the Hugo site.

- [ ] **Step 3: Wait for DNS and certificate readiness**

Check public resolution with `dig` and Fly status with `flyctl certs check earnings.sandeepgangarapu.com -a sandeep-earnings-sankey` until the certificate is issued.

- [ ] **Step 4: Verify the public service and cold-start configuration**

Run:

```bash
curl --fail https://earnings.sandeepgangarapu.com/healthz
curl --fail https://earnings.sandeepgangarapu.com/api/sample > /tmp/earnings-sankey-public-sample.json
flyctl status -a sandeep-earnings-sankey
flyctl logs -a sandeep-earnings-sankey
```

Confirm valid HTTPS, sample payload fields, zero-minimum autostart/autostop configuration, and no request-body or SEC identity data in logs.

### Task 6: Final branch verification

**Files:**
- Verify all files changed by Tasks 1-3.

**Interfaces:**
- Consumes: the complete branch and live service.
- Produces: evidence that code, container, configuration, automation, and public endpoint meet the approved design.

- [ ] **Step 1: Run all local checks from a clean state**

Run the Python suite, Node suite, offline CLI smoke test, Docker build, container health/sample checks, `flyctl config validate`, `git diff --check`, and `git status --short`.

- [ ] **Step 2: Review commits and changed-file scope**

Run `git log --oneline main..HEAD` and `git diff --stat main...HEAD`. Confirm the branch contains only the request-pacing safeguard, deployment artifacts, automation, and documentation.

- [ ] **Step 3: Run final public checks**

Verify the Fly hostname and custom hostname over HTTPS, the sample API, Fly health checks, Machine count, and certificate status. Record any unavoidable authentication or DNS propagation blocker precisely instead of claiming completion.
