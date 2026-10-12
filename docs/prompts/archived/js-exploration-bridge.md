# Foundry MCP — Live JavaScript Exploration Bridge

**Status:** Proposed enhancement  
**Repository:** https://github.com/sesopenko/foundry-mcp  
**Target:** Foundry VTT v13, Python FastMCP server, Foundry browser module  
**Purpose:** Enable an AI coding agent such as Codex to explore the live Foundry JavaScript API through MCP.

---

## 1. Project context

Foundry MCP is an experimental integration between a large language model and a running Foundry Virtual Tabletop session.

The existing architecture consists of:

1. A Python MCP server using FastAPI and FastMCP.
2. A Foundry VTT browser module written in JavaScript.
3. A WebSocket RPC bridge connecting the two.
4. An MCP client such as LibreChat or Codex.

An MCP tool call is forwarded to the Foundry browser, where JavaScript executes using the native Foundry API. The result is returned through the WebSocket connection.

### Current implementation

The repository already provides:

- MCP over Streamable HTTP.
- WebSocket request/response messaging with UUID correlation.
- Asynchronous RPC calls and response handling.
- RPC timeout and error propagation.
- Automatic browser reconnection with exponential backoff.
- GM-only initialization of the browser bridge.
- A basic health endpoint.
- One game-facing MCP tool, `get_player_names()`.

Relevant source files:

| File | Responsibility |
|---|---|
| `foundry_mcp_server/main.py` | FastAPI application, WebSocket endpoint, health endpoint |
| `foundry_mcp_server/ws/connection.py` | WebSocket connection management and RPC correlation |
| `foundry_mcp_server/mcp_server/server.py` | FastMCP server initialization |
| `foundry_mcp_server/mcp_server/tools.py` | MCP tool definitions |
| `foundry-module/scripts/main.js` | Foundry lifecycle hooks and bridge initialization |
| `foundry-module/scripts/foundryBridge.js` | Browser WebSocket connection and RPC handlers |
| `foundry-module/module.json` | Foundry module manifest |

The existing architecture should be preserved where practical.

## 2. Problem being solved

Developing MCP tools for Foundry VTT has been difficult because understanding the Foundry JavaScript API requires considerable exploration.

The public API documentation describes classes and methods, but it can be challenging to determine:

- Which APIs are available in the current Foundry version.
- How objects relate to each other.
- Which methods operate on which document types.
- How installed game systems extend Foundry's data models.
- What actual runtime objects look like.
- Which methods are safe to call.
- What operations require GM privileges.
- How to interact with Actors, Scenes, Tokens, Items, Journals, and combat encounters.

Previously, this investigation required substantial manual effort.

Modern coding agents can instead explore the runtime directly if given suitable tools.

## 3. Proposed solution

**Add a development-only MCP tool that executes arbitrary JavaScript within the connected Foundry GM browser and returns structured results to the MCP client.**

Proposed MCP tool:

`execute_javascript(code: str) -> dict`

Corresponding browser RPC method:

`executeJavaScript`

The tool will allow a coding agent to:

1. Submit JavaScript code through MCP.
2. Execute the code in the actual Foundry browser runtime.
3. Access Foundry globals such as `game`, `canvas`, `ui`, `foundry`, and `CONFIG`.
4. Await asynchronous operations.
5. Receive serialized results or structured errors.
6. Use the findings to implement permanent, narrowly scoped MCP tools.

### Architecture

```text
Codex
  |
  | MCP tool: execute_javascript(code)
  v
Python FastMCP Server
  |
  | WebSocket RPC:
  | method = executeJavaScript
  | params = { code }
  v
Foundry VTT Browser (GM session)
  |
  | Evaluate JavaScript
  | Access game / canvas / ui / foundry
  | Await result
  v
Result Serializer
  |
  | JSON-safe response
  v
Python MCP Server
  |
  v
Codex
```

The goal is to expose a controlled development console, not to replace the existing RPC architecture.

## 4. Initial implementation requirements

### 4.1 Python MCP tool

Add an `execute_javascript` tool in:

