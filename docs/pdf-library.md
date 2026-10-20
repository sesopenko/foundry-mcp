# GM-private PDF reference library

This opt-in library runs inside the existing Python process. SQLite FTS5 and
pypdf supply lexical candidates and canonical extracted text; there is no
cloud model, semantic embedding, OCR, or additional database/server. Retrieval
works without a connected Foundry browser. Extracted content is untrusted data,
never instructions. Search candidates and scores are not factual confidence.
Read source pages before making mechanical claims; cite the book and PDF page
label, keeping physical page numbers for reproducibility.

## Access policy and provisioning

Enable only on an authenticated MCP endpoint used **exclusively by trusted GMs**.
`FOUNDRY_MCP_PDF_TRUSTED_GM_MCP=true` explicitly attests this deployment policy.
Basic Auth authenticates credential possession, not Foundry roles. There are no
player credentials on this endpoint: if players need MCP tools, give them a
separate server with PDFs disabled and separate credentials. All PDF tools fail
closed when the library is disabled. No HTTP PDF download/static routes or
player Foundry document/chat integration exist.

Uploads additionally require `FOUNDRY_MCP_PDF_UPLOAD_ENABLED=true` and a private
`FOUNDRY_MCP_PDF_UPLOAD_TOKEN`, different from bridge/MCP credentials. The world
bridge credential alone cannot authorize any PDF protocol operation, including
listing or status queries. Possession of the private capability is the server's
authorization policy; an asserted `isGM` flag is never trusted. Configure the
**PDF upload password** beside the production browser bridge credential in
Foundry module settings. It is **world-scoped**, shared across browsers, and
readable by players. Foundry permissions restrict editing, not reading.
Consequently, this credential is not a confidential GM-only authorization
boundary: anyone who reads it can manually authorize upload/list/status
operations despite the GM-only interface. Use this configuration only in worlds
where that access is acceptable. MCP PDF source retrieval still requires the
separate GM-trusted MCP credentials. Existing client-local values are not copied
automatically; configure the world setting once after updating.

Remote traffic must use trusted HTTPS/WSS. When TLS terminates at a proxy, set
`FOUNDRY_MCP_PDF_TRUST_TLS_PROXY=true` only after enforcing TLS at that proxy
and restricting direct upstream access. This setting is an operator assertion,
not verification of forwarded headers. Without it the server accepts PDF
transport only through TLS or authenticated loopback; the module's existing
production URL validation requires WSS for remote hosts. Loopback development
requires existing separate development caller/browser authentication as well as
the PDF capability. Anonymous development mode cannot enable PDFs.

## Persistent container setup

Use the current `deploy/compose.yaml` and `.env.example`. Its two named volumes
persist source books and index/job/staging state across container replacement.
The image initializes mount points for UID/GID 10001. Do not use `down -v`.

```dotenv
FOUNDRY_MCP_PDF_ENABLED=true
FOUNDRY_MCP_PDF_TRUSTED_GM_MCP=true
FOUNDRY_MCP_PDF_UPLOAD_ENABLED=true
FOUNDRY_MCP_PDF_UPLOAD_TOKEN='replace-with-a-separate-private-capability'
FOUNDRY_MCP_PDF_TRUST_TLS_PROXY=true
FOUNDRY_MCP_PDF_MAX_UPLOAD_BYTES=134217728
FOUNDRY_MCP_PDF_QUOTA_BYTES=2147483648
```

The TLS-proxy setting above assumes the operator has configured the required
HTTPS/WSS protection. Proxy configuration is separately managed.

For host-managed bind mounts instead of named volumes:

```bash
sudo install -d -m 0700 -o 10001 -g 10001 pdf-library pdf-state
```

Mount these into `/data/pdf-library` and `/data/pdf-state`. For source execution,
set absolute `FOUNDRY_MCP_PDF_LIBRARY_DIR` and `FOUNDRY_MCP_PDF_INDEX_DIR` paths to
separate, dedicated, non-symlink private directories. Neither directory may
contain the other. The service restricts root permissions to 0700 and database
and staged source files to 0600. Never mount the library into Foundry static
assets or commit PDFs/indexes. Store backups privately.

