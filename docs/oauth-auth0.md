# Auth0 OAuth deployment (unreleased)

This server is an OAuth protected resource. Auth0 owns login, consent, access
tokens and refresh; ChatGPT holds the OAuth client secret. No client secret,
login database, token exchange, DCR endpoint or OAuth storage volume belongs on
the MCP server. `Auth0MCPProvider` is used directly, not `Auth0Provider`'s proxy.

Choose exactly one mode: `none` for existing local development, `basic`, or
`oauth`. OAuth never accepts Basic credentials or falls back during an outage.
Read [verification and remaining live gates](oauth-verification.md) before rollout.

## Auth0 dashboard

1. In tenant settings enable **Resource Parameter Compatibility Profile** and
   **Include Issuer in Authorization Responses**. Do not set a tenant default
   audience. Verify the discovered issuer spelling, including its trailing slash.
2. Create an API named `foundry-mcp`. Its identifier must equal your complete MCP
   endpoint, for example `https://mcp.example.com/mcp/mcp`. Select **RS256** and
   the **RFC 9068 access token profile** (`rfc9068_profile`). Define `foundry:gm`
   as permission to use the complete GM tool surface, including private data and
   any write tools. It is not a read-only permission.
3. Create a **Regular Web Application** for ChatGPT. Enable authorization-code
   and refresh-token grants, with token endpoint authentication
   **client_secret_post**. Enable the intended database or social login
   connection for that application. Do not use a machine-to-machine application.
4. Copy the full callback URI shown in ChatGPT into **Allowed Callback URLs**.
   Do not use wildcards or a callback on this server. Keep the client secret in
   ChatGPT and your private operator store only.
5. Enable **Allow Offline Access** on the API. Configure application refresh-token
   rotation and expiration. Start with a short access-token lifetime (for example
   15 minutes) and test refresh before production. ChatGPT requests `offline_access`.
6. Record the exact owning user's `sub` (Auth0 user ID, including its provider
   prefix) and the application's public client ID in the server allowlists.
   An email address, successful login or scope alone does not grant access.
   Consider disabling public signup for a personal database connection.

