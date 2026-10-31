# Foundry MCP operations

For the unreleased Auth0 alternative, use the separate
[OAuth runbook and cutover/rollback procedure](oauth-auth0.md),
[ChatGPT setup](oauth-chatgpt.md) and [verification gates](oauth-verification.md).
Select exactly one MCP authentication mode per instance. The Basic deployment
below stays independently usable; do not merge its environment into OAuth.

This guide deploys the bridge independently of your Foundry installation.
The production deployment example requires MCP HTTP Basic Auth and separate
browser WebSocket authentication. It does not configure Foundry hosting, TLS, a
reverse proxy, or public exposure. Development execution remains a separate,
loopback-only authenticated capability and is disabled in the production example.

## Architecture and prerequisites

There are two independent clients:

1. The GM's **browser** opens `/ws/foundry` at the URL saved in module settings.
   This connection does not originate in the Foundry server container.
2. LibreChat opens `/mcp/mcp` from its container. It must be able to route to the
   bridge's LAN endpoint independently of the GM browser.

`localhost` refers to the calling machine or container. Docker service names do
not normally resolve in the GM browser. An HTTPS Foundry page needs a
browser-compatible, trusted `wss://` endpoint for a remote bridge. This service
provides plain HTTP/WS; an appropriate existing TLS endpoint is an operator
prerequisite when needed. Do not disable browser security to work around this.

The service holds no persistent world state. The connected browser is
authoritative. Exactly one GM bridge is admitted; a second socket is rejected
with close code 1008. The connection limit applies after browser authentication. Use one world and one owning GM tab per bridge deployment.

Required: Docker Engine with Compose v2, a `linux/amd64` deployment host,
Docker Hub connectivity, a separately managed compatible Foundry installation,
and a GM browser. The operator decides host addressing and LAN access policy.

## Production authentication and migration from 1.1

Deploy server and module 2.4.0 together. Source execution defaults to
`FOUNDRY_MCP_AUTH_MODE=none` for backward compatibility; production Compose
explicitly selects `basic`. Supplying production credentials with mode `none`
fails startup rather than silently exposing the service. Production Basic Auth
and development execution cannot be enabled together.

Set `FOUNDRY_MCP_BASIC_USERNAME`, `FOUNDRY_MCP_BASIC_PASSWORD`, and
`FOUNDRY_MCP_BRIDGE_TOKEN` in the private deployment environment. The username
must be nonempty without a colon (the Basic Auth separator). Password and bridge
token must be nonempty; length, character-strength and distinctness policies
are left to the operator. Optional credential generation: `python -c 'import secrets; print(secrets.token_urlsafe(32))'`.
Use a private `.env` with mode 0600; never put real credentials in tracked files.
All `/mcp` HTTP methods, including initialization, discovery and session cleanup,
require Basic Auth. Rejected requests return 401 with a Basic challenge.
`/health` stays public for liveness and reports connected clients; it is not
proof of an authenticated end-to-end connection.

LibreChat supports static Authorization headers for streamable HTTP. Store
`FOUNDRY_MCP_BASIC_AUTH` in its private environment as Base64 of the literal
`username:password` bytes (not a shell expression or an already prefixed header).
Base64 is not encryption. Ensure the value is available to the API container;
recreate only `api` when changing its Compose-provided environment. Set
`requiresOAuth: false` and the header shown below. Check startup logs privately:
LibreChat versions may print expanded configuration, including custom headers;
never publish those logs. Use HTTPS for any connection crossing an untrusted
network. The current same-host LAN HTTP route remains operator-managed.

Before upgrading the module, record the intended old client-scoped URL and
settings privately. All module settings now use **world scope**, including
`bridgeUrl`, `developmentExecution`, the hidden development `browserToken`,
`productionAuthentication`, and `bridgeCredential`. There is no automatic
promotion of an arbitrary browser's settings to shared world configuration.
After updating, enter the URL, enable production authentication, enter the
server bridge token, and leave development execution off. Save once for the
world. World settings restrict editing but are not treated as a confidential
GM-only secret store; connected players may be able to obtain the browser
credential. The MCP password is never entered into Foundry.