Other limits: `FOUNDRY_MCP_PDF_MAX_CONCURRENT_UPLOADS=2` (maximum 8),
`FOUNDRY_MCP_PDF_IDLE_SECONDS=120`; quota includes source, staged, pending, index and extraction-output bytes. Indexing
reserves estimated text-index overhead; transfers also require 256 MiB of free
disk headroom. Maintain additional free space for backups. Each parser
is bounded to 768 MiB address space, 90 CPU seconds, 120 wall seconds, 2000 pages,
16 MiB extracted text, and 32 MiB output. Per-page extracted text is capped at
1 MiB. Limits can reject a legitimate complex PDF; this is a failure, not a
claim that the book has no relevant rules. Unix resource limits are required.

## Foundry upload workflow

On a GM browser, open **Game Settings → Configure Settings → Foundry MCP Proxy →
Manage PDF Library**. Configure the PDF upload password in the module settings, choose a PDF,
and upload. Other users see no manager, and client helpers check GM status before
sending; server capability checks remain authoritative.

The existing `/ws/foundry` socket carries protocol-version-1 JSON messages with
32 KiB decoded base64 chunks. Transfer is stop-and-wait; progress is acknowledged
bytes divided by declared bytes. At 100%, bytes are durable in private pending
storage, **not validated or searchable yet**. The manager polls index status;
only `ready` after the SQLite transaction commits means searchable. Failed
validation/indexing remains failed with a sanitized error. Cancel/disconnect
removes incomplete transfers; completed transfers survive and continue indexing.
Reopen/authorize/refresh the manager to recover status after disconnect.

The protocol uses distinct `pdf.upload.*` types and bounded request IDs:
`authorize`/`authorize_ack`, `begin`/`begin_ack`, `chunk`/`ack`,
`cancel`/`cancel_ack`, `finish`/`index_status`, `list`/`list_ack`,
`index_status`, and `error`. Every request includes `protocol:1` and `request_id`;
chunks/finish/cancel include the server-owned `upload_id`. Every PDF operation
requires an independently authorized exact socket. Leases last one hour;
restart/config rotation/disconnect revoke them. Out-of-order chunks or invalid
operations discard incomplete data. Filenames are display metadata only.
Completed bytes are SHA-256 deduplicated. Different contents sharing a name
receive different document IDs; existing ready sources are never overwritten.

## Grounded MCP workflow

1. `list_pdf_documents`: discover IDs, ready/failed status and physical page counts.
2. `locate_pdf_entry`: prefer named heading/bookmark candidates; inspect context.
3. `search_pdf_documents`: broaden with all-word lexical FTS matching when needed.
4. `read_pdf_pages`: read canonical text from each physical page and continue
   returned character offsets until complete. Pass returned revision while reading.
5. Cite book name and `page_label`. Distinguish source text, interpretation,
   optional variants, and unresolved ambiguity. Read related rules as necessary.

Tool discovery descriptions specify bounds, selectors, continuation and failures.
List/search offset continuations should be restarted if the library changes.
Search considers only ready documents and caps lexical candidates at 2000;
narrow book/query when `candidate_cap_reached` is true. Bookmarks and uppercase/
stat-block title patterns are candidates, not proof of a full definition or
ruleset/edition. Optional-variant evidence derives from bookmark ancestry; its
absence does not establish default status. Book-scoped regression checks located all eleven specified Player Core/GM Core
entries at rank one. This finite corpus check does not establish general heading
or definition-detection accuracy on arbitrary PDFs.

Two-column reading order and table structure remain unverified on every page.
Never assign numeric values to a table solely because they occur near a heading.
Sparse text warns of extraction limitations; no OCR is performed. Tables may
require checking the original PDF outside these text-only tools.

## Maintenance and recovery

- Manually copy PDFs into the configured library root and call
  `refresh_pdf_index`. Only top-level regular lowercase `.pdf` filenames are
  scanned; symlinks and oversized files are skipped. This uses the same private
  pending/validation/index pipeline as uploads. Ready content is immutable by
  SHA-256; changed bytes create another document rather than changing citations.
