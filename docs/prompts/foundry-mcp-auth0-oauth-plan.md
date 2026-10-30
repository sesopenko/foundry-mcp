# First-class Auth0 OAuth for foundry-mcp

**Implementation plan · researched 29 October 2026**

**Confirmed authentication requirement:** Basic Auth and Auth0 OAuth are mutually exclusive per server instance. Enabling Auth0 makes MCP Basic Auth unavailable. This is an explicit design requirement, not a temporary first-release limitation.

**Repository baseline:** `sesopenko/foundry-mcp`, commit `35b34f80853d6a271cd8cdbb47bacb393067bbd6` (project version `2.2.0`). This is a proposed implementation, not a record of completed changes. Repository files, Auth0 settings, and production services have not been modified. Recheck the baseline before implementation. [R1]

## 1. Decision

Implement the MCP server as an **OAuth protected resource**, using **Auth0 as the external authorization server** and **ChatGPT as the OAuth client**. Auth0 supplies the hosted login, authorization-code flow, consent, signing keys, and token refresh. The project validates access tokens and decides who may use the Foundry bridge. Traefik remains responsible for HTTPS and routing. This follows the MCP separation of roles. [S19]

Use FastMCP's built-in **`Auth0MCPProvider`**, introduced in FastMCP 4.0, with a small project-owned token-policy adapter. Do **not** confuse it with `Auth0Provider`, which turns FastMCP into an OAuth proxy. The direct resource-server provider does not require an upstream OAuth client secret on the MCP server. [S10]

```text
Browser login / consent:
    ChatGPT → Auth0 Universal Login → exact ChatGPT callback

Tool requests:
    ChatGPT → HTTPS / bearer token → Traefik → foundry-mcp
                                                │
                                                ├─ Validate Auth0 access token
                                                ├─ Enforce local GM/client policy
                                                └─ Existing WebSocket RPC → GM browser

Browser bridge:
    GM browser → WSS /ws/foundry → existing separate bridge-token handshake
```

The first supported client profile is **ChatGPT's User-Defined OAuth Client**, registered manually in Auth0. Pre-registration is a supported MCP mechanism; this architecture does not require DCR merely because FastMCP's direct-provider example demonstrates DCR. Registration happens between the client and Auth0, not inside the resource server. [S01][S19]

### Scope of the first release

Deliver one Auth0 issuer, one configured public MCP endpoint, and explicitly approved GM identities. Preserve the existing Basic Auth deployment mode as an alternative to OAuth, not alongside it, and preserve local development mode. Preserve `/mcp/mcp`, `/ws/foundry`, tool names, and tool behavior.

Do not implement a combined Basic-plus-OAuth mode, credential-based selection between authentication methods within one deployment, a second Basic-authenticated route to the same instance, or automatic fallback from Auth0 to Basic Auth. The selected authentication mode applies to the entire MCP surface, including initialization, tool discovery, tool calls, and session operations. Public OAuth discovery metadata is not an alternate route to tool access.

Do not add a local login screen, password database, authorization/token endpoints, refresh-token storage, Pomerium, or an Auth0 Management API dependency. Do not add player access, per-world tenancy, account linking, or a generic identity-provider framework. Supporting other providers later should require a new authentication adapter, not rewriting tools.

**Free-tier constraint:** Auth0's published comparison currently excludes role management from Free. Therefore, this plan does not require Auth0 roles, paid RBAC features, FGA, Organizations, Token Vault, or custom token exchange. The server's subject allowlist is the authoritative GM authorization rule. Confirm actual tenant entitlements outside any temporary trial before rollout. [S09]

## 2. Library choice and dependency prerequisite

| Candidate | Decision |
| --- | --- |
| FastMCP `Auth0MCPProvider` plus `JWTVerifier`/`TokenVerifier` | Preferred. Use the framework's transport authentication and protected-resource discovery, with project policy added at the verified-token boundary. [S10][S16][S17] |
| Auth0's `auth0-fastapi-api` | Useful for ordinary FastAPI endpoints, but choosing it would still require integrating authentication with the mounted MCP transport and implementing its discovery contract. Not the primary integration here. [S21][S19] |
| Authlib directly | Appropriate OAuth primitives, but unnecessary as a new application-level OAuth implementation when FastMCP already provides the integration. Do not build an authorization server just to validate Auth0 access tokens. [S22] |

The repository pins `fastmcp==2.14.1` and `fastapi==0.128.0`. The selected provider is not available at that FastMCP pin, and FastMCP's current security policy marks 2.x unsupported. [R1][S10][S13]

