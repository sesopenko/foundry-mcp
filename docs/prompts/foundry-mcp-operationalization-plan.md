# Foundry MCP — Operationalization Iteration Plan

**Status:** Implementation contract; repository implementation is underway. Production deployment remains human-operated.  
**Priority:** Operational readiness before additional MCP features.  
**Target:** Local developer machine → private image registry → deployment host Docker host → gaming Foundry VTT world → LibreChat.  
**Default scope:** Foundry VTT v13 gaming deployment; validate v14 separately rather than assuming compatibility.

## Agreed decisions (supersede conflicting original recommendations)

- Production MCP and WebSocket endpoints use the trusted LAN without authentication or Traefik routing. Preserve development-only authentication and loopback restrictions.
- Gaming Foundry is separately managed: do not access, restart, reconfigure, upgrade, or test it. Configure only this module's browser URL and document transport requirements.
- Synchronize server/module versions at 1.1.0. Prepare releases in this repository; the operator controls public visibility and publication.
- Registry hostname is GitHub Actions secret `REGISTRY_HOST`; credentials are `SECRET_REGISTRY_USERNAME` and `SECRET_REGISTRY_PASSWORD`. `PUSH_IMAGE_ENABLED` is a variable, disabled by default. Do not disclose image references in public build artifacts or summaries.
- Sensitive addresses, host details, and reference repository locations are in [ignored local context](../../.local/operationalization-context.md). Public examples use placeholders. `.local/` and reference clones must also be excluded from Docker and ZIP artifacts.
- Reference clones are under ignored `.cache/reference-repos/`; use them read-only. Never print their sensitive configurations.
- Sanitize this document in its unpublished introducing commit, preserve unrelated changes, expire obsolete local history copies, and verify no sensitive original remains reachable. Do not rewrite or push origin.
- Keep `bridgeUrl` client-scoped, preserve existing values, and reconnect on settings changes. Validate complete ws/wss URLs and expose bounded status feedback through public APIs.
- Production Compose requires a pinned `FOUNDRY_MCP_IMAGE` and deliberate LAN bind address. No Foundry/source mounts, proxy labels, or persistence by default.
- Local baseline and focused tests precede changes; run both suites before commits. Validate actual MCP discovery and a disposable development browser separately from mocks.
- Deliver image/module packaging, CI, complete setup/update/rollback instructions, and a verification record distinguishing local evidence from pending human acceptance. Do not publish or deploy automatically.

## 1. Mission and boundaries

Make the existing `sesopenko/foundry-mcp` usable during real gaming sessions without a managed development workspace. Package the Python/FastAPI/FastMCP/WebSocket service as a reproducible image; publish it through existing private-registry CI; supply Compose and operator instructions; configure the Foundry browser module using Foundry's supported settings UI; and distribute/update that module using a manifest and versioned releases.

**Do not add game features, PDF RAG, LangChain, or new infrastructure in this iteration.** Preserve the existing MCP tool contracts and `/mcp/mcp`, `/ws/foundry` paths unless a documented compatibility migration is essential. Do not alter the deployment host infrastructure, `reference deployment repository`, live Foundry stack, or LibreChat automatically. The build agent may modify **only the `foundry-mcp` working copy** for its implementation. External repos are references, not targets. Real gaming-world install/verification is a **human-executed acceptance stage**.

## 2. Verified baseline and source references

