# Map-aware image tools

Browse world Scene folders with `browse_maps`, follow a named map into
`get_map_info`, and choose its exact level background/foreground record. Its
`info_next_call`/`preview_next_call` contains a complete `request.map` selector:

```json
{"request":{"map":{"scene_uuid":"Scene.<returned id>","level_id":"<returned Level ID>","role":"background"}}}
```

Info accepts exactly one of `image`, `src`, `map`; URL accepts exactly one of
those or `source_id`. Omit unused inputs rather than null. No names, inferred
Scene, current/viewed level, compendium Scene or caller-chosen arbitrary source
URL is substituted. Map reading is core Foundry, independent of PF2e or an active
canvas. Role images are separate files, never a full Scene composition.

## Source binding and annotation

Info returns the same seven technical fields as ordinary images, without a
public URL. It privately resolves the owning role through fresh FilePicker
membership, transfers/probes the original, and validates map/note revision before
atomic cache admission. The cache's trusted synchronous receipt factory attaches
an immutable `BoundMapContext` without a second dictionary or separate lifetime.
Failure/cancellation before admission cleans staging and publishes no handle.
Snapshot TTL remains1800 seconds from admission, with512MiB original quota.

Safe stored paths remain visible in map info for understanding; signed level
references remain private and use the same map-selector next calls. Configured
S3 is selected through exact private picker membership, never by trusting a raw
URL. Credential-bearing references remain unsupported. Tile inventory retains
bare file followups and does not invent map context.

Use the info handle for repeated crops without another transfer:

```json
{"request":{"source_id":"<returned handle>","map_notes":true,"crop":{"x":200,"y":200,"width":800,"height":600}}}
```

`map_notes` is a strict boolean, default false. False preserves the original URL
result fields and omits `map_notes` entirely. True requires map-bound context;
raw/image/src requests never infer a Scene from a shared path. Foregrounds are
fetchable without annotations. V1 annotation support is exactly
[Foundry14.369 default background placement](map-context.md), using the public
Scene rectangle, padding/shift and display-oriented source scaling. Nondefault
texture transforms, foreground annotation, Tile composition and unverified builds
return `UnsupportedMapMapping` rather than guessed positions.

Before new map-bound previews the adapter revalidates the exact asset, owner,
caller, world and GM socket. Annotation additionally requires unchanged mapping,
permissions, aliases and note revision before/after rendering/publication.
Note-only changes still allow ordinary pinned file previews. Replacement bytes
at an unchanged path do not alter the pinned original; fresh info stages the new
file. Already-issued derivatives remain immutable for their independent seven-day
life. The URL contains only the random derivative path; annotation state is
never encoded into a query or source path.

The existing authenticated issuance, disabled-origin-first check, original/
worker/output limits, quotas, anonymous GET/HEAD and capability-log protections
remain in force. Native rendering uses [fixed glyphs](note-glyphs.md) and
[bounded layout/encoding](note-layout.md):16px final em, outlined ink<=20px,
at most100 numeric aliases, disjoint boxes and<=5% aggregate label area. Crops
select pin centers with exclusive right/bottom bounds. Crowded/tiny/edge cases
omit keys honestly; labels never shrink to conceal density failures.

## Bounded result and legend

True adds precisely `map_notes` with:

- `map:{scene_uuid,level_id,role}`, `revision`;
- `total_in_region`, `rendered_count`, `omitted_count`, `complete`, `keys`;
- `omission_reasons` positive counts (`limit`, `density`, `collision`, `edge`,
  `tiny_image`), `scope_status`, `limitations`;
- `legend_next_call`, or null when no key rendered.

`complete` means all applicable authorized in-region pins were rendered. It
does not establish complete permission scope or completed legend pagination.
True with zero notes returns explicit zero counts and null legend. Partial note
scope stays explicit even when every available pin rendered. Request tighter
detail crops for omitted keys; the area bound does not promise that every map
feature remains unobscured.