**Initial migration candidates:** `fastmcp==4.1.4` and `fastapi==0.162.0`, the stable releases verified during this research. These are candidate pins, not a tested compatibility claim for this repository. Resolve and test them before committing the resulting lockfile. [S14][S15]

FastMCP 4 requires Starlette 1.x; its migration guide identifies FastAPI 0.133.0 as the first compatible FastAPI release. Upgrading FastMCP alone while keeping FastAPI 0.128.0 is not a viable dependency plan. Python 3.12 can remain the project target; the existing Pydantic 2.12.5 pin meets FastMCP's documented minimum, subject to the actual resolver result. [S12][R1]

Make the dependency migration a separate reviewable change. Read both the 2→3 and 3→4 migration guides, checking decorator behavior, imports, middleware, transport/session behavior, MCP result models, and tests that use HTTP clients. Audit the old `fakeredis` constraint rather than carrying it forward without its original dependency. Keep unrelated package upgrades out unless required for compatibility or security. [S11][S12]

**Migration exit condition:** the existing offline suites and isolated container smoke test pass with OAuth still disabled. Record intentional protocol/model changes separately from business-logic changes. Never resolve a migration failure by silently disabling tests or exposing an unauthenticated fallback.

## 3. Public configuration contract

Add `oauth` to `FOUNDRY_MCP_AUTH_MODE`, retaining `none` and `basic`. This single setting is the exclusive mode selector; it is not a list of methods to enable. Use the following mode contract:

| Selected mode | MCP Basic Auth | Auth0 OAuth | Required behavior |
| --- | --- | --- | --- |
| `basic` | Enabled | Disabled | Require the existing Basic credentials and separate bridge token. Do not construct an Auth0 provider or advertise OAuth support. |
| `oauth` with provider `auth0` | Disabled | Enabled | Require an approved Auth0 access token for protected MCP requests. Reject Basic credentials, even credentials that worked before migration. |
| `none` | Disabled | Disabled | Preserve existing explicit local/development behavior and its separate development-token guards. Never select this mode as an authentication-error fallback. |
| Combined values such as `basic_and_oauth`, `both`, or `basic,oauth` | Not supported | Not supported | Reject configuration at startup. |

Start with the following proposed OAuth configuration surface:

```dotenv
FOUNDRY_MCP_AUTH_MODE=oauth
FOUNDRY_MCP_OAUTH_PROVIDER=auth0
FOUNDRY_MCP_PUBLIC_URL=https://mcp.example.com
FOUNDRY_MCP_OAUTH_ISSUER=https://YOUR_TENANT.REGION.auth0.com/
FOUNDRY_MCP_OAUTH_ALLOWED_SUBJECTS=auth0|REPLACE_WITH_YOUR_USER_ID
FOUNDRY_MCP_OAUTH_ALLOWED_CLIENT_IDS=REPLACE_WITH_CHATGPT_AUTH0_CLIENT_ID
FOUNDRY_MCP_BRIDGE_TOKEN=REPLACE_WITH_SEPARATE_BROWSER_SECRET
FOUNDRY_MCP_DEV_EXECUTION=false
# Do not supply FOUNDRY_MCP_BASIC_USERNAME or FOUNDRY_MCP_BASIC_PASSWORD.
```

These are proposed variable names, not variables that the current release supports. Values are placeholders. The Auth0 user ID is an exact subject identifier; social-login identities may use a different prefix.

For this release, accept an HTTPS **origin** in `FOUNDRY_MCP_PUBLIC_URL`, without a mount prefix, query, fragment, user information, or trailing path. Derive the canonical resource by appending `/mcp/mcp` exactly once:

```text
Public origin:         https://mcp.example.com
MCP resource:          https://mcp.example.com/mcp/mcp
Auth0 API identifier:  https://mcp.example.com/mcp/mcp
Expected JWT audience: https://mcp.example.com/mcp/mcp
Required API scope:    foundry:gm
```

One derived value should drive the metadata resource identifier and expected token audience. Do not expose several independently configurable audience/path values that can drift apart. The Auth0 API identifier must use that same value. Preserve the exact configured/discovered issuer, including its trailing slash; verify discovery returns the expected issuer. [S01][S04]

Startup validation must reject unknown modes/providers, missing allowlists, missing bridge credentials, malformed URLs, and OAuth combined with development execution. Keep the existing fail-closed treatment of incomplete production configuration. [R2]

