# Foundry MCP operationalization implementation contract

Status: repository implementation in progress; no publication or production
deployment is authorized automatically. See [operations](../operations.md) and
[verification record](../operationalization-verification.md) for resulting
artifacts, commands, evidence, and pending human acceptance.

## Mission and boundaries

Make the bridge usable during real gaming sessions without a managed developer
workspace. Deliver a reproducible Python service image, private-registry CI,
standalone Compose deployment, browser-module settings, installable/updateable
module releases, and operator-ready setup/update/rollback instructions.

Production Foundry is a separate, independently managed installation. Do not
access, restart, upgrade, reconfigure, or test it. Do not modify LibreChat,
production hosts, reference repositories, repository visibility, or GitHub
settings automatically. Only this working copy is an implementation target.
Production deployment and gaming-world acceptance are human-executed.

Do not add game features, PDF RAG, LangChain, multi-world routing, automatic
updates, proxy infrastructure, or package-directory registration. Preserve
existing tools, response/continuation contracts, and protocol paths.

## Locked decisions

| Concern | Implementation |
| --- | --- |
| Deployment access | Trusted LAN; no production MCP or WebSocket authentication; no Traefik route. |
| Protocol | `/mcp/mcp`, `/ws/foundry`, `/health`; browser remains authoritative. |
| GM ownership | One bridge; duplicate rejected; pending calls belong to their originating socket. |
| Foundry settings | Preserve client-scoped keys and saved values; full browser-reachable WS/WSS URL; reconnect on changes. |
| Development execution | Disabled by default; keep distinct credentials, loopback-only peers, and browser opt-in. |
| Versions | Synchronize server/module starting at 1.1.0; validate release tag against both. |
| Distribution | Release assets in this repository; operator decides when repository/releases become public. |
| Registry privacy | Hostname in Actions secret `REGISTRY_HOST`; credentials in `SECRET_REGISTRY_USERNAME` and `SECRET_REGISTRY_PASSWORD`. |
| Publication switch | Variable `PUSH_IMAGE_ENABLED`, disabled unless explicitly `true`. |
| Sensitive context | Ignored `.local/operationalization-context.md`; public examples use placeholders. |

The browser starts the WebSocket, not the Foundry container. Browser and
LibreChat addresses can differ. `localhost` means the caller's own machine or
container. An HTTPS Foundry page needs a browser-compatible WSS endpoint for
remote access. Document that prerequisite without changing Foundry hosting or
introducing TLS/proxy infrastructure into this iteration.

## Sources, required audit, and privacy

Follow AGENTS.md and its required reading in full. Read the relevant complete
Python/browser source, tests, startup scripts, `.env.example`, and development
execution security guide before extending them. Search hostnames, IPs, fixed
ports/paths, URL schemes, CORS/origin behavior, credentials, and logs; classify
values as runtime env, browser setting, protocol constant, development-only,
or test fixture. Do not turn protocol paths into arbitrary configuration.

Reference clones are available in ignored `.cache/reference-repos/`. Actual
repository names, source URLs, inspected revisions, host details, and deployment
observations belong in the [private local context](../../.local/operationalization-context.md).
Use them read-only. Never print complete sensitive Compose/configuration files.

Retain these reference lessons:

- Reference CI gates publication on tests, checks registry TLS, uses
  `docker/login-action`, Buildx, and build-push actions with named secrets.
  Add trusted-event restrictions rather than copying its publication gate blindly.
- Reference container uses uv but assumes Python 3.13 and a packaged project.
  This project requires Python 3.12 and `package=false`; adapt both differences.
- Existing deployment reference has an old LibreChat development MCP endpoint
  and an allowed-domain policy. Replace the endpoint, not add a duplicate.
- Its Foundry core version is checked-in configuration, not evidence of the
  running instance. Human acceptance must record the actual runtime build.
- Host paths, addressing, ownership, networks, and registry access are
  operator-specific. Do not infer them from reference names or copy credentials.

Before making public, move sensitive details from this tracked plan to the
ignored context and replace personal examples/paths in current files. Preserve
Git name/email and license attribution. Confirm branch state against origin,
amend the unpublished introducing commit while preserving unrelated fixes,
remove obsolete local reflog/object copies, and verify the original sensitive
blob is no longer reachable or stored. Do not rewrite/push origin. Report older
published disclosures separately. Exclude private context, reference clones,
credentials, browser profiles, traces, Git metadata, and Foundry data from
Docker and release artifacts independently of `.gitignore`.

