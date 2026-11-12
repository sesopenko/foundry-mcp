# Caller-bound private originals — task 04b

`SourceSnapshots` stores verified04a originals for exactly1,800 seconds from
successful staging. It is process-local and separate from the persistent public
derivative store. Its factory defaults to512 MiB of compressed files including
pending size reservations. No valid handle is evicted to make room.

`stage(manager,request)` returns only `source_id,source_expires_at`. The handle is
a fresh UUIDv4, opaque to callers. The service reserves the validated original
size before04a creates a Python file or requests chunks, preventing concurrent
staging from exceeding cache capacity. Expired unleased snapshots are pruned
before admission; insufficient remaining capacity is SourceCacheFull. Failed,
cancelled or incomplete staging produces no handle and relinquishes reservations.

`lease(manager,source_id)` verifies caller identity, expiry, current ready GM/
world and exact canonical membership through the private byte-free
`validateImagePreviewSource({image})` RPC. Its private reply includes only
world/GM/image/scope, excluding fetch target/credentials. A later socket may
revalidate the same caller/world/GM; a socket change during work rejects that
in-progress request. New membership checks never download replacement bytes.

The lease yields private `original` and compact `receipt`, plus `recheck()`.
Call recheck immediately before publishing any new derivative; it checks current
principal/socket/world/GM/membership and source lifetime. Issuance still needs
the independent public-store/auth gates in later tasks. Keep private file paths,
source digest, signed source selector and original bytes out of MCP and logs.

An active lease protects a worker's input from expiry/pruning/discard/shutdown.
New uses are denied at `now>=expires_at`, including expiry during an awaited
membership check. The final returning lease deletes an expired/retired original.
`prune()` and `close()` provide lifecycle hooks for task10's runtime wiring;
close retires all handles and removes the owned temporary root after active
staging/leases finish. New cache instances have no prior process's handles.
Originals are never stored on the public preview route.

SourceUnavailable deliberately combines missing/expired/cross-caller handles
and directs callers to fresh `get_foundry_image_info`. SourceContextLost means
current world/GM/membership could not be revalidated; reconnect the ready
authorized GM and restage. These messages disclose no native errors or paths.
Replacing file contents at the same source path does not change existing pinned
bytes; a fresh info call stages a separate snapshot. Public derivative lifetime
and retrieval remain independent downstream.

## Authenticated identity evidence

Identity comes from a live HTTP MCP request, never client arguments, session IDs,
raw bearer strings or identity headers. The existing Basic/development boundary
adds a server-only, unforgeable ASGI scope proof after credential validation.
Basic binds the configured verified account; development binds its verified
local caller. Unauthenticated mode supplies no proof. All existing transport
credential checks and exclusive mode selection remain authoritative.

OAuth uses FastMCP's public `get_access_token()` and `get_http_request()` helpers,
verified against installed4.1.4 source and the upstream
[authorization](https://gofastmcp.com/docs/servers/authorization) and
[context](https://gofastmcp.com/docs/servers/context) documentation on2026-11-11.
The configured provider supplies verified claims; issuer/subject/client form a
stable identity across refreshed tokens. Exact current allowlists, scope and
expiry are checked again after asynchronous work. Missing HTTP/auth context
fails closed, including in-memory production invocations. No signature fallback,
Auth0 tenant change or real login/refresh acceptance is implied.

## Tests and runtime gates

- 10 deterministic cache tests cover exact expiry, current/changed principal,
  subjects/clients/issuers, replacement bytes, worker leases, denied membership,
  socket changes/revalidation, concurrent reservations, cancellation, discard,
  shutdown and process-local handles. A real04a assembly integration rejects
  quota before any chunk request/file creation.
- 3 actual HTTP→FastMCP→snapshot tests verify Basic/development proofs, anonymous/
  forged-header/session-ID/in-memory denial, RS256 two-user/two-client isolation,
  stable refreshed identity and invalid-token/scope rejection. JWT keys/discovery
  are offline fixtures; no real Auth0 tenant/login/refresh was used.
- 04a assembly10, connection6, production-auth13, OAuth19 and JS transfer/auth/
  bridge/main27 focused regressions passed outside sandbox.

Dedicated browser membership/discovery evidence and final full-suite counts are
recorded in the task/progress completion. Actual production image-tool use of the
cache awaits task10 registration and12a integration. Live S3 needs a configured
readable bucket/CORS; real Auth0 login/refresh and public HTTPS/target-ChatGPT
visual acceptance remain their separate external gates. No game assets changed.
