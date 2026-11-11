# Foundry image previews and map crops for ChatGPT

Implement two production MCP tools in `sesopenko/foundry-mcp`. A GM should be able to ask ChatGPT what an NPC portrait shows or what is written in one room on a large map. ChatGPT first identifies the Foundry file, can ask for its original dimensions, and can fetch an overview or a selected rectangle through a unique HTTPS URL. The feature reads existing Foundry content. Its writes belong to the MCP server’s private image store.

**Codex CLI handoff.** Read this entire file and the checkout’s `AGENTS.md` before starting. **Immediately after every context compaction or session resume, reopen this plan from disk and reread it in full** before choosing your next action. Recover its saved path from the kickoff prompt. Reconcile the current diff and test results against the acceptance criteria below, then continue from the first unfinished item. Use the repository’s normal unattended development workflow. Complete all independent work if a live service is unavailable and report the exact unverified step. The handoff covers implementation and local verification.

## Contract and example

Add `get_foundry_image_info` and `get_foundry_image_url` to actual FastMCP discovery with strict typed inputs and outputs. Accept the existing canonical `image` selector (`source`, `directory`, optional `bucket`, exact `src`), a single `src` taken from stored journal HTML or a portrait reference, or the scene-aware `map` selector described below. These work without a previous browse call. The URL tool also accepts `source_id` from the info tool. Require exactly one of those input forms. The URL tool alone accepts optional `crop` and `map_notes` (default false).

| Tool | Required result |
| --- | --- |
| `get_foundry_image_info` | `source_id`, `source_expires_at`, `width`, `height`, `mime_type`, `size_bytes` and `frame_policy`. Width and height are original, display-oriented pixels. The handle pins the exact source bytes. This call issues no public URL. |
| `get_foundry_image_url` | `url`, `expires_at`, `source_id`, `source_expires_at`, `source_width`, `source_height`, `region:{x,y,width,height}`, `width`, `height`, `mime_type`, `size_bytes`. `region` is the area covered in original pixels. The final width and height describe the actual fetched image. A missing crop selects the whole image. |

**Map example.** A text journal contains `<img src="worlds/test/maps/floor.webp">`. Call `get_foundry_image_info({"src":"worlds/test/maps/floor.webp"})`. Suppose it returns 10,000 × 5,000 and a `source_id`. Use that ID for the overview, then again for this detail request, substituting the actual ID.

```json
{
  "source_id": "<source_id from get_foundry_image_info>",
  "crop": {"x": 7200, "y": 3100, "width": 1280, "height": 960}
}
```

The full map can yield a 2,048 × 1,024 overview. The detail request covers original columns 7,200–8,479 and rows 3,100–4,059. It retains 1,280 × 960 pixels when it fits the byte budget. For a portrait, pass `entries[i].image` from `browse_journal_images` directly as `image` to the URL tool and omit `crop`.

**Coordinates.** Use zero-based integers with the origin at the top left of the display-oriented original. X increases right, Y down, and the right and bottom edges are exclusive. Require positive width and height and a fully contained rectangle. Reject floats, booleans, zero area, negatives and overflow with `InvalidCrop` and the valid source dimensions. Preserve exact bounds without clipping or padding. To select from a fetched preview, map its left edge `u` back with `region.x + floor(u × region.width / preview.width)`. Use `ceil` for the exclusive right edge and the same calculation on Y. The rule also works when zooming further into an earlier crop.

## Resolve and transfer the original

