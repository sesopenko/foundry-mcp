# sesopenko/foundry-mcp

This project provides a Model Context Protocol (MCP) bridge between a Large Language Model (LLM) and a running Foundry VTT game.  
It consists of a Python MCP proxy server and a Foundry VTT client module that communicate over a WebSocket-based RPC channel.

The Python side exposes a small, well-defined set of MCP tools (over HTTP) that the LLM can call. Those tool calls are forwarded over WebSockets to the Foundry browser runtime, which is the single source of truth for game state and executes all Foundry API calls. Responses flow back over the same channel so that, from the LLM’s perspective, each tool call is synchronous and deterministic.

Key goals of this project:

- Enable safe, synchronous LLM interaction with a live Foundry VTT world
- Keep all game logic and state inside Foundry’s browser/Electron runtime
- Use a simple, explicit JSON-RPC style protocol over WebSockets
- Provide a minimal, maintainable Python server that focuses on validation, orchestration, and error handling rather than mirroring Foundry APIs

In practice, you run the Python MCP server, load the companion module in Foundry, and then connect an MCP-aware LLM client. The LLM can then call tools like “get world information”, “inspect actors”, or other narrowly scoped operations that are implemented in the Foundry module and mediated by the Python server.

Further reading: [docs/mcp_foundry_architecture.md](docs/mcp_foundry_architecture.md)

## Foundry (Docker)

`docker-compose.yml` reads Foundry credentials from a local `.env` file (gitignored).

1. Copy `.env.example` to `.env` and fill in values.
2. Start Foundry: `docker compose up -d foundry`

Foundry data is persisted in `./data`.

## Dependency Management with `pip-tools`

This project uses [`pip-tools`](https://github.com/jazzband/pip-tools) to manage Python dependencies in a reproducible way.

The workflow is:

1. Create and activate a virtual environment in `.venv`
2. Install `pip-tools` into that environment
3. Declare top-level dependencies in `requirements.in`
4. Compile a fully pinned `requirements.txt` using `pip-compile`
5. Install dependencies from `requirements.txt` using `pip`

---

### 1. Create a virtual environment in `.venv`

From the root of the repository:

```bash
python -m venv .venv
```

Activate it:

- On **Linux / macOS**:

  ```bash
  source .venv/bin/activate
  ```

- On **Windows (PowerShell)**:

  ```powershell
  .venv\Scripts\Activate.ps1
  ```

- On **Windows (cmd.exe)**:

  ```cmd
  .venv\Scripts\activate.bat
  ```

You should now see `(.venv)` in your shell prompt.

---

### 2. Upgrade `pip` and install `pip-tools`

With the virtual environment activated:

```bash
python -m pip install --upgrade pip
pip install pip-tools
```

You now have the `pip-compile` and `pip-sync` commands available in this environment.

---

### 3. Declare top-level dependencies in `requirements.in`

Edit `requirements.in` and list your direct (top-level) dependencies, one per line. For example:

```text
fastapi
websockets
mcp
```

You generally do **not** list transitive dependencies here; `pip-tools` will resolve and pin them for you.

---

### 4. Build `requirements.txt` from `requirements.in`

To compile a fully pinned `requirements.txt` from `requirements.in`, run:

```bash
pip-compile requirements.in
```

This will:

- Resolve all dependencies of the packages listed in `requirements.in`
- Generate (or update) a `requirements.txt` file with exact, pinned versions
- Include comments showing which top-level package required each dependency

If you want to upgrade all packages to their latest compatible versions, run:

```bash
pip-compile --upgrade requirements.in
```

---

### 5. Install dependencies from `requirements.txt` using `pip`

Once `requirements.txt` has been generated, install the dependencies into your active `.venv`:

```bash
pip install -r requirements.txt
```

This ensures your environment matches the pinned versions in `requirements.txt`.

---

### Typical Workflow

When you add or change dependencies:

1. **Edit** `requirements.in` to add/remove top-level packages.
2. **Recompile**:

   ```bash
   pip-compile requirements.in
   ```

3. **Install** the updated dependencies:

   ```bash
   pip install -r requirements.txt
   ```

Commit both `requirements.in` and `requirements.txt` so others can reproduce the environment exactly.

---

### Optional: Using `pip-sync`

If you want your virtual environment to contain **only** the packages listed in `requirements.txt` (and their dependencies), you can use:

```bash
pip-sync requirements.txt
```

This will uninstall any packages not specified in `requirements.txt`. Use with care, as it may remove other tools you installed into the same environment.