**Mutually exclusive configuration:** in `oauth` mode, reject any nonempty `FOUNDRY_MCP_BASIC_USERNAME` or `FOUNDRY_MCP_BASIC_PASSWORD`; do not silently ignore retained credentials. In `basic` mode, reject nonempty `FOUNDRY_MCP_OAUTH_*` settings, including the provider, issuer, and identity/client allowlists. In `none` mode, reject production Basic credentials, the production bridge token, and nonempty OAuth-specific settings. Empty optional values may count as unset, but required values must still be nonempty for the selected mode. Error messages must identify conflicting variable names without printing secrets. Supplying `FOUNDRY_MCP_OAUTH_PROVIDER=auth0` does not implicitly select OAuth or override an incompatible mode.

The bridge token, private-PDF upload credential, and TLS/trust controls are separate from MCP Basic credentials. They remain required wherever their existing production features require them, including in OAuth mode. Do not remove those protections while removing Basic Auth.

Construct only the authentication stack selected by validated configuration. Invalid configuration prevents startup; Auth0 discovery/JWKS failures or token rejection must never activate Basic Auth or unauthenticated mode. Changing modes requires an explicit configuration change and process restart/recreation, not an incoming request or an automatic recovery path.

The server stores no OAuth client secret. Its allowed client ID is only a public authorization-policy value; ChatGPT holds the confidential client's secret. Keep the bridge token private and distinct from all other credentials.

Use a single constant for the initial `foundry:gm` scope. It authorizes the existing GM-level tool surface, including private information and any mutating tools already exposed. It is **not** a read-only scope. Finer-grained scopes require a later, explicit tool-permission design.

## 4. Auth0 configuration runbook

Create `docs/oauth-auth0.md` with dashboard-first instructions. Do not make tenant administration an automatic server-startup operation, and do not commit tenant secrets or real tokens.

### Tenant and login

Enable **Resource Parameter Compatibility Profile** and **Include Issuer in Authorization Responses**. The resource compatibility setting lets the standard MCP `resource` parameter identify the API without a custom audience-translation proxy. Do not set a tenant-wide default audience as a workaround. [S04]

Choose an Auth0 database or social login connection and enable it for the manually registered application. Auth0 provides the login interface; no additional self-hosted identity provider is required. Do not automatically enable tenant-wide dynamic registration or broaden connections for third-party clients merely because a DCR-oriented tutorial does so. [S05]

### API registration

Create an API named `foundry-mcp` with the exact canonical resource URL as its identifier. Select RS256 signed access tokens and the RFC 9068 access-token profile (`rfc9068_profile`). Define the `foundry:gm` API scope with a description that makes its GM-level access clear. Leave the additional `permissions` claim unnecessary for this implementation. [S05][S08]

Do not make Auth0 role assignment a prerequisite. With RBAC disabled, requested API scopes do not establish that a particular user should be a GM; local subject authorization must still deny every user outside the configured allowlist. Later RBAC support may narrow issuance, but must not replace that first-release boundary accidentally. [S08]

### ChatGPT application

Register a **Regular Web Application** representing ChatGPT's OAuth client. Select authorization-code and refresh-token grants, and configure token endpoint authentication as **`client_secret_post`**. ChatGPT must use the same method. Do not use an M2M application or the client-credentials grant for the interactive user login. [S06]

Copy the exact callback URI shown by the current ChatGPT configuration page into Auth0's Allowed Callback URLs. Do not reconstruct it from the truncated screenshot, use a wildcard, or point it at a callback on `foundry-mcp`. Complete registration and then record that application's public client ID in the server allowlist. [S01]

Enable **Allow Offline Access** on the API and configure refresh-token expiration/rotation on the application. Request `offline_access` from ChatGPT and verify the provider advertises/supports it. Choose a short access-token lifetime appropriate for this personal service; 15 minutes is a proposed starting policy, with refresh and reconnect behavior tested before production. ChatGPT, not the MCP server, performs refresh exchanges. [S07][S03]

Capture the exact Auth0 `sub` for the owning account in the server configuration. A successful Auth0 login, matching email address, or possession of the scope alone must never grant access. Where practical, disable public signup for a personal database connection, but treat this only as defense in depth.

## 5. Implement the authentication boundary

Add a small package such as `foundry_mcp_server/auth/`, with configuration-independent policy tests. Suggested responsibilities:

| File | Responsibility |
| --- | --- |
| `auth/factory.py` | Construct only the selected provider from validated settings; return no OAuth provider only in an explicitly selected non-OAuth mode. Never build or activate both production authentication stacks. |
| `auth/auth0.py` | Build `Auth0MCPProvider`, obtain trusted discovery/JWKS configuration, and wire the verifier. |
| `auth/policy.py` | Enforce required claims, exact subject/client allowlists, and granted-scope semantics after library signature verification. |
| `config.py` | Parse OAuth settings, reject conflicting modes/credentials, and expose shared production-authentication predicates without enabling both MCP authentication methods. |
| `mcp_server/server.py` | Pass the provider into `FastMCP(..., auth=provider)` before constructing its HTTP app. |