A remote credential-bearing browser connection requires browser-trusted WSS.
The reverse proxy terminates TLS and forwards WebSockets to the service;
proxy/DNS/certificate configuration is outside this repository change.
Do not add proxy Basic Auth to the WebSocket route: browser JavaScript cannot
supply an Authorization header there. Python validates the first message
`{"type":"auth","token":"<bridge token>"}` within five seconds (4 KiB maximum).
Only an admitted GM receives `{"type":"auth","status":"ok"}` before game RPCs.
Authentication failures/duplicates close with 1008; oversized authentication
messages close with 1009. The module waits for acknowledgment before reporting
Connected. Rejection or acknowledgment timeout requires correcting settings
and saving to reconnect; ordinary network failures retain backoff retries.

For rotation, generate both new credentials, update the server environment,
recreate the bridge, update LibreChat's private header and recreate only its
API as needed, then update the Foundry world's bridge credential. Existing
MCP sessions must reconnect. Keep the same host port and preserve Foundry data.
Rollback requires restoring the previous image, module and private deployment
configuration together; 1.1 has no production authentication and must not be
left exposed through an internet-facing proxy.

## Runtime configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `FOUNDRY_MCP_HOST` | `127.0.0.1` in source; `0.0.0.0` in image | Uvicorn bind hostname/IP. |
| `FOUNDRY_MCP_PORT` | `8000` | Integer port, 1–65535. Protocol paths stay fixed. |
| `FOUNDRY_MCP_AUTH_MODE` | `none` in source; `basic` in production Compose | Protect MCP and browser bridge in production. |
| `FOUNDRY_MCP_BASIC_USERNAME` | empty | Production MCP username without colons. |
| `FOUNDRY_MCP_BASIC_PASSWORD` | empty | Nonempty production MCP password. |
| `FOUNDRY_MCP_BRIDGE_TOKEN` | empty | Nonempty production browser credential. |
| `FOUNDRY_MCP_DEV_EXECUTION` | `false` | Exposes the development tool only when explicitly enabled with credentials. |
| `FOUNDRY_MCP_CALLER_TOKEN` | empty | Nonempty development MCP bearer credential. |
| `FOUNDRY_MCP_BROWSER_TOKEN` | empty | Nonempty development browser credential. |
| `FOUNDRY_MCP_EXECUTION_TIMEOUT` | `15` | Development execution timeout, finite and greater than zero, at most 120 seconds. |
| `FOUNDRY_MCP_TRACE_PATH` | unset | Optional private evaluation log; leave unset for ordinary production operation. |

Bind variables configure `python -m foundry_mcp_server.main` (including the
foreground launcher and container). The managed development user service keeps
its explicit loopback port 8000 so the repository launchers and health probes
remain stable; do not use it as the production deployment mechanism.

Forwarded headers are not trusted by the normal Python entrypoint. Development
mode rejects non-loopback peers even with correct credentials. Do not expose it
through a forwarding arrangement that makes remote peers appear local.
See [development execution](js-exploration.md) for its separate setup.

Normal RPC defaults to 10 seconds; player-name requests use 5 seconds.
WebSocket responses are limited to 65,536 UTF-8 bytes; journal responses have
their own 48,000-byte bound and continuation contract. See [journal tools](journal-tools.md).
`/health` returns `status` and `foundry_clients`; an empty client list is healthy
server liveness, not end-to-end world readiness.

## Local source and container checks

Reuse the root Compose instance for active Foundry development. Preserve the
existing v13 packaging fixture and its configured world; exploratory Foundry
packaging testing is needed only after significant Compose changes. Routine
code changes, rebuilds, and version bumps use automated checks without another
Foundry setup. Follow AGENTS.md before provisioning or resetting any instance.


Provision dependencies once, then run the offline suites:

```bash
uv sync --locked
./scripts/test.sh
```

For source execution use `./scripts/start-server.sh`, or the managed service
commands in README. Source and container execution do not enable the reloader.
For deliberate source development only:

```bash
uv run --locked python -m uvicorn foundry_mcp_server.main:app --host 127.0.0.1 --port 8000 --reload --no-proxy-headers
```

Build and test an isolated container on loopback port 18000:

```bash
docker compose -p foundry-mcp-smoke -f deploy/compose.local.yaml up -d --build --wait --wait-timeout 90
docker compose -p foundry-mcp-smoke -f deploy/compose.local.yaml run --rm --no-deps -T smoke
docker compose -p foundry-mcp-smoke -f deploy/compose.local.yaml stop
docker compose -p foundry-mcp-smoke -f deploy/compose.local.yaml ps -a
docker compose -p foundry-mcp-smoke -f deploy/compose.local.yaml down
```

