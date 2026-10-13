# Grounded PDF Rule Lookup for `foundry-mcp`

**Build-agent handoff — revised after testing two Pathfinder rulebooks**

**Repository:** https://github.com/sesopenko/foundry-mcp  
**Research date:** October 12, 2026  
**Status:** Research and implementation specification. No repository files have been modified.

## 1. Mission

Add a local PDF reference library to the existing gameplay-facing Python MCP server so that Codex or another MCP-enabled LLM can **look up actual game rules, spells, conditions, feats, items, tables, and GM guidance before answering questions**.

The primary goal is to prevent confident, invented game mechanics.

The LLM must be able to find the original source, read the relevant passage, cite the correct book and page, and distinguish direct source evidence from its own interpretation.

**A search result is a candidate, not proof. A vector similarity score is not a measure of factual correctness.**

The solution must work without an additional RAG server, database daemon, paid LLM API, or cloud embedding API. Codex provides reasoning; the Python MCP server provides retrieval.

### Essential constraints

- Integrate into the existing Python 3.12 FastAPI/FastMCP application.
- Do not route local PDF operations through the Foundry browser/WebSocket bridge.
- Accept a configured local folder containing user-owned PDFs. Never expose arbitrary filesystem paths as MCP tool arguments.
- Keep source files and extracted content local to the indexing process, except for bounded excerpts returned to the connected MCP client.
- Do not require LangChain, LlamaIndex, Docker, or a remote vector database.
- Grounded Docs is exclusively development tooling for Foundry API documentation. It is not part of the gameplay PDF implementation.
- Do not put copyrighted books, derived indexes, embeddings, or extracts into Git.
- Preserve differences between rulesets, editions, optional variants, house rules, and GM interpretation.
- Do not claim that hallucination is eliminated; demonstrate grounding and safe abstention.

## 2. Integration with the existing repository

Current relevant files:

- `pyproject.toml`: Python 3.12, `uv`, FastAPI, FastMCP and Uvicorn.
- `foundry_mcp_server/mcp_server/server.py`: the central FastMCP instance.
- `foundry_mcp_server/mcp_server/tools.py`: existing MCP tool registration.
- `foundry_mcp_server/mcp_server/journals.py`: good examples of bounded tools, opaque identifiers, pagination, and descriptive contracts.
- `foundry_mcp_server/main.py`: ASGI app, `/mcp/mcp` endpoint, and Foundry WebSocket.
- `foundry_mcp_server/config.py`: existing environment configuration.
- `AGENTS.md`: mandatory conventions for documenting, validating and testing MCP tools.

PDF lookup belongs directly in the Python MCP runtime and must operate independently of the connection to the GM browser.

Suggested structure:

```text
foundry_mcp_server/
  mcp_server/
    pdf_library.py
  pdf_reference/
    extract.py
    headings.py
    chunks.py
    store.py
    indexer.py
    search.py
    embeddings.py  # optional phase 2
```

Maintain the repository's single-process architecture and its existing test/lockfile conventions.

## 3. Dependencies

### 3.1 `pypdf` — source extraction

`pypdf` is a BSD-3-Clause pure-Python PDF parser. It reads PDF structures, pages, content streams, fonts, outlines/bookmarks, metadata, and page-label definitions.

`page.extract_text()` reconstructs text using the character drawing instructions embedded in the PDF. It does not visually interpret a rendered page, recover semantic paragraphs reliably in every document, or perform OCR.

Example:

```python
from pypdf import PdfReader

reader = PdfReader(pdf_path, strict=False)
labels = reader.page_labels

for index0, page in enumerate(reader.pages):
    text = page.extract_text() or ""
    pdf_page_number = index0 + 1
    page_label = labels[index0]
```

`reader.outline` and `reader.get_destination_page_number(...)` expose the hierarchical bookmarks and their target physical pages.

**Integration requirements:**

- Store source-extracted text separately from normalized search text.
- Store physical page numbers and PDF-defined page labels separately.
- Preserve bookmark hierarchy, including parent sections.
- Detect encrypted, malformed and non-extractable PDFs without silently claiming a complete index.
- Avoid automatically treating short divider/art pages as scanned documents.
- Respect PDF stream memory and processing limits.
- Use ordinary extraction as the initial retrieval-text default, not layout extraction, subject to regression testing.
- Never silently invent table row/column relationships from flattened text.

