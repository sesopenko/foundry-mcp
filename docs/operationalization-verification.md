# Operationalization verification record

Implementation: synchronized server/module version **1.1.0**. This record
separates executed local checks from publication and human production acceptance.
No production Foundry instance, deployment host, or LibreChat service was accessed.

## Local results

| Check | Evidence/result |
| --- | --- |
| Baseline offline suites | 48 Python tests; four JavaScript file suites passed before behavioral edits. |
| Final offline suites | 54 Python tests; 31 JavaScript tests across five files pass. Focused runtime, URL/reconnect, packaging, and publication checks also pass. |
| Workflow syntax | `rhysd/actionlint:1.7.7` checked `.github/workflows/ci.yml` with no diagnostics. |
| Production Compose | Validated with documentation-only image/address placeholders using `config --quiet`. |
| Linux/amd64 image | Built locally from digest-pinned Python 3.12.12 slim-bookworm and uv 0.9.16, with locked dependencies. |
| Clean committed-source build | Exported committed files with `git archive`, rebuilt the container, and reproduced the module ZIP byte-for-byte without ignored/local files. |
| Runtime filesystem | UID 10001; allowlisted application files and venv only, plus license attribution; no environment files or development/source mounts. |
| Health and MCP | Isolated image healthy; protocol initialization, production tool catalog/schema presence, no-GM error, synthetic RPC, duplicate rejection, disconnect, and reconnect passed. |
| Real browser RPC | Local v14.369 development world and, on 2026-10-18, the existing v13.351 packaging world both answered player and journal reads through the production container with development execution disabled. |
| Development credential containment | Normal LAN mode never transmits a leftover browser development credential; regression covered. |
| Production execution tool | Absent from production container discovery. Existing authenticated development discovery still exposes it only when opted in. |
| Browser configuration | Client scope and saved credential preserved; invalid URL produces Misconfigured; correcting it reconnects without reload. |
| Restart behavior | Container restart followed by successful real-browser RPC; `unless-stopped` also recovered health after an in-container SIGTERM. |
| Graceful stop | Container stopped with exit code 0, without forced termination. |
| Browser console | Normal refresh on v14.369: zero uncaught exceptions, zero bridge errors, zero network errors during the 10-second observation. |
| Release assets | Automated artifact validation passes. On 2026-10-18 the existing v13 fixture installed a local-manifest package, then updated it from test version 1.0.0 to 1.1.0 through Foundry Setup. Installed runtime assets match the canonical release ZIP. |
| Privacy cleanup | Current tracked and intended new public files have no matches for the audited private domain, LAN addresses, host nickname, personal home paths, private-key/access-token patterns. |

During intentional settings switching, closing an in-progress old socket can
produce a transient network diagnostic. The clean final refresh/observation
and successful RPC establish the restored state. The original development URL,
execution setting, and credential were preserved/restored after container tests.

The native MCP session became stale after the managed server restart. A fresh
locked-Python FastMCP client verified actual authenticated discovery, schemas,
and read-only runtime information. Native Chrome MCP tools were not available;
local browser checks used CDP attached only to the dedicated development
profile, discovered from its DevToolsActivePort. No ordinary browser was attached.

## Commands and procedures executed

Representative reproducible commands, using no private infrastructure values:

```bash
./scripts/test.sh
.venv/bin/python -m unittest discover -s tests -p 'test_runtime.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_packaging.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_image_publication.py' -v
node --test tests/js/bridge.test.js tests/js/main.test.js tests/js/connectionConfig.test.js
.venv/bin/python scripts/package-module.py --tag v1.1.0
docker compose -p foundry-mcp-smoke -f deploy/compose.local.yaml up -d --build --wait --wait-timeout 90 foundry-mcp
docker compose -p foundry-mcp-smoke -f deploy/compose.local.yaml run --rm --no-deps -T smoke
docker compose -p foundry-mcp-smoke -f deploy/compose.local.yaml restart foundry-mcp
docker compose -p foundry-mcp-smoke -f deploy/compose.local.yaml stop
docker compose -p foundry-mcp-smoke -f deploy/compose.local.yaml ps -a
git diff --check
```

