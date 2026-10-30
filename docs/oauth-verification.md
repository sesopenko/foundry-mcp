# Auth0 OAuth verification

Implementation evidence recorded 29 October 2026. This is an unreleased source
change, not approval to deploy or a claim of successful ChatGPT login.

## Framework migration

Resolved FastMCP 4.1.4, FastAPI 0.162.0, MCP SDK 2.3.0 and Starlette 1.10.0
with Python 3.12 and the existing Pydantic pin. Direct HTTP/JOSE dependencies
are httpx2 2.16.0 and joserfc 1.7.7. Removed the obsolete Fakeredis constraint;
Pydocket/Fakeredis are no longer in the lockfile. Resolver changes are recorded
in `uv.lock`; unrelated application dependencies were not deliberately upgraded.

The existing environment already contained FastMCP 4 before source migration,
so the first baseline failed on removed imports. Focused failures established
the required migration changes: public Tool imports, plain decorated-function
access, `list_tools()` replacing `get_tools()`, dictionary request metadata,
httpx2 transport helpers, and the SDK `REQUEST_TIMEOUT` constant replacing 408.
The initialization timeout test explicitly uses the legacy handshake because the
new protocol is sessionless. No business-logic tests were removed.

FastMCP's schema dereferencing is disabled to retain the existing compact `$defs`
contracts. The migrated non-OAuth baseline passed 588 Python tests (one existing
skip) and 623 JavaScript tests before OAuth was wired into transport. The isolated
Basic container smoke also passed. See upstream
[2→3](https://gofastmcp.com/getting-started/upgrading/from-fastmcp-2) and
[3→4](https://gofastmcp.com/getting-started/upgrading/from-fastmcp-3) migration guides.

## Automated evidence

Final `./scripts/test.sh`: **607 Python tests, one existing skip; 623 JavaScript
tests, zero failures**. Tests run offline with ephemeral signing keys and mocked
discovery/JWKS; they require no Auth0 account, tokens, Internet or live game.
The full suites ran outside the sandbox because PDF/threaded checks stalled
inside it. Focused OAuth checks are `test_oauth*.py`.

Covered boundaries include:

- Exclusive configuration, conflicting variables, exact canonical HTTPS URLs,
  required allowlists and no non-OAuth provider construction/discovery.
- Real RS256 verification, algorithm/signature/issuer/audience failures, required
  RFC9068 claims, expiration/nbf, ID-token rejection, user/client policy and
  `scope` versus `permissions`/`scp`. Denied HTTP calls assert zero handler calls.
- Public resource metadata at the actual external path, exact resource/audience,
  Bearer-only challenges, duplicate/malformed headers, 403 insufficient scope,
  Basic rejection in OAuth and Bearer rejection in Basic. Session IDs cannot
  replace credentials. Fresh application processes verify all three modes.
- JWKS reuse, rotation, unknown-key throttling, expired cache, malformed keys and
  outages. Discovery is parsed through the pinned library and checked for issuer
  and endpoint drift. Failure does not construct a Basic/anonymous fallback.
- Shared browser authentication, invalid/oversized/missing/timeout messages,
  acknowledgment ordering, concurrent admission and single-GM ownership in both
  production modes. OAuth tokens cannot replace the browser secret.
- Private PDF explicit GM trust and distinct upload capability, alongside the
  existing TLS/upload/path regression suite.
- Read-only validator bounds and mismatches; separate Compose environments.

The rebuilt isolated container passed `scripts/container-smoke.py`: authentication,
health, discovery/schema, no-GM diagnostics, synthetic RPC, duplicate rejection,
disconnect and reconnect. The isolated PDF smoke passed capability denials,
multi-chunk acknowledgments, concurrent RPC, indexing and no-browser source lookup.
No existing Foundry world, production tenant or gaming document was modified.

## Discovery size and behavior

`tests/test_oauth_application.py` launches fresh actual applications for Basic,
OAuth and none, with a 30-second process limit and two MCP calls each: tool listing
and `get_bridge_versions`. Each run completed. Compact sorted UTF-8 JSON:

| Mode | Tools | Catalog bytes | Diagnostic result bytes |
| --- | ---: | ---: | ---: |
| Basic | 25 | 123,760 | 768 |
| OAuth | 25 | 125,310 | 768 |
| None | 25 | 123,760 | 768 |

OAuth adds 1,550 bytes (62/tool) for `_meta.securitySchemes`. Removing that field
produces identical catalog hashes across modes:
`2b484530834bba8d1b9d35bf987d7df60f7493be5d493719cd711d791d8fe57e`.
Tool names, descriptions, input/output schemas and annotations match. Tool response
selection/pagination is unchanged; existing selective-read/reconstruction/budget
regressions pass. This is a mode comparison on the new framework, not a claim of
equal-byte catalogs across FastMCP major versions. No token billing or response
savings are inferred from byte counts.

## Operator acceptance still required

No real Auth0 tenant configuration, public Traefik route, ChatGPT login or refresh
was supplied/exercised. The following remain release/deployment gates:

1. Verify actual tenant entitlements outside trial. Create a staging API identifier
   and manually registered ChatGPT/Inspector clients, separate from production.
   An existing free tenant is sufficient if it permits the required features.
2. Run `scripts/oauth-validate.py` through the real TLS proxy. Verify exact issuer,
   resource/audience, scope, S256, `client_secret_post` and issuer identification.
3. Exercise authorization-code + PKCE in MCP Inspector with its own approved client
   and exact callback. Then connect ChatGPT, log in, list tools and call
   `get_bridge_versions` using the unchanged bridge.
4. Confirm ChatGPT consumes the documented `_meta.securitySchemes` compatibility
   field. The pinned Python SDK omits unknown top-level fields. No serializer
   monkey-patch was added; public HTTP OAuth remains authoritative regardless.
5. Test access-token expiration and refresh, server restart, reconnect, a second
   unapproved user, local subject/client removal and discovery cache refresh.
   Check that credentials never enter bridge messages or logs.
6. Through Traefik and the isolated backend, verify old Basic credentials remain
   denied and simulate Auth0 unavailability without downgrade. Verify the real
   proxy-only network/TLS restrictions, including optional PDFs.
7. Only then perform the documented maintenance-window cutover. Retain a private
   known-good Basic configuration for explicit rollback; never run competing GM
   bridges or automatically change authentication mode.

JWT logout/refresh revocation does not immediately revoke issued access tokens.
Test the local allowlist removal/restart denial path. No release, push, tenant
mutation or production cutover was performed by this implementation.