| Source | Observed state / consequence |
|---|---|
| `foundry-mcp/README.md` | Python 3.12; `uv sync --locked`; FastAPI + FastMCP; service currently port 8000, browser WebSocket `/ws/foundry`, MCP Streamable HTTP `/mcp/mcp`; unit test scripts; developer-only JavaScript exploration security gates. |
| `foundry-mcp/pyproject.toml` | `fastapi==0.128.0`, `fastmcp==2.14.1`, `uvicorn==0.40.0`; Python `>=3.12,<3.13`, `package=false`; `uv.lock` present. Avoid copying an unrelated Python 3.13 Dockerfile verbatim. |
| `foundry-mcp/foundry-module/scripts/main.js` | Already registers `bridgeUrl` in visible Foundry settings, default `ws://localhost:8000/ws/foundry`, `scope: client`; `developmentExecution` visible; `browserToken` currently `config:false`. Existing functionality should be corrected/refined, not implemented from scratch. |
| `foundry-mcp/foundry-module/scripts/foundryBridge.js` | Runtime reads `game.settings.get('foundry-mcp','bridgeUrl')`, connects on GM `ready`, reconnects with capped exponential backoff; optional browser token is sent as first WebSocket message. Development execution enforces loopback URL plus credentials. Preserve these security properties. |
| `foundry-mcp/foundry-module/module.json` | Module `id: foundry-mcp`; version `1.0.0`, `compatibility.minimum: 13`, `verified: 14`; **no manifest or download URL**. Current build is not yet remotely installable/updateable. Reassess compatibility claims. |
| `foundry-mcp/docker-compose.yml` | Development `felddy/foundryvtt:release` mounts `./foundry-module` to `/data/Data/modules/foundry-mcp:ro`; do NOT carry this source bind mount into the gaming installation. |
| `reference deployment repository/foundry/docker-compose.yml` | Gaming Foundry is also `felddy/foundryvtt:release`, persistent `./data:/data`, user `operator-selected UID:GID`, `FOUNDRY_VERSION=operator-confirmed v13 build` **in the checked-in file**. Confirm the running server version before acting. Existing file contains sensitive configuration; do not copy credentials into docs or issues. |
| `reference deployment repository/LibreChat/librechat.yaml` | Already contains `foundry-vtt` Streamable HTTP entry to a **development-host** IP on `:8000/mcp/mcp`. Needs a conscious cutover to new reachable endpoint, not a second duplicate entry. Has `mcpSettings.allowedDomains`; inspect and adjust only as required. |
| `reference deployment repository/LibreChat/docker-compose.override.yml` | LibreChat uses shared external `operator-selected Docker network`; a same-network service name may be the simplest endpoint, otherwise an explicit LAN hostname/Traefik route. Confirm network membership, not guess. |
| `reference CI project/.github/workflows/ci.yml` | Relevant private-registry workflow: CI gate → conditional image push (`vars.PUSH_IMAGE_ENABLED`) → TLS preflight → `docker/login-action@v3` with `SECRET_REGISTRY_USERNAME` and `SECRET_REGISTRY_PASSWORD` → Buildx → `docker/build-push-action@v7`; pushes `REGISTRY_HOST_PLACEHOLDER/sesopenko/reference CI project` `latest` and commit SHA. Reuse pattern, **not application dependencies**. |
| `reference container project/Dockerfile` | Shows uv-based FastMCP Docker image pattern; uses Python 3.13 and packaged project, unlike this project. Adapt thoughtfully. |
| Supplied `deployment-host-docker-host-deployment-context.md` | Debian 12, `linux/amd64`, Compose stacks, current Traefik on deployment host, private registry, no default auto-updates, controlled upgrades; host paths/network names/registry auth must be verified in target environment. |

**Source links:**
- https://github.com/sesopenko/foundry-mcp
- [private reference: see local context]
- [private reference: see local context]
- [private reference: see local context]
- [private reference: see local context]
- [private reference: see local context]

**Mandatory pre-implementation audit:** read the current complete source of `foundry_mcp_server/`, `foundry-module/scripts/`, security/auth docs (`docs/js-exploration.md`), tests, startup scripts and `.env.example`; grep for `localhost`, `127.0.0.1`, `0.0.0.0`, `8000`, fixed WebSocket paths, `ws://`, development hostnames/IPs, CORS/origin checks, tokens, and logging of secrets. Current source findings above do not imply all hardcoded values have been found.

## 3. Recommended architecture

```text
  Gaming user's GM browser, viewing Foundry over HTTPS
         | WSS outbound from browser, URL set in Foundry module settings
         v
  [Traefik HTTPS/WSS route OR trusted LAN endpoint]
         |
  [foundry-mcp container]  FastAPI/Uvicorn
         |-- /ws/foundry     (Foundry GM browser connection)
         |-- /mcp/mcp       (Streamable HTTP MCP for LibreChat/Codex)
         `-- health endpoint (use existing exact endpoint)
         ^
         | HTTP through Docker network / LAN / reverse proxy
  [LibreChat container] or other authenticated MCP client

  [felddy/foundryvtt gaming container]
         ^  browser loads installed module from persistent /data
         |  module installed via Foundry manifest URL
  [GitHub release: module.json + version-pinned module ZIP]

  [GitHub Actions] --> [private registry image]
                       --> [deployment host docker compose pull/up]