This is a responsibility map, not a requirement to create a large provider framework. Prefer composition around FastMCP's public verifier interface over copied OAuth or cryptographic implementation.

### Verification and policy order

Use the library to verify the signature with trusted Auth0 JWKS, an explicit RS256 algorithm, exact issuer, and explicit canonical audience. Then apply project policy to the **verified** claims before returning an accepted access token. Require a valid expiration, a nonempty subject, the expected RFC 9068 client identity, and the agreed access-token profile. Validate `nbf` when present and apply a documented small clock-skew policy consistently. Reject malformed or missing required claims, ID tokens, and tokens for other APIs. [S17][S19]

The selected FastMCP verifier's source allows an absent expiration and should not be assumed to enforce every application-required claim. Add focused claim validation and tests rather than assuming that “JWT signature verified” means “appropriate token for this server.” Use established JOSE claim-validation facilities where appropriate; do not reimplement signature verification. [S17]

Check `sub` against `FOUNDRY_MCP_OAUTH_ALLOWED_SUBJECTS` and the verified client identity against `FOUNDRY_MCP_OAUTH_ALLOWED_CLIENT_IDS`. For the selected RFC 9068 profile, require `client_id`; do not silently accept another claim dialect. Adding legacy token profiles should be an explicit tested extension.

Check the actual granted `scope` for `foundry:gm`. Do not substitute a user's full `permissions` list. Auth0 distinguishes requested/granted scopes from all assigned permissions, and FastMCP's Auth0-specific verifier merges those claims. The project adapter must preserve the stricter granted-scope requirement. A token containing `permissions: ["foundry:gm"]` but lacking that OAuth scope must fail. [S08][S16]

**Audience-binding trap:** supplying a custom `token_verifier` to `Auth0MCPProvider` disables its default audience auto-binding. Explicitly configure the canonical audience on the underlying verifier, and test it. Otherwise a seemingly harmless policy customization could remove the audience check. [S16]

Let transport middleware enforce authentication before MCP initialization, discovery, or execution. Use 401 Bearer challenges for missing/invalid credentials, and the framework's insufficient-scope handling for valid tokens without the required scope. Test for the expected 403/`insufficient_scope` response; do not accidentally convert all scope failures into repeated login prompts. Verify where `required_scopes` is enforced in the pinned provider/middleware and avoid rejecting them prematurely in the cryptographic verifier.

In OAuth mode, a protected request carrying `Authorization: Basic ...` must return 401 with a Bearer challenge and must not reach tool or session handlers. Do not check Basic credentials, issue a Basic challenge, redirect to a Basic-authentication gateway, or attempt another authentication method after a Bearer failure. Reject ambiguous/duplicate Authorization headers rather than trying each supplied credential. In Basic mode, retain the existing Basic challenge and reject OAuth Bearer credentials; do not contact Auth0 to authenticate them.

Apply authorization to every protected HTTP request, including session operations when the negotiated protocol uses sessions. A session ID must not substitute for a bearer token. Subject/client policy denial must never reach tool code, regardless of whether the chosen supported middleware reports 401 or 403. Define and test that response contract rather than leaking identity details.

Cache JWKS using the library's bounded refresh behavior, keep outbound timeouts finite, and fail closed when a key cannot be verified. Test rotation, unknown key IDs, repeated failures, and Auth0 outages. Never derive discovery/JWKS URLs from an unverified token's issuer. Avoid logging tokens, authorization headers, complete claim sets, client secrets, or refresh credentials. [S17]

## 6. Routing, metadata, and existing protections

The current server creates an MCP app with `path="/mcp"` and mounts it at `/mcp`, producing `/mcp/mcp`. Simply attaching an auth provider to that layout risks placing discovery endpoints under the wrong external prefix. [R3][R4]

Prefer configuring the MCP HTTP app with `path="/mcp/mcp"`, then mounting it at `/` **after** explicit FastAPI routes such as `/health` and `/ws/foundry`. Preserve the existing combined lifespan for MCP and the PDF library. Verify this exact composition with the chosen versions before adopting it; do not introduce an endpoint migration as a side effect. [S18]

Make protected-resource metadata public at the correct externally visible location, normally:

```text
/.well-known/oauth-protected-resource/mcp/mcp
```

