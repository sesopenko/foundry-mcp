# Connect ChatGPT using Auth0

First complete [Auth0 setup](oauth-auth0.md). This feature ships in v2.3.0 and
[live acceptance](oauth-verification.md) is still required.

In the current [custom MCP flow](https://developers.openai.com/api/docs/guides/custom-mcp-server),
open **Plugins → + → Add custom MCP server**, then install the resulting plugin.
Accounts with legacy Apps screens may expose **Settings → Apps → Create** instead.
Follow the labels available in your account; no custom visual interface is needed.

| Field | Value |
| --- | --- |
| MCP server URL | `https://mcp.example.com/mcp/mcp` |
| Authentication | OAuth (initialization/tool listing/calls protected; OAuth metadata public) |
| Registration method | User-Defined OAuth Client |
| Client ID / secret | Manually registered Auth0 Regular Web Application credentials |
| Token endpoint auth method | `client_secret_post` |
| Callback URL | Copy the complete displayed URI into Auth0 Allowed Callback URLs |
| Base scopes | `foundry:gm offline_access` |
| Default scopes | `foundry:gm` |
| Auth / Token URL | Discovered Auth0 `/authorize` and `/oauth/token` endpoints |
| Authorization server base | Exact Auth0 issuer, including trailing slash |
| Resource | Full canonical MCP server URL above |
| Registration URL | Unused |
| PKCE | S256 |
| OIDC | Optional; discovery belongs to Auth0 |

If ChatGPT requests advertised `openid`, `email` or `profile`, ensure the Auth0
application supports them. They do not confer GM access. CIMD is a future
interoperability option; project-owned DCR is not implemented.

The server protects initialization, tool listing and calls with HTTP OAuth.
It publishes each tool's required `foundry:gm` scope via the documented
[`_meta.securitySchemes` compatibility field](https://developers.openai.com/plugins/reference).
The pinned Python protocol model drops unknown top-level `securitySchemes` fields;
acceptance of the compatibility metadata must be verified with the real client.
Read-only/destructive annotations are preserved. Scope does not make writes safe
or read-only. There is no anonymous or Basic alternative on this instance.

Start a fresh connection after changing discovery. Complete login and call
`get_bridge_versions`, then verify expiration and refresh, restart/reconnect,
and denial for an unapproved Auth0 user. Check the
[OpenAI authentication requirements](https://developers.openai.com/plugins/build/auth)
if discovery or callbacks fail. Do not paste JWTs, client secrets or callback
codes into logs or issue reports. The server never receives refresh tokens.