The pinned release needs compatibility validation on Python 3.12. The two-book experiments used `pypdf 5.9.0`; the previously identified newer release was `6.20.1`. Repeat the tests after choosing the final pin.

Documentation: https://pypdf.readthedocs.io/en/stable/user/extract-text.html

### 3.2 `fastembed` — optional semantic search

FastEmbed generates local vector representations of text with ONNX Runtime. It is not a PDF reader or an LLM.

The default `BAAI/bge-small-en-v1.5` model produces 384-dimensional embeddings and has a 512-token input limit. These vectors can be compared with cosine similarity to find passages discussing similar concepts in different wording.

For example:

```python
from fastembed import TextEmbedding

model = TextEmbedding(
    model_name="BAAI/bge-small-en-v1.5",
    cache_dir="/persistent/model-cache",
    local_files_only=True,
    threads=2,
)

passages = list(model.passage_embed(["A rules passage"]))
query = list(model.query_embed("A question about the rule"))[0]
```

**Important gotchas:**

1. FastEmbed normally downloads model artifacts on first initialization. Provision these explicitly and retain a persistent cache. Normal gameplay must not surprise users with a download.
2. The BGE-small input limit is 512 *embedding-model* tokens. The previously proposed 800–1,200 token chunks are too long.
3. Start around 300–400 embedding tokens per chunk with roughly 40–60 overlapping tokens, then tune against retrieval benchmarks.
4. FastEmbed's `token_count()` can count already-truncated token sequences. Do not use it alone to prove the entire source passage fits. Validate chunk lengths with an untruncated tokenizer.
5. Pin package and model identities; record model revisions and dimensions. Changing a model requires index invalidation/re-embedding.
6. ONNX inference is synchronous CPU work. Do not block the FastAPI event loop with large indexing batches.
7. Similar passages are not necessarily equivalent game mechanics. Semantic retrieval should improve discovery, not override direct definitions.
8. Local inference does not mean the complete Codex interaction is offline. Excerpts returned over MCP are passed to the connected model client.

**Recommendation:** FastEmbed should be optional in phase 2. First prove that a smaller lexical and heading-aware implementation finds the actual source rules correctly.

FastEmbed source: https://github.com/qdrant/fastembed

### 3.3 SQLite FTS5 — first-line search

Use Python's built-in SQLite support and FTS5 for text search, phrases and BM25 ranking.

SQLite also holds document metadata, pages, headings, indexing status and source revisions.

No external database process is needed.

If embeddings are later enabled, store validated `float32` vectors in SQLite BLOBs and search a bounded NumPy matrix in memory. A 50,000 × 384 float32 matrix requires approximately 73 MiB of raw vector memory.

Use parameterized SQL and safe FTS5 query generation. Parameter binding alone does not make arbitrary `MATCH` syntax valid or harmless.

## 4. Validation using two user-owned Pathfinder PDFs

The proposed solution was evaluated against:

| Characteristic | Player Core | GM Core |
|---|---:|---:|
| Physical PDF pages | 466 | 338 |
| File size | 28.85 MB | 16.52 MB |
| PDF bookmarks | 666 | 489 |
| Median extracted characters/page | 4,759 | 4,851 |
| Pages with fewer than 100 extracted characters | 16 | 4 |
| Pages with no extracted text | 0 | 0 |
| Cover page label | `Front Cover` | `Cover` |

Both are text-searchable PDFs with multi-column layouts and extensive navigation. Neither sample requires OCR.

Their first physical page is a cover, and physical page 2 has page label `1`. The cover labels differ, demonstrating why page mappings must be read from each PDF rather than inferred by arithmetic.

**Important:** These results describe the specific uploaded copies. They do not prove that all Pathfinder PDFs, revisions, or third-party rulebooks behave identically.

### 4.1 What generalized across both books

- PDF physical page numbering differs from printed/page-label numbering.
- Repeated side navigation, section references and indexes can contaminate search.
- Two-column extraction behavior varies by page.
- PDF bookmarks are useful for locating sections and tables.
- Bookmarks are not a complete index of individual rules, spells and items.
- A search hit may be a passing mention, a list entry, or a full definition.
- Extracted numeric tables must be checked for correct row/column relationships.
- The authoritative source text must be read after a search before the LLM makes a specific mechanical claim.

### 4.2 Page-level SQLite FTS5 baseline