## Phase 0 — Baseline and architecture record

- Check/start the existing managed bridge; do not start a competing foreground server.
- Establish focused behavior baselines and run both offline suites.
- Confirm actual FastMCP mount behavior, bind/reload settings, health fields,
  RPC timeouts/byte limits, shutdown, socket correlation, and duplicate/no-GM behavior.
- Record existing metadata: server 0.1.0, module 1.0.0, missing release URLs,
  client `bridgeUrl`, hidden `browserToken`, unconditional settings reload,
  and development source bind mount. Correct existing mechanisms rather than duplicating them.
- Inspect official Foundry docs via Grounded Docs before using APIs; match
  indexed major versions, inspect freshness/source, visibility, and deprecations.
  Installed source/live probes may confirm documented behavior but cannot make
  private or undocumented members supported.

Gate: baseline evidence and explicit configuration/security decisions recorded.

## Phase 1 — Runtime and browser configuration

- Add validated `FOUNDRY_MCP_HOST` and `FOUNDRY_MCP_PORT`. Source defaults:
  loopback, port 8000; image defaults: all container interfaces, port 8000.
  Reject invalid values at startup. Disable reload in the production entrypoint;
  document deliberate development reload separately. Do not trust forwarded headers.
- Preserve native client-scoped settings and existing values. Explain browser
  reachability, per-profile storage, and development separation in labels/hints.
- Parse full WS/WSS URLs safely; require host and `/ws/foundry`, reject
  embedded credentials/query/fragment, and handle invalid/blocked URLs without
  throwing during ready. Give actionable HTTPS/mixed-content guidance.
- Show Connecting/Connected/Disconnected/Misconfigured feedback through public
  notification APIs. Deduplicate notifications and avoid logging credentials.
- Reconnect on settings changes without page reload; cancel old timers, reset
  backoff, and ignore stale events. Keep GM-only startup, 1–30 second backoff,
  duplicate rejection, and prompt pending-call cleanup.
- Preserve development execution defaults, authentication, loopback constraints,
  hidden client credential, and tool visibility. No remote execution bypass.
- Test invalid config, URL variants, settings timing/reconnect, stale events,
  RPC success, auth regressions, duplicate/no-GM behavior, and disconnect cleanup.

Gate: environments are configured without JavaScript edits and regressions pass.

## Phase 2 — Image and local end-to-end checks

- Add a Python 3.12 slim, uv-based, non-root multi-stage image with locked
  production dependencies, compatible build/runtime Python, pinned base/tool
  references, version/source/revision labels, exec-form startup, and graceful SIGTERM.
- Add a standard-library healthcheck; no curl dependency or GM readiness requirement.
- Use runtime/context allowlists; no host venv, development mounts, credentials,
  private references, data, or persistent volume in ordinary operation.
- Build `linux/amd64` locally. Use alternate loopback port 18000 for the isolated
  test service, preserving managed development port 8000.
- Use a protocol-aware MCP client for discovery/schema checks and tool calls;
  a plain browser GET failure does not establish broken MCP.
- Test synthetic RPC, no GM, duplicates, pending disconnect, reconnect, real
  development-browser reads, server restart, clean shutdown, and runtime contents.
- Follow the development browser skill: focused tests, normal refresh, wait
  for Foundry readiness/bridge ownership, inspect console/network errors, and
  verify live behavior. Use only the dedicated test profile/world.
- Verify v13 on disposable data first; never downgrade v14 data in place.
  Verify v14 separately. Do not claim compatibility based on manifest text or mocks.

Gate: independently runnable image, recorded local evidence, and honest runtime gaps.

## Phase 3 — CI and private image publication

- Add tests, module contract checks, image build, protocol smoke, and graceful
  stop as prerequisites for publication. Failed checks must block publishing.
- Follow reference TLS/login/Buildx flow with secret hostname/credentials.
  Accept an unauthenticated registry 401; fail TLS/connectivity errors safely.
- Publish only trusted main/tag push events with the explicit enable variable;
  never publish from PRs. Use `contents: read` unless module asset upload needs write.
- Produce full-commit SHA tags and synchronized version tags. Require pinned
  release/SHA/digest deployment references. Refuse release-image replacement.
