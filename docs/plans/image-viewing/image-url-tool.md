# Overview and crop capability issuance

`get_foundry_image_url` is registered through the typed FastMCP boundary with
OAuth discovery metadata. Provide exactly one selector under `request`: canonical
`image`, bare stored `src`, exact level/role `map` from `get_map_info`, or a caller-bound `source_id` from image info/a prior
URL call. Optional `crop` uses original display-oriented integer pixels, with
exclusive right/bottom edges and no clipping. Opt-in `map_notes:true` requires
explicit or source-bound map context; see [map image tools](map-image-tools.md).

```json
{"request":{"source_id":"<handle returned by get_foundry_image_info>","crop":{"x":7200,"y":3100,"width":1280,"height":960}}}
```

After strict input validation, disabled issuance returns `PreviewNotConfigured`
before source reads, probing or rendering. Issuance needs the explicitly
configured trusted HTTPS origin, authenticated Basic/OAuth/development identity
and the ready authorized GM. Plain-none cannot issue; discovery and authenticated
info remain available independently of the public origin.

Image/src/map requests stage/probe a new original; source handles lease their pinned
bytes without another transfer. Current caller, socket, world, GM and exact file
membership are rechecked around rendering/publication. Same-path byte replacement
does not change an existing original snapshot. Deleted/denied paths, expired
handles or lost authorization cannot issue through an old handle.

The supervised worker extracts/orients/resizes/encodes the selected region. The
publication boundary independently checks strict geometry, exact requested region,
bounded container dimensions/MIME/size and original byte length before atomic
SQLite publication. Output budgets remain2048/edge,2359296 pixels,2MiB, no
enlargement. PNG is preferred, then WebP90/82 and15% dimension reductions.
Original limits, first-frame/page behavior and SVG restrictions remain unchanged.

The result contains exactly `url`, `expires_at`, `source_id`, `source_expires_at`,
`source_width`, `source_height`, `region`, `width`, `height`, `mime_type` and
`size_bytes` when `map_notes` is false (the default). True adds a bounded typed
`map_notes` section with rendered aliases/counts, exact map/revision identity,
scope/omission information and a paginated legend next call; never a full legend.
Original receipt expires1800s from staging; the immutable derivative
expires604800s from publication. Delivered dimensions describe actual fetched
pixels, independently of original region coordinates. Use floor for mapping a
preview's left/top to original coordinates and ceil for exclusive right/bottom.

Each issuance receives a fresh UUID4 PNG/WebP path under trusted configuration;
the URL encodes no source/crop/credential/expiry. Anyone holding it can read those
pixels for seven days, including after GM disconnect, without a login/cookie or
redirect. GET/HEAD query values cannot select a different rectangle or original.
Keep bearer links private. Python logs/evaluation traces redact capabilities,
including HTTP-client URL objects interpolated by logging formatters; external
proxy/client logs require their own policy.

Quota/storage failures return fixed actionable `PreviewQuotaExceeded` or
`PreviewStorageUnavailable`; existing links remain usable. Cancellation drains
owned publication work before releasing its source lease. An atomic commit that
finishes during cancellation/context loss may retain an unreturned immutable
derivative until normal seven-day expiry/quota cleanup. No partial image or
successful result is returned for canceled work, and no retry/idempotency promise
is introduced. Source snapshots remain available for subsequent authorized crops.

Actual MCP tests fetch issued bytes through the production app, compare decoded
crops against independent original pixels and verify overview/all input forms,
one-transfer reuse, replacement snapshots, distinct URLs, expiry/principal/
membership isolation, changed context during render/publication, malformed output,
quota retention and cancellation. A forged valid worker result covering another
region failed the required rejection test before the final region comparison;
the same unchanged test passes. The URL-object log regression also failed before
correction and passes unchanged.

Exact focused/full/package/runtime evidence is in
[task11](tasks/11-image-url-mcp-tool.md). Local production-app and packaged checks
do not establish public HTTPS or target-ChatGPT visual acceptance. Those remain
the explicit later runtime/client gates, as do live configured S3 checks.