A diagnostic FTS5 index was constructed from the ordinary `pypdf` text extraction of every physical page in both books. Exact phrases were ranked using `bm25()`.

These are page-level baseline measurements, not benchmarks of the proposed entry-aware retrieval system or FastEmbed.

| Book | Query | Correct source (printed page) | Correct-page ranking |
|---|---|---|---|
| Player | `sure strike` | Full spell, 361 | 6 of 8 |
| Player | `grabbed` | Condition, 444 | 10 of 22 |
| Player | `persistent damage` | Condition, 445 | 1 of 24 |
| Player | `spellcasting services` | Table, 295 | 1 of 1 |
| GM | `free archetype` | Variant, 84 | 1 of 44 |
| GM | `automatic bonus progression` | Variant, 83 | 1 of 44 |
| GM | `victory points` | Subsystem, 184 | 1 of 25 |
| GM | `encounter budget` | Table, 75 | 2 of 4 |
| GM | `dcs by level` | Table, 53 | 2 of 2 |
| GM | `treasure table` | Main catalogue, 320 | **66 of 169** |
| GM | `bracelet of dashing` | Complete item entry, 286 | **2 of 2** |

The ranking variability is significant. Some direct definitions are easy for FTS5 to find, while others are outranked by unrelated references.

**The definition-vs-mention failure is now independently demonstrated in both books.**

### 4.3 New issue: item catalogue mentions can outrank stat blocks

*GM Core*'s **Bracelet of Dashing** illustrates this well.

The full item stat block appears on printed page **286** (physical PDF page **287**). It provides the item's name, level, traits, price, usage, and activation/effect details.

The **Treasure Table** on printed page **320** (physical **321**) lists that item in a catalogue row.

A plain FTS5 search for the item name ranked the *catalogue row first*, ahead of the complete item definition.

Moreover, *Bracelet of Dashing* has **no named PDF bookmark**. *Ring of Sigils* is another example of an item entry without a corresponding named bookmark.

**Implementation consequences:**

- Detect actual stat-block headings from extracted text in addition to using PDF bookmarks.
- Keep `item_stat_block`, `table_listing`, `section`, and `mention` roles distinct where confidently identifiable.
- Rank full stat blocks above directory/index/table listings for named item lookups.
- Allow a list or catalogue to serve as navigation toward its complete item entry.
- Return a surrounding span sufficiently long to include the item's activation details; do not return only the heading or price.

A full item entry should be retrievable without needing semantic embeddings.

### 4.4 New issue: variant rules need context

*GM Core* contains optional rules in **Chapter 2: Building Games > Variant Rules**, including:

- **Automatic Bonus Progression**, printed page 83, physical page 84.
- **Free Archetype**, printed page 84, physical page 85.
- **Proficiency without Level**, within the same variant-rules section.

The PDF's nested bookmarks include the section hierarchy.

When the LLM retrieves *Free Archetype*, it should know it has located **an optional variant**, not a mandatory default rule.

The server should preserve:

```text
document: GM Core
chapter: Building Games
section: Variant Rules
entry: Free Archetype
entry_role: variant_rule
page_label: 84
pdf_page_number: 85
```

Do not silently enable optional rules or merge them with ordinary Pathfinder mechanics.

The same applies to GM advice: a relevant recommendation from *GM Core* is not necessarily the underlying default mechanical rule from *Player Core*.

### 4.5 New issue: tables can have correct values but wrong associations

*GM Core* printed page **53** (physical **54**) contains several distinct tables:

- **DCs by Level**
- **Spell Rank DC**
- **DC Adjustments**
- **Simple DCs**

The DCs by Level table itself has two adjacent groups of level/DC columns.

In ordinary `pypdf` extraction, the **DCs by Level** heading is followed by the **Spell Rank DC** values before the level/DC rows appear later.

That can lead to a particularly dangerous retrieval failure: the numerical values exist in the text, but the LLM may associate them with the wrong table.

The system must not treat nearby extracted text as proof that a value belongs to a heading.

For numeric/table-based questions, require either:

- a confidently extracted row and column association, or
- a way for the LLM/client to visually inspect the rendered PDF page.

If neither is available, expose an explicit `table_layout_uncertain` warning and avoid presenting a guessed numerical result as verified.

### 4.6 Extraction-mode comparison

Ordinary `extract_text()` and layout extraction were compared on selected pages and against rendered page images.