Additional private local helpers captured CDP observations, fresh MCP discovery,
real-world RPC success without printing world content, image inspection,
restart count/health recovery, and privacy results. They are retained under
ignored `.local/`, not shipped. The actionlint invocation used an ignored
Compose helper mounting only workflow files read-only.

## Compatibility and package-install evidence

| Core | Status |
| --- | --- |
| v14.369 | Live settings, notifications, invalid URL/recovery, refresh, bridge reconnect, and real container RPC verified in the existing root development world. |
| v13.351 | On 2026-10-18, reused the user-configured packaging fixture and existing `test` world. Fresh local-manifest install, higher-version update, module enablement, native settings save without reload, player/journal RPC, refresh, and reconnect after MCP-container restart passed. |

The user completed license/setup and configured the existing v13 world. No
additional Foundry instance was created for these checks; worlds, systems,
other module selections, credentials, and data were preserved. The root
instance remains the default for development. The v13 fixture is reserved for
packaging checks after significant Compose changes, not a routine version
matrix. Preserve its completed setup and follow AGENTS.md before further testing.

### Local installer/update procedure (2026-10-18)

- Built ignored local-only test variants from the generated module ZIP. Their
  manifest pointed at `http://assets:8000/module.json`, with version-specific
  ZIP paths on the existing fixture's static-artifact service.
- Used Foundry Setup's **Install Module → Manifest URL** to install test version
  1.0.0. Advanced the local manifest to 1.1.0 and used its normal package update
  control. The on-disk package and Setup UI both confirmed 1.1.0.
- Test versions used the current runtime assets: this tests the installer and
  update contract, not historical 1.0.0 runtime compatibility. Canonical release
  metadata and ZIP were not rewritten or published.
- Compared every installed runtime asset and license against the canonical ZIP;
  only the fixture manifest contains local test URLs. Canonical ZIP SHA-256:
  `d117f62f2ad567148de6936864a5a8a2485204e7ddd7b95dd17d9e13bfef147b`.
- Relaunched the existing world, enabled only Foundry MCP while preserving the
  other module selections, and saved `ws://localhost:18000/ws/foundry` in native
  module settings. Development execution remained false. A browser marker
  proved saving the URL did not reload the page.
- Read player names and the journal tree through the production container with
  a fresh protocol-aware MCP client; the execution tool was absent. No world
  content was printed, imported, or edited.
- Normal refresh restored Connected status. A 10-second observation found zero
  uncaught exceptions, bridge errors, or network errors. RPC succeeded again
  after restarting only the MCP container.

The fixture remains configured for reuse: Foundry at localhost:30013, MCP at
localhost:18000, and local package assets at localhost:18013. Its world/module
state is retained. The root development instance was not started or modified.
Local helpers remain ignored and attached only to the dedicated browser profile.

New API dependencies were checked against official indexed v13/v14 docs:
public `ClientSettings.register/get/set`, client `scope`, `hint`, `onChange`,
and public notifications. The v13 checks establish the packaging/connection
paths above, not exhaustive coverage of every content tool and optional-module
interaction. The manifest's broader `verified` declaration remains omitted;
minimum 13 is unchanged. Public GitHub downloads and real CI publication remain
separate acceptance gates. See [operations](operations.md) for official links.

## CI Node 22 follow-up (2026-10-18)

The first hosted `verify` run at commit `f3250b8` passed all 54 Python tests but
failed the exploration test's unconditional `assert.ok(response.error.stack)`.
Local Node 20.19.2 exposes native error stacks as data properties; the runner's
Node 22.23.3 exposes them as accessors. Descriptor-only error handling deliberately
omits accessor-backed stacks instead of invoking getters.

Reproduced the identical failure before editing using a transient
`node:22.23.3-bookworm-slim` container. Corrected the test to require error type
and message while allowing an unavailable native stack. Added engine-independent
wire-round-trip checks for bounded explicit stack/message data, uninvoked hostile
getters, and missing stacks. Updated the documented optional-stack contract.
Production JavaScript, images, manifests, and workflows are unchanged.

