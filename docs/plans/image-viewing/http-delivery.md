# Preview HTTP delivery and runtime configuration

The production app now serves private-store derivatives through explicit GET/
HEAD routes ahead of the final MCP mount. [Typed URL issuance](image-url-tool.md)
is integrated through MCP; [capability privacy/auth checks](capability-privacy.md)
cover its preceding security boundary.
This source checkpoint is not a released deployment or public-client acceptance.

| Setting | Contract |
| --- | --- |
| FOUNDRY_MCP_IMAGE_PREVIEW_ORIGIN | Optional canonical HTTPS origin without trailing slash, path, query, fragment or credentials. Validated by the existing https_origin helper; independent of the OAuth-only FOUNDRY_MCP_PUBLIC_URL. |
| FOUNDRY_MCP_IMAGE_PREVIEW_DATA_DIR | Absolute private directory; container default `/data/image-previews`. Empty, relative and NUL-containing values fail configuration. |

An absent origin disables store setup and issuance without removing discovery
or the later image-info capability. With an origin, startup opens/prunes the
store and fails clearly if private persistence is unavailable. The directory
must be writable by the service user (UID10001 in the image); deployments need
durable volume backing to preserve links across container replacement. Both
[deployment templates](../../../deploy/compose.yaml) now mount the private
image-previews named volume; see [operations](../../image-viewing.md).
Source snapshots/decoder scratch remain separate.

Server issuance policy requires an origin plus Basic, OAuth or authenticated
development mode. Plain none cannot issue. A configured store can still serve
previously issued links when issuance is disabled; public reading depends only
on its capability and expiry. The later authenticated tool independently checks
caller/GM authorization. Runtime policy is not a substitute for that boundary.

`PreviewRuntime` owns startup, one60-second periodic prune task, and shutdown.
SQLite operations run in owned threads. Cancellation waits for those threads
before releasing ownership; shutdown drains pending work before closing the
store. Cancelled startup closes a successfully constructed store. Failure to
start the MCP framework also closes the owned store. Failed periodic cleanup
emits only a fixed storage category; per-lookup expiry remains authoritative.

GET `/image-previews/{uuid4}.{jpg|png|webp}` returns raw immutable bytes, exact MIME
and Content-Length, `Cache-Control: private, no-store`, and
`X-Content-Type-Options: nosniff`. HEAD returns identical headers with no body.
Neither requires reader Authorization, a cookie, GM connectivity or a login
redirect. Incidental query values do not alter lookup; source/crop query values
cannot change the derivative. Public URLs use only trusted origin plus the
store-issued canonical path; Host/Forwarded headers never choose an origin.

Unknown, malformed, expired or extension-mismatched paths return the same empty
404/no-store response. Explicit root/catch-all handlers prevent trailing-slash
redirects and MCP fallback for malformed preview GET/HEAD requests. Storage
failures return an empty503/no-store and a fixed server diagnostic, without SQL,
paths or token values. No HTTP issuance/write endpoint is added.

The app's MCP middleware still authenticates `/mcp` and `/mcp/*`; existing bridge
and PDF authorization is retained. Capability-safe Uvicorn/evaluation logging
and the full authentication matrix are verified in09b; final proxy examples
remain task13. Issuance uses the authenticated MCP tool. Real-listener/curl/public-client acceptance
remains the later runtime/client gates, distinct from these ASGI tests.

`test_image_preview_http.py` uses the actual production app, real SQLite and an
injected clock to check both formats, GET/HEAD/query/404 contracts, exact expiry
with pruning paused, GM-independent reading, trusted origin, store shutdown/
reopen, periodic cleanup, startup failures and cancellation-safe thread draining.
Its HTTP client logs are disabled so fixture bearer paths cannot enter failing
test diagnostics. Existing Basic/OAuth and JS authentication regressions pass.
The root filename-query regression demonstrated200 instead of required404;
reading `request.path_params` directly now guarantees path-only lookup. The
same unchanged assertion passes without changing query semantics elsewhere.

Public response/lifespan contracts were checked against pinned Starlette1.10.0
[Response documentation](https://github.com/Kludex/starlette/blob/1.10.0/docs/responses.md)
and [lifespan documentation](https://github.com/Kludex/starlette/blob/1.10.0/docs/lifespan.md)
through GitHub MCP, alongside current installed FastAPI/FastMCP behavior.
The unwritable-store regression first failed because MCP's task group wrapped
the storage category; moving local setup before that context made the same test
pass. Test-only NUL-environ and read-only lifespan-property mock setup errors
were corrected without production changes or weakened expected behavior.
