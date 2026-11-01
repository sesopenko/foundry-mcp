# GM-private PDF reference library

In version 2.0.0, search_pdf_documents uses the [version-two selective
contract](selective-reads.md). Snippets and entry context are opt-in; exact-page
reading and the other PDF tools retain their existing contracts.

PDF search now matches extracted page text together with page-associated bookmark
headings and section ancestry. Results retain exact page selectors; contextual
matches remain candidates to verify against source pages. This intentionally
changes default matching and ranking while preserving `contract_version:2`.

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
boundary: anyone who reads it can manually authorize upload/list/status/delete
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

The default per-file upload limit is **128 MiB (134,217,728 bytes)**, configurable
through `FOUNDRY_MCP_PDF_MAX_UPLOAD_BYTES`; it is not a fixed maximum. For a 150 MB
PDF, set `FOUNDRY_MCP_PDF_MAX_UPLOAD_BYTES=268435456` (256 MiB) in the server
deployment environment. The shipped Basic/OAuth Compose files forward this
variable. Recreate the MCP container with `docker compose up -d --force-recreate`
from its deployment directory, or restart a source service after changing its
environment. A container restart alone does not apply changed environment values.
The configured per-file limit cannot exceed the total quota. A larger upload
limit does not raise the separate parser page/text/memory/time limits above.

## Foundry upload workflow

On a GM browser, open **Game Settings → Configure Settings → Foundry MCP Proxy →
Manage PDF Library**. Configure the PDF upload password in the module settings, choose a PDF,
and upload. Other users see no manager, and client helpers check GM status before
sending; server capability checks remain authoritative.

The existing `/ws/foundry` socket carries protocol-version-1 JSON messages with
32 KiB decoded base64 chunks. Transfer is stop-and-wait; progress is acknowledged
bytes divided by declared bytes. At 100%, bytes are durable in private pending
storage, **not validated or searchable yet**. The manager polls index status;
only `ready` after the SQLite transaction commits means searchable. The list updates
while processing, and the final success/error message stays visible. Uploading the same filename or identical bytes creates a replacement job and
reprocesses the uploaded PDF. The old ready version remains searchable until the
replacement commits successfully; a failed replacement leaves it available. Failed
validation/indexing remains failed with a sanitized error. Cancel/disconnect
removes incomplete transfers; completed transfers survive and continue indexing.
Reopen/authorize/refresh the manager to recover status after disconnect.

The protocol uses distinct `pdf.upload.*` types and bounded request IDs:
`authorize`/`authorize_ack`, `begin`/`begin_ack`, `chunk`/`ack`,
`cancel`/`cancel_ack`, `finish`/`index_status`, `list`/`list_ack`,
`index_status`, `delete`/`delete_ack`, and `error`. Every request includes `protocol:1` and `request_id`;
chunks/finish/cancel include the server-owned `upload_id`. Every PDF operation
requires an independently authorized exact socket. Leases last one hour;
restart/config rotation/disconnect revoke them. Out-of-order chunks or invalid
operations discard incomplete data. Filenames are display metadata only.
The finish response includes `replacing:true` when the upload matches existing
PDFs by exact filename or SHA-256. It always returns a new `document_id` and
queues validation/indexing, including for identical bytes. A successful commit
atomically retires the matched old IDs and their index records; their managed
sources are cleaned up afterward. Shared identical source bytes are preserved
for the new record. Pending replacements recover after restart. If a matching
PDF is already processing, wait for that job to finish before trying again.
Filenames select replacement candidates, never filesystem destinations.

## Delete or replace a PDF

Each ready or failed PDF in **Manage PDF Library** has a **Delete PDF** button.
Confirm the named PDF to permanently remove its server-owned source, any pending
copy, extracted pages, entries and full-text index. The list refreshes after the
server acknowledges deletion. PDFs still processing cannot be deleted until the
job finishes; active uploads must finish or be cancelled first. Deletion uses
the same independently authenticated browser connection and upload password as
other PDF management. It is not an MCP write tool.

