# Bridge version diagnostics

`get_bridge_versions` compares the MCP server's packaged identity with the
identity embedded in the JavaScript loaded by its currently connected GM.
It is read-only, takes no arguments, and uses normal MCP authentication in
production and development. It does not query GitHub/Docker Hub for updates,
change settings, or install software.

## Response contract

| Field | Meaning |
| --- | --- |
| `server` | Server build identity; always present, even without a GM. |
| `module` | Loaded browser module identity, or `null` when unavailable. |
| `comparison` | `match`, `mismatch`, `unverified`, or `unavailable`. |
| `module_status` | `connected`, `not_connected`, `unsupported`, `timed_out`, `disconnected`, or `invalid_metadata`. |
| `message` | Explanation and next recovery step. |

Each identity contains `version` (`X.Y.Z` or `null`), `release_tag` (`vX.Y.Z`
or `null`), `revision` (40-character commit SHA or `null`), and `build_kind`
(`release`, `unreleased`, `source`, or `unknown`). Only two valid tagged
releases receive an exact-equality `match` or `mismatch` verdict. Any source,
untagged, or unknown identity makes the comparison `unverified`, even when
version numbers happen to agree. A match does not establish Foundry core or
protocol compatibility, nor confirm that this is the intended game world.

Example (illustrative versions):

```json
{
  "server": {"version":"1.3.0","release_tag":"v1.3.0","revision":null,"build_kind":"release"},
  "module": {"version":"1.2.3","release_tag":"v1.2.3","revision":null,"build_kind":"release"},
  "comparison": "mismatch",
  "module_status": "connected",
  "message": "Packaged release versions differ. Update the older component, reload the GM browser and reconnect."
}
```

The server queries `getModuleBuildInfo` through the existing GM RPC connection,
with empty parameters and a five-second timeout. There are no document IDs,
filters, pagination, or continuation fields. No browser returns `module: null`,
`module_status: not_connected`, and `comparison: unavailable`, while preserving
server identity. A legacy module that lacks this RPC returns `unsupported`.
Timeouts, disconnects and malformed metadata likewise return diagnostic results
rather than tool errors; check `module_status` and `message` and reconnect or
update/reload as directed. Use `get_player_names` afterward to test a real world
read. Tool transport/authentication failures remain ordinary MCP failures.

## Foundry operator feedback

After authenticated admission, the server includes `server_build` in the
`{"type":"auth","status":"ok"}` acknowledgment. Development and unauthenticated
modes receive `{"type":"serverInfo","server_build":{...}}` during admission.
These control messages precede game RPC availability. Older clients may ignore
these additive fields/messages; older servers without identity metadata remain
usable but cannot trigger automatic comparison.

The module compares the server identity with its imported `buildInfo.js`
constant, not a freshly fetched manifest that could describe newer installed
files than the browser has loaded. For a tagged mismatch it shows a dismissible
persistent warning naming both versions and the older component to update.
Normal tools continue operating. Warnings are deduplicated per identity pair
for the page lifetime, so ordinary reconnects do not repeat them. A changed
pair can warn again. Unverified identities produce informational feedback,
not a false match or mismatch claim. Stale sockets cannot update this feedback.

Notifications use documented public [v13](https://foundryvtt.com/api/v13/classes/foundry.applications.ui.Notifications.html)
and [v14](https://foundryvtt.com/api/v14/classes/foundry.applications.ui.Notifications.html)
`ui.notifications.warn`/`info` APIs. Unit tests cover comparison and notification
behavior without requiring another manual Foundry setup.

## Build and release identity

- Tracked source identities are `foundry_mcp_server/build-info.json` and
  `foundry-module/scripts/buildInfo.js`, marked `source` and synchronized by the
  repository release helper. Python loads server metadata once at process
  startup; runtime environment variables do not override it. Invalid or missing
  server metadata reports `unknown` rather than a fabricated release identity.
- CI resolves the workflow's actual tag and commit once. A release tag must be
  exactly `v<project version>` and agree with the module manifest. Main/PR builds
  carry the declared version and commit but are explicitly `unreleased`.
- Docker build arguments `VERSION`, `RELEASE_TAG` and `REVISION` generate the
  image's metadata file. OCI labels supplement this file; Python reads the
  embedded file. Untagged local image builds are `unreleased`.
- Module packaging replaces `scripts/buildInfo.js` inside the ZIP with the same
  generated identity; it does not rewrite the tracked source file. The
  `release-module` job verifies the ZIP's identity against its workflow tag and
  commit before publishing. ZIP metadata remains deterministic for identical
  inputs.

For a deliberately tagged local artifact check, supply the matching tag and
actual build commit to `scripts/package-module.py --tag vX.Y.Z --revision <SHA>`.
Omitting `--tag` produces an explicitly unreleased artifact; local checks are
not evidence that a release has been published. See [operations](operations.md)
for release, update and rollback procedures. No deployment is automatically
changed by diagnosis.

## Implementation verification

Local verification on 2026-10-19 passed 79 Python tests and 41 JavaScript tests
on Node 22, including fresh MCP discovery, structured output, legacy clients,
timeouts, stale sockets, and notification deduplication. An isolated MCP-only
container passed authenticated smoke checks for packaged identity, matching and
mismatched releases, and missing/disconnected GM clients. Tagged ZIP checks
verified embedded tag and commit metadata. These were local build fixtures,
not published releases.

The notification's actual appearance in a live Foundry browser remains
unverified; deterministic browser mocks cover its content and lifecycle.
Existing Foundry instances and production deployments were left untouched.
