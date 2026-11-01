# Build plan: Context-aware lexical PDF search for foundry-mcp

**Handoff for Codex CLI · Prepared October 30, 2026**

**Repository:** `sesopenko/foundry-mcp`

**Reviewed revision:** `a56db3905f299792204110296bf680cd7332e93b` (`main` at review time)

**Status:** Implemented for v3.1.0. See the [integration verification record](../pdf-library.md#contextual-search-verification-2026-10-31). The research and feasibility notes below describe the original proposal and its evidence at handoff.

## 1. Goal and decision

Implement **searchable heading and section context** in the existing private PDF library. A query should be able to match some words in extracted page text and other words in the page's available bookmark titles or bookmark ancestry. Continue returning the actual book identity, physical page, PDF page label and source revision, and continue requiring a source-page read before making a rules claim.

**Use the existing stack. No additional runtime dependency is required.** The repository pins Python `>=3.12,<3.13` and `pypdf==6.21.1`. Its worker already extracts bookmark titles, ancestor titles, page destinations, page labels and heuristic heading candidates. SQLite FTS5 already supplies lexical matching and BM25 ranking. FTS5 supports multiple indexed columns, column filters and per-column BM25 weights. [R1] [R2] [R3] [U1] [U2]

This is deterministic metadata-enriched lexical retrieval—not semantic search and not LLM-generated contextual summaries. It will not match synonyms that are absent from both source text and metadata, repair broken PDF tables, or establish that a navigation heading is a complete rule definition.

**Scope for the first release:** enrich each page using entries already attached to that physical page. Index the ancestor path stored on those entries, even when the ancestor heading was printed on an earlier page. Do not infer new section spans or carry the last heading forward across arbitrary pages. That is a separate feature requiring reliable boundary extraction.

### Implementation instruction

Read the current `AGENTS.md` and relevant nested guidance before editing. Reconcile this plan with the checkout rather than assuming the reviewed revision is still current. Implement, test and document the feature locally. Do not push, publish, deploy to production, replace user PDFs, or mutate game documents. Follow the repository's existing editing and verification conventions. This handoff does not authorize any production-library mutation.

## 2. What is already implemented

| Location | Verified behavior | Consequence for this build |
| --- | --- | --- |
| `pyproject.toml` | Pins pypdf 6.21.1 and the Python 3.12 runtime range. | Keep dependencies unchanged. |
| `pdf/worker.py` under `foundry_mcp_server/` | Uses `PdfReader.outline`, `get_destination_page_number`, `page_labels` and `extract_text`. Emits entries with `title`, `page`, `context`, `provenance`. | Reuse the extracted metadata; do not add another PDF parser. |
| `pdf/library.py` | Stores canonical text in `pages`, metadata in `entries`, and normalized page text in `page_fts(document_id UNINDEXED, page UNINDEXED, text)`. | Add a derived contextual index without rewriting canonical text. |
| `Library.search()` | Builds an all-word AND expression, ranks page-text matches with BM25, then optionally attaches entry metadata. `locate=True` also promotes exact normalized title matches. | Make context participate in candidate retrieval, not merely in returned decoration. |
| `mcp_server/selective.py` | Registers the actual typed `search_pdf_documents` tool and forwards to `Library.search()`. | Updating only `mcp_server/pdfs.py` is insufficient. |
| `mcp_server/selective_models.py` | Defines `PdfSearchRequest`, `PdfSearchSelect`, `PdfCandidate` and `PdfResult`. | Add inputs and opt-in explanation fields at this public boundary. |

The source reader already returns `physical_page` and `page_label`. Preserve them. A PDF page label is the PDF's label metadata; it can match the printed number, but that equivalence is not guaranteed for every PDF. [R2] [R3] [R4] [R5] [R6] [U2]

**Important existing limitation:** a heuristic heading's `context` is inferred using the last collected bookmark whose destination is at or before the page. That is not a verified parent-child relationship. Do not promote those inferred paths into authoritative searchable ancestry. Use actual bookmark-entry paths for ancestry, and heuristic titles as a separate, lower-weight field. Even bookmark paths remain publisher/navigation metadata, not proof of rule scope. [R2]

## 3. Behavior to deliver

Use this synthetic example, not copyrighted rulebook text, for the first regression test:

```text
Extracted page text: A checkpoint requires a careful approach.
Bookmark title:      Infiltration
Bookmark ancestors: Subsystems
Query:               Infiltration checkpoint
```

Current text-only search cannot find this page because the page text lacks `Infiltration`. Contextual lexical search must find it because all query words occur across the indexed fields for that same page. Reading the page must still return only `A checkpoint requires a careful approach.`

Preserve the distinctions between **retrieval metadata**, **derived snippets**, **canonical extracted text**, and **interpretation by the assistant**. A page selected solely by a bookmark is a candidate even when text extraction is empty; retain its sparse-text warning and do not pretend that the missing text was read.

Acceptance behavior also includes a reliable legacy text-only mode, identical source-page reads before and after upgrade, unchanged document IDs and source revisions, compact default responses, and consistent operation after upload, replacement, deletion and restart.

## 4. Index design

### 4.1 Retain the current body-only index

Keep `page_fts` intact and maintained. Add a separate contextual FTS table. This is intentionally an augmentation, not a replacement of source storage or a redesign of the PDF library.

Keeping the old index provides a genuine baseline and an explicit text-only search mode. A `body:` filter on the new table is not necessarily an equivalent ranking baseline: FTS5's BM25 document-length normalization considers the indexed row, including metadata columns. [U1]

Proposed schema:

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS page_context_fts USING fts5(
    document_id UNINDEXED,
    page UNINDEXED,
    body,
    bookmark_titles,
    bookmark_ancestors,
    heading_candidates,
    context_warnings UNINDEXED,
    tokenize = 'unicode61'
);

CREATE TABLE IF NOT EXISTS pdf_context_index_state (
    document_id TEXT PRIMARY KEY,
    source_revision TEXT NOT NULL,
    build_version INTEGER NOT NULL,
    inputs_sha256 TEXT NOT NULL,
    page_count INTEGER NOT NULL
);
```

Keep the default full FTS detail and column-size support. Do not introduce external-content tables, custom SQLite extensions, a vector database, or a new ORM for this change.

### 4.2 Build one contextual row per physical page

Create a focused helper, proposed path `foundry_mcp_server/pdf/search_context.py`, used by both migration and new indexing. It should produce deterministic rows from stored pages and entries:

- `body`: exactly the existing search normalization, `' '.join(page_text.split())`.
- `bookmark_titles`: titles of `provenance='bookmark'` entries attached to this page.
- `bookmark_ancestors`: ancestor strings from those bookmark entries only.
- `heading_candidates`: titles of `provenance='heading_candidate'` entries on this page, excluding duplicates already represented by bookmark titles.
- `context_warnings`: a JSON list for derived-index limitations, initially empty or containing a context-truncation warning.

Normalize whitespace and deduplicate metadata case-insensitively, while retaining readable spellings for explanations. Define stable ordering rather than depending on incidental SQLite row order. Keep provenance in the original `entries` records; do not rewrite those records just to build a search string.

Limit the combined metadata payload to **8,192 UTF-8 bytes per page**, admitting complete strings in a documented order: bookmark titles, bookmark ancestors, then heuristic titles. Do not cut halfway through a UTF-8 sequence or manufacture a partial keyword. Emit `search_context_truncated` when the limit discards material. This is a proposed starting bound; test it against the available corpus before release.

Do not index document IDs, page labels, physical page numbers or display filenames as search terms. Use `document_id` to restrict the book and `read_pdf_pages` to select a known physical page. This avoids filename and page-number matches being confused with numeric rules.

Pages with no applicable metadata still receive a row containing their body. Do not fabricate headings. Preserve existing title/path truncation limitations; the stored metadata cannot reconstruct information that the extractor already omitted.

### 4.3 Keep matching and ranking explicit

Add `search_mode: Literal['contextual', 'text'] = 'contextual'` to the public search request and to `locate_pdf_entry`. Pass it as a keyword argument through to `Library.search()`.

`text` uses the existing `page_fts` query and ranking. `contextual` uses `page_context_fts`. Both retain the current token extraction, all-word AND behavior, book restriction, ready-document restriction and deterministic tie-breakers. Neither accepts caller-supplied SQL or raw FTS operators.

Start contextual ranking with:

```sql
ORDER BY bm25(page_context_fts, 0, 0, 1.0, 3.0, 0.5, 0.75, 0),
         d.id,
         f.page
```

These weights are initial engineering choices, not measured optimal values. They distinguish direct bookmark titles, body text, broad ancestors and heuristic headings. Use fixed, named constants; do not expose arbitrary weights in the MCP tool. Verify positional alignment with all seven columns.

Do not compare raw BM25 scores between the two separate indexes or combine them as if they were calibrated confidence values. Default contextual search queries its own index, rather than running two searches and merging unrelated scores.

Preserve exact normalized title promotion in `locate_pdf_entry`, including its fallback for bookmark-only pages. Exact-heading candidates must not disappear because the lexical candidate cap was reached. Deduplicate by `(document_id, physical_page)` and retain the existing bounded heading-lookup policy; report any coverage limits honestly. Do not turn a title match into a claim that the complete rule is present.

## 5. Public MCP contract and explanations

### 5.1 Separate selection from search semantics

`select.context` currently controls returned entry ancestry and requires `select.entries`. Keep that behavior. It must not control which fields are searched. Enabling or disabling response details must never change candidate identities or ranking, except for the number fitting within a byte-limited response. [R6]

Example future request:

```json
{
  "query": "Infiltration checkpoint",
  "document_id": "<ID returned by list_pdf_documents>",
  "search_mode": "contextual",
  "limit": 5,
  "select": {
    "snippet": true,
    "entries": true,
    "context": true,
    "match_details": true
  }
}
```

The placeholder above is explanatory, not a valid document selector. Always discover real IDs.

### 5.2 Add small, opt-in match explanations

Add `match_details: bool = False` to `PdfSearchSelect`. Add an optional typed `match_details` object to `PdfCandidate`, omitted when unselected. Suggested shape:

```json
{
  "matched_fields": ["body", "bookmark_titles"],
  "body_matches_all_terms": false,
  "metadata_excerpt": "Infiltration",
  "metadata_excerpt_derived": true
}
```

`matched_fields` means that at least one query term matched in that field; it does not mean every term matched there. Compute this using FTS tokenization and allowlisted column queries, not Python substring tests. For per-field explanations, use OR across query terms; the overall candidate query remains AND. Batch these checks for the returned rows and run them only when requested.

`body_matches_all_terms` means the full AND expression matches the body. Use it to explain why context was necessary. Bound `metadata_excerpt` to 300 Unicode characters and include it only when metadata contributed. Do not add full paths and descriptions by default.

Keep `snippet` body-derived. Explicitly select the body column rather than allowing FTS5 to choose a metadata column automatically. If a metadata-only hit has no readable body, return an empty body snippet and the appropriate warnings. The metadata excerpt is a separate field, never a replacement for source evidence.

### 5.3 Update the real registration path

Update `PdfSearchRequest`, `PdfSearchSelect` and `PdfCandidate` in `selective_models.py`; `pdf_search()` forwarding and `PDF_DOC` in `selective.py`; and the relevant descriptions/signatures in `pdfs.py`. Preserve the registered tool names and `contract_version: 2`; this design adds optional inputs/details without removing existing required fields. Document the changed default ranking/search scope as an intentional behavior change.

Test discovery through `fastmcp.Client(mcp)`, not just direct Python calls. The published schema must expose the enum and optional selection, reject invalid values, and retain strict validation. Keep the default response budget and omission semantics; no extra `null` fields or full metadata dump.

Tool descriptions must explain context-enriched lexical matching, the `text` comparison mode, source-versus-metadata distinctions, continuation requirements, and that only page-associated metadata is used. Direct assistants to `read_pdf_pages` before rules claims. Restart offset pagination after library/index changes, and reuse the same query, mode, scope, selections and bounds for continuation.

## 6. Upgrade and lifecycle safety

### 6.1 Backfill already-indexed books without re-upload

Add a derived-index build version separate from the source revision. Compute an input fingerprint from canonical page text and ordered entry records, using unambiguous, deterministic serialization. Include the context-builder version in the rebuild decision.

During `Library.setup()`/startup, before PDF tools are available and before pending indexing jobs resume, create the new schema and backfill ready documents with missing, stale or incomplete contextual indexes. Use persisted `pages` and `entries`: no PDF parsing, network access, model call, replacement job or user upload is necessary.

For each document, rebuild its contextual rows and update `pdf_context_index_state` in one transaction. Verify that the contextual rows have exactly the same page-key set as the canonical pages, with no duplicates or missing pages; a matching row count alone is insufficient. A crash must leave either the previous complete per-document index or no committed new index state, never a marker claiming that a partial build is complete. Do not serve partial contextual coverage during startup.

Check fingerprints on later startups so older code or interrupted maintenance cannot leave a silently stale derived index after an upgrade. Skip unchanged builds. Remove orphan contextual/state rows for deleted documents. Use explicit transactions, and account for Python sqlite3's transaction behavior; do not accidentally commit midway through a migration via `executescript`.

If migration fails because of storage, invalid persisted metadata or resource limits, leave source tables and source statuses untouched and report a sanitized actionable startup error. Do not mark readable source books as failed PDFs, silently fall back to an incomplete contextual search, delete volumes, or replace document IDs.

### 6.2 Update every mutation path

Centralize helpers for inserting/removing derived search rows. Call them in the same database transactions that currently handle:

1. Initial indexing and explicitly retried indexing.
2. Successful upload replacement and retirement of old IDs.
3. User-requested deletion and any associated cleanup/recovery.

A failed replacement must keep both old indexes usable. A successful replacement must remove all old contextual rows and build-state records alongside the existing rows. A deleted PDF must disappear from both search modes. Startup backfill is not a substitute for correct ongoing writes.

Do not implement this migration by calling `Library.index()` on every ready book: that path changes processing status and reparses the source. Likewise, the current scan/refresh operation deduplicates existing sources and is not a general search-schema migration mechanism. [R3]

### 6.3 Account for storage and rollback

The contextual index duplicates normalized body text and adds postings/metadata. Extend the existing quota/headroom calculations to budget both indexes, metadata and migration transaction overhead. Measure actual growth on a synthetic corpus and, when available, a private copy of GM Core/Player Core. Do not claim an exact growth factor without measuring it.

Keep filesystem permissions, GM-trusted endpoint requirements, parser limits and sanitized logging unchanged. Never log page text or credentials. No Foundry browser or JavaScript module change should be required for this server-side feature.

Document backup and rollback using the project's existing private-volume procedures. Never present a live filesystem copy of an open SQLite database as a consistent backup. Test upgrade/restart on an isolated copy first; do not automatically migrate the user's production volumes during development verification.

## 7. Implementation sequence

| Step | Work | Completion gate |
| --- | --- | --- |
| 1. Baseline | Read current guidance, record existing named-lookup results and public schemas, add a synthetic context-only failure fixture. | The fixture demonstrably fails in text-only retrieval, and baseline tests pass. |
| 2. Pure context builder | Add `search_context.py` with deterministic provenance-aware projection, bounds and fingerprinting. | Unit tests cover deduplication, malformed metadata, empty metadata, and rejected heuristic ancestry. |
| 3. Derived index lifecycle | Add schema, startup backfill and atomic insertion/deletion/replacement hooks. | Migration, restart, quota-failure and lifecycle tests pass without source changes. |
| 4. Retrieval and contract | Implement the two modes, weighted matching, exact-title preservation, opt-in explanations, and typed tool wiring. | Direct and actual MCP-client tests agree; selection does not alter ranking. |
| 5. Evaluation | Compare synthetic challenge queries and the available private corpus in both modes. | Required functional gates pass; rank/latency/storage changes are recorded. |
| 6. Documentation | Update PDF/search docs, tool descriptions and relevant agent guidance. | Document limitations and evidence; do not overstate semantic or table support. |

Likely edited files: `pdf/library.py`, `mcp_server/selective.py`, `mcp_server/selective_models.py`, `mcp_server/pdfs.py`, `docs/pdf-library.md`, `docs/selective-reads.md`, and focused tests. Proposed new files: `pdf/search_context.py`, `tests/test_pdf_context_search.py`, `tests/test_pdf_context_migration.py`, and a bounded evaluation script if needed. Paths under `pdf/` and `mcp_server/` are relative to `foundry_mcp_server/`.

No extractor rewrite is required for this scope. Add tests documenting the current worker metadata assumptions. Any separately discovered outline-parser defect should receive its own focused fix and migration analysis rather than silently changing source extraction during this feature.

## 8. Test matrix

Use synthetic PDFs built with the existing pypdf-based test helper, plus small controlled SQLite fixtures for large/boundary cases. Do not commit copyrighted PDFs, extracted pages, private indexes or credentials. The repository already tests library restart, source reads, disabled-library denial, MCP discovery and uploads; extend those patterns. [R7] [R8]

| Area | Required assertions |
| --- | --- |
| Cross-field retrieval | The synthetic `Infiltration checkpoint` query misses in text mode and finds exactly the intended page in contextual mode; a missing extra term still causes a miss. |
| Ancestor-only context | A query term absent from page text but present in a bookmark ancestor contributes to matching. |
| Metadata-only page | A bookmark-only hit remains a candidate with sparse-text limitations and no invented body snippet. |
| Provenance | A false `heading_candidate.context` does not contribute ancestry terms; its title can still be indexed separately. |
| Page boundaries | Metadata from another page/book cannot leak into this page; sibling headings remain page-level navigation, not fabricated sentence-level scope. |
| Canonical reads | Document IDs, source revisions, labels, page text, warning lists, offsets and reconstructed page content are unchanged by the derived-index upgrade. |
| Ranking | Exact normalized heading promotion remains functional; ties are stable; `text` mode preserves the old index's ranking. |
| Selection | Candidate order is identical with details on/off; absent optional fields stay omitted; byte budgets can reduce a page of results without changing the underlying ordering. |
| Explanation | Cross-field matches report the right contributing fields; `body_matches_all_terms` is correct; metadata is never returned as the body snippet. |
| Query safety | Empty/punctuation-only queries, Unicode, underscores, diacritics, maximum word/character counts, quotes and operator-like input retain documented safe behavior. |
| Pagination | Limits, offsets, cap warnings, last-page behavior and ResponseTooLarge paths work in both modes. |
| Migration | Legacy database, fresh database, repeated startup, interrupted build, changed fingerprint and inconsistent row-count cases recover correctly without PDF re-upload. |
| Lifecycle | New upload, failed replacement, successful replacement, deletion and restart keep both indexes synchronized. |
| Bounds/security | Metadata truncation is reported; missing/disabled library and invalid selectors fail appropriately; quota/storage failures preserve sources and reveal no private text. |
| Discovery | `fastmcp.Client(mcp)` exposes the new fields through the real registered tool and validates both request and response. |

Run focused tests first:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_pdf*.py' -v
```

Then run the repository's CI entry point:

```bash
./scripts/test.sh
```

Use the existing Python 3.12 environment and locked dependencies. Current CI provisions Python 3.12, runs `uv sync --locked`, then `./scripts/test.sh`, and includes isolated container PDF-persistence checks. Extend those smoke checks where appropriate without modifying production deployments. [R9]

## 9. Retrieval evaluation and release gates

Record results for the eleven existing named-rule lookups documented in `docs/pdf-library.md`, including `DCs by Level`, `Free Archetype`, `Automatic Bonus Progression`, `Victory Points`, and `Bracelet of Dashing`. Re-establish the baseline on the actual available books; previously documented results are not a new test run.

Add at least ten queries where a necessary word is present only in a bookmark title or ancestor, plus negative controls and ambiguous broad-heading queries. Use a fixed evaluation set; do not tune weights and then report performance on only the same examples without disclosure. Compare Recall@1, Recall@5 and mean reciprocal rank, and record candidate counts, latency, build time and index size. These are proposed measurements, not claimed improvements.

Release gates:

- All synthetic functional, migration, lifecycle and public-contract tests pass.
- Existing named-rule lookups do not regress on the available baseline set.
- Metadata-dependent fixtures improve retrieval by construction, while negative controls remain negative.
- Source identity and page-read equality checks pass across the upgrade.
- Storage growth, latency and corpus limitations are recorded; missing private-corpus access is explicitly marked unverified.

For numeric table questions such as the level-based DC example, successful retrieval is not enough to establish row/column relationships. Keep the existing table warning and use a rendered source or an independently structured compendium table when a ruling depends on layout. This feature does not fix table extraction.

## 10. Deliberate exclusions and future augmentation

Do not add embeddings, FastEmbed, an LLM call, OCR, a reranker, fuzzy matching, query rewriting, generated summaries, automatic ruleset classification or a second service in this build. Do not index fabricated aliases for rule names.

Two possible follow-on projects are distinct from this one:

**Section-span propagation:** associate continuing pages with section ancestry using explicit outline structure, boundary rules, provenance and ambiguity handling. A bookmark is a destination, not an authoritative section end. Do not implement “last heading wins” as a shortcut.

**Semantic/hybrid search:** add semantic candidates only after measured terminology-mismatch failures justify it, while retaining source-page reads and lexical matching. It is not necessary to make the metadata already stored by foundry-mcp searchable.

## 11. What Codex should report at completion

Summarize changed files, migration behavior, public contract changes, tests actually run, and before/after retrieval measurements. Distinguish synthetic tests, local corpus evaluation, container checks and production verification. State any skipped checks and remaining risks. Do not describe this plan's isolated feasibility experiment as a project integration test.

The user-facing description should be approximately: “PDF search now matches extracted page text together with page-associated bookmark headings and section ancestry. Results retain exact page selectors; contextual matches remain candidates to verify against source pages.”

## 12. Evidence and feasibility record

Repository inspection was read-only. A separate in-memory experiment using **Python 3.13.5 / SQLite 3.46.1** verified the proposed FTS mechanics: cross-column AND matching, a negative extra term, a bookmark-only candidate, weighted ordering syntax and unchanged body text. This was not run inside foundry-mcp's Python 3.12 environment, did not use private rulebooks, and did not execute the repository test suite. Repeat the relevant tests in the target environment during implementation.

### Repository sources, pinned to the reviewed revision

[R1]: https://github.com/sesopenko/foundry-mcp/blob/a56db3905f299792204110296bf680cd7332e93b/pyproject.toml
[R2]: https://github.com/sesopenko/foundry-mcp/blob/a56db3905f299792204110296bf680cd7332e93b/foundry_mcp_server/pdf/worker.py
[R3]: https://github.com/sesopenko/foundry-mcp/blob/a56db3905f299792204110296bf680cd7332e93b/foundry_mcp_server/pdf/library.py
[R4]: https://github.com/sesopenko/foundry-mcp/blob/a56db3905f299792204110296bf680cd7332e93b/foundry_mcp_server/mcp_server/selective.py
[R5]: https://github.com/sesopenko/foundry-mcp/blob/a56db3905f299792204110296bf680cd7332e93b/foundry_mcp_server/mcp_server/pdfs.py
[R6]: https://github.com/sesopenko/foundry-mcp/blob/a56db3905f299792204110296bf680cd7332e93b/foundry_mcp_server/mcp_server/selective_models.py
[R7]: https://github.com/sesopenko/foundry-mcp/blob/a56db3905f299792204110296bf680cd7332e93b/tests/test_pdf_library.py
[R8]: https://github.com/sesopenko/foundry-mcp/blob/a56db3905f299792204110296bf680cd7332e93b/tests/test_pdf_tools.py
[R9]: https://github.com/sesopenko/foundry-mcp/blob/a56db3905f299792204110296bf680cd7332e93b/.github/workflows/ci.yml
[U1]: https://www.sqlite.org/fts5.html
[U2]: https://pypdf.readthedocs.io/en/6.21.1/modules/PdfReader.html

- [R1] Dependency manifest.
- [R2] PDF extraction and metadata provenance.
- [R3] Storage, indexing, search, page reading and lifecycle paths.
- [R4] Actual typed search-tool registration and forwarding.
- [R5] PDF tool wrappers and source-reading contracts.
- [R6] Public request/result and selective-response models.
- [R7] Existing PDF library tests.
- [R8] MCP discovery, source-read and access-boundary tests.
- [R9] CI runtime and verification workflow.
- [U1] Official SQLite FTS5 documentation: indexed columns, UNINDEXED, column filters, snippets and BM25.
- [U2] Official documentation for the pinned pypdf version: outline, destination-page and page-label APIs.