```

**Crucial networking fact:** The WebSocket originates in the **user's GM web browser**, not the Foundry container. `localhost` resolves to the machine running that browser; Docker service DNS names are not resolvable there. The browser must reach the WebSocket server, and if the Foundry page is HTTPS, a `ws://` endpoint can be blocked as mixed active content. For remote player/GM browsers prefer `wss://` via existing Traefik TLS; allow LAN `ws://` only when appropriate and tested. Traefik must forward WebSocket upgrades. Streamable HTTP clients and browsers may require different publicly resolvable / internal URLs for the *same* service.

**Security boundary:** A remote MCP server accepting Foundry browser connections and MCP tool calls potentially grants access to sensitive world content and privileged GM operations. Production mode must not expose unauthenticated world access to the internet. Review binding, auth, authorization, origin handling, session isolation, request timeouts, rate limits and development JavaScript execution separately. Do not treat browser opt-in/GM checks as MCP-client authentication. Design a practical access policy for private LAN/Docker network, and stronger protection if a public HTTPS route is needed. Never log credentials. Keep `execute_javascript` disabled by default and maintain its loopback/developer restrictions; do not weaken them merely to make a remote deployment work.

## 4. Work packages — ordered, test-gated

### Phase 0 — Audit, decisions, compatibility matrix

- [ ] Inspect all server entrypoints and actual `uvicorn`/FastMCP mount configuration. Document verified bind host, port, health endpoint, request/response lifetime and shutdown behavior; include WebSocket lifecycle and active-GM selection semantics.
- [ ] Inventory environment-specific constants in Python, JS, tests, scripts, documentation and Codex configuration. Classify values as **server env**, **Foundry UI**, **protocol constant** or **dev-only**. Do not make internal protocol paths arbitrary settings without a use case.
- [ ] Record operational risk of multiple simultaneous GM clients: one bridge vs many browsers; startup without GM; reconnect on refresh; which session receives calls; stale sessions; no-GM errors. Define and test deterministic behavior or document supported limit clearly.
- [ ] Determine exact deployed Foundry core version; support v13 first, verify v14 separately. Do not label v14 verified solely because the existing manifest says so.
- [ ] Inspect existing auth mechanism. Define which endpoints remain private, whether any proxy auth is needed, and how browser token setup works. No hardcoded production token or disabled auth for convenience.

**Gate:** short architecture/config decision record and documented security/deployment assumptions.

### Phase 1 — Runtime configuration and Foundry module UX

- [ ] Preserve `game.settings.register` and add meaningful labels, hints, validation and user-facing status/error messages. `bridgeUrl` already exists; it should accept full `ws://` or `wss://` URL including host, port and `/ws/foundry`, avoiding separate IP/port fields that fail for domain/TLS/routing paths. Validate with `new URL()` and ensure valid scheme/host/path; handle invalid data gracefully without throwing during `ready`.
- [ ] Choose **world** scope for shared game endpoint if one URL fits all GM devices, versus **client** scope if GMs on different networks need distinct endpoints; offer an explicit override only if essential. Existing setting is client-scoped: migration must preserve manually configured values and avoid silent behavior changes. Use `game.settings.registerMenu` with ApplicationV2 only if advanced configuration/status needs it; native settings fields are simpler for basic URL/checkboxes.
- [ ] Make production/development settings clearly separate; preserve `developmentExecution` default `false` and no remote `execute_javascript` bypass. Reevaluate `browserToken` storage/UI: browser-side secrets are accessible to code in that browser; cannot be treated as hardened secret storage. Ensure it is not accidentally made globally readable via a world setting.
- [ ] Set explicit connection control semantics: `ready` only on authorized GM; clear status of Connected / Connecting / Disconnected / Misconfigured; reconnection with backoff and no runaway errors. On settings change, reconnect cleanly or request reload via supported `requiresReload` semantics rather than unconditionally reloading all windows.
- [ ] Python service: support configurable bind address and port via env (e.g., `FOUNDRY_MCP_HOST=0.0.0.0`, `FOUNDRY_MCP_PORT=8000`), safe defaults for local source runs, consistent validation and docs. Determine whether forwarded-header/trusted proxy settings are required; minimize exposed ports.
- [ ] Add JS and Python tests for URL parsing, bad configuration, change/reconnect, auth and successful RPC; keep existing tests passing.