- Disable uploading with `PDF_UPLOAD_ENABLED=false` (full environment prefix
  above) and recreate the service; read-only retrieval remains available.
- Rotate the upload token in the private server environment and recreate only
  the MCP service. This closes sockets and revokes leases. Update the world-scoped PDF upload password in module settings. Rotate bridge/MCP credentials separately if exposed.
- Back up **both** private volumes with the service stopped for a consistent
  SQLite snapshot. Source PDFs are user data; SQLite/search state is derived,
  but also includes display names and queued-job metadata. Keep a pre-upgrade
  backup before rolling back to a release without PDF support.
- To rebuild from canonical PDFs, stop the server, move the old state directory
  to a private backup, initialize an empty state directory with correct ownership,
  restart, and call `refresh_pdf_index`. Canonical filenames are content hashes,
  so display names/IDs can change after rebuilding; preserve the old database
  when those citations matter. Never delete source PDFs as an index repair.
- Startup cleans abandoned upload staging and resumes queued/validating/indexing
  jobs. Fully received pending PDFs are retained across process interruption.
- Read-only/unavailable mounts fail startup rather than silently falling back to
  ephemeral storage. Full-disk transfer errors discard incomplete staging and
  return safe errors. Index failures never publish partial pages as ready; fix
  storage/source and retry refresh. No parser text/path/credential is logged.

Implementation references: [pypdf extraction](https://pypdf.readthedocs.io/en/stable/user/extract-text.html),
[SQLite FTS5](https://www.sqlite.org/fts5.html), and documented Foundry
[v13 settings](https://foundryvtt.com/api/v13/classes/foundry.helpers.ClientSettings.html),
[v13 DialogV2](https://foundryvtt.com/api/v13/classes/foundry.applications.api.DialogV2.html),
[v14 settings](https://foundryvtt.com/api/v14/classes/foundry.helpers.ClientSettings.html).
The manager uses its own HTML and documented application render/close hooks,
not Foundry sidebar DOM or internal APIs.

## Verification record (2026-10-19)

Private Player Core (466 physical pages) and GM Core (338) were indexed outside
Git. All eleven handoff queries placed the expected page first with the book
scoped: Sure Strike (362/label361), Grabbed (445/444), Persistent Damage (446/445),
Spellcasting Services (296/295), Free Archetype (85/84), Automatic Bonus
Progression (84/83), Victory Points (185/184), Encounter Budget (76/75), DCs by
Level (54/53), Treasure Table (321/320), and Bracelet of Dashing (287/286).
Free Archetype returned variant ancestry; table pages returned explicit caution.
The complete Bracelet entry page outranked its treasure-table mention.

A source-grounded check read Sure Strike's actual text: it is a fortune spell
that makes the next attack roll before the end of the turn use two rolls and
the better result (Player Core, printed p.361; physical PDF p.362). This statement
comes from a source-page read, not from a search snippet. Related interactions
still require reading their definitions; it is not a complete rules ruling.
No private book text is bundled in this record, tests, image or module ZIP.

The 28,849,599-byte Player Core transfer used 881 acknowledged chunks and became
searchable immediately after indexing without server restart. An isolated
MCP-only container also passed capability denials, synthetic upload integrity,
gameplay RPC during transfer, browser-independent retrieval, and persistence
across container replacement. The full suites passed 91 Python and 44 JavaScript tests. Completed-pending
recovery, corrupt/encrypted rejection, cleanup, schema discovery, quota/expiry
and browser acknowledgment behavior have deterministic tests. CI now repeats synthetic upload and
container-replacement checks without the private corpus.

**Remaining live verification:** actual Foundry GM/non-GM manager visibility,
world-setting persistence, file-picker/progress rendering, and browser WSS
acceptance have not been exercised in this session (development Chrome MCP tools
are unavailable). No new Foundry instance or production deployment was created.
These gaps must not be represented as passing UI acceptance tests. Text-only
table interpretation and general retrieval accuracy remain explicit limitations.