| Page | Ordinary text | Layout mode |
|---|---:|---:|
| GM Core 53 — DC tables | 4,351 chars | 13,390 chars |
| GM Core 133 — Magic item DCs/prices | 3,893 chars | 39,527 chars |
| GM Core 184 — Victory Points | 4,346 chars | 7,108 chars |
| GM Core 320 — Treasure Table | 3,790 chars | **83,582 chars** |
| Player Core 295 — Spellcasting Services | 4,238 chars | 41,203 chars |
| Player Core 361 — Sure Strike | 4,849 chars | 18,260 chars |

Layout mode sometimes produced dramatically more fixed-width whitespace and did not solve semantic table reconstruction.

Use **ordinary pypdf extraction for baseline indexing**, subject to later quality tests. Preserve original extracted text separately from a normalized search representation.

Do not simply feed raw layout-mode text into the embedding model: extensive whitespace and disordered table content waste context and can obscure the real rule.

### 4.7 Cross-book ambiguity

A combined FTS5 search for **Hero Points** ranked relevant passages from both books:

- *Player Core*, printed page **413** — general Hero Point mechanics.
- *GM Core*, printed page **57** — guidance for awarding Hero Points.

Both can matter to a gameplay question. Their roles differ.

The MCP must preserve source identity and context so Codex can inspect both when appropriate, rather than synthesize one untraceable rule.

Likewise, cross-references in *GM Core* pointing back to *Player Core* should be treated as navigation to an additional source, not as replacements for the complete source rule.

## 5. Proposed retrieval architecture

```text
Codex / LLM Client
   |
   | MCP requests
   v
Existing FastMCP application
   |
   +-- PDF reference tools
         |
         +-- Configured PDF directory
         |
         +-- pypdf extraction
         |     - page text
         |     - page labels
         |     - bookmark hierarchy
         |     - extraction diagnostics
         |
         +-- Heading / stat-block detection
         |
         +-- SQLite
         |     - documents
         |     - pages
         |     - entries
         |     - FTS5 chunks
         |
         +-- Optional FastEmbed search
```

This operates alongside, but independently of, the existing Foundry WebSocket-based tools.

### Configuration

Suggested environment variables:

```dotenv
FOUNDRY_MCP_PDF_LIBRARY_DIR=/absolute/path/to/owned-books
FOUNDRY_MCP_PDF_INDEX_DIR=/absolute/path/to/index
FOUNDRY_MCP_PDF_EMBEDDINGS_ENABLED=false
FOUNDRY_MCP_PDF_MODEL_CACHE=/absolute/path/to/models
```

Absent configuration should produce an actionable **PDF library not configured** result. It must not initiate an unrestricted scan of the user's home directory.

### Index records

**Documents:** opaque ID, relative path, display title, hash, modification metadata, number of pages, ruleset/edition when known, indexing status, source revision.

**Pages:** document ID, physical PDF index/number, PDF page-label string, label provenance, original extracted text, normalized search text, extraction-quality flags.

**Entries:** document ID, heading, entry type, source span, page number, parent chapter/section, bookmark/heading detection provenance, variant-rule context when grounded.

**Chunks:** source span, text, document ID, entry linkage where available, version/content hash.

**FTS5:** lexical retrieval over headings, normalized chunks, and book/title metadata.

**Embeddings (optional):** model identifier, artifact revision, dimensions, source-chunk hash, stored vector.

Do not discard the original page text when building derived search indexes.

### Retrieval priority

1. Resolve an exact named rule, spell, condition, feat, item, table, or subsystem heading if present.
2. Use PDF bookmarks and parent section paths for sections/tables.
3. Detect stat-block headings missing from bookmark outlines.
4. Search lexical FTS5 candidates and prefer actual definitions over lists/index references.
5. Optionally expand with semantic search if that measurably improves recall.
6. Return bounded candidates with source, page, section, role, and quality information.
7. Let the LLM read exact source text before making a rule claim.
8. Search additional related rules or books as necessary.
9. If source information is incomplete, conflicting or structurally ambiguous, report uncertainty rather than inventing a ruling.

Repeated navigation headings must not be mistaken for full definitions. Uppercase text alone is insufficient evidence that a segment is a stat block.

## 6. Proposed MCP tools

### `list_pdf_documents()`

Discover indexed books and index health.

Return document IDs, display titles, relative paths, page counts, indexing status, editions when known, and incomplete/unsupported warnings.