**Gate:** module connects against local Docker endpoint without source changes for each environment; invalid URL gives actionable feedback.

### Phase 2 — Docker image, local build and smoke tests (before CI)

- [ ] Add project-specific `Dockerfile` and `.dockerignore`. Use an exact compatible Python 3.12 image; install locked dependencies using uv (`uv sync --locked` or tested equivalent), no development dependencies; account for `package=false` and module execution `python -m foundry_mcp_server.main`. Prefer a slim, non-root runtime and avoid copying venv from a mismatched OS/Python image. Pin tool/image versions where practical.
- [ ] Use `0.0.0.0` **inside** the container, not `127.0.0.1`, for ports exposed to Docker networks. Specify `linux/amd64` support. Define image metadata/version labeling and healthcheck using existing application endpoint, without requiring curl if image does not contain it.
- [ ] Add a minimal **standalone service Compose example** (`compose.yaml` or README snippet), `.env.example` (nonsecret), pinned image tag, `restart: unless-stopped`, sensible network, and optional loopback-only port publication for local testing. No persistent volume unless the service actually writes state; do not inherit the dev Foundry bind mount.
- [ ] Build locally: `docker build --platform linux/amd64 -t foundry-mcp:local .`; run the production container locally; verify health, logs and both endpoints. MCP Streamable HTTP should be tested with a protocol-aware client: an HTTP browser GET error does not prove broken MCP.
- [ ] Start the project's dev Foundry Compose stack and connect via settings to a reachable WebSocket URL. Test one GM, no GM, reload/reconnect, wrong URL, server restart, MCP tools and controlled shutdown. Confirm browser console does not show mixed-content or origin issues.
- [ ] Test `docker compose config`, image startup without dev bind mounts, graceful SIGTERM, restart policy, no credentials in image or logs, and all unit suites (`./scripts/test.sh`).

**Gate:** clean-clone Docker image is independently runnable and passes scripted + human-observed local end-to-end smoke tests.

### Phase 3 — GitHub Actions private-registry publication

- [ ] Follow `reference CI project/.github/workflows/ci.yml` structure: test gate; optional push controlled by `vars.PUSH_IMAGE_ENABLED` (or release/tag gate); registry TLS preflight; `docker/login-action@v3` using `SECRET_REGISTRY_USERNAME` and `SECRET_REGISTRY_PASSWORD`; Buildx; build/push action. Use least-privilege `permissions: contents: read` unless release asset upload needs `contents: write`.
- [ ] Image target: `REGISTRY_HOST_PLACEHOLDER/sesopenko/foundry-mcp`. Produce immutable `sha-<commit>` and optionally `vX.Y.Z` and moving `latest` tags; **production Compose pins release or SHA**, not latest. Add provenance/SBOM only if compatible with registry; inspect registry support first.
- [ ] Verify registry hostname, TLS trust, runner connectivity, credential permissions and private repo Actions access. Keep push off pull requests from forks; never expose registry credentials in CI logs. Separate Docker image publication from Foundry module publishing: distinct artifacts and possible release workflows.
- [ ] Publish image after successful local tests and pass CI `docker build` smoke test. Verify pull by digest/tag on a separate machine or sandbox before host deployment.

**Gate:** CI builds and pushes a versioned image; test pull works; failed tests cannot publish.

### Phase 4 — Foundry module manifest and GitHub Releases