A root `/.well-known/oauth-protected-resource` alias may serve the same document if needed for compatibility. Its `resource` remains the full `/mcp/mcp` URL. Configure the provider to generate metadata, rather than maintaining inconsistent copies. The 401 challenge must point to a real public metadata URL. Metadata must advertise the exact Auth0 issuer and the `foundry:gm` API scope. [S19]

Auth0 owns authorization-server discovery, `/authorize`, and `/oauth/token`. The selected provider also offers an authorization-metadata mirror; if exposed, its issuer and endpoints must continue to describe Auth0. Do not advertise `foundry-mcp` as a token issuer or invent local authorization/token/registration handlers. [S16]

### Preserve the separate browser and PDF trust boundaries

**Required fix:** `main.py` currently sets `production_auth = settings.auth_mode == "basic"`. Replace this coupling with a shared predicate that is true when either Basic or OAuth production mode is selected. This predicate means the browser bridge requires production authentication; it must not enable both MCP authentication methods. Keep the browser's first-message bridge-token handshake, timeout, size limit, constant-time comparison, authentication acknowledgment, and single-GM connection rule unchanged. Never accept an Auth0 bearer token in place of that bridge credential. [R3]

`pdf/config.py` also accepts only Basic Auth or development authentication when enabling the private PDF library. Extend its authenticated-GM predicate deliberately for OAuth, while retaining the trusted-GM acknowledgement, separate upload capability, path checks, and TLS requirements. Update the WebSocket upload `secure` calculation to recognize OAuth production mode without relaxing any other condition. [R3][R5]

Keep the Foundry module's existing production-authentication settings and wire protocol. No Auth0 credentials belong in Foundry world settings. Verify module compatibility; require a module change only if testing establishes a genuine protocol dependency.

Leave Basic Auth enforcement active only in Basic mode and development-token checks active only in their existing development mode. In OAuth mode, bypass or omit the old middleware's Basic credential-checking branch entirely; do not let it emit a Basic challenge or accept Basic credentials as a fallback. Expose OAuth discovery routes only in OAuth mode; do not advertise an available Auth0 flow in Basic mode. Do not expose an alternate path, listener, hostname, or proxy credential-translation route that restores Basic access to the same OAuth-enabled instance. Private-PDF TLS checks remain independent of the selected MCP authentication method.

## 7. ChatGPT configuration and tool metadata

Create `docs/oauth-chatgpt.md`, tied to the field labels in the supplied screenshots. The current OpenAI guide describes a Plugins flow, while existing accounts may still expose legacy Apps screens. Document both entry points briefly without making navigation labels part of the protocol implementation. No custom visual app interface is required for a tool-only MCP server. [S02][S03]

| ChatGPT field | First-release value |
| --- | --- |
| MCP server URL | Canonical public endpoint ending `/mcp/mcp`. |
| Authentication | OAuth; not mixed or unauthenticated discovery. |
| Registration method | User-Defined OAuth Client. |
| Client ID / secret | Credentials of the manually registered Auth0 application. |
| Token endpoint auth method | `client_secret_post`, matching Auth0. |
| Callback URL | Copy the complete value from ChatGPT into Auth0. |
| Base scopes | `foundry:gm` and `offline_access`. |
| Default scopes | `foundry:gm`; avoid unrelated permissions. |
| Auth / Token URL | Discovered Auth0 authorization and token endpoints. |
| Authorization server base | Exact Auth0 issuer. |
| Resource | Canonical full MCP resource URL. |
| Registration URL | Unused for this registration method. |
| PKCE | S256 enabled and advertised in Auth0 metadata. |
| OIDC | Optional for the initial connection; discovery still comes from Auth0. |

OpenAI may request OIDC scopes advertised by the provider. Ensure advertised `openid`/`email`/`profile` scopes are usable for the chosen application when requested; do not treat them as the API's GM permission. Enabling ChatGPT's optional OIDC identity features is separate from protecting tools with OAuth access tokens. [S01]

Verify tool descriptions and annotations remain accurate after the framework upgrade. Use the documented OAuth `securitySchemes` metadata where appropriate, consistently declaring `foundry:gm`, without adding a `noauth` alternative. Keep server-side enforcement authoritative. Preserve truthful read-only/destructive annotations; an OAuth scope does not make a write tool read-only. [S01][S02]

Document CIMD as a later interoperability option, not a prerequisite. Do not add project-owned DCR or a second OAuth-proxy architecture to this implementation.

## 8. Automated test contract

Add focused offline tests using temporary signing keys, mock/local JWKS and discovery responses, and isolated configuration. Ordinary CI must not require an Auth0 account, credentials, internet access for authentication, or a live Foundry game. Use an isolated synthetic bridge only in the existing isolated smoke-test environment.