The request is `pdf.upload.delete` with the current `document_id` and `revision`
from the privileged PDF list. The server rejects stale/missing IDs or revisions,
unauthorized sockets and processing jobs. Success is `pdf.upload.delete_ack`
with matching `document_id` and `deleted:true`. File cleanup intent is recorded
transactionally before removing the source; startup retries interrupted cleanup.
If storage cleanup fails, the book is already excluded from search; repair the
storage and retry deletion or restart to complete cleanup.

Previously issued document IDs and citations become unavailable after deletion.
You can also upload the same filename or identical bytes directly to replace it
without deleting first. It receives a new ID after validation/indexing succeeds. Keep your original PDF/backup if you may need it again.
Operator-supplied import files are not deleted by filename: the original manual
copy is preserved, but its content hash is excluded from later scans so it does
not unexpectedly return. Explicitly uploading those bytes again clears that
exclusion. Deletion does not remove external backups or copies on your computer.

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

### Contextual lexical contract

`search_pdf_documents` and `locate_pdf_entry` accept `search_mode:"contextual"`
(default) or `"text"`. Both safely quote extracted query words and require all
words. Contextual mode searches one row per physical page across normalized body,
bookmark titles, bookmark ancestors and heuristic titles; text mode uses the
unchanged original body-only FTS index/ranking. It is not semantic or fuzzy search.
Only entries attached to that page contribute. No last-heading propagation,
inferred section spans, filenames, page labels or invented aliases are indexed.
Heuristic heading ancestry is ignored because the extractor's last-bookmark
context does not establish a parent relationship.