- [ ] Decide distribution visibility: **recommended public repository only after security/secrets review**, or publish public module release assets from a separate public distribution repository while keeping source private. A private GitHub release URL is not generally usable as an unauthenticated Foundry manifest/download URL. Do not make source public automatically.
- [ ] Produce manifest fields `id`, `title`, `description`, `authors`, `version`, `compatibility`, `esmodules`, `url`, `manifest`, `download`. `id` must match `foundry-mcp` install directory. Remove misleading/unsupported metadata such as unverified compatibility or unused flags after inspection.
- [ ] Stable update manifest: `https://github.com/sesopenko/foundry-mcp/releases/latest/download/module.json` **only if repository/releases are public**. Release-specific zip: `https://github.com/sesopenko/foundry-mcp/releases/download/vX.Y.Z/foundry-mcp.zip`. The release asset `module.json` must carry a `download` URL pinned to its matching release, while its `manifest` points to the stable latest asset. Never point `download` to a mutable latest ZIP.
- [ ] CI release job must create a ZIP of **the contents of `foundry-module/`**, with `module.json` at ZIP root, and include every necessary JS asset; exclude development files, source maps containing secrets, other repo content and credentials. Validate manifest JSON; validate zip root paths; compare release tag against manifest version; test URLs unauthenticated over HTTPS with redirects.
- [ ] Initial versioning: current module manifest says `1.0.0` while Python package is `0.1.0`. Agree on independent vs synchronized version scheme and ensure each module release increments module manifest version. Do not silently republish same version with changed content.
- [ ] Test install/update on disposable **local** Foundry data before attempting gaming-world install. Publish as GitHub release assets; no Foundry package-directory registration is required for direct Manifest URL installation. Official module listing can be a later optional phase.

**Gate:** manifest and version-specific ZIP are anonymously retrievable; fresh installation and higher-version update succeed in local Foundry.

### Phase 5 — Compose and LibreChat integration for deployment host

- [ ] Include a complete deployment-ready example Compose and a matching `.env.example` in `foundry-mcp` README; optionally supply `deploy/compose.yaml`. Use pinned `REGISTRY_HOST_PLACEHOLDER/sesopenko/foundry-mcp:<version-or-sha>`, `restart: unless-stopped`, healthcheck, and only required variables. Do not expose 8000 globally if Docker-network access suffices.
- [ ] Inspect actual deployment host Traefik network, `operator-selected Docker network`, and deployment DNS/routes. Determine whether new MCP server needs membership in the existing LibreChat network and a browser-accessible Traefik `wss://` endpoint. Avoid creating new proxy instances.
- [ ] Existing LibreChat config references dev URL. Document replacement with either `http://foundry-mcp:8000/mcp/mcp` when reachable through shared Docker network **or** the proper TLS/LAN hostname. Preserve `type: streamable-http`, `timeout: 30000`, `serverInstructions: true`. Revisit `mcpSettings.allowedDomains` for new hostname and reload/recreate LibreChat according to its configuration behavior.
- [ ] Test HTTP MCP client requests from *inside* LibreChat container, not just host; test WSS from a GM browser on actual gaming access URL. Validate session behavior for GET/POST and any streaming transport through Traefik; disable buffering/timeouts only as needed. A WebSocket connection does not imply MCP is reachable or vice versa.
- [ ] No API tokens, Foundry admin keys or registry passwords in tracked Compose files. Existing checked-in Foundry production config contains credentials: treat as sensitive, remove from future examples; recommend separate security remediation/rotation as a follow-up, not part of the operational deployment.

**Gate:** deployment instructions demonstrably cover both separate network paths; all operator-specific values are marked rather than guessed.

### Phase 6 — Human-run production installation and final acceptance

> The Codex build agent **must not** access, restart, or test the real gaming Foundry instance or host on the user's behalf. It prepares a validated runbook; the human executes production steps and records results.

- [ ] Before deployment: backup Foundry `/data`, verify matching module ID is not mounted from source in gaming Compose, document existing module state, and select a non-session maintenance window.
- [ ] On deployment host, log in to registry securely, pull pinned image, `docker compose config`, deploy only new MCP service, check `docker compose ps`, health and logs. No Foundry server restart should be needed just to launch a separate MCP container.
- [ ] In gaming Foundry **Setup → Add-on Modules → Install Module → Manifest URL**, paste the public stable manifest URL, install; then launch desired world, **Manage Modules** to enable it. In world, **Game Settings → Configure Settings → Foundry MCP**, set the browser-reachable WSS URL, disable dev JS execution; reconnect/reload and check status. Manual install fallback: place package in the persistent `/data/Data/modules/foundry-mcp/` using correct UID/GID and restart Foundry for discovery, but manifest install is preferred.
- [ ] Replace LibreChat's old dev `foundry-vtt` MCP URL with the reachable new server URL; apply LibreChat config safely; verify MCP tools appear and can read current world state. Validate behavior from an actual GM browser. Test the no-GM, multi-GM, reconnect and server-restart situations if supported.
- [ ] Before gaming sessions, check module enabled, GM browser connected, MCP service healthy and LibreChat client functional. Document how to recognize a connection failure versus a tool failure. Keep a rollback-ready prior image tag and module ZIP.
- [ ] Rehearse upgrade: new GitHub release increments module version, Foundry Setup package **Check Update/Update** follows stable `manifest` and fetches versioned ZIP; Compose change pinned image tag, `docker compose pull` and `docker compose up -d`, verify; coordinate compatible server/module releases. Do not let old client/new server silently break protocol.
- [ ] Rehearse rollback: restore previous image tag/digest and prior module package version (Foundry package UI may require manual older-version install); backup/restore any changed module settings if needed. Module updates and image updates are distinct operations.

