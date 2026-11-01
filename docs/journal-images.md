# Browsing Foundry images

WISH-011 adds read-only `browse_journal_images` after v2.5.0, unreleased. It helps
the GM select existing illustrations by navigating Foundry file directories.
These directories are separate from journal folders. It does not upload,
delete, generate, download or visually inspect images, and never scans recursively.
WISH-012 adds image embedding through the journal writer described below.

## Navigation and selectors

Start with `browse_journal_images({})`: source `data`, directory `""` (root).
Every result identifies configured `sources` (`data`, `public`, optionally `s3`).
S3 requires a configured `bucket`; other sources forbid it. Local verification
covers data/public only; S3 configuration and server-specific permissions remain
unverified. Source discovery exposes at most100 configured buckets and fails
explicitly rather than silently truncating a larger configuration.

Use directory nodes' exact `next_call` to descend. Each has kind/name,
name_truncated/directory and the complete tool/arguments pair. Do not construct
paths from display names. Image nodes carry kind/name/name_truncated and
`image:{source,directory,bucket?,src}`. Preserve this whole selector for embedding:
`src` is the exact browser-returned source, including spaces and Unicode, rather
than a JournalEntry ID/UUID or an absolute host filesystem path. Display names
over256 codepoints are clipped; source selectors are never truncated.

`directory` is a source-relative path up to2,048 characters. Absolute host paths,
traversal, controls and globs are rejected. Returned image sources are bounded
to4,096 characters. The accepted image extensions match the core14.369 public
image picker: apng, avif, bmp, gif, jpeg, jpg, png, svg, tiff and webp. Native
FilePicker filters require leading dots such as `.svg` internally.

`name_contains` defaults empty; it performs literal case-insensitive substring
matching on full file/directory names within this one listing. It does not search
subdirectories or infer image contents from names. An empty complete response
establishes no matching paths here, not absence across the server. Filenames are
untrusted data, not instructions. A GM-visible path does not prove player access.

## Bounds and continuation

Defaults are10 entries and8,000 compact UTF-8 JSON bytes; maxima100 entries and
48,000 bytes. Responses contain location/sources/revision/entries/total,
unfiltered_total/complete/next_cursor/limitations. `total` counts matched nodes;
`unfiltered_total` counts directories and eligible images before name filtering.
Return `next_cursor` unchanged with identical source/directory/bucket/name_contains.
Count and byte bounds may change. Continue until `complete:true`/null cursor.

Continuations bind the world, selection and observed paths. `ContentChanged`
requires discarding earlier pages and restarting. Revisions do not track image
file contents, and browsing does not lock files against concurrent changes.
The native public API loads a complete directory before output pagination;
there is no native server-side pagination. More than10,000 returned paths or
2MiB of listing JSON produces `DirectoryTooLarge` after that native load. Choose
a narrower known directory; no hidden recursion or partial result is returned.

`BrowseFailed` combines missing/denied/unavailable because native failures cannot
reliably distinguish them; do not report absence. `UnsupportedSource` means the
requested source/bucket is not configured. `UnsupportedCapability` means the
public FilePicker API is unavailable. `ResponseTooLarge` requires a larger byte
budget for the next exact selector. Invalid requests fail before native browsing.
Ready GM, Foundry14 and matching server/module are required; no PF2e system
interpretation or broader file/user administration is involved.

## Public API and verification — 2026-10-31