| Area | Required cases |
| --- | --- |
| Configuration | Every valid mode; missing/empty allowlists; malformed public URL/issuer; unsupported provider; partial settings; OAuth + development; OAuth with either or both Basic credential variables fails startup; Basic with nonempty OAuth-specific settings fails startup; `none` with production/OAuth credentials fails startup; combined-mode values rejected; no silent fallback. |
| JWT validity | Accepted valid token; bad signature; wrong issuer; wrong/absent audience; expired/missing/malformed expiration; future `nbf`; missing subject/client; wrong algorithm; ID token; malformed bearer header; duplicate Authorization headers. |
| Authorization | Approved subject + client + scope succeeds; wrong user fails even after successful login; wrong client fails; absent scope fails; permissions-only token fails; machine identity is not implicitly a GM. |
| Discovery | In OAuth mode, public metadata works without Basic credentials; resource/issuer/audience match exactly; Bearer challenge URL resolves through the production path layout; malformed discovery or issuer mismatch fails closed. In Basic mode, OAuth discovery is not advertised or served as an active integration. |
| HTTP boundary | Initialization, tool listing, calls, and supported session methods require the selected mode's credentials; no reusable unauthenticated session bypass. Formerly valid and invalid Basic credentials both fail with 401/Bearer in OAuth mode; valid Auth0 Bearer credentials fail with 401/Basic in Basic mode. Never emit a combined Basic/Bearer challenge. |
| Exclusivity and outages | Only the selected authentication stack is constructed; non-OAuth modes make no Auth0 authentication/discovery/JWKS calls. Auth0 outage, expired token, invalid token, or policy denial never enables Basic or anonymous access. No alternate Basic route exists on the OAuth-enabled instance. |
| Mode transitions | Restart/recreate Basic → OAuth and OAuth → Basic using clean, mode-specific configurations. Old credentials and pre-switch session IDs cannot bypass the new mode; incomplete/conflicting configuration prevents startup. Preserve the independent browser bridge handshake across both transitions. |
| Key handling | JWKS cache, key rotation, throttled unknown-key refresh, timeout, stale/missing key, malformed response; no secret-bearing logs. |
| Existing bridge | Correct browser token succeeds; wrong/missing token and duplicate GM fail in both production modes; first-message size/time limits unchanged. |
| Private PDF | OAuth recognized only with explicit GM trust; separate upload credential still required; TLS and upload guards preserved. |
| Regression | Existing Python/JavaScript suites, tool schemas/results, evaluation tracing, lifespan shutdown, Basic mode, local/development mode, Docker smoke test. |

Include negative tests that assert the tool handler was **not called**, rather than checking only an HTTP status. Keep cryptographic verification exercised in integration tests; mocks that automatically accept every token cannot establish this boundary.

## 9. Deployment and live acceptance

Add a separate OAuth deployment example and environment template rather than silently changing the existing Basic Auth example. The OAuth template must not inject `FOUNDRY_MCP_BASIC_USERNAME` or `FOUNDRY_MCP_BASIC_PASSWORD`; the Basic template must not inject OAuth-specific settings. Do not layer an OAuth override over the Basic Compose environment in a way that retains Basic credentials or required-value interpolation. Document inspection of the resolved environment privately, without publishing secrets.

Document the cutover explicitly: stop/drain the old instance, select `oauth` and provider `auth0`, remove Basic credentials from the effective process/container environment, supply the required OAuth and shared bridge settings, and recreate the process/container. Existing Basic-only clients stop working against this instance after the switch; they must be reconfigured for supported OAuth or remain disconnected. Restarting with unchanged container environment is not a substitute for recreating it with the new configuration. Do not keep a compatibility Basic endpoint or proxy that exchanges Basic credentials for an accepted OAuth token.

Rollback is another explicit mode switch: stop the OAuth instance, restore the known-good Basic image/configuration and credentials, remove OAuth-specific settings from the effective environment, and recreate the process/container. Basic becomes available again only after that operator-controlled rollback. Never automatically roll back authentication in response to an Auth0 outage. Retain rollback secrets privately outside the active OAuth deployment environment.

In OAuth mode, Traefik must route the MCP endpoint and public discovery paths without a Basic Auth or browser-login middleware, preserve Bearer and challenge headers, and support the existing streaming transport. Remove any Basic header injection or credential-translation configuration for this instance. Keep the backend private so public requests cannot bypass the intended TLS/network boundary. Route `/ws/foundry` without requiring ChatGPT's OAuth token. Keep health details internal or deliberately minimized.