**Gate:** human signs off first gaming session; no developer workstation process, source volume, or background user systemd service required.

## 5. Concrete implementation contract for Codex

**Deliverables inside `foundry-mcp` only:**

1. `Dockerfile`, `.dockerignore`, optional container test and healthcheck scripts.
2. Production-safe config for server host/port and existing runtime knobs, with explicit env documentation; module settings improvements and automated tests.
3. `deploy/compose.yaml` and `.env.example` or equally complete README-inline Compose; avoid affecting existing development Compose.
4. `.github/workflows/ci.yml` (or equivalent) containing tests, image build and gated private-registry push.
5. Module release packaging workflow and verified installable `module.json` release template; README steps for public-vs-private publishing decision.
6. `docs/operations.md` or README sections with **local setup**, **test**, **registry setup**, **CI secrets**, **Foundry install/update**, **deployment host Compose deployment**, **LibreChat connection**, **troubleshooting**, **rollbacks** and **human verification checklist**.
7. Unit/integration tests that cover the new configuration and release build contract; maintain current tests.

**Preferred delivery sequence:** one phase per logical PR or commit; commit only code/docs in `foundry-mcp`; report exact files changed and test results, unresolved assumptions, and steps user must perform. Stop before changing live infrastructure or making a private repository public. Setup instructions are **part of the definition of done**, not optional commentary.

## 6. Suggested reference snippets (adapt to audited code)

### Standalone production Compose, illustrative

```yaml
services:
  foundry-mcp:
    image: REGISTRY_HOST_PLACEHOLDER/sesopenko/foundry-mcp:${FOUNDRY_MCP_IMAGE_TAG:?pin-image-tag}
    restart: unless-stopped
    environment:
      FOUNDRY_MCP_HOST: 0.0.0.0
      FOUNDRY_MCP_PORT: "8000"
    # Join actual existing LibreChat/proxy networks only if verified.
    # networks: [operator-selected Docker network, traefik-net]
    # No ports necessary if reachable through shared networks + Traefik.
    # For initial trusted LAN testing only, deliberately publish a port.
    # ports: ["127.0.0.1:8000:8000"]

# networks:
#   operator-selected Docker network:
#     external: true
#   traefik-net:
#     external: true
```

This is a template, **not a verified working production configuration**. Add actual healthcheck, endpoint, auth, TLS routing labels, network names and image tag after audits. Explicitly determine whether the gaming browser can reach a private address and whether Foundry is accessed over HTTPS.

### GitHub Actions image build approach

Reference `reference CI project` for credential names and registry flow, but use the current project's Python 3.12 test suite as the prerequisite. Use `docker/build-push-action@v7`, registry `REGISTRY_HOST_PLACEHOLDER`, and SHA/version tags. Restrict secret-bearing steps to trusted branches/tags. Release workflows use `contents: write` only as needed to attach **module ZIP and module.json**, never registry credentials for module packaging.

### Foundry release manifest shape (example only)

```json
{
  "id": "foundry-mcp",
  "title": "Foundry MCP Proxy",
  "version": "1.0.1",
  "compatibility": {"minimum": "13", "verified": "13"},
  "esmodules": ["scripts/main.js"],
  "url": "https://github.com/sesopenko/foundry-mcp",
  "manifest": "https://github.com/sesopenko/foundry-mcp/releases/latest/download/module.json",
  "download": "https://github.com/sesopenko/foundry-mcp/releases/download/v1.0.1/foundry-mcp.zip"
}
```