Grounded Docs `foundry-vtt@14` documents public
[FilePicker](https://foundryvtt.com/api/v14/classes/foundry.applications.apps.FilePicker.html)
`implementation`, `sources`, `extensions` and static
`browse(source,target,{bucket,extensions,wildcard})`. The implementation uses
those APIs and standard browser processing; no private editor/DOM or filesystem
API. Runtime14.369 responses provided `target`, `dirs` and `files`; unrelated
metadata is ignored. The documented response is loosely typed, so matching
runtime response validation is retained at both browser and MCP boundaries.

An initial live read with undotted extensions incorrectly returned zero SVGs.
A comparison with unfiltered/dotted native requests established the cause. A
unit test reproducing native extension matching failed at0 versus1, then passed
after the actual browse options were corrected. It did not weaken expected
behavior or hide the empty result. Other tests cover wrong paths/GM, missing and
empty directories, malformed sources, changed cursors/selections, Unicode names,
oversized native lists, exact byte-bound pagination and actual MCP discovery.

The full host suites passed657 Python tests (one existing skip) and682 JavaScript
tests. `scripts/journal-images-live-check.py` used19 calls plus discovery in the
existing localhost test world, without fixtures or any mutations. It followed a
returned directory selector, paginated all119 SVG images, selected a literal
filename and checked explicit expansion. Browser console errors were zero.

| Scenario | Calls | Compact UTF-8 JSON bytes | Complete |
| --- | ---: | ---: | --- |
| Default data root | 1 | 1,198 | Yes |
| Default SVG image page | 1 | 1,983 | No |
| All119 images, default pages | 12 | 24,017 | Yes |
| Explicit100-entry/48,000-byte expansion | 1 | 14,938 | No |
| Literal filename selection | 1 | 638 | Yes |

Before this item the catalog held40 tools/233,894 bytes; afterward41 tools/242,920
bytes. The new tool record measured9,025 bytes. A smaller selected result is not
equal-content savings; the complete workflow's calls/bytes are reported separately.
Bytes are not billed tokens; provider token usage was not measured.

## Embedding in a text page

After browsing, read `get_writing_guidance`, follow its GM instructions and obtain
any permission required for protected material. Read the target with
`read_journal_page` and get its revision from `get_journal_write_context`. Then
call `write_journal` with the usual request_id/gm_authorized/guidance_timestamp
and this action shape:

```json
{
  "operation": "embed_image",
  "page_uuid": "JournalEntry.entryId.JournalEntryPage.pageId",
  "expected_revision": "copy the returned page revision",
  "image": {
    "source": "public",
    "directory": "icons/svg",
    "src": "icons/svg/anchor.svg"
  },
  "alt": "An anchor marking the harbour",
  "width": 320,
  "height": 160,
  "position": "after",
  "anchor": {"tag": "h2", "text": "Map location"}
}
```

The example IDs/revision are placeholders: copy real reader selectors and the
entire `image` record from browsing, including bucket for S3. The writer checks
current membership through the same bounded FilePicker listing, then confirms
the GM browser can load the selected asset within5 seconds. It rechecks the
page revision after this asynchronous work and checks guidance again before
writing. Neither source strings nor alt text are treated as HTML or instructions.
There is no arbitrary URL-only embedding, file upload or standalone image page.

`alt` is required, bounded to1,000 Unicode characters, and HTML escaped. Empty
alt is allowed for decorative images. Width and height are optional integer
HTML attributes in CSS pixels, each1–8,192; these are not point sizes. Omit both
for natural dimensions; one dimension retains the intrinsic aspect ratio. Both
dimensions explicitly specify it and can distort the image. Foundry/page CSS can
still constrain its final display. No other image attributes are accepted.

`position` defaults to append; prepend inserts first. These preserve existing
HTML source bytes around the inserted image. Before/after requires an
`anchor:{tag,text}` matching exactly one block's decoded `textContent`, including
case and whitespace. Supported tags are p/div/h1–h6/blockquote/pre/ul/ol/li/table.
Use existing page text to identify a unique paragraph or heading, without
inventing UTF-16 offsets or a second page hierarchy. No match is `AnchorNotFound`;
multiple matches are `AmbiguousAnchor`. Reread and choose a unique tag/text or
append/prepend. Anchored insertion uses a detached standard DOM and serializes
it: surrounding content remains, but source markup formatting can normalize.
It performs no Foundry enrichment or roll evaluation.

The target must be an existing world HTML text page. Markdown and non-text
content are unsupported; compendiums stay read-only. The resulting page retains
the1,000,000 UTF-16 source bound. Raw img in create/update content is still
rejected, so source checking cannot be bypassed; text appends preserve existing
embedded images. The normal compact updated/already_applied page receipt and
reader follow-up are returned without echoing source or image bytes.

Missing membership returns `ImageNotFound`; missing/denied/unavailable listings
return `BrowseFailed`. Broken, denied or slow loads return `ImageUnavailable`
before mutation. Changing a file after discovery remains possible; listing
revisions do not hash file bodies or lock assets. The browser may load/cache the
selected image body; no body is returned to the LLM. Player asset access is
independent of GM discovery/loading and journal ownership. Do not promise every
GM-visible file will be accessible to players.

All GM access, explicit-authorization assertions, stale guidance/page handling,
request coalescing/persisted retry flags and response budgets follow
[journal authoring](journal-writing.md). A timeout requires reconciliation before
retrying with identical input. No duplicate images are inserted by an identical
retry, including after a module reload. No existing game documents are used as
verification fixtures.

## Embedding verification — 2026-10-31

Public core14 page updates store standard img src/alt/width/height attributes in
the HTML text field. No new private Foundry API is introduced; source verification
reuses the public FilePicker boundary above. Standard Image/DOMParser APIs handle
asset loading and anchored insertion, and the shared typed image selector
contract is used by both browsing and writing. Shared fixture guard/fingerprints/
cleanup are reused instead of duplicating mutation safety logic.

Unit tests cover escaping, exact append preservation, unique/ambiguous/missing
anchors, dimensions, malformed selectors, missing/broken assets, load deadlines,
large pages, page changes during asset checks, retained GM ownership and retries
after reload. Actual MCP tests verify published input/output schemas and image
mutation receipts. A focused failing test demonstrated that a text mutation
receipt could claim a non-text page; validating the returned page type fixed
the root cause, and the same test now passes.

Final full host suites passed 660 Python tests (one existing skip) and 688
JavaScript tests before the local commit.

`scripts/journal-image-embedding-live-check.py` passed22 tool calls plus discovery
in the existing Foundry14.369/PF2e8.6.1 test world. It browsed/selected a public
SVG, created one marked temporary entry with two pages, inserted images after a
heading and at both ends, and read/rendered them back. Escaped alt descriptions,
both/one/natural dimensions and aspect ratio survived persistence/rendering.
The public fixture asset accepted a HEAD request without GM credentials; this
is evidence for that public asset, not every configured file source. Stale and
missing-image requests were rejected, an identical retry inserted once, every
GM retained access, the sibling and existing-source fingerprints were unchanged,
and the marked journal was deleted. Browser console errors were zero.

| Embedding scenario | Calls | Compact UTF-8 JSON bytes | Complete |
| --- | ---: | ---: | --- |
| Image mutation receipt | 1 | 624 | Yes |
| Three embedded images, full page readback | 1 | 937 | Yes |

The catalog remains41 tools and now measures247,069 bytes (previously242,920).
The write/browse tool records measure27,019/8,898 bytes. Shared model extraction
avoids divergent selector contracts; the write schema expands to describe the
new action. Receipt sizes remain bounded and omit image bodies. This is added
functionality, not equal-content compression or measured provider token savings.