Generate public URLs from validated configuration, not arbitrary Host or Forwarded headers. The current entrypoint disables proxy-header trust; do not change that to trust every sender. For the private PDF TLS-proxy setting, document the actual network restriction and TLS termination that justify enabling it. [R3][R5]

### Live acceptance sequence

1. Run all offline and isolated container checks. Deploy a staging instance using a distinct Auth0 API identifier and client registration; use the existing tenant if its free plan has only one tenant. Do not require a paid second environment or change production traffic.
2. Inspect the public metadata and Bearer challenge through Traefik. Verify issuer, audience, resource URL, scopes, S256, and token auth method against the real Auth0 discovery document.
3. Test authorization-code + PKCE with MCP Inspector using a separately registered staging client and exact callback. Keep the test client ID separate from production's allowlist.
4. Create the ChatGPT connection, log in to Auth0, complete authorization, list tools, and call a harmless diagnostic such as `get_bridge_versions`. Confirm no Auth0 tokens or client secrets reach the browser bridge or logs.
5. Exercise access-token expiry and refresh, server restart, disconnect/reconnect, a second unapproved Auth0 user, and removal of an approved user/client from the local configuration. Confirm that formerly valid Basic credentials fail through Traefik and at the isolated backend, with a Bearer-only challenge and no tool execution. In staging, simulate Auth0 unavailability and verify that Basic/anonymous access remains unavailable. Retest any metadata changes with a fresh connection if the client caches discovery.
6. Only after those checks, switch the production instance during a maintenance window. Keep the previous image/configuration and Basic client settings for rollback. Do not run a second competing GM bridge against the live world as a shortcut.

Do not claim immediate JWT revocation through Auth0 logout. With local JWT verification, already-issued access tokens may remain valid until expiry unless local policy rejects them. Removing an allowed subject/client and restarting/reloading policy provides a project-controlled denial path for subsequent requests; test its timing. Revoking a refresh token prevents future refreshes but is not equivalent to revoking every existing access token. [S07]

No login/token database or new persistent OAuth volume is required for this direct resource-server design. Existing PDF storage is unaffected. A cold start may depend on Auth0 discovery/JWKS availability; record timeout and failure behavior rather than promising outage-independent startup.

## 10. Delivery order and definition of done

**Change 1 — maintained framework baseline.** Update reviewed exact pins and lockfile, adjust only necessary compatibility code, run existing tests, and record smoke-test results. Do not enable OAuth in this change.

**Change 2 — OAuth feature and regression protection.** Add validated, mutually exclusive authentication configuration, Auth0 provider factory, verified-claim policy, discovery routing, bridge/PDF predicate fixes, and offline tests. Preserve existing client-facing endpoints and separately selected non-OAuth modes. Include negative tests for conflicting configuration, cross-mode credentials, and forbidden fallback.

**Change 3 — operator documentation and verified deployment.** Add Auth0 and ChatGPT runbooks, OAuth-specific Compose/environment examples, a read-only validation helper, and a verification record. Update README/operations and agent guidance. Use the repository's established release process; do not push, publish, or mutate the production tenant automatically.

The validation helper should report non-secret expected URLs and metadata mismatches, make bounded read-only requests, exit nonzero on failure, and never print live credentials or JWTs. It must not create Auth0 applications or change tenant settings.

**Definition of done:** ChatGPT completes Auth0 login and token refresh, authorized calls reach the unchanged tool implementations, unapproved callers never reach tools, discovery works through Traefik, the separate GM browser/PDF protections remain intact, regression tests pass, and the documentation distinguishes automated evidence from operator-performed live checks. Exactly one MCP authentication mode is active per instance: Auth0-enabled instances never accept Basic Auth, Basic instances never accept OAuth tokens, mixed configuration fails startup, and authentication failures/outages never change the selected mode. Cutover and rollback are documented and tested as explicit, restart/recreation-based mode changes.

Unresolved until implementation: the exact lockfile solution and migration diff; the tenant's real feature availability and metadata; and successful end-to-end ChatGPT login/refresh against this application. These are explicit acceptance gates, not assumptions already proven by documentation.

## Sources and implementation references

All external references below are primary documentation or upstream source. Documentation was consulted on 29 October 2026. Code links use the inspected repository snapshot or the selected upstream release where practical.

