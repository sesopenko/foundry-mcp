# Original image information and private snapshots

`get_foundry_image_info` is registered in actual MCP discovery with strict
Pydantic input/output models and the existing OAuth metadata middleware. It
requires an authenticated caller and the connected ready Foundry14 GM. It needs
no public preview origin, PF2e system or active Scene.

Pass exactly one input under `request`: `image`, copied from an exact
`browse_journal_images`/`upload_image` image record, `src`, copied from a stored
journal image/portrait reference, or `map:{scene_uuid,level_id,role}` from
`get_map_info` assets. Follow `read_journal_page.next_cursor` until
the complete img tag is reconstructed when HTML is fragmented. Neither form
requires a preceding browse call.

```json
{"request":{"src":"worlds/test/maps/floor.webp"}}
```

Resolution and transfer retain fresh bounded source membership, configured
data/public/S3 scope, exact socket/world/GM guards and private bounded chunks.
The server probes the complete immutable file in its isolated native worker,
then rechecks membership/context before admitting a source handle. Probe or
validation failure/cancellation releases the file and reservation; no invalid
handle is published. Request validation and worker metadata validation reject
unknown fields before they can become public results.

Returns exactly `source_id`, `source_expires_at`, `width`, `height`, `mime_type`,
`size_bytes` and `frame_policy`. Width/height are original display-oriented
pixels, size is compressed original bytes, and frame policy is `still` or
`first_frame` (also first page). JPEG, PNG/APNG, WebP, AVIF, BMP, GIF, TIFF and
the admitted self-contained SVG subset share the existing decoder limits:
128MiB,32768 pixels/edge,128000000 pixels, independently supervised resources.

The source handle binds exact original bytes to the verified caller and browser
world/GM identity for1800 seconds from staging, independently of file replacement
or later seven-day derivatives. It exposes no source path, digest, original bytes
or public URL. Next use `get_foundry_image_url` with that handle for overview or
crop; [that tool is now integrated](image-url-tool.md) in task11.
Scene-aware [map selectors and annotations](map-image-tools.md) bind exact level
and role identity privately to that handle; they never infer a Scene from a path.

`SourceRuntime` starts/closes the private cache in app lifespan independently of
public delivery configuration, prunes every60 seconds and protects cleanup from
repeated cancellation. Expiry is also enforced when handles are used; periodic
cleanup timing never extends validity. Cache close defers deleting files held by
active workers until their owners return. No game asset is changed.

Recovery: `SourceUnavailable` requires fresh info with the original selector;
`SourceContextLost` requires restoring the intended authorized ready GM then
fresh info. `AmbiguousSource` requires a bounded parent browse and exact image.
Unsupported/oversized sources require a supported/smaller original; denied or
unavailable listings do not establish absence. Raw browser/native diagnostics
are replaced by fixed actionable categories.

Tests exercise actual MCP schemas/calls, Basic HTTP authority, OAuth discovery
metadata, native oriented probing, malformed browser/worker responses, missing
authority/GM, context mutation, expiry, probe cancellation and cache lifecycle.
The cancellation-close regression failed before the owned-close correction and
passes unchanged. The bounded localhost checker performs four MCP calls and
prints aggregate technical metadata only. Its assertion tests reject private
extra output fields without returning their contents.

The first live core-icon call exposed conservative SVG admission rejecting
inert class/touch-action hints. A failing independent-pixel test proved that
boundary; the guard now strips those hints while retaining presentation and
external-resource validation. See [SVG subset details](safe-svg.md).

Exact verification and current runtime measurements are recorded in
[task10](tasks/10-image-info-mcp-tool.md). Public HTTPS and target-client pixel
acceptance remain later gates, as does live S3 without configured bucket/CORS.