Contextual [FTS5 BM25](https://www.sqlite.org/fts5.html#the_bm25_function) weights
are body 1, bookmark titles 3, bookmark ancestors 0.5 and heuristic titles 0.75.
These fixed engineering choices are not tuned or calibrated confidence scores.
Ties use document ID then physical page. Locate promotes exact casefolded,
whitespace-normalized titles, including bookmark-only pages beyond the lexical
cap; at most 20,000 ordered headings are inspected. The cap flag covers either
heading or lexical limits. Narrow scope/query when capped.

Selections affect returned details only. `select.context` still requires
`select.entries`. `select.match_details:true` adds `matched_fields` (at least one
query term matched in that field), `body_matches_all_terms` (the full AND query
matches body), and, only when metadata contributed, `metadata_excerpt` (at most
300 Unicode characters) and `metadata_excerpt_derived:true`. Explanations use
FTS column queries, including its Unicode tokenization, rather than substring
tests. They are computed only for the requested result window. The excerpt is
navigation metadata, never source evidence. Snippets always select body text;
empty-body candidates retain an empty snippet and sparse-text warnings.

```json
{"query":"Infiltration checkpoint","search_mode":"contextual","limit":5,"select":{"snippet":true,"entries":true,"context":true,"match_details":true}}
```

Use real `document_id` values from `list_pdf_documents` to restrict a book.
Reuse query, mode, scope, selection and bounds with returned `next_offset`.
Restart after library/index changes; offset continuations have no revision lock.
Unselected optional fields stay omitted; defaults remain ten candidates and
8,000 JSON bytes (maximum 48,000). A byte-limited page may contain fewer results.

Metadata whitespace is normalized and casefold-deduplicated. Whole strings are
admitted in stable lexicographic order within each category: bookmark titles,
bookmark ancestors, then heuristic titles. Combined metadata is limited to
8,192 UTF-8 bytes per page including separating spaces; discarded material emits
`search_context_truncated` on contextual candidates. Existing extractor title/path
limits still apply. Publisher navigation metadata does not prove sentence scope
or a complete rule definition. Tables remain unverified.

### Search-index upgrades and rollback

Startup creates a separate contextual FTS index and builds missing/stale ready
documents from persisted pages and entries before tools/jobs become available.
No PDF parse, upload, network or model call is involved. Build version, source
revision, deterministic input fingerprint and exact physical-page key coverage
govern rebuilding; unchanged builds are skipped. Each document's rows and build
marker commit atomically. Source text, warnings, labels, IDs, revisions and source
statuses are untouched. Uploads/retries maintain both indexes; successful
replacement and deletion remove both indexes and markers in the same transaction.
Failed replacements keep the old indexes usable.

Quota/headroom checks reserve for both FTS indexes, metadata and transaction
overhead (a conservative estimate, not a guaranteed growth factor). Migration
storage or malformed-metadata failures stop startup with a sanitized actionable
error; they do not mark source books failed or silently serve partial coverage.
Repair private storage/quota/metadata or restore a consistent pre-upgrade backup.
Before upgrading, stop the service and back up both private volumes using the
procedures below. Test the upgrade and restart on an isolated copy first. For
rollback, stop the service and restore that backup together with the previous
image; never delete the volumes or copy an open SQLite file as a consistent backup.

Two-column reading order and table structure remain unverified on every page.
Never assign numeric values to a table solely because they occur near a heading.
Sparse text warns of extraction limitations; no OCR is performed. Tables may
require checking the original PDF outside these text-only tools.

## Maintenance and recovery

- Manually copy PDFs into the configured library root and call
  `refresh_pdf_index`. Only top-level regular lowercase `.pdf` filenames are
  scanned; symlinks and oversized files are skipped. This uses the same private
  pending/validation/index pipeline as uploads. Filesystem scans deduplicate by SHA-256; changed bytes create a new document.
  Browser uploads explicitly replace matching filenames or identical content,
  retiring old IDs after successful indexing. Rediscover IDs after replacements.
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

### Deletion verification (2026-10-19)

The deletion change passed 93 Python and 51 JavaScript tests, including
confirmation/cancel, authorization and stale revisions, active-job rejection,
source/index removal, re-upload, scan exclusion and interrupted-cleanup recovery.
A live check through the existing Foundry 14.369 development GM browser uploaded,
indexed and deleted a synthetic PDF over the existing authenticated bridge. Both
previously uploaded rulebooks remained listed. No user-owned book was deleted.
The module archive validation also passed.

### Replacement verification (2026-10-19)

The replacement change passed 95 Python and 53 JavaScript tests and module ZIP
validation. Coverage includes identical re-uploads, changed contents with the
same filename, failed replacements preserving readable old content, legacy
unique-hash schema migration, and restart recovery of queued replacements.
A live synthetic test through the existing Foundry 14.369 GM browser replaced
one PDF with a changed version, verified that the old synthetic ID retired,
then deleted the test version. The existing user-owned PDF remained listed.
The local index was backed up privately before enabling the additive migration.

### Contextual search verification (2026-10-31)

Implemented against checkout `a952845d066b133c4ccd9e7d7a28f10c8e4ae215`
with Python 3.12 and the locked dependencies. The bounded
`scripts/pdf-context-audit.py` uses temporary private storage, at most 400 calls
and 120 seconds per run. Its `--source-state` option opens the original SQLite
database read-only and uses SQLite's backup API; it does not copy an open database
file, read/reparse source PDFs, change the running service or migrate live volumes.

The fixed ten synthetic challenges require one word from bookmark metadata and
one from body text. Recall@1, Recall@5 and MRR improve from 0 to 1 by construction;
all extra-term negative controls remain empty. This is a deterministic functional
gate, not an independent relevance benchmark or weight-tuning study. Initial
weights were retained without tuning. Body-derived default payload comparisons
use the same neutral `checkpoint` query in both modes.

The private snapshot contains Player Core, Player Core 2 and GM Core (1,126 pages).
The eleven historical named queries are explicitly scoped to Player Core and
GM Core, with the same expected physical pages listed above. All eleven remain
rank one in text and contextual locate modes: Recall@1, Recall@5 and MRR are 1
in both; 162 candidates were returned across the top-20 result windows per mode.
Negative extra-term controls remain empty. This re-establishes the baseline;
it does not extend the reviewed relevance set to Player Core 2 or establish
general relevance for broad headings. No private text or index is tracked.

| Measurement | Synthetic | Private SQLite snapshot |
| --- | ---: | ---: |
| Body-only database bytes | 81,920 | 19,197,952 |
| Database after contextual build | 122,880 | 28,348,416 |
| Initial contextual build | 3.72 ms | 315 ms |
| Median text lookup | 0.67 ms | 49.25 ms |
| Median contextual lookup | 0.81 ms | 48.83 ms |

These are single local runs, not stable performance estimates. The private
database grew by 9,150,464 bytes (about 47.7%); the synthetic database grew by
40,960 bytes (50%). Source PDFs are excluded from those SQLite-only figures.
All canonical document/page/entry records, including labels, warnings, text and
revisions, hashed identically before/after migration and restart. The private
snapshot's maximum indexed page metadata was 496 bytes, with zero truncated
pages; this does not guarantee that other books fit the 8,192-byte bound.

Actual in-memory `fastmcp.Client` discovery/invocation validates the new interface.
For comparison, the harness reconstructs the prior published PDF schemas and
descriptions from Git HEAD on a separate in-memory server, using the retained
text index for baseline responses. It does not claim a historical live-service
trace. Compact UTF-8 structured JSON sizes for the private snapshot's representative
`Sure Strike` search across books:

| Scenario | Baseline bytes / returned | Contextual bytes / returned | Complete? |
| --- | ---: | ---: | --- |
| Default, one call | 3,367 / 10 | 3,367 / 10 | No |
| Snippet, one call | 5,427 / 10 | 5,433 / 10 | No |
| Snippet + entries + context, one call | 7,535 / 7 | 7,535 / 7 | No |
| Same expansion plus new match details, one call | unavailable | 7,990 / 6 | No |
| Complete identity traversal, limit 3 | 8,120 / 20 | 8,120 / 20 | Yes, 7 calls each |

New details consume budget and can reduce first-page counts; this is not a
payload-savings claim. Search discovery grows from 3,458 to 5,575 bytes including
the description, input schema and output schema. The current full catalog is
246,906 bytes; substituting the prior discovered PDF contracts into the otherwise
unchanged catalog reconstructs a 244,296-byte baseline. These measurements are
JSON bytes, not billed tokens. The final private audit used 68 bounded calls in
2.39 seconds; the synthetic audit used 58. Calls include direct searches and
MCP discovery/invocation; build/restart checks are also bounded by elapsed time.

Focused tests cover provenance/deduplication/truncation, field-tokenized
explanations, sparse pages, cross-page/book isolation, deterministic pagination,
byte limits, legacy schema backfill, unchanged restart, duplicate/wrong page keys,
changed fingerprints, sanitized storage/metadata failures and transaction rollback.
They also cover upload/retry/replacement/deletion synchronization and actual
request/response validation through MCP. Two diagnosed defects have regression
tests: audit selection previously confused Player Core 2 with Player Core;
compact locate selection previously removed the exact-title flag before ranking.
Both were demonstrated failing before their fixes.

Final validation: all 31 focused PDF tests passed, followed by
`./scripts/test.sh`: 675 Python tests (one optional native code-graph integration
test skipped because `CODE_GRAPH_INTEGRATION` was not enabled) and 688 JavaScript
tests, with no failures. `git diff --check` passed. Reproduce the offline checks
outside the agent sandbox:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_pdf*.py' -v
PYTHONPATH=. .venv/bin/python scripts/pdf-context-audit.py
./scripts/test.sh
```

For the private-copy audit, add `--source-state` with the existing private
`library.sqlite3` path; it is opened read-only. The harness requires Git history
to reconstruct its HEAD baseline. No model/provider token usage was measured.

The isolated MCP-only container build and smoke passed synthetic upload,
context-dependent lookup with a text-mode negative control, no-browser reads,
container recreation/persistence and deletion from both modes. Its containers
and network were removed, retaining its synthetic test volumes. No Foundry
module changes, new Foundry instance, production deployment or live private-library
migration were performed. Numeric table/layout verification remains outside this
feature; rendered-source checking is still required for such rules claims.
