# Operationalization verification record

Implementation: synchronized server/module version **1.1.0**. This record
separates executed local checks from publication and human production acceptance.
No production Foundry instance, deployment host, or LibreChat service was accessed.

## Local results

| Check | Evidence/result |
| --- | --- |
| Baseline offline suites | 48 Python tests; four JavaScript file suites passed before behavioral edits. |
| Final offline suites | 54 Python tests; 29 JavaScript tests across five files pass. Focused runtime, URL/reconnect, packaging, and publication checks also pass. |
| Workflow syntax | `rhysd/actionlint:1.7.7` checked `.github/workflows/ci.yml` with no diagnostics. |
| Production Compose | Validated with documentation-only image/address placeholders using `config --quiet`. |
| Linux/amd64 image | Built locally from digest-pinned Python 3.12.12 slim-bookworm and uv 0.9.16, with locked dependencies. |
| Clean committed-source build | Exported committed files with `git archive`, rebuilt the container, and reproduced the module ZIP byte-for-byte without ignored/local files. |
| Runtime filesystem | UID 10001; allowlisted application files and venv only, plus license attribution; no environment files or development/source mounts. |
| Health and MCP | Isolated image healthy; protocol initialization, production tool catalog/schema presence, no-GM error, synthetic RPC, duplicate rejection, disconnect, and reconnect passed. |
| Real browser RPC | Existing local v14.369 `test` GM browser connected to the production container with browser development execution disabled; player and journal reads succeeded. |
| Development credential containment | Normal LAN mode never transmits a leftover browser development credential; regression covered. |
| Production execution tool | Absent from production container discovery. Existing authenticated development discovery still exposes it only when opted in. |
| Browser configuration | Client scope and saved credential preserved; invalid URL produces Misconfigured; correcting it reconnects without reload. |
| Restart behavior | Container restart followed by successful real-browser RPC; `unless-stopped` also recovered health after an in-container SIGTERM. |
| Graceful stop | Container stopped with exit code 0, without forced termination. |
| Browser console | Normal refresh on v14.369: zero uncaught exceptions, zero bridge errors, zero network errors during the 10-second observation. |
| Release assets | Version/tag/metadata/import validation, ZIP root paths, deterministic ZIP bytes, exclusion of private/dev files and symlinks tested. |
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

## Compatibility and package-install limitations

| Core | Status |
| --- | --- |
| v14.369 | Live settings, notifications, invalid URL/recovery, refresh, bridge reconnect, and real container RPC verified in the existing local test world. |
| v13.351 | Separate disposable service provisioned; installed application metadata reports 13.351.0. Browser entry redirects to `/license`; setup/activation is incomplete. No GM runtime compatibility claim is made. |

The v13 fixture has its own ignored data directory, with no v14 data downgrade.
The build agent did not complete license setup or launch a world there. It is
stopped after inspection. To resume locally, use the ignored fixture Compose,
complete its setup in the dedicated development browser, install a compatible
system/test world, and run the browser and release-install/update checks.

New API dependencies were checked against official indexed v13 and v14 docs:
public `ClientSettings.register/get/set`, client `scope`, `hint`, and `onChange`;
public `Notifications.info/warn/error`. v13 runtime behavior remains unverified.
The manifest retains minimum 13 but omits a `verified` claim pending completion
of the target-version acceptance. See [operations](operations.md) for official links.

**Fresh manifest installation and higher-version package update have not been
executed.** The existing local v14 module is source-mounted, so refreshing it
does not establish package-manager installation/update. Generated ZIP checks
are packaging evidence only. Run those remaining checks on disposable data
before declaring module distribution ready.

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
  sanitized. Those older disclosures were not rewritten; review before making
  the entire repository public if historical removal is required.
- Git name/email and license/module attribution are retained. Pattern scanning
  is not a guarantee that all personal information or secrets are absent.
- Reference clones, browser data, credentials, and traces remain ignored and
  excluded independently by Docker/module allowlists. The reference deployment
  configurations were not copied into public files.

## Unexecuted external acceptance

The following are intentionally pending and must not be inferred from local passes:

- [ ] Complete the disposable v13 runtime, fresh manifest install, and higher-version update checks.
- [ ] Configure Actions secrets and publication switch; inspect the first real CI run.
- [ ] Verify registry TLS/access from the hosted runner, private image push, and pull from a separate deployment environment.
- [ ] Verify secret hostname masking in normal/error logs and absence from public artifacts; local actionlint cannot establish this.
- [ ] Decide repository visibility after reviewing remaining historical disclosures.
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
