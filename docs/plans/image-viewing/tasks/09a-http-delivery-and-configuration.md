# 09a — HTTP delivery and configuration

Points: **5** — store-backed routes, configuration, and application lifecycle.
Split from original task 09, estimated at 13 points.

Dependencies: [08](08-persistent-preview-store.md).
Intended commit: `feat(images): serve private-store preview capability URLs`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design](../../../prompts/foundry-image-previews-plan.md),
[plan index](../README.md), and this task. Reconcile dependency commits and test
evidence. Follow the index's execution and commit protocol.

Read `main.py` route/middleware order, `config.py`'s `https_origin`, evaluation
logging, auth tests, and [OAuth operations](../../../oauth-auth0.md). Anonymous
delivery must not weaken issuance or other protected surfaces.

## Implementation and interfaces

- Add opt-in `FOUNDRY_MCP_IMAGE_PREVIEW_ORIGIN`, validated by `https_origin`.
  It is independent of the OAuth-only public resource URL and works for Basic
  or OAuth, plus existing authenticated local development. Missing origin leaves
  discovery/info available; URL issuance reports `PreviewNotConfigured` before
  source work. Plain unauthenticated mode cannot issue links.
- Add `FOUNDRY_MCP_IMAGE_PREVIEW_DATA_DIR` with a private container default
  `/data/image-previews`. Initialize the store when previews are enabled and
  fail clearly if enabled persistence is unwritable. Tie startup prune,
  periodic prune, and graceful close to the app lifespan; store cleanup is not
  the authority for expiry. Originals/scratch use a separate private location.
- Define explicit GET and HEAD `/image-previews/{uuid4}.{ext}` routes before
  `app.mount('/', mcp_app)`. Lookup only by path token/actual format; ignore
  incidental query values. GET returns 200 raw bytes, exact Content-Type and
  Content-Length, `Cache-Control: private, no-store`, and
  `X-Content-Type-Options: nosniff`. HEAD has matching headers and no body.
- Unknown, expired, malformed, and extension-mismatched capabilities produce
  generic 404 with `no-store`, without redirects or information about existence.
  Never serve original files or accept crop/source selectors at this route.
  No reader authentication, cookies, login, or HTML wrapper is required; links
  continue working after GM disconnect. Do not expand anonymous access to any
  other route, MCP operation, GM WebSocket, or PDF operation.
- URL generation uses configured HTTPS origin plus fresh UUID path only:
  no source identity, crop, credentials, expiry, query, or fragment in issued
  URLs. Implement issuance-enabled policy as a shared internal check for 11.
- Keep issuance internal/unregistered until
  [09b](09b-auth-boundaries-and-capability-privacy.md) completes authentication
  matrix and capability-safe logging. This task tests route/store/configuration
  correctness; no public proxy or release is enabled here.

## Tests and acceptance

Add `tests/test_image_preview_http.py` using the production ASGI app with real
store and injected clock. Test GET/HEAD bytes and headers, unknown/mismatched
tokens, exact expiry with cleanup paused, query equivalence, no redirects or
Set-Cookie, disconnected GM retrieval, startup/shutdown, and configuration errors.
Public preview delivery needs no Authorization header. Keep real test tokens
out of test failure diagnostics. The full Basic/OAuth/development/plain-none
boundary matrix and emitted-log assertions belong to 09b.

Run outside the sandbox:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_http.py' -v
./scripts/test.sh
```

Accept when direct route behavior, configuration, and lifecycle pass against
the production app. Commit HTTP/config code, tests,
and route/configuration documentation together. No public deployment is needed.

## Completion record

- Implementation: not started.
- Dependency commit SHA(s): pending.
- Commit: pending (`this commit` when completed).
- Focused/full checks, HTTP/config/lifecycle evidence: not run.
- Pending deployment prerequisites: pending.