`foundry_mcp_server/mcp_server/tools.py`

The tool should:

- Accept JavaScript source code as a string.
- Validate input type and length.
- Forward execution through `FoundryConnectionManager.call()`.
- Target a specifically authorized Foundry GM client.
- Support an appropriate configurable RPC timeout.
- Return structured results.
- Raise meaningful MCP tool errors when execution fails.
- Be disabled by default and enabled only through explicit development configuration.

Example interface:

```python
@mcp.tool
async def execute_javascript(code: str) -> dict:
    """
    Execute JavaScript inside the connected Foundry browser.

    Development environments only.
    """
    ...
```

Only register this tool when development execution is explicitly enabled. Merely placing a warning in the tool description is not sufficient.

### 4.2 Foundry browser RPC handler

Add `executeJavaScript` to the `rpcHandlers` mapping in:

`foundry-module/scripts/foundryBridge.js`

The handler should:

- Validate the incoming parameters.
- Compile the supplied JavaScript into an asynchronous function.
- Execute it within the existing Foundry browser context.
- Support JavaScript `return` statements and `await`.
- Serialize the returned value.
- Capture and return structured errors.

Conceptual implementation:

```javascript
async executeJavaScript(params) {
  if (typeof params.code !== "string") {
    throw new Error("Expected JavaScript source code");
  }

  const AsyncFunction = Object.getPrototypeOf(
    async function () {}
  ).constructor;

  const execute = new AsyncFunction(
    `"use strict";\n${params.code}`
  );

  const value = await execute();

  return {
    value: serializeForRpc(value),
    foundryVersion: game.version
  };
}
```

This illustrates the intended execution mechanism, not a production-ready implementation.

The browser must independently verify that development execution is enabled. It must not assume that requests arriving from the Python server are automatically authorized.

### 4.3 Result serialization

Foundry objects may contain:

- Circular references.
- Class instances.
- Functions.
- Maps, Sets, and collections.
- Non-JSON-compatible values.
- Very large nested structures.
- Getters with side effects.
- Potentially sensitive data.

Create a serializer that produces bounded, JSON-compatible results.

Initial requirements:

- Limit traversal depth.
- Limit array and collection entries.
- Limit the total serialized response size.
- Handle circular references.
- Represent functions descriptively.
- Represent undefined values and BigInts.
- Preserve useful type information.
- Serialize errors, including stack traces where appropriate.
- Avoid blindly traversing or invoking getters.
- Handle serialization failures gracefully.

Foundry document instances may be converted using suitable public APIs such as `toObject()` where appropriate.

Raw document serialization should not be assumed safe for arbitrary objects.

### 4.4 Structured errors

Execution failures should include:

```json
{
  "error": {
    "type": "JavaScriptError",
    "message": "Example error",
    "stack": "..."
  }
}
```

Distinguish between:

- Invalid tool parameters.
- No connected Foundry client.
- Unauthorized execution.
- JavaScript compilation errors.
- JavaScript runtime errors.
- Serialization failures.
- RPC transport errors.
- Execution timeouts.

### 4.5 Execution timeout limitations

Python-side timeouts prevent the MCP caller from waiting indefinitely, but do not necessarily terminate running JavaScript.

An infinite synchronous loop can block the Foundry browser's event loop.

A timeout around a Promise cannot forcibly cancel arbitrary JavaScript or roll back previously completed Foundry operations.

The first implementation should explicitly document this limitation.

Use an isolated, disposable Foundry world for development.

## 5. Example exploration tasks

### Inspect environment

```javascript
return {
  foundryVersion: game.version,
  world: game.world.title,
  system: game.system.id,
  systemVersion: game.system.version,
  actorCount: game.actors.size,
  sceneCount: game.scenes.size
};
```

### Inspect an Actor

```javascript
const actor = game.actors.contents[0];

if (!actor) {
  return { error: "No actors found" };
}

return {
  name: actor.name,
  type: actor.type,
  methods: Object.getOwnPropertyNames(
    Object.getPrototypeOf(actor)
  ),
  data: actor.toObject()
};
```