- Suppress public build records/summaries/attestations containing private image
  references. Keep public artifacts and module release notes free of registry values.
- Actual first push, masked/error log review, registry support/access, and pull
  from another deployment environment are operator acceptance checks.

Gate: workflows validated locally; actual publication/pull recorded separately.

## Phase 4 — Module releases and installation/update contract

- Populate supported metadata: id/title/description/authors/version,
  compatibility, esmodules, repository URL, stable manifest URL, and pinned ZIP URL.
  Remove unused flags and unverified compatibility claims.
- Use this repository's stable `releases/latest/download/module.json` URL and
  `releases/download/vX.Y.Z/foundry-mcp.zip` download. Never use a mutable latest ZIP.
- Package module contents with `module.json` at ZIP root and all referenced
  scripts. Exclude other repository content, secrets, maps, unsafe paths, and symlinks.
- Validate synchronized Python/module/application versions and matching release tag.
  Version changes require lockfile/URL updates; never replace existing release assets.
- Keep module asset publication separate from private registry credentials.
  Skip public module publication while repository is private; never change visibility.
- Test fresh install and a higher-version update on disposable local Foundry
  using locally served test artifacts. Public GitHub URL/download checks require
  actual operator publication; verify anonymously with redirects and compare bytes.

Gate: validated assets; installation/update and public availability supported by
actual evidence or explicitly marked pending.

## Phase 5 — LAN Compose and LibreChat instructions

- Provide standalone deployment Compose and nonsecret environment example,
  separate from development Compose. Require pinned `FOUNDRY_MCP_IMAGE` and
  explicit LAN interface bind address; `restart: unless-stopped`, healthcheck,
  and graceful stop. No Foundry container/mount, proxy labels, or automatic updates.
- Use host port 8000 consistently in production examples. Mark all host-specific
  values. Validate config privately without exposing interpolation output.
- Document private registry login, pull, service-only up/status/log/health checks.
- Document replacement of existing LibreChat `foundry-vtt` URL with a reachable
  LAN endpoint. Preserve Streamable HTTP, timeout 30000, and serverInstructions.
  Adjust allowed domains only as needed and apply config using the installed version.
- Test from inside LibreChat's container/network and from the GM browser as
  distinct human steps. Optional shared-network DNS needs deliberate operator setup.

Gate: instructions cover both client paths with no guessed deployment configuration.

## Phase 6 — Human acceptance, updates, and rollback

The build agent must not execute these production steps:

- Back up Foundry data/settings, record actual core build/module state, verify
  no source mount, and choose a non-session maintenance window.
- Pull the pinned image, validate/deploy only MCP, and check health/logs.
- Install the module through Setup → Add-on Modules → Install Module → Manifest
  URL; enable in the desired world; set client browser URL; keep development
  execution off; confirm one connected GM and an actual read.
- Provide persistent module-directory manual fallback with correct ownership,
  no nested ZIP directory, and operator-managed discovery/restart procedure.
- Cut over LibreChat and verify actual tools/read on the intended world.
- Rehearse browser/server restart, no-GM, and duplicate behavior during maintenance.
- Upgrade module and container separately to the tested pair. Module updates
  follow stable manifest/pinned ZIP; container updates change pinned image then pull/up.
- Roll back image and module independently using retained prior artifacts;
  restore settings when needed. Explain possible manual package downgrade.
- Check each session: module enabled, intended GM connected, service healthy,
  LibreChat functional, no developer process/source mount required.

## Deliverables and definition of done

Deliver runtime/module improvements and regression tests; Dockerfile/context
exclusions/healthcheck; separate production/local Compose examples; gated image
and module CI; validated release packager; README links; complete operations
runbook; and verification record with actual commands/results, precise local
versions, privacy/history findings, remaining limitations, and human checklist.

Run focused checks after each meaningful behavior change and `./scripts/test.sh`
before commits. Prefer deterministic checks; any fresh-agent evaluation must
follow the repository's budgeted process, not expand into a benchmark campaign.
Commit logical phases locally; do not push/publish/deploy automatically.

Completion requires distinguishing implemented/local-tested work from external
acceptance. Health alone is not RPC evidence; synthetic RPC is not Foundry API
evidence; prepared CI is not a successful registry publication; generated ZIPs
are not a proven Foundry install/update; local assets are not public GitHub downloads.
Do not mark any unexecuted gate passed.