Follow the exact returned `get_map_info` call with owning Scene/level,
`section:"notes"`, `expected_revision` and the rendered `note_keys`. Paginate
with returned cursors to completion using the same semantic inputs. The legend
maps aliases to Note UUID and permitted journal/page identity; labels and bodies
are not painted. `page.page_uuid` feeds `read_journal_page`; entry-only pins use
the bare ID after `JournalEntry.` with `get_journal_contents`. Distinct pins
linking the same target retain distinct keys. Never join aliases across revisions.

Recovery:

| Error | Action |
| --- | --- |
| MapContextRequired | browse_maps → get_map_info assets → stage exact map selector |
| MapContextChanged | Refresh map metadata and map image info; discard prior alias joins |
| UnsupportedMapMapping | Choose verified default background or omit map_notes |
| SourceUnavailable/SourceContextLost | Restore authorized context and stage fresh original |
| InvalidCrop | Correct bounds using original display dimensions |
| PreviewNotConfigured | Configure trusted HTTPS origin/private store before URL issuance |

## Verification evidence

Actual FastMCP/production Node readers plus real Python multichunk assembly,
native rendering, SQLite and production anonymous image routes pass map workflows.
The focused suite17 (26.716s) covers
strict contracts/discovery, exact returned map calls, default omissions, owning
level/role, foreground fallback, private configured-S3 mock, zero/partial/dense
notes, complete rendered-key legend pagination, pinned replacement bytes,
caller/expiry/socket isolation, mutations across render/publication, quota/
cancellation, actual Basic HTTP authority and the bounded native-verifier checks.
Existing image-tool24, source12, context23, model9, map-info17 and JS33 regressions
pass. First full run exposed old pre-map schema assertions; those usage points
were updated for the authorized extension. Full final runner passes1007 Python
(1 existing skip)/794JS before four final discovery/verifier tests; commit hook verifies
the final staged revision. No production failure workaround was introduced.

Production Docker build/native/supervised/glyph smokes pass asUID10001. Packaged
contract3 and actual native layout15 (6.926s) pass read-only/no-network with only
tests mounted. Node is a host test/browser fixture dependency and is not added
to the production Python image. Module ZIP packages successfully without a
version bump or release.

Measured fixture workflow:7 MCP tool calls,1 original transfer,3 real chunks,
two independent annotated derivatives/legend lookups plus ordinary preview.
The complete single-key legend is obtained for each rendered crop.

| Call | Compact JSON bytes | MCP result bytes |
| --- | --- | --- |
| Map assets |1918|4288|
| Map image info |193|596|
| Annotated overview |937|2170|
| Annotated crop |941|2178|
| Each exact-key legend |1121|2560|
| Ordinary bound preview |392|1012|

These are bounded technical measurements, not billed tokens or equal-content
savings against unrelated prior fixtures. Full legend/collection measurements
remain in M06 alongside earlier baseline comparisons.

After offline checks, restart of the existing service and dedicated-browser
refresh yielded readyGM14.369/test with0 console errors. Native
`python -m foundry_mcp_server.map_image_audit` passed7 MCP calls under8/600s:
actual6800×9000/4405816B source stages through the new map selector and owning
map/note revision, initial2-row legend agrees, active Scene unchanged. Info
198B/606B MCP, assets2819B/6148B MCP, first legend2347B/5120B MCP. This initial
legend page is not claimed complete. Catalog47/323516B versus47/314317B before
M05 (+9199B); live info6219B/URL15834B tool records. Bytes use compact SDK-model
catalog records; test discovery conventions may differ.

The native URL request correctly returns `PreviewNotConfigured`: local public
origin remains unset. Native annotation issuance/delivery therefore remains
pending configured trusted HTTPS origin/private store in14a; target-ChatGPT
visual acceptance remains14b, and live S3 needs configured bucket/CORS. The
native verifier does not claim those passed. One normal private original is
owned by the cache's1800s TTL/pruning; no persisted game fixture, existing asset
write, public URL or additional Foundry instance was created.
