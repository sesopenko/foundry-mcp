# Local JavaScript exploration

`execute_javascript(code)` runs an async function body inside a GM browser.
It supports `await`, explicit `return`, and Foundry globals. It can modify or
remove world data and access everything available to that browser. Use a
**disposable development world**, never your campaign world.

The tool is absent from MCP discovery by default. The server must explicitly
opt in, authenticate the MCP caller, and authenticate one authorized browser.
The browser separately checks its development setting and current GM status.
The browser credential grants authority; a claimed client name or GM flag
sent over the network does not. Keep credentials private and separate.

## Configure the server

Generate two distinct random credentials (for example, run
`.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))'` twice).
Place them in a private, gitignored `.env.mcp` file:

```dotenv
FOUNDRY_MCP_DEV_EXECUTION=true
FOUNDRY_MCP_CALLER_TOKEN=replace-with-first-random-credential
FOUNDRY_MCP_BROWSER_TOKEN=replace-with-second-random-credential
FOUNDRY_MCP_EXECUTION_TIMEOUT=15
```

Tokens must each contain at least 32 characters. Invalid development
configuration stops startup. The timeout accepts finite values greater than
zero and at most 120 seconds.

Protect the file with `chmod 600 .env.mcp`. The updated service template binds
to `127.0.0.1` and loads this file. Run `./scripts/server.sh install` to update an
existing installed unit, then `./scripts/server.sh restart`. Foreground launches
do not load this file automatically; export the variables before launching.

Configure your MCP client to send
`Authorization: Bearer <FOUNDRY_MCP_CALLER_TOKEN>` on every request to
`http://127.0.0.1:8000/mcp/mcp`, including discovery. Reconnect your MCP client
when changing tool registration. For this repository's Codex setup,
`./scripts/codex.sh` loads the caller token from `.env.mcp`, and the project
configuration uses `bearer_token_env_var = "FOUNDRY_MCP_CALLER_TOKEN"`.
Launch a new session through that script after enabling exploration. Other
launch methods must provide this environment variable themselves.

Development mode rejects non-loopback HTTP and WebSocket peers even if the
server was launched on another interface. This first implementation supports
only a browser and bridge on the same machine. Do not expose it through a
reverse proxy, SSH forward, or shared host: such arrangements can make remote
traffic appear local. Remote development requires additional authenticated
transport and deployment access controls. In development mode the same local Bearer authentication protects all MCP
tools. Production Basic Auth is a separate mode; see the operations guide.

## Configure the GM browser

Reload Foundry to load the updated module. In Module Settings set the MCP
WebSocket URL to `ws://localhost:8000/ws/foundry` (or a loopback `wss://` endpoint
appropriate for an HTTPS page). Before enabling execution, use the browser
console to store the browser credential in the test world's settings:

```javascript
await game.settings.set("foundry-mcp", "browserToken", "your-browser-credential");
```

This reconnects the bridge without reloading the page. The credential is deliberately hidden from the ordinary
settings UI and is not sent in the URL. It is stored by Foundry world settings;
other code running in this browser can read it. Then enable **Enable development
JavaScript execution (GM only)** in Module Settings; this reconnects again. The
credential is sent as the first WebSocket message. The server rejects missing
or incorrect credentials and a second authenticated GM socket. Close an old
GM tab before connecting another. Reconnects use the existing backoff policy.

## Use and verify

Call `execute_javascript` with this function body:

```javascript
return { foundryVersion: game.version, world: game.world.title };
```

The result has `foundryVersion` plus a `value` snapshot. Objects use
`{$type, properties, truncated}`, arrays use `{$type: "Array", values, truncated}`,
and Maps/Sets retain their type and bounded entries. Functions, undefined,
BigInts, accessors, circular references, and non-finite numbers have tagged
representations. Errors include bounded messages and an optional stack.

Snapshots traverse at most five levels, 50 entries per container, and roughly
1,000 nodes. Strings are clipped to 1,000 UTF-16 units, with a cumulative
20,000-byte string budget. A snapshot over 60,000 UTF-8 bytes is replaced by a
truncation marker; the server rejects WebSocket messages over 65,536 bytes.
Source code is limited to 32,768 UTF-8 bytes. Properties are inspected through
descriptors without invoking getters, `toJSON`, or `toObject`. For a document,
explicitly return `actor.toObject()` when its contents are appropriate to expose.
Serialization traps produce an `Unserializable` marker. Proxy traps and
arbitrary execution itself can still run code; this is not a sandbox.

Failures distinguish invalid parameters, authorization, missing clients,
compilation, runtime, serialization, transport, and timeout errors. Browser
errors preserve `{error: {type, message}}` in MCP tool error text, plus `stack`
when it is available as an own string-valued data property. Messages and stacks
are each clipped to 2,000 UTF-16 units. Accessor-backed, missing, or non-string
stacks are omitted; getters on thrown objects are never invoked to obtain them.
Native errors may therefore lack a returned stack on engines such as Node 22
whose stack property is an accessor. Stack traces are an
[engine-specific facility](https://v8.dev/docs/stack-trace-api/), not a required
field. Error type and message remain available for recovery.
The server logs a SHA-256 source fingerprint, byte count, and execution outcome;
raw source and results are omitted to avoid leaking arbitrary embedded secrets.
Returned values and error stacks may contain secrets: choose exploration code
carefully. Timeout does **not** terminate JavaScript, undo mutations, or stop
an infinite synchronous loop from freezing the browser.

Disable execution by setting `FOUNDRY_MCP_DEV_EXECUTION=false`, restarting the
service, and turning off the browser development setting. Clear the stored
browser token with `game.settings.set("foundry-mcp", "browserToken", "")`.

## Validation

Run `./scripts/test.sh` for both suites. Tests cover authentication, default tool
visibility, socket ownership and cleanup, execution, structured errors,
getters, unusual values, and serialization bounds. Node tests use representative
objects rather than Foundry internals. Live Foundry acceptance requires the
opt-in setup above and a disposable world; compatibility with an installed
Foundry version or game system is not implied by these tests.