Validation: focused tests pass on Node 20.19.2 and 22.23.3; the full JavaScript
suite passes all 31 tests on Node 22.23.3, and `./scripts/test.sh` passes locally
with 54 Python tests. No Foundry instance was started, recreated, or changed.
Hosted CI still needs rerunning after the fix is pushed. Its action-runtime
Node 20 deprecation warning is separate from the failed assertion.

## Privacy and local Git history

- Original deployment details moved into private ignored
  `.local/operationalization-context.md`; its directory is 0700 and file 0600.
- The sole unpublished introducing commit was amended while preserving its
  unrelated service fix/tests. Origin was fetched/checked, never rewritten or pushed.
- Obsolete unreachable reflog entries were expired for HEAD/main, followed by
  local object pruning. Both the original introducing commit and original
  sensitive document blob are absent from local object storage.
- The pre-implementation scan covered 29 reachable commits and 153 historical
  blobs. A post-amend scan covered 155 historical blobs; current-file matches
  for the audited patterns were empty.
- **Older already-published history still contains a former README LAN example
  and a workstation path in an older skill revision.** Current versions are
  sanitized. On 2026-10-18 the user explicitly approved retaining those historical
  values. No further history rewrite is required for them.
- Git name/email and license/module attribution are retained. Pattern scanning
  is not a guarantee that all personal information or secrets are absent.
- Reference clones, browser data, credentials, and traces remain ignored and
  excluded independently by Docker/module allowlists. The reference deployment
  configurations were not copied into public files.

## Unexecuted external acceptance

The following are intentionally pending and must not be inferred from local passes:

- [ ] Configure Actions secrets and publication switch; inspect the first real CI run.
- [ ] Verify registry TLS/access from the hosted runner, private image push, and pull from a separate deployment environment.
- [ ] Verify secret hostname masking in normal/error logs and absence from public artifacts; local actionlint cannot establish this.
- [ ] Make the repository/releases publicly accessible when ready; the user approved retaining the historical LAN/path examples.
- [ ] Publish a new immutable release; verify anonymous stable manifest and version-pinned ZIP URLs.
- [ ] Human: back up gaming Foundry data/settings and confirm actual running core build.
- [ ] Human: deploy only the bridge, install/enable/configure the module, and replace LibreChat's old endpoint/allowlist as required.
- [ ] Human: test MCP from LibreChat's container and WebSocket from the real GM browser independently.
- [ ] Human: rehearse upgrades/rollback and sign off the first gaming session.

No secrets/settings were configured on GitHub, no release or image was published,
no repository visibility changed, and no production service was modified.

## File inventory

Local branch changes relative to origin, including the preserved pre-existing
service startup fix and its regression test:

```text
.agents/skills/foundry-compose-upgrade/SKILL.md
.dockerignore
.github/workflows/ci.yml
.gitignore
AGENTS.md
Dockerfile
README.md
deploy/.env.example
deploy/compose.local.yaml
deploy/compose.yaml
docs/js-exploration.md
docs/operationalization-verification.md
docs/operations.md
docs/prompts/foundry-mcp-operationalization-plan.md
foundry-module/LICENSE.txt
foundry-module/module.json
foundry-module/scripts/README.md
foundry-module/scripts/connectionConfig.js
foundry-module/scripts/foundryBridge.js
foundry-module/scripts/main.js
foundry_mcp_server/config.py
foundry_mcp_server/healthcheck.py
foundry_mcp_server/main.py
pyproject.toml
scripts/check-image-tag.py
scripts/container-smoke.py
scripts/package-module.py
scripts/server.sh
tests/js/bridge.test.js
tests/js/connectionConfig.test.js
tests/js/main.test.js
tests/test_image_publication.py
tests/test_packaging.py
tests/test_runtime.py
tests/test_server_launcher.py
uv.lock
```