1. Start from the current checkout. The reviewed baseline is `5188fbe900c4faca5e1f8aac88a713c0fa822f02` (3.3.1). Complete the required reading in `AGENTS.md`, then trace the relevant sections of `docs/mcp_foundry_architecture.md`, `docs/journal-images.md`, `docs/image-uploads.md` and the Foundry module conventions. Check actual `tools/list` and measure the existing browse and journal response sizes before editing. Confirm any new Foundry API in the repository’s versioned Grounded Docs workflow. [Reviewed source tree](https://github.com/sesopenko/foundry-mcp/tree/5188fbe900c4faca5e1f8aac88a713c0fa822f02)

2. Reuse `ImageSelector` in `foundry_mcp_server/mcp_server/journal_image_models.py` and `resolveJournalImage()` in `foundry-module/scripts/journalImages.js`. It already verifies exact membership via a fresh bounded FilePicker listing. For bare `src`, resolve only the referenced parent in the configured sources, with Foundry’s route prefix and URI encoding preserved. Match the browser-returned file and pass that canonical selector through the same resolver. Accept local `data` and `public`, and configured S3 files when the browser can read their bytes. Never crawl directories. For ambiguous paths return `AmbiguousSource` with a bounded browse recovery call. Treat missing, denied and unavailable listings according to the existing browse semantics. [Foundry v14 FilePicker](https://foundryvtt.com/api/v14/classes/foundry.applications.apps.FilePicker.html)

3. Read selected bytes from the ready GM browser. Use its same-origin credentials only for local assets. For configured S3 use the exact picker-selected object and normal browser CORS, with Foundry credentials omitted. Treat a raw absolute URL as a selection hint only when it resolves to an allowed Foundry source. Reject unrelated URLs, traversal, host filesystem paths, executable schemes and off-source redirects. Use the canonical picker result for the fetch. Compare escaped path segments without double-decoding or turning encoded separators into directory boundaries. A harmless cache-busting suffix on a local journal reference may be ignored during matching. Protect signed S3 information throughout. `read_journal_page` already returns stored HTML in `content`; teach callers to follow `next_cursor` if a tag spans fragments.

4. Add private begin / chunk / release RPCs in `foundry-module/scripts/foundryBridge.js`, using the existing socket-owner guard and `foundry_mcp_server/ws/connection.py`. Hold one bounded immutable original in the browser for the transfer. Count bytes while streaming the fetch, including when `Content-Length` is absent. Pull indexed chunks of at most 32 KiB raw with a bounded window of up to 16 in flight. Size frames to the configured response ceiling including JSON and base64 overhead. Validate request ownership, offsets, lengths and complete coverage. Write to a private temporary file and hash the assembled source. Match the same socket, world and GM across awaits. Release on success, error, timeout, cancellation or disconnect. Cap each stalled read at 15 seconds and the full transfer at 5 minutes. The current default inbound frame limit is 65,536 bytes. The PDF channel supplies a chunking precedent and has separate authorization. No private transfer bytes, paths, credentials or signed source URLs belong in MCP tool results or logs.

5. Stage the compressed original once for info, overview and repeated crops. Bind its opaque `source_id` to the authorized caller context, GM, world and exact selector. Capture the source digest privately. Keep it for 30 minutes from staging, bounded to 512 MiB total in a private cache. Check authorization and current membership again before issuing each new preview. An existing handle describes the original snapshot even if the file contents are replaced at that path. A fresh info call can stage the replacement. An expired handle or lost authorized context produces a typed recovery error. The browser listing revision describes paths and cannot detect replacement bytes. A user can fetch an already-issued preview throughout its separate seven-day lifetime.

## Render maps and portraits on the MCP server

| Limit | Implementation default |
| --- | --- |
| Original image | 128 MiB compressed, 32,768 pixels per edge and 128 million pixels total. These limits admit a 10,000 × 10,000 map. Enforce all three. |
| Delivered whole image or crop | 2,048 pixels per edge, 2,359,296 pixels total (1,536²) and 2 MiB encoded. Preserve aspect ratio and skip enlargement. |
| Worker | One render at a time. Start with a 1 GiB resident-memory budget, 2 GiB private scratch and a 90-second render deadline. Enforce and measure these independently of the existing upload worker. Set bounded libvips thread and operation caches. |

The long-edge limit allows a wide map overview. The area limit keeps square portraits at up to 1,536 × 1,536, and the byte limit bounds every public fetch. These are project defaults. OpenAI’s image preprocessing depends on the model and detail level. Fine labels remain accessible by requesting a smaller source rectangle. [OpenAI image sizing and detail guidance](https://developers.openai.com/api/docs/guides/images-vision)

Use Python `pyvips` with libvips for the new preview worker. Use demand-driven, file-backed operations and allowlisted loaders. Pin the dependency and lockfile, package the required codecs in the production image, and test that image as its service user. Reuse the existing isolated-worker lifecycle in `foundry_mcp_server/image_worker.py` and `foundry_mcp_server/mcp_server/image_uploads.py`. Keep the inbound upload validator’s Pillow limits and behavior intact. libvips may read an entire compressed stream or use temporary disk for random access. Bound scratch, memory, concurrency and runtime, kill and reap aborted workers, and clean staging on every exit. [pyvips installation](https://github.com/libvips/pyvips) · [How libvips opens files](https://www.libvips.org/API/current/how-it-opens-files.html)

1. Probe the staged file’s header in the worker. Validate dimensions, orientation and actual format before allocating pixels. Where possible, the info operation should finish without decoding the full raster. Return only the required technical metadata. For all eight EXIF orientations, metadata and crop coordinates must describe the same displayed image.

2. Logically orient the original and extract the selected rectangle at source resolution. A verified mapping to raw pixels before orientation is equivalent. Apply the output budgets only to that region. Use one aspect-preserving scale `min(1, 2048/max(w,h), sqrt(2359296/(w*h)))` and integral dimensions within all budgets. Use the Lanczos3 reduction filter for shrinking. Skip resampling at native size. Premultiply alpha before filtering, undo it afterwards, and convert colors to sRGB where appropriate. Exclude EXIF, GPS, comments, and embedded thumbnails from output. [libvips region extraction](https://www.libvips.org/API/current/method.Image.extract_area.html) · [libvips resizing and alpha handling](https://www.libvips.org/API/8.17/method.Image.resize.html)

3. Prefer lossless PNG when it fits, especially for text, icons and small crops. If PNG exceeds 2 MiB, try WebP at quality 90 and then 82, preserving alpha. If still oversized, reduce dimensions by 15% per attempt, always resampling from the original selected region. Stop at the first compliant encoding. Bound encoding attempts to the worker deadline. Verify MIME, dimensions and encoded byte length before minting a URL. Report actual delivered dimensions so a caller can request a tighter crop if needed.

4. Cover the browser’s advertised raster formats (JPEG, PNG/APNG, WebP, AVIF, BMP, GIF and TIFF). Render the first displayable frame or first page for multiframe sources. Describe this via `frame_policy` with values `still` or `first_frame`. Handle common self-contained Foundry SVG icons using a bounded, non-interactive raster loader such as libvips with librsvg. Use 96 CSS pixels per inch for the SVG coordinate system and derive a size from the viewBox if needed. Accept local fragment references. Reject unsafe or unsupported constructs and block external resources, script and file access. Serve only the resulting raster. Use `UnsupportedImage` for unsupported content and `ImageTooLarge` with any safely known dimensions when source limits are exceeded. Verify codec coverage in the shipped image with fixtures and give typed errors for malformed or unsupported inputs.

## Publish one immutable preview for seven days

1. Implement `GET` and `HEAD` at `/image-previews/{uuid4}.{ext}` in `foundry_mcp_server/main.py` before the final `app.mount('/', mcp_app)`. Use a new cryptographically random UUIDv4 for each successful issuance, even for identical crops. The suffix is the actual `png` or `webp` format. Mint a complete public HTTPS URL containing only the origin and this path. The UUID selects exactly one derivative. Neither source identity, crop coordinates, credentials, expiry, query string nor fragment belongs in the issued URL.

2. Make issuance use the existing authenticated MCP boundary and GM bridge. Add an opt-in `FOUNDRY_MCP_IMAGE_PREVIEW_ORIGIN`, validated with the existing `https_origin` helper. Configure the public HTTPS origin explicitly for Basic or OAuth. Allow the existing authenticated development mode for local verification. Plain unauthenticated mode cannot mint links. Keep discovery available. Image info requires an authenticated Foundry connection and private staging, and works without a public origin. Return `PreviewNotConfigured` before processing a URL request if issuance is disabled. Generate URLs from trusted configuration alone. A public reader needs only the URL, including when the GM disconnects.

3. Atomically store the derivative bytes, MIME, size, token digest and absolute UTC expiry in a private SQLite database. Set expiry at publication to exactly 604,800 seconds later. Use a configurable private data directory backed by a named volume in deployment templates and writable by UID 10001. Enforce `now < expires_at` on every GET and HEAD. Start up with expired records pruned, prune periodically, and reject new issuance at a 1 GiB live-preview quota or 4,096 live rows after pruning. Preserve already-issued links across process/container restarts using the volume. Short-lived original snapshots and decoder spill files stay outside the public route.

4. GET returns `200`, raw image bytes, the exact `Content-Type` and `Content-Length`, `Cache-Control: private, no-store` and `X-Content-Type-Options: nosniff`. HEAD returns the same headers and an empty body. Expired, unknown or mismatched token/extension combinations return a generic `404` with `no-store`. Serve the canonical URL directly without a redirect, cookies, login or HTML wrapper. Ignore incidental query values on reception. The lookup depends solely on the path, allowing an honest comparison of the same object with and without `?probe=1`.

5. Explain in tool discovery that anyone holding the link can read the selected pixels for seven days. Keep anonymous image access confined to this exact preview route. Preserve protection of `/mcp`, the GM WebSocket and PDF operations. Publish compact model-visible metadata and the URL in the actual tool result so ChatGPT can open it with an image-capable fetch. Scrub capability URLs from Uvicorn access logs, evaluation traces and example reverse-proxy logs. Update both Basic and OAuth deployment examples, operations guidance and the Docker Hub overview. Document externally reachable HTTPS, uncached proxy routing for this prefix and upgrade of the server and module together.

## Acceptance and handoff

Add focused tests alongside each behavior, then run `./scripts/test.sh` using the repository’s prescribed test permissions. Register the tools through `foundry_mcp_server/mcp_server/tools.py`, including the repository’s OAuth discovery metadata. Exercise actual MCP discovery and invocation, the production HTTP app, browser RPC handlers and the packaged decoder. Verify the following before reporting completion.

- [ ] **Fresh journal and browse workflows.** Read an actual stored `<img>` from a text-page fixture, including a tag split across fragments. A caller can issue a portrait URL from its raw `src` and directly from `browse_journal_images`’s exact `image`. Test spaces, percent encoding, Unicode, Foundry route prefixes, a core SVG, a configured S3 mock, ambiguous paths, denied membership, non-GM access and a changed socket. Report live S3 only when configured and tested.

- [ ] **Map detail and crop geometry.** Generate a real 10,000 × 10,000 test map with small distinct symbols or labels at the center and far edges. Use nonrevealing names and separate expected values. Confirm info returns 10,000 × 10,000, the overview fits, and a small bottom-right crop matches independently generated source-region pixels at native resolution. Include a 10,000 × 5,000 example, border-touching and one-pixel crops, a large crop that needs reduction, transparency, rotated and mirrored orientations, and invalid rectangles. Compare decoded pixels on lossless fixtures and use an appropriate tolerance for lossy cases. Record peak worker memory, scratch and elapsed time on the large case. Test real multi-chunk bytes and multiple crops after one transfer.

- [ ] **Lifecycle and limits.** Test identity separation, file replacement after info, expired source handles, decoder failures and resource limits, a missing or short chunk, out-of-order replies, cancellation, reconnection and cleanup. Prove one principal cannot use another’s source handle. Verify that two successful issuances get distinct UUIDs and one crop URL cannot be used to read the original or a different rectangle. Check new requests fail cleanly at quota while issued links still work.

- [ ] **HTTP, curl and expiry.** Use a disposable fixture and the real HTTP listener. With curl, perform GET twice without `-L`, once with the issued URL exactly and once with only `?probe=1` appended. Record status, MIME, length, cache headers, redirects and body SHA-256. Both must return `200`, zero redirects and identical decodable bytes. Check HEAD separately, with no body. Check no credential header is required. Use an injected clock to test immediately before and exactly at seven days, including with cleanup paused. Restart with the same volume and verify a still-valid link. Keep real URL tokens out of transcripts.

- [ ] **Actual visual acceptance.** Use the existing authorized Foundry development world after offline tests pass. Give the target ChatGPT client a journal with an opaque map filename. Ask it to inspect a particular area and identify a randomized symbol, short label or color pair present only in the crop. The expected answer stays outside the prompt, caption, filename, alt text and tool result. Record whether the client called info, requested the correct rectangle, fetched the returned URL and answered correctly from pixels. In a separate controlled host comparison, try the exact link and its `?probe=1` variant with equivalent fresh context and record each observed outcome. An HTTP pass establishes server behavior. Mark ChatGPT visual acceptance passed only after the target client demonstrates it. If the client or public deployment is unavailable, leave that result pending with the exact prerequisite and verification prompt.

- [ ] **Finish.** Update tool descriptions, schema and minimal journal/browse guidance so a fresh LLM can discover both paths. Document snapshot lifetime, seven-day expiry, limits, coordinates and concrete recovery for expired handles, unsupported files and invalid crops. Report tests and measured results, compact MCP sizes and remaining live checks. Work in the development checkout and existing test world. Publication, release and changes to live game assets are outside this handoff.

## Map browsing and note-overlay extension — 2026-11-11

This extension is part of the target design. Read the
[research handoff](../plans/image-viewing/map-browsing-notes-research.md) after
every context compression/resume as well as this entire prompt. Research facts
and verification gaps remain distinct from the implementation requirements here.
The [task index](../plans/image-viewing/README.md) owns the sized execution graph.

### Browse maps and choose a file

Add typed `browse_maps` and `get_map_info` tools to actual MCP discovery with
OAuth metadata. Both are authenticated, ready-GM, read-only core Foundry tools;
they do not require PF2e or an active/rendered Scene. Scope is world Scenes and
Scene folders, including imported adventure Scenes. Unimported compendium Scene
catalogs and reconstruction of the sidebar's DOM/prepared tree are excluded.

- `browse_maps` accepts optional `folder_uuid` (null = root), `name_contains`
  (default empty), `limit`, `max_bytes`, and `cursor`. Return immediate child
  folders and maps, canonical UUIDs, names, named ancestry, sort context, and
  concrete next calls. Build hierarchy from public folder parent/membership
  fields. Preserve duplicate names and empty readable folders. Show all Scenes,
  including those without a usable background, with explicit capability limits.
  Matching is a literal case-insensitive substring of immediate child names,
  not image contents or recursive server search. Folders precede maps; respect
  alphabetical/manual folder sorting, with UUID as the deterministic final tie.
- `get_map_info` requires `scene_uuid`, accepts optional `level_id`, and selects
  `section: assets|tiles|notes` (default assets), plus bounds/cursor and optional
  `expected_revision`. `notes` requires explicit `level_id`; it may filter up to
  100 exact returned `note_keys`. Other sections reject note-only arguments.
  Assets list every selected level, even missing-media levels, with separate
  background/foreground role records. Tiles are a separate optional file
  inventory, not an implicit part of a background image preview.
- Return scene identity/ancestry, `geometry` (width, height, padding, shiftX/Y,
  and public scene rectangle), complete `grid` fields (type, size, distance,
  units, style, thickness, color, alpha), `initial_level_id`, selected section,
  and paged `entries`. Preserve absent/null/zero fields without inventing grid
  defaults or interpreting Scene dimensions as original file dimensions.
- Asset records retain level identity, role, safe exact stored file reference,
  media/support status, and info/preview next calls. Redact credential-bearing
  or signed references and resolve them privately through the map selector.
  Do not infer that a stored path exists: byte reading still uses fresh picker
  membership and browser access. Identify foregrounds, videos, tiles, and missing
  files explicitly. Do not promise fog, lights, tokens, walls, or full Scene
  composition from a single image.
- Both tools default to 10 entries and 8,000 compact JSON bytes; limits are
  1–100 entries and 1,024–48,000 bytes. Return `revision`, `total`, `complete`,
  `next_cursor`, `scope_status`, and `limitations`; browse additionally returns
  `location` and named ancestry. Completion covers the selected page stream;
  `scope_status: partial` cannot establish exhaustive availability. Denied data
  must not leak names/paths. Fail explicitly if identity alone cannot fit.
- Cursors bind world, caller/scope, selection/filter, and observed document/
  permission revision. Return cursors verbatim with identical semantic inputs;
  bounds may change. `ContentChanged`/expected-revision mismatch requires
  discarding prior pages and restarting. The revision describes metadata, not
  replacement bytes at an unchanged file path. Do not silently truncate levels,
  tiles, note keys, names without markers, or hierarchy.
- For a selected level, use the same map/note metadata revision across asset
  and notes views and note-key filters; pagination bounds/filtering do not
  renumber aliases or create an agreeing legend for a changed snapshot. Order
  level entries by declared sort then UUID. Include exact scene/level identity
  in every legend follow-up, not just its revision token.

The new exclusive image input is
`map:{scene_uuid,level_id,role:background|foreground}`. Explicit level IDs come
from map info; never silently substitute the viewed/active level. Info stages
the selected file through the existing resolver/transfer/probe and binds map
context to its source handle. URL accepts this selector directly or a bound
`source_id`. Existing `image`, `src`, and unbound handles retain their original
behavior. Annotating a bare file without map context returns `MapContextRequired`
with a map-discovery recovery call. A map reference never bypasses authorization,
source validation, transfer limits, or snapshot isolation.

### Render compact note identifiers

`get_foundry_image_url(..., map_notes=true)` is opt-in. V1 annotates supported
background-image mappings. Foregrounds remain fetchable without annotations;
tile-only/composited maps and unverified transforms return
`UnsupportedMapMapping` for annotation requests. Preserve ordinary previews.

- Use public NoteDocument coordinates/label/entry/page and verified per-level
  applicability. Read no journal bodies. Verify empty/null level membership and
  transform semantics through official contracts plus focused runtime checks;
  never depend on protected tooltip styling or internal mesh transforms. For
  unsupported/unclear configurations, fail clearly rather than guess positions.
- Assign N1, N2, ... by canonical Note UUID order within the complete authorized
  level snapshot, before crop filtering. Keep aliases stable across repeated
  crops of the same snapshot, retain distinct pins linking the same journal,
  and map keys to full Note/journal/page UUIDs through the bounded notes section.
  Missing/unlinked targets are explicit, not permission to read denied labels.
- Pin annotation identity/revision, note aliases, and the verified coordinate
  mapping with map-bound original snapshots. Recheck scene/level/asset membership,
  permission, and mapping/note revision before new annotated issuance. A change
  returns `MapContextChanged` and fresh-info recovery. An unchanged source path
  still refers to the handle's pinned original bytes. Issued links remain
  immutable and readable for their independent seven-day lifetime.
- Convert Scene coordinates using `getDimensions()` and verified inverse image
  placement before crop coordinates. Account for grid-rounded padding and shift,
  source-vs-Scene size, display orientation, and supported level transforms.
  For the measured normal rectangle: source_x = (note_x-sceneX) ×
  original_width/sceneWidth, with the analogous Y rule. Crop/output conversion
  then uses the existing region contract; reject guessed transforms.
- Render generated ASCII keys only using a bundled fixed font, targeting **16
  pixels at final output resolution**, white fill with a 1-pixel dark outline.
  No journal body, full raw UUID, or arbitrary Pango markup is rendered. Measure
  actual font output; cap ink height including outline at 20 output pixels.
  Keep source originals unchanged. Recompose labels at final size on every
  encoding/reduction attempt under the existing 90-second and byte budgets.
- Use deterministic placements around the pin (NE, NW, SE, SW, E, W, N, S), with
  4-pixel gaps and leader marks to preserve location. Include outline/leader/pin
  extents in bounds and collision checks; never wrap or cut a key at image edges.
  Do not move a key to another room without its leader. Require disjoint label
  boxes and cap their aggregate box area at **5% of delivered image area**.
  Render at most **100** keys per image. These conservative defaults bound
  obstruction; they do not prove that every map feature stays unobscured.
  Process keys by numeric alias ordinal (N1, N2, ...), not lexical N1/N10/N2.
- Select notes whose pin centers lie inside the source crop. If no valid
  placement fits, omit that key with an explicit reason (density, collision,
  edge, or tiny image) and recommend a tighter/detail crop. Never shrink keys
  below the fixed legibility target to hide a crowded-layout failure.
- When enabled, add a typed `map_notes` result containing map identity,
  `revision`, `total_in_region`, `rendered_count`, `omitted_count`, `complete`,
  rendered `keys` (at most 100), `omission_reasons`, `scope_status`, `limitations`,
  and `legend_next_call`.
  The follow-up is `get_map_info(section=notes, expected_revision=..., note_keys=...)`
  for the rendered keys; paginate it to completion. Zero rendered keys uses a
  null follow-up. `complete` means every applicable in-region pin was rendered,
  independent of legend pagination. `scope_status`/limitations must separately
  expose unsupported or denied note content. Omit this result section when the
  flag is false; a true flag with no notes returns explicit zero counts.

### Additional acceptance

Cover folder hierarchy/duplicate names/manual ordering, all grid values in the
user screenshots, multiple levels, missing/video/background/foreground/Tile
references, unchanged active Scene during browsing, and non-PF2e worlds. Test
actual MCP discovery/calls, pagination/budgets, stale revisions, forged map
selectors, permission isolation, and reuse of one transfer for annotated crops.
Verify padding/shift/size/orientation with independent pixel oracles; treat
unverified transforms and level applicability as explicit implementation gates.
Exercise label font metrics, dark/light maps, edges, one-pixel crops, dense pins,
alias/legend identity, byte-budget retries, and honest omission reporting.

Measure map catalog and complete legend workflows alongside existing payload
baselines. Test the bundled font and annotations as UID 10001 in the shipped
image. Reuse the existing local world and marked fixtures after offline tests.
Target-client acceptance must demonstrate browsing a map, choosing its correct
level file, fetching an annotated crop, and following a rendered key to its
journal/page. Retain the separate hidden-pixel-answer test; do not put its answer
in labels, captions, filenames, legends, or tool results. Leave unavailable
public-host/client acceptance precisely pending rather than claim it passed.
