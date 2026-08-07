# Fly.io Subdomain Hosting Design

## Goal

Publish the existing Earnings Sankey web application at
`https://earnings.sandeepgangarapu.com`. The deployment must retain live SEC
data generation, use the same Fly.io hosting pattern as the existing PDF Genie
subdomain, and stop when idle to minimize recurring compute charges.

## Scope

This change covers containerizing the current application, configuring a
single Fly Machine, deploying it from GitHub Actions, connecting the custom
subdomain, and verifying the public application. It does not redesign the
interface, add persistent storage, or change the Hugo site at
`sandeepgangarapu.com`.

## Architecture

The browser connects over HTTPS to `earnings.sandeepgangarapu.com`. DNS routes
the subdomain to Fly.io, where Fly Proxy terminates TLS and starts the Machine
if it is stopped. The container runs `earnings-sankey-server` on
`0.0.0.0:8080`; that process serves both the static browser assets and the JSON
API. Live generation requests fetch Company Facts from the SEC, normalize the
filing data, and return the rendered SVG and normalized statement JSON.

The deployment uses one `shared-cpu-1x` Machine with 512 MB of memory in the
San Jose region. `auto_stop_machines` is set to `"stop"`,
`auto_start_machines` is enabled, and `min_machines_running` is zero. There is
no volume or database. The existing in-memory SEC cache is intentionally
ephemeral and is rebuilt after a cold start.

## Repository Changes

- Add a production Dockerfile based on Python 3.12 slim and install the locked
  project with `uv`.
- Add `.dockerignore` rules so local environments, caches, Git metadata, test
  output, and unrelated generated artifacts are excluded from the image.
- Add `fly.toml` for the Fly app, region, internal port, HTTPS redirect,
  scale-to-zero behavior, resource size, concurrency limits, and `/healthz`
  health check.
- Add a GitHub Actions workflow that deploys pushes to `main` with a scoped
  `FLY_API_TOKEN` repository secret.
- Update the README with the public URL and concise deployment notes.

## Public-Endpoint Safeguards

The application continues to require each user to provide an SEC-compliant
identity containing a contact email. Request bodies and that identity remain
excluded from application logs.

Before publishing, SEC request pacing will be made process-wide rather than
per `SECClient` instance. This prevents concurrent public requests from
bypassing the intended interval between outbound SEC calls. The existing
30-second upstream timeout and one-megabyte inbound request limit remain in
place. Fly Proxy concurrency limits protect the small Machine from excessive
simultaneous work without adding a database-backed rate-limiting system.

## Deployment and Domain Setup

The Fly app will be created in the account that already hosts PDF Genie. The
initial deployment will use the generated `*.fly.dev` address. After its health
check passes, Fly will provision a certificate for
`earnings.sandeepgangarapu.com` and provide the required DNS target or
ownership records. The corresponding subdomain record will be added through
the domain's current DNS provider. DNS and certificate status must both be
healthy before the custom URL is treated as live.

Future deployments run from GitHub Actions on successful pushes to `main`.
The Fly deploy token is stored only as a GitHub Actions secret and is not
written to the repository.

## Failure Handling

- Fly Proxy returns a temporary platform error if a Machine cannot cold-start;
  no state is lost because the service is stateless.
- `/healthz` confirms that the process is accepting requests without depending
  on SEC availability.
- SEC timeouts and upstream errors continue to return user-facing JSON errors
  from the application.
- A failed GitHub Actions deployment leaves the previous Fly release available
  and exposes the failure in the workflow logs.
- DNS or TLS provisioning failures are diagnosed independently using Fly
  certificate status and public DNS lookups.

## Verification

Automated verification will include the existing Python and Node test suites,
new tests for process-wide SEC pacing, a production container build, and a
local container health check. After deployment, verification will cover the
Fly health check, the sample response, a live SEC generation request, HTTPS at
the custom domain, cold-start behavior after idle shutdown, and the absence of
request identity data in logs.

## Success Criteria

- `https://earnings.sandeepgangarapu.com` serves the Earnings Sankey interface
  with a valid certificate.
- The bundled example and a live SEC-backed chart both work from the public
  site.
- The only Machine stops after idle time and automatically starts on the next
  visit.
- Deployments from `main` are reproducible through GitHub Actions.
- Existing tests remain green and the public service respects process-wide SEC
  request pacing.