Roles, RBAC, Organizations, FGA and paid token exchange are unnecessary. Confirm
the required features in your actual tenant after any trial expires. Keep RBAC
optional: the local subject allowlist remains authoritative, and `permissions`
never substitutes for the granted OAuth `scope`. See Auth0's
[resource parameter guide](https://auth0.com/ai/docs/mcp/guides/resource-param-compatibility-profile),
[MCP authorization guide](https://auth0.com/ai/docs/mcp/get-started/authorization-for-your-mcp-server),
[application types](https://auth0.com/docs/get-started/applications/confidential-and-public-applications),
and [refresh-token guidance](https://auth0.com/docs/secure/tokens/refresh-tokens).

## Server configuration

Use the separate [OAuth Compose file](../deploy/compose.oauth.yaml) and
[environment template](../deploy/.env.oauth.example), never an override layered
on the Basic example. Set a pinned OAuth-capable image; v2.2.0 does not contain
this unreleased feature. Keep `.env.oauth` private and outside version control.

| Variable | Contract |
| --- | --- |
| `FOUNDRY_MCP_AUTH_MODE` | `oauth` |
| `FOUNDRY_MCP_OAUTH_PROVIDER` | `auth0` |
| `FOUNDRY_MCP_PUBLIC_URL` | HTTPS origin, no trailing slash, path, query, fragment or user information |
| `FOUNDRY_MCP_OAUTH_ISSUER` | Exact HTTPS Auth0 issuer origin, ending in `/` |
| `FOUNDRY_MCP_OAUTH_ALLOWED_SUBJECTS` | Nonempty comma-separated exact `sub` values |
| `FOUNDRY_MCP_OAUTH_ALLOWED_CLIENT_IDS` | Nonempty comma-separated exact `client_id` values |
| `FOUNDRY_MCP_BRIDGE_TOKEN` | Separate existing browser credential |
| `FOUNDRY_MCP_DEV_EXECUTION` | `false` |

Remove both Basic credential variables. Basic/none reject nonempty OAuth settings
and `PUBLIC_URL`; none also rejects production credentials. Unknown modes and
OAuth variables fail startup. Changing mode or allowlists requires process
restart/container recreation. There is no per-request mode selection.

The resource, audience and Auth0 API identifier are all `PUBLIC_URL + /mcp/mcp`.
JWT validation requires RS256, exact issuer/audience, access-token `typ`, numeric
`exp` and `iat`, valid optional `nbf`, nonempty `jti`, allowed subject and
RFC9068 `client_id`. Machine grants are rejected. Clock skew is zero: keep clocks
synchronized. Granted `foundry:gm` is required; missing scope returns 403
`insufficient_scope`. Invalid tokens or local identity policy denial return 401
Bearer without identity details. No ID tokens, legacy `azp` dialect or
`permissions`-only authorization is accepted.

Startup fetches OIDC discovery with a ten-second timeout and fails closed on
failure or incompatible metadata. Authorization, token and JWKS endpoints must
use the configured HTTPS issuer origin. The library caches JWKS for one hour,
throttles refresh attempts to one per 30 seconds including failures, and uses a
ten-second JWKS timeout. Cached known keys can work during an outage until cache
expiry; unknown or stale keys fail closed. Rapid key rotation may require retry
after the throttle interval. There is no automatic downgrade.

## Traefik and browser/PDF boundaries

Route `/mcp/mcp` and `/.well-known/oauth-protected-resource/mcp/mcp` to port 8000.
Preserve Authorization, WWW-Authenticate and MCP headers, SSE and streaming.
Remove Basic middleware, login redirects, Basic injection and credential
translation for this instance. Do not publish a parallel Basic route. Keep the
backend private and restricted to the TLS proxy. Public URLs come from validated
configuration, never Host or Forwarded headers. Proxy-header trust remains off.

Auth0 serves its own OIDC and authorization-server metadata. The MCP server does
not mirror AS discovery or expose authorization, registration or token handlers.
Keep `/health` internal; it can include bridge/evaluation status.

Route `/ws/foundry` over WSS without requiring an OAuth token. Enable the module's
existing production authentication and configure only its separate bridge token.
The first-message handshake, five-second deadline, 4 KiB limit, acknowledgment
ordering and single-GM ownership are unchanged. No Auth0 credentials enter world
settings. Those settings are player-readable, not a confidential secret store.

Private PDFs still require explicit `FOUNDRY_MCP_PDF_TRUSTED_GM_MCP=true`, separate
upload capability and safe storage paths. Set `FOUNDRY_MCP_PDF_TRUST_TLS_PROXY=true`
only if the backend is network-restricted to the actual HTTPS/WSS terminating
proxy; otherwise leave it false. OAuth does not waive transport checks. Preserve
existing PDF volumes and use the same Compose project name when switching modes.

## Cutover and rollback

After staging acceptance, drain and stop the existing instance. Privately inspect
the resolved Compose/process environment; do not publish `docker compose config`
output containing secrets. Remove Basic credentials from the active deployment,
select the standalone OAuth file, and recreate the service:

```bash
docker compose --env-file .env.oauth -f compose.oauth.yaml config --quiet
docker compose --env-file .env.oauth -f compose.oauth.yaml up -d --force-recreate --wait
```

Use the same explicit `-p` project name as the old deployment if it had one.
Restarting an existing container does not change its environment. Basic clients
must migrate to OAuth or disconnect. Keep rollback credentials privately outside
the active OAuth environment.

Rollback is an operator-controlled mode switch: stop OAuth, restore the known-good
Basic image/configuration, remove all OAuth-specific settings, and recreate the
Basic instance. Never roll back automatically on Auth0 failure. Do not delete
volumes or run two GM bridges against the live world.

Local JWT verification does not promise immediate revocation on logout. Issued
access tokens can remain valid until expiration. Remove an allowed subject/client
and restart to deny subsequent requests; revoking refresh credentials prevents
future refresh but does not invalidate every issued access token.

Run the read-only public checker before [ChatGPT setup](oauth-chatgpt.md):

```bash
.venv/bin/python scripts/oauth-validate.py https://mcp.example.com https://YOUR_TENANT.REGION.auth0.com/
```

It makes at most four anonymous GETs, caps each response at 64 KiB, uses five-second
HTTP timeouts and a 25-second overall deadline, reports only expected URLs and
field mismatches, and exits nonzero on failure. It never creates tenant resources
or prints credentials/tokens. Passing it does not establish successful login.
