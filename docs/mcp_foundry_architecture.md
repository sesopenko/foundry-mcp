# MCP ↔ Foundry VTT WebSocket Bridge Architecture

## Overview

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
   - Avoid arbitrary code execution
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

## Outcome

This architecture provides:
- Safe, synchronous LLM access to Foundry
- Minimal infrastructure
- Clear separation of concerns
- High debuggability
- Long-term maintainability

It is suitable for solo development and can be extended incrementally as needed.