### Inspect document schema

```javascript
const actor = game.actors.contents[0];

if (!actor) return null;

return {
  fields: [...actor.schema.fields.entries()].map(
    ([name, field]) => ({
      name,
      type: field.constructor.name,
      required: field.required,
      nullable: field.nullable
    })
  )
};
```

### Inspect current scene

```javascript
const scene = canvas.scene;

if (!scene) return null;

return {
  name: scene.name,
  tokens: scene.tokens.map(token => ({
    id: token.id,
    name: token.name,
    actorId: token.actorId,
    x: token.x,
    y: token.y
  }))
};
```

These experiments demonstrate the desired functionality. They should be validated against the actual installed Foundry version and system.

## 6. Follow-up introspection tools

After implementing JavaScript execution, consider adding higher-level read-only tools that reduce repeated exploratory code.

| Tool | Description |
|---|---|
| `get_foundry_environment` | Report Foundry version, system, installed modules, and capabilities |
| `inspect_object` | Inspect object properties, descriptors, and types |
| `inspect_class` | Discover prototype methods, inheritance, and property definitions |
| `inspect_document_schema` | Inspect DataModel field definitions |
| `get_document` | Retrieve a Foundry document by UUID |
| `list_document_types` | Enumerate available document types |

These tools should return compact structured representations instead of enormous raw objects.

Potential future enhancement: correlate discovered classes and methods with the official Foundry API documentation.

## 7. Documentation and source-code discovery

Official Foundry API documentation:

https://foundryvtt.com/api/

Foundry VTT v13 documentation:

https://foundryvtt.com/api/v13/

The official JavaScript API documentation is generated through TypeDoc.

No official OpenAPI/Swagger specification has been confirmed for this API. OpenAPI is primarily intended for HTTP APIs, whereas Foundry exposes an in-process JavaScript API.

Investigate the following sources:

1. Official TypeDoc documentation.
2. Whether machine-readable TypeDoc JSON is published or can be generated.
3. Community-maintained TypeScript declarations.
4. Locally installed Foundry source files, subject to license restrictions.
5. Runtime introspection through the proposed MCP JavaScript execution tool.

Potential type-definition reference:

https://github.com/anandamideio/foundry-types

Relevant local Foundry source locations may include:

- `client/`
- `common/`
- `client/client.mjs`
- `public/scripts/foundry.mjs`

Verify these paths against the installed Foundry version.

**The coding agent should combine documentation, source inspection, and runtime experiments rather than relying on any single source.**

## 8. Security requirements

Arbitrary JavaScript execution inside a Foundry GM browser is a remote-code-execution capability.

This is acceptable only under deliberately constrained development conditions.

Required precautions:

- Disable arbitrary execution by default.
- Require explicit development opt-in.
- Restrict network access to trusted local or private environments.
- Authenticate and authorize MCP callers.
- Authenticate the browser-to-server connection.
- Do not trust a self-declared GM client identity.
- Ensure that production deployments cannot accidentally expose the tool.
- Log executed code and outcomes, with appropriate secret redaction.
- Set input and output size limits.
- Use disposable development worlds and test data.
- Never assume that timeouts safely terminate JavaScript.
- Do not treat client-side execution flags as sufficient authorization.

If the tool is exposed to another host or a shared network, implement proper authenticated transport rather than relying solely on localhost assumptions.

## 9. Existing issues to consider

The current repository uses a single hard-coded WebSocket client identity:

`gm`

Multiple connected GM browser sessions may overwrite each other's connections.

Address client identity and disconnect handling before relying on the bridge for unattended exploration.

Other considerations:

- Browser WebSocket URL is hard-coded to `ws://localhost:8000/ws/foundry`.
- HTTP and WebSocket endpoints need access controls.
- Pending RPC futures should be cleaned up when sending fails.
- Disconnections should fail pending calls promptly.
- The browser's active socket should be identifiable.
- Runtime execution and returned output should be observable for debugging.

These improvements should preserve the existing architecture rather than introduce unrelated frameworks.