### `locate_pdf_entry(name, document_id=None, limit=10)`

Locate an exact or normalized **entry heading**.

Examples:

- `Sure Strike`
- `Grabbed`
- `Bracelet of Dashing`
- `Free Archetype`
- `Treasure Table`

Return candidate pages, heading source (`bookmark`, `stat_block_heading`, `heuristic`), chapter/section breadcrumb, match role, optional-rule context, and enough metadata to retrieve the complete source.

A heading not found in the bookmark outline must not be treated as evidence the entry does not exist.

### `search_pdf_documents(query, document_id=None, limit=10, cursor=None)`

Find bounded text matches using FTS5 (optional hybrid search later).

Expose the search semantics and whether results are complete. Return text excerpts, document/source IDs, physical pages, page labels, optional-rule context, and result roles where known.

Use safe construction of FTS5 `MATCH` queries. Handle spell names, apostrophes, hyphens, quotation marks, and punctuation.

### `read_pdf_pages(document_id, pdf_page_number, max_chars=12000, cursor=None)`

Read canonical extracted text from one physical page.

Return exact document/page identity, label, revision, source text fragment, offsets, completeness, continuation cursor, and extraction-quality warnings.

Warn when numerical tables have uncertain structure. Clearly distinguish physical page numbers from PDF page-label strings.

Opaque cursors must fail as stale after relevant source/index revisions.

### `refresh_pdf_index()`

Scan for new, changed and removed documents.

Update extracted content and search metadata incrementally. Report indexing status, updated/skipped/error counts, and actionable diagnostics.

Do not block the MCP server event loop while extracting hundreds of pages. Prevent overlapping refreshes.

All tools must have self-contained FastMCP discovery descriptions, as required by `AGENTS.md`.

## 7. Index lifecycle, reliability, and security

- Scan only the configured allowlisted directory.
- Reject filesystem paths supplied by the LLM. Prefer rejecting symlinked PDFs for the initial release.
- Persist extracted content/index outside the repository.
- Detect file revisions using size, modification time and content hash, and avoid rebuilding unchanged books.
- Separate an unavailable library mount from a legitimately empty library. Do not delete cached contents because a mount temporarily disappears.
- Use transactions to publish consistent document/page/FTS records.
- Keep reader access available during background indexing when possible.
- Prevent multiple simultaneous index writers.
- Bound PDF size, decompressed-stream resource use, pages, extraction time, query size and response bytes.
- Keep health checks and existing Foundry tools responsive while indexing.
- Do not log complete copyrighted passages.
- Treat PDF content as untrusted **data**, not as instructions to the assistant or MCP server.
- Handle model cache misses and unsupported PDF features with explicit errors.
- Ensure no indexing/embedding API calls leave the user's computer, apart from separately authorized model provisioning.
- Be clear that tool-returned text is sent to the configured LLM client.

## 8. Testing and acceptance criteria

### Automated tests

Use small, synthetic, redistributable PDF fixtures to test:

- File discovery, updates, deletions, renames and broken sources.
- Correct page numbers and custom page labels.
- Source IDs, index revisions and stale cursors.
- Two-column text, nav noise, line breaks, ligatures and hyphenation.
- Named definitions outranking mentions.
- Complete item stat blocks outranking catalogue rows.
- Heading detection when bookmark metadata is missing.
- Nested outline context for optional variant rules.
- Numeric table headings whose values appear in unexpected extraction order.
- Multiple documents providing complementary rules.
- Safe FTS query escaping and bounded result sizes.
- Indexing without breaking FastAPI responsiveness.
- Offline use, no surprise downloads, and correct failure diagnostics.
- Optional embedding token truncation and model-version invalidation.

### Real-book regression: Player Core

Use the developer's own legal local copy, not a committed test fixture.

1. Detect **466** physical pages and the PDF label mapping.
2. Find the full **Sure Strike** spell definition, printed **361**, physical **362**.
3. Find the **Grabbed** condition definition, printed **444**, physical **445**.
4. Find **Persistent Damage**, printed **445**, physical **446**.
5. Retrieve **Spellcasting Services**, printed **295**, physical **296**, without inventing table associations.
6. Verify that source pages, not earlier mentions, are what Codex reads before answering.

### Real-book regression: GM Core