| Reference | What to read |
| --- | --- |
| [S01] | OpenAI: Authentication — discovery, PKCE, client registration, callbacks, scopes, and tool authentication metadata. |
| [S02] | OpenAI: Custom MCP server integration and connection/testing workflow. |
| [S03] | OpenAI Help: Connecting custom MCP servers; current and legacy UI, refresh-token requirements. |
| [S04] | Auth0: Resource Parameter Compatibility Profile and issuer response settings. |
| [S05] | Auth0: Authorization for Your MCP Server. Adapt the direct-token pattern; do not copy all DCR/RBAC prerequisites into this personal-use profile. |
| [S06] | Auth0: Confidential and public application types and token authentication methods. |
| [S07] | Auth0: Refresh tokens, offline access, and rotation. |
| [S08] | Auth0: API RBAC and the distinction between granted scopes and assigned permissions. |
| [S09] | Auth0: Current pricing/feature comparison; verify actual tenant entitlements. |
| [S10] | FastMCP: Auth0 integration; direct `Auth0MCPProvider` versus proxy `Auth0Provider`. |
| [S11] | FastMCP: Migration from version 2. |
| [S12] | FastMCP: Migration from version 3, including FastAPI/Starlette requirements. |
| [S13] | FastMCP 4.1.4 security policy and supported versions. |
| [S14] | FastMCP 4.1.4 release. |
| [S15] | FastAPI 0.162.0 release. |
| [S16] | FastMCP 4.1.4 Auth0 provider source, including custom-verifier audience behavior. |
| [S17] | FastMCP 4.1.4 JWT verifier source; check claims, scopes, cache, and failure handling. |
| [S18] | FastMCP: FastAPI integration and application lifespan. |
| [S19] | MCP authorization specification, 2026-07-28. |
| [S21] | Auth0's official FastAPI API library. |
| [S22] | Authlib documentation. |
| [R1] | Inspected project dependency pins and version. |
| [R2] | Inspected project runtime configuration. |
| [R3] | Inspected FastAPI middleware, mounting, WebSocket authentication, and lifespan. |
| [R4] | Inspected FastMCP initialization and HTTP-app construction. |
| [R5] | Inspected private PDF authentication/TLS configuration. |

[S01]: https://developers.openai.com/plugins/build/auth
[S02]: https://developers.openai.com/api/docs/guides/custom-mcp-server
[S03]: https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt
[S04]: https://auth0.com/ai/docs/mcp/guides/resource-param-compatibility-profile
[S05]: https://auth0.com/ai/docs/mcp/get-started/authorization-for-your-mcp-server
[S06]: https://auth0.com/docs/get-started/applications/confidential-and-public-applications
[S07]: https://auth0.com/docs/secure/tokens/refresh-tokens
[S08]: https://auth0.com/docs/get-started/apis/enable-role-based-access-control-for-apis
[S09]: https://auth0.com/pricing
[S10]: https://gofastmcp.com/integrations/auth0
[S11]: https://gofastmcp.com/getting-started/upgrading/from-fastmcp-2
[S12]: https://gofastmcp.com/getting-started/upgrading/from-fastmcp-3
[S13]: https://github.com/PrefectHQ/fastmcp/blob/v4.1.4/SECURITY.md
[S14]: https://github.com/PrefectHQ/fastmcp/releases/tag/v4.1.4
[S15]: https://github.com/fastapi/fastapi/releases/tag/0.162.0
[S16]: https://github.com/PrefectHQ/fastmcp/blob/v4.1.4/fastmcp_slim/fastmcp/server/auth/providers/auth0.py
[S17]: https://github.com/PrefectHQ/fastmcp/blob/v4.1.4/fastmcp_slim/fastmcp/server/auth/providers/jwt.py
[S18]: https://gofastmcp.com/integrations/fastapi
[S19]: https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization
[S21]: https://github.com/auth0/auth0-fastapi-api
[S22]: https://docs.authlib.org/
[R1]: https://github.com/sesopenko/foundry-mcp/blob/35b34f80853d6a271cd8cdbb47bacb393067bbd6/pyproject.toml
[R2]: https://github.com/sesopenko/foundry-mcp/blob/35b34f80853d6a271cd8cdbb47bacb393067bbd6/foundry_mcp_server/config.py
[R3]: https://github.com/sesopenko/foundry-mcp/blob/35b34f80853d6a271cd8cdbb47bacb393067bbd6/foundry_mcp_server/main.py
[R4]: https://github.com/sesopenko/foundry-mcp/blob/35b34f80853d6a271cd8cdbb47bacb393067bbd6/foundry_mcp_server/mcp_server/server.py
[R5]: https://github.com/sesopenko/foundry-mcp/blob/35b34f80853d6a271cd8cdbb47bacb393067bbd6/foundry_mcp_server/pdf/config.py
