# Foundry MCP

Connect AI assistants to Foundry Virtual Tabletop for Game Master assistance through the Model Context Protocol (MCP).

**[Source code and issues](https://github.com/sesopenko/foundry-mcp)** · **[Releases](https://github.com/sesopenko/foundry-mcp/releases)** · **[Operator guide](https://github.com/sesopenko/foundry-mcp/blob/main/docs/operations.md)** · **[License](https://github.com/sesopenko/foundry-mcp/blob/main/LICENSE.txt)**

This image runs the Python MCP server. A companion Foundry module connects the GM's browser to the server over WebSocket; MCP clients such as LibreChat and OpenAI Codex can then use its tools. Foundry remains the source of game data. Current tools provide server/module version diagnostics, active player names, and journal navigation, search, and reading, with room for additional GM assistance features.

The image does not include Foundry VTT or a chat interface. Use your existing licensed Foundry installation and world. The companion module requires the **Pathfinder Second Edition (`pf2e`) game system** and declares Foundry 13 as its minimum version; see the operator guide for tested compatibility and limitations. The image targets **Linux amd64** and needs no source mounts. Optional PDF references require persistent private volumes.

## Unreleased source capability

The source branch adds GM-only Actor/Item capability discovery, selected-source
reading, owned Item navigation, world Actor folders/name search, Scene/Token
navigation, and scoped Actor/Item pack index search on the verified
Foundry 14.369/PF2e 8.6.1 pairing. Canonical identities, bounded continuations and
explicit failed/incomplete scopes preserve readable context without imports.

Shared physical source fields include quantity, Bulk, stack price-per quantity,
carrying/identification state and serialized attachment metadata. Action Items
map activation kind/count, stored frequency, traits and named self-effects;
explicit immediate relationship reads do not apply them. NPC attack Items retain
authored modes, bonus/damage and additional-effect labels, including explicit
null-range/thrown limitations. Other concrete type readers and effective Actor
statistics remain staged or unsupported. These are
unreleased source capabilities; inspect the delivered registry and the
[Actor/Item contracts](https://github.com/sesopenko/foundry-mcp/blob/main/docs/actor-tools.md).
Lore Items expose owner-aware stored modifiers and labelled ranks; Actor Skills
currently returns partial Lore specialty references with canonical Item/token
context. Effective check totals remain unsupported.
NPC source reading includes authored attributes, defenses, skills, movement and
IWR with source provenance. Explicit Actor description reads separate bounded
NPC blurb, public notes and GM-private notes. Integrated/effective statistics
remain pending; elite/weak adjustments are not calculated.
Explicit NPC strikes and abilities expose actual owned attack/action Item
references for follow-up reading, with partial completeness and token context.
Effect source preserves duration units, badge types/formulas and context fields.
Explicit relationships resolve immediate origin/target identities with permission
and token-context checks. Formula evaluation and effective expiry remain unsupported.
Condition source preserves valued flags, persistent-damage metadata, local
references and override slugs. Explicit relationships resolve actual owner-local
Item IDs; slugs remain unverified. Activity and suppression remain unsupported.
PF2e8.6.1 production disables affliction Items. Discovery marks their reading
unsupported; original poison/disease/curse descriptions remain the source.
Weapon source includes damage, runes, range and ammunition configuration;
carried weapons are not automatically effective Strikes or usable attacks.
Ammunition reading preserves separate stock/uses and crafting categories. Only
explicit weapon selection follows a stack; carried effects are not applied.
Armor reading preserves stored defenses, thresholds, runes and carrying state;
source armor bonuses are not total Actor AC or automatic worn benefits.
Shield reading preserves source durability, reinforcing and integrated configuration;
held is not raised, and source values do not establish blocking or class benefits.
Equipment preserves usage, investment, traits and exact prose abilities;
uninvested mundane uses remain readable and magical benefits are not applied.
Consumable source separates stock, uses and healing/damage formulas; contained-spell
definitions and exact prose retain source-path identity without separate spell UUIDs.
Spell definitions preserve base rank, textual casting time, damage/healing and
variant source; entry links retain owner context without assuming castability.
Casting entries preserve mode-specific resource source and individual preparations;
zero slot counters do not prove exhaustion, and missing expenditure flags stay absent.











## Run with Docker Compose

Create a deployment directory containing the following two files.

### `compose.yaml`

```yaml
services:
  foundry-mcp:
    image: ${FOUNDRY_MCP_IMAGE:?set the MCP image}
    platform: linux/amd64
    restart: unless-stopped
    environment:
      FOUNDRY_MCP_HOST: 0.0.0.0
      FOUNDRY_MCP_PORT: "8000"
      FOUNDRY_MCP_DEV_EXECUTION: "false"
      FOUNDRY_MCP_AUTH_MODE: basic
      FOUNDRY_MCP_BASIC_USERNAME: ${FOUNDRY_MCP_BASIC_USERNAME:?set MCP username}
      FOUNDRY_MCP_BASIC_PASSWORD: ${FOUNDRY_MCP_BASIC_PASSWORD:?set MCP password}
      FOUNDRY_MCP_BRIDGE_TOKEN: ${FOUNDRY_MCP_BRIDGE_TOKEN:?set browser credential}
      FOUNDRY_MCP_PDF_ENABLED: ${FOUNDRY_MCP_PDF_ENABLED:-false}
      FOUNDRY_MCP_PDF_TRUSTED_GM_MCP: ${FOUNDRY_MCP_PDF_TRUSTED_GM_MCP:-false}
      FOUNDRY_MCP_PDF_LIBRARY_DIR: /data/pdf-library
      FOUNDRY_MCP_PDF_INDEX_DIR: /data/pdf-state
      FOUNDRY_MCP_PDF_UPLOAD_ENABLED: ${FOUNDRY_MCP_PDF_UPLOAD_ENABLED:-false}
      FOUNDRY_MCP_PDF_UPLOAD_TOKEN: ${FOUNDRY_MCP_PDF_UPLOAD_TOKEN:-}
      FOUNDRY_MCP_PDF_TRUST_TLS_PROXY: ${FOUNDRY_MCP_PDF_TRUST_TLS_PROXY:-false}
    volumes:
      - ./pdf-library:/data/pdf-library
      - ./pdf-state:/data/pdf-state
    ports:
      - "${FOUNDRY_MCP_LAN_ADDRESS:?set the host LAN IP}:8000:8000"
    stop_grace_period: 15s
```

### `.env`

```dotenv
FOUNDRY_MCP_IMAGE=sesopenko/foundry-mcp:latest
# Replace with an actual LAN address belonging to the Docker host.
FOUNDRY_MCP_LAN_ADDRESS=192.0.2.10
FOUNDRY_MCP_BASIC_USERNAME=librechat
FOUNDRY_MCP_BASIC_PASSWORD='replace-with-your-mcp-password'
FOUNDRY_MCP_BRIDGE_TOKEN='replace-with-your-browser-credential'
# Optional PDF library; see the access and HTTPS/WSS requirements below.
FOUNDRY_MCP_PDF_ENABLED=false
FOUNDRY_MCP_PDF_TRUSTED_GM_MCP=false
FOUNDRY_MCP_PDF_UPLOAD_ENABLED=false
FOUNDRY_MCP_PDF_UPLOAD_TOKEN='replace-with-a-separate-pdf-upload-password'
FOUNDRY_MCP_PDF_TRUST_TLS_PROXY=false
```

Replace the example address and credentials before starting. The password and bridge credential must be nonempty; the project does not impose password-strength or distinctness requirements. The Basic Auth username cannot contain a colon. Use single quotes in Compose `.env` files to preserve literal `$` signs; those surrounding quotes are not part of the value.

The `./pdf-library` and `./pdf-state` folders are stored on the Docker host,
alongside `compose.yaml`. They preserve uploaded PDFs, completed uploads awaiting
indexing, and the SQLite index when the container is restarted or replaced.
Keep and back up **both folders**. Do not delete them when refreshing the stack.
Create them for the container's UID/GID 10001 before the first start.

Keep `.env` private and out of version control:

```bash
sudo install -d -m 0700 -o 10001 -g 10001 pdf-library pdf-state
chmod 600 .env
docker compose config --quiet
docker compose pull
docker compose up -d --wait --wait-timeout 90
```

Public image pulls require no registry login. `latest` follows published version-tag releases; main-branch builds publish `sha-<full-commit>` tags. For controlled upgrades and rollback, replace `latest` with a published `vX.Y.Z` tag or image digest from the repository's Docker Hub tags.

To use another host port, change only the published port in the mapping, for example `"${FOUNDRY_MCP_LAN_ADDRESS}:28643:8000"`. Update client URLs accordingly; the container still listens on port 8000.

### Endpoints and health

| Endpoint | Purpose |
| --- | --- |
| `/mcp/mcp` | Streamable HTTP MCP endpoint; requires HTTP Basic Auth. |
| `/ws/foundry` | GM browser bridge; requires the bridge credential in its first message. |
| `/health` | Public liveness endpoint; does not require credentials. |

Using your chosen host address and port:

```bash
curl -fsS http://192.0.2.10:8000/health
curl -i http://192.0.2.10:8000/mcp/mcp
```

The first request should return `{"status":"ok","foundry_clients":[]}` before a GM connects. The second should return **401 Unauthorized** with a Basic Auth challenge. An authenticated plain GET is not an MCP initialization request and may return a protocol error; use a real MCP client to verify tool discovery.

For diagnostics:

```bash
docker compose ps
docker compose logs --tail=100 foundry-mcp
```

## Connect the Foundry module

1. In Foundry **Setup → Add-on Modules → Install Module**, enter this manifest URL:

   ```text
   https://github.com/sesopenko/foundry-mcp/releases/latest/download/module.json
   ```

2. Launch your existing world, log in as GM, and enable **Foundry MCP Proxy** in **Manage Modules**.
3. Open **Configure Settings → Foundry MCP Proxy** and set the full browser-reachable WebSocket URL, ending in `/ws/foundry`.
4. Enable **Authenticate production bridge** and enter the value of `FOUNDRY_MCP_BRIDGE_TOKEN` in **Production browser bridge credential**. Leave local development execution disabled.
5. Save and look for **Connected** after authentication. Keep one owning GM browser tab connected; a second bridge is rejected. After installing updated module code, reload the browser normally.

These are world settings. They persist with the world and restrict editing through Foundry permissions, but are not a confidential GM-only secret store. The MCP Basic Auth password belongs in the MCP client, not the Foundry module.

### HTTPS and WSS

For an HTTPS Foundry page, remote bridge connections require a browser-trusted TLS endpoint, such as:

```text
wss://mcp.example.com/ws/foundry
```

Configure your reverse proxy to forward WebSocket upgrades to the MCP service and preserve `/ws/foundry`. Use HTTPS for MCP connections across untrusted networks. TLS termination, DNS, and certificates are managed separately from this image.

The browser authenticates inside the WebSocket connection; it cannot add a custom HTTP Authorization header. A proxy Basic Auth challenge on that route would prevent this authentication flow. Let the Python service validate the browser credential.

## Prepare the MCP client's Basic Auth value

MCP clients use the server's `FOUNDRY_MCP_BASIC_USERNAME` and `FOUNDRY_MCP_BASIC_PASSWORD`. The header format is `Authorization: Basic <base64(username:password)>`. Base64 is encoding, not encryption.

In Bash, prompt for the exact configured values without placing the password in shell history:

```bash
read -r -p 'MCP username: ' mcp_username
read -r -s -p 'MCP password: ' mcp_password
printf '\n'
export FOUNDRY_MCP_BASIC_AUTH="$(printf '%s:%s' "$mcp_username" "$mcp_password" | base64 | tr -d '\r\n')"
unset mcp_username mcp_password
```

`FOUNDRY_MCP_BASIC_AUTH` contains only the encoded value, without the `Basic ` prefix. Run this in the shell used to launch your client, or store the value in that client's private environment configuration. Changing a Docker Compose `.env` requires recreating the affected container; restarting alone does not reload its environment.

## LibreChat example

Merge this into `librechat.yaml`, preserving your other MCP servers and allowed-domain entries. Replace `mcp.example.com` with the hostname reachable from LibreChat's container, or use your server's trusted LAN HTTP URL and explicitly allow that host.

```yaml
mcpSettings:
  allowedDomains:
    - "mcp.example.com"

mcpServers:
  foundry-vtt:
    type: streamable-http
    url: https://mcp.example.com/mcp/mcp
    headers:
      Authorization: "Basic ${FOUNDRY_MCP_BASIC_AUTH}"
    requiresOAuth: false
    timeout: 30000
    serverInstructions: true
```

In LibreChat's private `.env`, set the encoded value prepared above:

```dotenv
FOUNDRY_MCP_BASIC_AUTH='replace-with-base64-of-username-colon-password'
```

Ensure this variable is loaded into LibreChat's API container, for example through its Compose `env_file: .env`. From the LibreChat stack directory, apply changes to only its API service:

```bash
docker compose up -d --no-deps --force-recreate api
```

Select `foundry-vtt` in LibreChat or assign it to an agent. Successful discovery does not require a GM browser, but player and journal calls do. With the intended GM connected, ask for active player names to check the complete path.

LibreChat supports environment-backed custom headers and `requiresOAuth: false` for static authentication. See [LibreChat's MCP configuration documentation](https://www.librechat.ai/docs/configuration/librechat_yaml/object_structure/mcp_servers). Treat expanded configuration and client logs as private because they may contain headers.

## OpenAI Codex example

Add this entry to `~/.codex/config.toml`, or the project's `.codex/config.toml` for a trusted project. Replace an existing `foundry-vtt` entry rather than defining it twice. Use the URL reachable from the machine running Codex:

```toml
[mcp_servers.foundry-vtt]
url = "https://mcp.example.com/mcp/mcp"
env_http_headers = { Authorization = "FOUNDRY_MCP_AUTHORIZATION" }
startup_timeout_sec = 30
tool_timeout_sec = 30
```

After preparing `FOUNDRY_MCP_BASIC_AUTH` in the shell above, set the **entire header value** and launch Codex from that same shell:

```bash
export FOUNDRY_MCP_AUTHORIZATION="Basic ${FOUNDRY_MCP_BASIC_AUTH}"
codex
```

Codex's `env_http_headers` reads the complete header from the named environment variable. It does not add `Basic ` automatically. Do not use `bearer_token_env_var` for this Basic Auth setup. A Compose `.env` is not automatically loaded into your Codex process; provide the variable in its launch environment. Restart Codex after changing configuration or credentials, then check `/mcp` for the available server and tools.

See the [official Codex MCP documentation](https://developers.openai.com/codex/mcp/).

For contributors working from a source checkout, the separate
[Debian 13 development setup](https://github.com/sesopenko/foundry-mcp/blob/main/docs/code-graph.md)
provides a pinned local Python/JavaScript code graph for Codex. Run
`./scripts/dev-setup.sh`, then `./scripts/codex.sh --code-only` for source analysis
without the Foundry stack, or the normal development launcher for runtime work.
The graph engine and index are development tools and are excluded from this
production image and the Foundry module ZIP. Container operators do not need
Node, npm or graph setup.


## Check server and module versions

Ask your MCP client to call `get_bridge_versions` with no arguments. It returns
`server` and `module` build identities, `comparison`, `module_status`, and an
actionable `message`. Identities include `version`, `release_tag`, `revision`,
and `build_kind`. With no GM connected, server information is still available
and `module` is null. Older modules lacking diagnostics report unsupported.

Tagged versions compare exactly as match/mismatch. Source, untagged and unknown
builds are explicitly unverified, even if their declared versions agree. Foundry
also shows both versions automatically when tagged releases differ, advising
which component needs updating; normal tools continue working. The module
reports the JavaScript actually loaded in the GM browser, so reload it after
updates. This checks running versions, not newer releases available online.
See the [full diagnostic contract](https://github.com/sesopenko/foundry-mcp/blob/main/docs/bridge-version-diagnostics.md).

## Update and troubleshoot

Pull and recreate the bridge after changing its image or server environment:

```bash
docker compose pull
docker compose up -d
```

Update the companion module through Foundry's package updater and reload the GM browser. See [release notes](https://github.com/sesopenko/foundry-mcp/releases) for migrations and matching server/module versions. The bridge stores no world database; keep your existing Foundry data and world backups independently.

| Symptom | Check |
| --- | --- |
| MCP client gets 401 | Verify the running username/password, encoded header, and whether containers were recreated after environment changes. |
| Health is OK, but `foundry_clients` is empty | Enable the module, log in as GM, and check the browser URL and bridge credential. |
| Browser reports Misconfigured or closes with 1008 | Check credentials and competing GM tabs; save corrected settings to reconnect. |
| HTTPS page rejects the bridge | Supply a trusted `wss://` endpoint; plain remote `ws://` is insufficient. |
| Proxy returns 404 or a certificate error | Check hostname routing, backend port, and certificate issuance. |
| MCP session errors after a server restart | Reconnect the MCP client to establish a new session. |

For detailed operations, compatibility, development setup, and tool contracts, visit the [GitHub project](https://github.com/sesopenko/foundry-mcp).

## Optional GM-private PDF library

The server includes local PDF extraction, heading/bookmark discovery, SQLite
FTS5 lookup, and source-page reading. It requires no paid API or extra service.
PDFs are private user data; only enable this on an authenticated endpoint whose
MCP credentials are exclusively for trusted GMs. Players need a separate endpoint
with PDFs disabled. Do not put books into Foundry assets or images.

To enable PDFs, set these environment values in the `.env` above. The main
Compose example already includes both persistent folder mounts. After saving,
apply the configuration with `docker compose up -d`:

```dotenv
FOUNDRY_MCP_PDF_ENABLED=true
FOUNDRY_MCP_PDF_TRUSTED_GM_MCP=true
FOUNDRY_MCP_PDF_UPLOAD_ENABLED=true
FOUNDRY_MCP_PDF_UPLOAD_TOKEN='replace-with-a-separate-pdf-upload-password'
FOUNDRY_MCP_PDF_TRUST_TLS_PROXY=true
```

The TLS-proxy flag requires operator-enforced HTTPS/WSS and restricted direct
upstream access. It does not verify your proxy. The mounted host folders must
remain writable by UID/GID 10001. The GM opens **Manage PDF Library** in module
settings. Configure **PDF upload password** beside the production bridge credential.
It is world-scoped and readable by players; editing restrictions do not make it
secret. Anyone obtaining it can manually authorize PDF uploads and library
list/status/deletion operations, despite the GM-only interface. Only enable this in worlds
where that access is acceptable. MCP source retrieval remains protected by its
separate GM-trusted credentials. World bridge credentials alone do not authorize
PDF management.

Uploads use 32 KiB chunks over the existing authenticated WebSocket; progress is
server-acknowledged bytes. Transfer completion is followed by validation/indexing;
only Ready means searchable. The list updates during processing, and uploads matching an existing filename or identical bytes replace it after
successful reprocessing. The old version remains searchable if processing fails. MCP tools `list_pdf_documents`, `locate_pdf_entry`,
`search_pdf_documents`, `read_pdf_pages`, and `refresh_pdf_index` work independently
of a connected GM browser. Search candidates must be verified by source reads;
reading order/numeric table structure are unverified, and OCR is unavailable.

See [storage, limits, backup, credential rotation and recovery](https://github.com/sesopenko/foundry-mcp/blob/main/docs/pdf-library.md)
before enabling this feature. Disable uploads separately while keeping retrieval.

To remove an accidental or outdated upload, click **Delete PDF** beside a ready
or failed book in **Manage PDF Library** and confirm its name. This permanently
removes its stored server copy and searchable index. Wait for in-progress indexing
to finish before deleting. You can also upload the same filename directly to replace it after successful
processing, without deleting first. Keep your original file or backup. Imported host originals remain on disk but are excluded from
future automatic scans until explicitly uploaded again. Deletion uses the same
PDF upload password and is available only through the browser manager protocol.
