# MCP ↔ Foundry VTT WebSocket Bridge Architecture

## Overview

The nine [selective read tools](selective-reads.md) use explicit Pydantic request
and response validation at FastMCP. Actor/Item projections retain private validated
source witnesses between browser and Python, then publish only the checked compact
result. No extra agent/model call or new game-state cache is involved.

This document describes the architecture and design of a system that allows a Large Language Model (LLM) to interact synchronously with a Foundry VTT game via the Model Context Protocol (MCP).

The system consists of:
- A **Python MCP proxy server**
- One or more **Foundry VTT browser clients**
- A **WebSocket-based RPC bridge** between them

The Python server exposes MCP tools to the LLM and forwards tool calls to the Foundry browser runtime, which is the authoritative source of game state.

---

## High-Level Architecture

```
LLM
 │
 │ HTTP (MCP)
 ▼
Python Server (FastAPI + FastMCP)
 │
 │ async RPC
 ▼
WebSocket Connection
 │
 ▼
Foundry VTT Module (Browser / Electron Runtime)
```

Key properties:
- Single Python runtime
- Single async event loop
- Browser executes Foundry APIs
- Python orchestrates and validates requests
- LLM experiences synchronous tool calls

---

## Components

### 1. Python MCP Proxy Server

Responsibilities:
- Expose MCP tools over HTTP
- Validate tool inputs
- Manage WebSocket connections
- Coordinate request/response lifecycles
- Enforce timeouts and error handling

Key technologies:
- FastAPI (ASGI host)
- FastMCP (MCP server framework)
- Raw WebSockets (JSON-RPC style)

The Python server **does not**:
- Store Foundry game state
- Mirror Foundry APIs
- Execute Foundry logic

---

### 2. Foundry VTT Module

Responsibilities:
- Bootstrap client-side JavaScript
- Open a persistent WebSocket connection to the Python server
- Execute Foundry VTT API calls
- Return structured results

Properties:
- Runs inside Foundry's Chromium/Electron runtime
- Has full access to `game`, `canvas`, `ui`, etc.
- Is the authoritative runtime for game data

---

### 3. WebSocket RPC Bridge

The WebSocket connection implements a synchronous RPC abstraction.

Request format:
```json
{
  "id": "uuid",
  "method": "getActorName",
  "params": { "actorId": "abc123" }
}
```

Response format:
```json
{
  "id": "uuid",
  "result": "Gandalf"
}
```

Errors are explicit and structured.

The Python server maps requests to `asyncio.Future` objects and resolves MCP tool calls when responses arrive.

---

## Core Abstraction

All Foundry access flows through a single conceptual interface:

```python
result = await foundry.call(
    client_id="gm",
    method="getActorName",
    params={"actor_id": "abc123"}
)
```

This abstraction:
- Is synchronous from the MCP perspective
- Is transport-agnostic
- Matches MCP's request/response semantics
- Keeps tools simple and predictable

---

## Why WebSockets (Not HTTP or Socket.IO)

- WebSockets avoid browser CORS preflight complexity
- Persistent connection fits RPC semantics
- Explicit protocol improves debuggability
- No framework-level magic
- Full control over identity, errors, and timeouts

Socket.IO-style semantics are implemented explicitly rather than inherited.

---

## CORS and Origin Considerations

- WebSocket connections are **not subject to browser CORS**
- Foundry modules can connect to external WS servers
- The server may optionally validate the `Origin` header
- HTTPS Foundry instances require `wss://`

The MCP HTTP endpoint is typically consumed by non-browser clients, so CORS does not apply.

---

## Design Principles

1. **Browser is authoritative**
   - All game state lives in Foundry
   - Python only queries, never mirrors

2. **Explicit RPC**
   - Clear request/response
   - Deterministic behavior
   - Transparent failure modes

3. **Small, intentional tools**
   - Keep permanent game tools narrowly scoped.
   - Arbitrary execution is a separately authenticated, opt-in development
     console; see [JavaScript exploration](js-exploration.md).
   - Prefer well-defined operations

4. **LLM-friendly errors**
   - Structured error objects
   - Clear messages
   - No silent failures

---

## Recommended Build Order

1. Implement WebSocket connection manager
2. Add RPC request/response handling
3. Build minimal Foundry module
4. Expose a trivial MCP tool (e.g. `get_world_name`)
5. Validate full end-to-end flow
6. Expand tool surface gradually

---

## Development browser control