## 10. Suggested implementation milestones

### Milestone 1 — Basic evaluation

- [ ] Add development-only MCP tool registration.
- [ ] Add browser-side `executeJavaScript` RPC method.
- [ ] Execute a simple JavaScript expression.
- [ ] Return JSON-compatible values.
- [ ] Support asynchronous JavaScript.
- [ ] Propagate compilation and execution errors.

**Acceptance criteria:** Codex can invoke an MCP tool and receive the Foundry version and world title from a running browser.

### Milestone 2 — Reliable exploration

- [ ] Add bounded serialization.
- [ ] Handle circular references and class instances.
- [ ] Improve structured error handling.
- [ ] Add response-size limits.
- [ ] Improve connection identity and cleanup.
- [ ] Add execution and RPC diagnostic logging.

**Acceptance criteria:** Codex can inspect real Actors, Scenes, and DataModel schemas without crashing the bridge or producing unbounded output.

### Milestone 3 — Security and configuration

- [ ] Add explicit development mode.
- [ ] Add meaningful authorization checks.
- [ ] Configure the browser WebSocket URL.
- [ ] Restrict access to trusted environments.
- [ ] Document the remote-code-execution implications.

**Acceptance criteria:** Arbitrary evaluation is inaccessible unless intentionally enabled in a trusted development setup.

### Milestone 4 — Purpose-built introspection

- [ ] Implement `get_foundry_environment`.
- [ ] Implement `inspect_object`.
- [ ] Implement `inspect_class`.
- [ ] Implement `inspect_document_schema`.
- [ ] Explore useful support for document UUIDs.
- [ ] Add tests using representative Foundry objects.

**Acceptance criteria:** Codex can discover common Foundry document interfaces using concise MCP calls without repeatedly constructing complex JavaScript expressions.

### Milestone 5 — Agent-assisted development

- [ ] Connect the MCP endpoint to a Codex editing session.
- [ ] Have Codex investigate a real Foundry API operation.
- [ ] Record the discovered behavior.
- [ ] Implement a permanent, constrained MCP tool based on the discovery.
- [ ] Verify the new tool against a running Foundry session.

**Acceptance criteria:** Codex can explore Foundry, understand an operation, implement an MCP tool, and verify the resulting functionality end-to-end.

## 11. Desired end-state

The development workflow should be:

1. Start a local Foundry test world.
2. Start the Python MCP server with development execution enabled.
3. Connect Codex to the MCP endpoint.
4. Ask Codex to implement a new Foundry capability.
5. Codex reads the official API documentation and relevant source code.
6. Codex executes exploratory JavaScript inside Foundry.
7. Codex interprets the returned objects and runtime behavior.
8. Codex implements a permanent MCP tool.
9. Codex tests the tool against the running Foundry instance.
10. Successful discoveries become reusable code, tests, and documentation.

**Central design principle:** Use arbitrary JavaScript execution as a development-time discovery mechanism, then translate successful experiments into narrowly scoped, validated MCP operations.

---

## 12. Instructions for the Codex implementation session

You are working in:

https://github.com/sesopenko/foundry-mcp

Your task is to implement the proposed developer-oriented JavaScript exploration functionality.

Start by inspecting the existing repository and validating the architecture described above. The notes are a design proposal, not an assertion that every code sample is production-ready.

Preserve the existing Python MCP server, WebSocket RPC manager, and Foundry module architecture where possible.

Prefer incremental, testable changes over a large rewrite.

Before implementing arbitrary execution, establish explicit development-mode controls and identify the trust boundary between Codex, the Python MCP server, and the Foundry browser.

Use the existing RPC mechanisms rather than adding a browser automation framework unless a concrete technical limitation requires it.

Keep the code understandable and maintainable.

Focus initially on making it possible for Codex to execute JavaScript inside the browser and retrieve structured results.

Do not expand the permanent game-facing tool API until the exploratory execution facility has been verified.

Document configuration, usage, security implications, and known limitations.

**First action:** Inspect the relevant source files and propose an implementation sequence based on the repository's actual state before making edits.