Populate other required metadata from existing manifest. This example assumes public release assets and v13 compatibility confirmed by tests; `1.0.1` is illustrative, not an instruction to use that exact version.

## 7. Risks and deliberate design choices

| Risk / integration gotcha | Mitigation / acceptance test |
|---|---|
| `localhost` in browser is *GM's machine* | Use URL shown in module setting; test from remote GM browser, not Docker container. |
| HTTPS Foundry + insecure `ws://` | Prefer Traefik-backed WSS, trusted cert and correctly forwarded upgrades. |
| Foundry container and Python container are separate | Do not assume bridge originates in Foundry container; test browser→bridge and LibreChat→MCP independently. |
| `bridgeUrl` setting already exists, but is client scope | Preserve existing key or migrate carefully; ensure the actual GM's browser has it configured. |
| Private GitHub repo manifest/download | Public assets or separate public distribution repository needed for straightforward Foundry installer. Confirm unauthenticated URLs. |
| Browser token / dev-execute tool | Keep JS execution disabled in production; do not move privileged execution auth into globally shared settings. |
| Multiple GM connections | Define whether supported; prevent wrong-world or wrong-GM RPC routing, fail loudly if ambiguous. |
| Browser WebSocket after server restart | Reconnect with bounded backoff, stale socket cleanup, timeout/missing browser surfaced to MCP client. |
| Module version ≠ Python project version | Document independent release versioning and a tested compatibility matrix. |
| `uv.lock` / Python version | Build for Python 3.12; use reproducible locked dependencies and avoid development-only requirements. |
| Registry credentials / image immutability | Use Actions secrets; deploy pinned SHA/release tags; avoid `latest` production deployment. |
| Production world & persistent `/data` | Back up before manifest install/update; no source bind mount, no destructive compose changes. |
| LibreChat allowed-domain and network settings | Update URL and allowlist appropriately; test from inside LibreChat container. |
| Reverse proxy streaming/idle timeout | Test MCP responses and browser WebSocket under realistic idle/restart conditions. |
| Foundry core v13 vs v14 | Only declare `verified` after tested; actual gaming Compose currently declares voperator-confirmed v13 build. |
| Sensitive values present in existing reference deployment repository configuration | Never reproduce values in new artifacts; flag for separate redaction/rotation. |

## 8. External documentation to give Codex

Official Foundry documentation (authoritative):
- Module development, manifest fields and packaging: https://foundryvtt.com/article/module-development/
- Module installation, manifest install, activation and manual fallback: https://foundryvtt.com/article/modules/
- Package management: how manifest-based update checks and versioned ZIP downloads work: https://foundryvtt.com/article/package-management/
- Game settings scopes and UI: https://foundryvtt.com/article/settings/
- `game.settings.register` / `registerMenu` v13/v14 API: https://foundryvtt.com/api/classes/foundry.helpers.ClientSettings.html

Supplementary public reference: https://github.com/League-of-Foundry-Developers/FoundryVTT-Module-Template (release artifact patterns; adapt to actual project). This plan does **not** require submitting the module to Foundry's official package directory.

## 9. Definition of done

- [ ] Build agent provides reproducible local setup instructions and a working locally built `linux/amd64` Docker container.
- [ ] Foundry module connects using GUI-specified endpoint; no environment-specific IP/port requires JS edits; errors/reconnect are intelligible.
- [ ] Test suite passes and CI publishes immutable image tag to private registry using proven reference CI project credential pattern.
- [ ] Manifest and release ZIP meet Foundry install/update contract; fresh local install and update are validated.
- [ ] Complete Compose deployment example and LibreChat cutover instructions are in README/docs, with no production secrets.
- [ ] Production deployment and real-world verification remain human-operated, with a pre-session checklist and rollback instructions.
- [ ] Build agent records actual findings vs assumptions, exact commands/tests performed, and unexecuted production steps.

**Implementation prompt for Codex:** "Implement this operationalization iteration in the current `foundry-mcp` repository only. Start with a read-only audit of the actual source and external reference configurations, then proceed through phase gates in order. Preserve MCP protocol paths and existing tool behavior. Write operator-ready setup/update/rollback instructions alongside code and tests. Do not access or change gaming production hosts or other GitHub repositories. Escalate security/repository-visibility decisions rather than silently weakening protections."