Chrome DevTools MCP is an independent development connection to the visible
Chrome profile. It handles refreshes, console/network inspection, UI checks,
and page JavaScript evaluation, including diagnosis when the Foundry WebSocket
bridge is unavailable. The Foundry bridge retains ownership of permanent game
tools and provides bounded object snapshots through its exploration facility.
Chrome evaluation and exploration overlap, but Chrome evaluation does not use
the bridge's serializer or authorization checks. Keep both capabilities
confined to the development profile and test world.

The current bridge admits one `gm` socket and correlates each pending RPC with
its originating socket. Duplicate connections are rejected; disconnects fail
pending requests promptly. Python orchestration and Foundry game-state
ownership remain unchanged. See [browser development](browser-development.md)
for the verified refresh workflow and connection recovery.

## Outcome

This architecture provides:
- Safe, synchronous LLM access to Foundry
- Minimal infrastructure
- Clear separation of concerns
- High debuggability
- Long-term maintainability

It is suitable for solo development and can be extended incrementally as needed.

## Production authentication

Production mode protects every MCP HTTP method with Basic Auth. Browser-native
WebSockets send a separate credential in a bounded first message, with a
five-second deadline. The manager serializes admission and sends the successful
authentication acknowledgment before making a GM socket available for RPC.
Failed authentication never replaces an existing owner. World-scoped module
settings persist with the world but are not a confidential GM-only secret store.
See operations for protocol, migration, TLS requirements and credential rotation.

## Packaged version identity

The image and released module embed tag/commit metadata. Source identities are
explicitly marked source; untagged images/packages are unreleased. The manager
sends server metadata during admission before exposing the GM to game RPCs.
The module compares it with its imported JavaScript identity, and exposes
`getModuleBuildInfo` for the server's read-only `get_bridge_versions` MCP tool.
Version mismatch warnings do not gate game tools. Missing/legacy identities
remain diagnosable without assuming compatibility. See
[the version diagnostic contract](bridge-version-diagnostics.md).

## Private PDF evidence

The optional Python-local PDF subsystem uses SQLite FTS5 and bounded pypdf
subprocesses. Its five MCP tools do not require Foundry RPC. Authenticated MCP
credentials must be exclusively GM-trusted; players require a separate endpoint.
Browser-originated `pdf.upload.*` messages use the existing GM socket with a
separate world-scoped upload password, exact-socket ownership and serialized sends.
World settings are readable by players; possession of this password permits
manual PDF management requests even though the interface is GM-only.
They never enter generic RPC response correlation. See [PDF library](pdf-library.md)
for protocol, persistent data, resource limits and recovery.

Journal source reading and Actor/Item reference resolution are separate RPCs.
`readJournalPage` supplies lazy follow-up metadata without hydrating every target.
`resolveJournalReference` checks one exact current source notation, resolves it
asynchronously relative to its originating page, and delegates PF2e identity and
permission admission to the existing Actor/Item document boundary. Python
validates the singleton result and canonical next-reader arguments before MCP
delivery. Failures stay local to that selected reference; no target source or
gameplay operation is executed.

PF2e character Build is a selected-source join implemented by `actorBuild.js`,
not a second character model in Python. The browser snapshots actual readable
owned build Items once, typed source and separate persisted grant claims within
the selected world/token owner. Python validates every paged source row using
its own persisted `/type` witness, exact donor/path/mapping and contributors;
outgoing reciprocal claims include exact inverse source evidence. There is no
top-level donor manifest. Membership, permissions, source and inverse evidence
participate in revision checks. The snapshot rejects more than 12,000 owner
Items or 24,000 records before shared record/byte pagination. Offered definitions
and options never establish acquisitions; NPC/familiar Build and effective
benefits are unsupported. See the [Build contract](actor-item-story-map/build-contract.md).

Character source extraction uses the separate `actorCharacter.js` allowlist on
detached `toObject(true)` data. It preserves nullable manual attributes, stored
ranks/resources and recorded choices without filling prepared fields. Biography
and language prose require explicit description selection and shared exact-text
fragmentation; empty biography arrays retain field markers. Python validates
source/notes mappings, primitive types, rank labels and exclusions independently.
The [current-statistics contract](actor-item-story-map/current-statistics-contract.md)
uses a separate public `toObject(false)` boundary for selected character/NPC
statistics. Raw values and contributors explicitly use transformed basis; Python
admits it only for the exact statistics allowlist, leaving every source contract
unchanged. Own data properties are selected without inherited/getter access.
Current values participate in snapshot revisions, including when persisted
source remains unchanged. Missing serialized fields stay unavailable and the
section remains partial; no private calculation or source fallback occurs.