1. Detect **338** physical pages and the `Cover` page label.
2. Locate **Free Archetype**, printed **84**, physical **85**, and identify its **Variant Rules** ancestry.
3. Locate **Automatic Bonus Progression**, printed **83**, physical **84**, and mark it optional.
4. Locate **Victory Points**, printed **184**, physical **185**.
5. Locate **Encounter Budget**, printed **75**, physical **76**.
6. Locate **DCs by Level**, printed **53**, physical **54**, and avoid confusing its Level/DC rows with Spell Rank/DC rows.
7. Locate the main **Treasure Table**, printed **320**, physical **321**, even though baseline full-page search ranked it 66th.
8. Locate the full **Bracelet of Dashing** stat block, printed **286**, physical **287**, despite the absence of a matching PDF bookmark and the catalogue hit ranking above it.
9. Verify extraction quality on printed **53**, **133**, and **320** against visual renders, especially the association between table headings, columns and values.
10. Preserve enough item text for Codex to read the activation/effect rather than extrapolate from the item name.

### Cross-book gameplay regression

Test a question involving **Hero Points** requiring both *Player Core*'s general mechanics (printed 413) and *GM Core*'s award guidelines (printed 57).

The response should preserve which book contributes which evidence.

Test an optional variant question and verify that the LLM does not imply the campaign uses Free Archetype merely because its rules are indexed.

Test an ambiguous numerical table question and verify safe uncertainty instead of an invented number.

### Required quality bar

Exact named entries should return the complete relevant definition among the first few candidates, ideally first.

The following are unacceptable as final behavior:

- `Grabbed` definition ranked 10th without heading-aware correction.
- `Treasure Table` buried at 66th despite an exact bookmark.
- *Bracelet of Dashing* catalogue mention treated as its full mechanical description.
- Optional Free Archetype rules presented as universally applicable.
- Unverified numeric table associations presented as confident facts.

## 9. Build sequence

**Phase 0 — Dependency and corpus baseline.** Validate Python 3.12 package compatibility, inspect repository conventions, create synthetic PDF fixtures, and repeat representative extraction tests using the pinned dependency versions.

**Phase 1 — Source-grounded lexical lookup.** Implement PDF root configuration, extraction, page labels, bookmark hierarchy, stat-block heading discovery, SQLite FTS5, bounded reads and MCP tools. No embeddings required.

**Phase 1b — Accuracy and safety.** Fix misranking caused by navigation/list references; preserve variant contexts; validate item entries and numeric tables; test cross-book retrieval and reliable abstention. Make sure existing Foundry tools remain responsive.

**Phase 2 — Optional FastEmbed.** Add local semantic candidate retrieval only if measured queries show lexical misses. Respect model tokenizer limits, offline model provisioning, index invalidation, and source-read-first semantics.

**Phase 3 — Targeted enhancements.** Consider visual page inspection for complex tables, OCR for actual scans, publisher errata relationships, and edition-specific source precedence as separately scoped improvements.

## 10. Build-agent handoff requirements

Before declaring completion, the implementation agent should report:

- Dependency versions and reasons for selection.
- Exact MCP discovery schemas, tool contracts, and configuration.
- Indexing/storage lifecycle.
- Automated tests and real-book tests actually run.
- Results of the definition-versus-mention retrieval cases.
- Known extraction errors, particularly tables and navigation text.
- Whether a model download or OCR capability remains optional.
- Confirmation that the PDF tools operate without a Foundry GM browser connected.
- Confirmation that no additional RAG server, remote embedding service, or paid model API is needed.

**Success is not that Codex always gives an answer. Success is that it can find the source, verify what it says, cite it correctly, and admit when the available evidence is inadequate.**

## 11. Source references

- Repository: https://github.com/sesopenko/foundry-mcp
- pypdf extraction: https://pypdf.readthedocs.io/en/stable/user/extract-text.html
- pypdf reader/bookmark APIs: https://pypdf.readthedocs.io/en/stable/modules/PdfReader.html
- pypdf PyPI: https://pypi.org/project/pypdf/
- FastEmbed: https://github.com/qdrant/fastembed
- FastEmbed guide: https://qdrant.github.io/fastembed/Getting%20Started/
- SQLite FTS5: https://www.sqlite.org/fts5.html

---

**Final recommendation:** Start with **pypdf + SQLite FTS5 + PDF-bookmark/stat-block-aware lookup + bounded page reading**. Treat optional rules and table ambiguity as first-class source metadata. Add local embeddings only if testing shows a real retrieval benefit.