The smoke client uses a synthetic browser, checks protocol initialization,
discovery/schema presence, no-GM errors, an RPC round trip, duplicate rejection,
pending-call disconnect, and reconnect. Run it only against an isolated empty
service, never a gaming bridge. Its checks validate transport, not Foundry API
compatibility. A browser GET error on `/mcp/mcp` is not an MCP protocol test.

The image runs as UID/GID 10001, installs Python 3.12 locked dependencies with
uv, and has a standard-library Python healthcheck. Dockerfile pins base image
and uv digests. Review and deliberately update those pins for maintenance.
No repository mount, source tree, systemd process, or persistent volume is
needed by the production image. Inspect the [verification record](operationalization-verification.md)
for actual tests and remaining gates.

## GitHub Actions setup and Docker Hub publication

In repository **Settings → Secrets and variables → Actions**, configure:

| Name | Type | Value |
| --- | --- | --- |
| `DOCKERHUB_USERNAME` | Secret | Docker Hub account with push access to `sesopenko/foundry-mcp`. |
| `DOCKERHUB_TOKEN` | Secret | Docker Hub access token with Read/Write permission. |
| `PUSH_IMAGE_ENABLED` | Variable | Set to `true` to enable publishing; absent/other values leave it disabled. |

The workflow logs in to `docker.io` and publishes to the public repository
[sesopenko/foundry-mcp](https://hub.docker.com/r/sesopenko/foundry-mcp).
The old `REGISTRY_HOST`, `SECRET_REGISTRY_USERNAME`, and
`SECRET_REGISTRY_PASSWORD` secrets are no longer used by this workflow.
Environment-scoped secrets require the publication job's environment to be
configured; repository secrets work with the supplied workflow.

CI runs tests, packages module assets, builds the image, exercises an isolated
container, and checks graceful shutdown. Trusted main/tag pushes may then publish:

- `sesopenko/foundry-mcp:sha-<full-commit>`.
- `sesopenko/foundry-mcp:v2.4.0` for matching release tags.
- `sesopenko/foundry-mcp:latest` updated alongside each published version tag; main-branch pushes publish only commit tags.

Pull requests do not publish. Docker Hub login must succeed before publication.
Existing commit images are preserved on reruns. Versioned release image
replacement is refused; increment versions instead of moving tags. Failed
verification prevents publication. Image and module publication are independent
jobs, so inspect both outcomes after a release; one can succeed while the other fails.

Build summaries, build-record uploads, provenance, and SBOM publication remain
disabled. Credentials and private deployment configuration must never be
included in image layers, logs, module artifacts, or release notes.

No build agent action changes repository visibility, configures secrets, pushes
commits/tags, or publishes assets automatically. Once ready, the human runs the
publication workflow by pushing the reviewed commit/tag.

## Module versioning and releases

The Python package, runtime application metadata, and module share version
`2.4.0`. Release tags are `vX.Y.Z`. For each release, update those versions,
`uv.lock`, both source build identities, module `download`, and the local Compose build-version argument
consistently. Run tests and package:

```bash
.venv/bin/python scripts/package-module.py --tag v2.4.0
```

Outputs under ignored `dist/module/` are `module.json` and `foundry-mcp.zip`.
The ZIP has `module.json` at its root and all module JavaScript assets, without
the containing `foundry-module/` directory. Packaging validates versions,
metadata, entrypoints, local imports, archive paths, and symlink exclusions.
Runtime JavaScript uses an explicit file allowlist; update it deliberately when adding assets.

Stable installation/update manifest:

```text
https://github.com/sesopenko/foundry-mcp/releases/latest/download/module.json
```

The manifest's `download` points to the matching version-specific ZIP:

```text
https://github.com/sesopenko/foundry-mcp/releases/download/v2.4.0/foundry-mcp.zip
```

The operator must make the repository/releases publicly accessible before
unauthenticated Foundry installation works. The module release job is skipped
while the repository is private. The agent does not change visibility.
Direct Manifest URL installation does not require Foundry package-directory registration.

On a matching tag push, CI publishes module assets only after verification and
refuses to replace an existing GitHub release. It checks anonymous versioned
downloads and the stable latest manifest against the generated artifacts. The
human must also verify those URLs from the installation environment.
Do not republish the same version with changed contents or move release tags.

## Deploy the bridge on the LAN — human operated

Use a maintenance window. Keep the preceding known-good image tag/digest and
module ZIP. This step deploys only the new MCP service and requires no Foundry
server restart.

1. Copy `deploy/compose.yaml` and `deploy/.env.example` to a new bridge deployment
   directory. Rename the latter to `.env`, set private permissions, and replace
   the examples: `FOUNDRY_MCP_IMAGE` with a published `sesopenko/foundry-mcp` tag or digest,
   and `FOUNDRY_MCP_LAN_ADDRESS` with the host's intended LAN interface address. Fill both production credentials and set the MCP username.
2. Public Docker Hub pulls require no login. If authenticating for pull limits,
   use `docker login` interactively or `--password-stdin`.
3. Validate privately with `docker compose --env-file .env -f compose.yaml config --quiet`.
   Do not post interpolated configuration or credentials in issues/logs.
4. Run `docker compose --env-file .env -f compose.yaml pull`, then
   `docker compose --env-file .env -f compose.yaml up -d --wait --wait-timeout 90`.
5. Check `docker compose --env-file .env -f compose.yaml ps` and logs privately.
   Fetch `http://<LAN-host>:8000/health` from a relevant client. Expect an empty
   GM list until a browser connects.

The example publishes only on the selected LAN address, runs with
`restart: unless-stopped`, allows a 15-second graceful stop, and uses private named volumes for optional
PDF source and index state, without source-code mounts. There are no Traefik labels or automatic updates.
Confirm the LAN address belongs to the host and container clients can route to it.

## Install and configure the module — human operated

Before changing the separately managed Foundry installation, back up its data,
record the running core build and current module version/settings, and confirm
the package directory is not a source bind mount. Do not upgrade/downgrade the
Foundry core as part of this bridge deployment.

1. Foundry **Setup → Add-on Modules → Install Module → Manifest URL**: paste
   the stable public URL above and install.
2. Launch the desired world and enable **Foundry MCP Proxy** in **Manage Modules**.
3. In **Game Settings → Configure Settings → Foundry MCP Proxy**, enable production authentication, enter the separate browser bridge credential, and set the full
   browser-reachable URL, for example `ws://mcp-host.example:8000/ws/foundry`.
   This setting is world-scoped: configure it once for the intended world.
4. Leave local development execution disabled. Saving connection settings
   reconnects without reloading the page. On first installing new module code,
   reload the browser normally so it loads the new scripts.
5. Observe Connecting/Connected notifications and confirm `/health` lists `gm`.
   A WebSocket can briefly open before duplicate/auth rejection; validate an
   actual MCP read before treating it as usable. Close competing GM tabs.

Invalid URLs produce Misconfigured feedback rather than an initialization
exception. Connection loss retries with backoff from 1 to 30 seconds. Status
notifications are deduplicated per browser load; console messages and health
remain useful for ongoing diagnosis.

Manual fallback: extract ZIP contents into the operator's persistent
`Data/modules/foundry-mcp/` directory with correct ownership, with no extra
nested directory. Follow the managed Foundry installation's restart/discovery
procedure. Preserve data/settings and use manifest installation where possible.

## Replace the LibreChat development endpoint — human operated

Edit the existing `foundry-vtt` entry rather than adding a duplicate:

```yaml
mcpServers:
  foundry-vtt:
    type: streamable-http
    url: http://mcp-host.example:8000/mcp/mcp
    timeout: 30000
    serverInstructions: true
    requiresOAuth: false
    headers:
      Authorization: "Basic ${FOUNDRY_MCP_BASIC_AUTH}"
```

Use a LAN hostname/IP reachable **inside LibreChat's container**. Add the new
host to `mcpSettings.allowedDomains` only as required; remove the obsolete
endpoint when appropriate. Apply configuration using the installed LibreChat
version's documented restart/recreate procedure. Do not recreate unrelated services.

Test health and actual MCP initialize/discovery/calls from within LibreChat's
network context, then verify tools appear in its UI and a read returns the
intended world's data. A host-only health check or browser WebSocket connection
does not establish LibreChat reachability. A same-network service name is an
optional operator-managed alternative only if network membership is deliberately configured.

## Diagnose server/module version mismatches

Call the read-only `get_bridge_versions` tool with no arguments. It reports
packaged server identity even without a GM, then queries the loaded browser
module when connected. Two tagged releases are compared exactly; source,
untagged and unknown identities are explicitly unverified. Legacy modules
without this RPC report unsupported and need an update/reload.

Foundry also warns automatically about tagged mismatches, showing both versions
and the older component to update. Normal tools keep working. The tool reports
running artifacts, not the newest release online. See [version diagnostics](bridge-version-diagnostics.md)
for response fields, unavailable states, metadata provenance and control messages.

## Troubleshooting

| Symptom | Meaning and recovery |
| --- | --- |
| Health unavailable | Check service status, LAN bind, published port, and routing. |
| Health OK, `foundry_clients: []` | Server is live but no GM bridge owns the socket. Check enabled module, browser settings, GM login, URL, and transport. |
| Misconfigured | Correct the complete URL or development prerequisites; save again. |
| HTTPS page rejects `ws://` | Supply a browser-trusted WSS endpoint through independently managed infrastructure. |
| Close code 1008 | Another GM owns the bridge, or development credentials/peer restrictions rejected it. |
| Disconnected/retrying | Check server availability and certificate/routing conditions. Backoff is capped at 30 seconds. |
| MCP HTTP 400 after restart | Client session is stale; reconnect the MCP client. |
| HTTP 401 / `UnauthorizedExecution` | In production check the Basic Auth header and server credentials; in development check Bearer credentials, loopback access and execution opt-in. |
| RPC timeout/disconnect | Browser was unavailable or failed during the request. Check console and retry read-only work after recovery. |
| Tool-specific error | Read the tool's contract; distinguish missing content, unsupported content, and partial results from transport failure. |

Development Chrome and native MCP tools require launching a fresh session with
`./scripts/codex-dev.sh` when absent or stale. Use only its dedicated test-world
profile. The normal launcher is `./scripts/codex.sh`. See [browser development](browser-development.md).

## Upgrade, rollback, and session acceptance

Container and module updates are separate operations even though release
versions are synchronized. Deploy the tested pair. Container upgrade: change
the private pinned image reference, pull, recreate only the bridge, and verify
health plus browser reconnect. Module upgrade: Foundry Setup package
**Check Update/Update** follows the stable manifest and version-specific ZIP;
reload the GM browser and verify tools. Never assume future core compatibility.

Rollback: restore the prior image tag/digest in private configuration, pull and
recreate the bridge; install the prior module ZIP/manifest using Foundry's
supported package workflow or the manual fallback. The UI may not directly
offer downgrade. Restore the intended world settings if necessary. Restore world data
only if an independently required data change warrants it; this bridge stores
no world database. Keep backups and verify the intended world before resuming play.

Human pre-session acceptance:

- [ ] Record core build, module/server version pair, pinned image, and backup location privately.
- [ ] Confirm module enabled, development execution off, intended GM browser connected, and no competing GM tab.
- [ ] Confirm service health and zero trace-write failures if recording was deliberately enabled.
- [ ] Confirm LibreChat discovers tools and reads the intended world's data.
- [ ] Test no-GM error, browser reconnect, server restart, module update, and rollback in a maintenance window.
- [ ] Confirm no developer workstation process or source mount is required.
- [ ] Inspect first CI publication logs/artifacts for private hostname leakage.
- [ ] Record registry pull and anonymous public-manifest/ZIP checks; sign off the first gaming session.

## Privacy and compatibility records

Sensitive operator context is in ignored `.local/operationalization-context.md`.
It is intentionally unavailable to public clones. Git name/email attribution
is retained. The Docker context and module archive use allowlists independent
of Git ignore rules. Never attach ignored reference configurations, browser
profiles, environment files, or traces to a public release or issue.

See [verification](operationalization-verification.md) for live version evidence,
privacy/history cleanup results, and operator gates not executed by the build agent.
Official references: [module development](https://foundryvtt.com/article/module-development/),
[module installation](https://foundryvtt.com/article/modules/),
[package management](https://foundryvtt.com/article/package-management/),
[v13 settings](https://foundryvtt.com/api/v13/classes/foundry.helpers.ClientSettings.html),
and [v13 notifications](https://foundryvtt.com/api/v13/classes/foundry.applications.ui.Notifications.html).

## Private PDF references

An opt-in GM-private PDF library provides lexical lookup and source-page reading,
plus acknowledged uploads through the existing Foundry bridge. See
[PDF library setup, access policy and recovery](pdf-library.md).
Do not share a PDF-enabled endpoint's MCP credentials with players.

The browser PDF manager also supports confirmed deletion of ready/failed PDFs.
Uploading the same filename or identical bytes replaces the existing PDF after
successful reprocessing; the old version remains searchable if the new job fails.
Keep an original or backup when explicitly deleting a book. See the PDF guide
for processing-job restrictions and interrupted-cleanup recovery.
