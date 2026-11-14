# Default JPEG preview output

Version 4.0.0 adds `FOUNDRY_MCP_IMAGE_PREVIEW_JPEG=true`, including when unset.
Only literal `true`/`false` are accepted; empty values fail startup. Both Compose
templates and public examples pass the option explicitly. Restart the native
server or recreate the container to change the policy. This is a format option,
not a demonstrated correction for ChatGPT networking or vision delivery.

All new previews, crops and annotated maps use baseline JPEG quality80, 4:4:4
sampling, and a white background for alpha. Oversized candidates reduce dimensions
by15% with quality fixed at80, within the existing2048-edge/2359296-pixel/2MiB
limits. Source metadata is removed; the only generated metadata is a fixed96DPI
JFIF header. Pixel decoding and encoding stay in the supervised worker. Parent
checks accept only bounded single-scan baseline containers and reject source
metadata, thumbnails, progressive scans, invalid framing and trailing bytes.

The trusted server policy travels explicitly in both worker request paths;
worker environment sanitization continues to exclude server configuration and
credentials. MCP request fields are unchanged. The output MIME enum now includes
`image/jpeg`, with canonical `.jpg` capability URLs and matching GET/HEAD headers.
Image-info metadata continues to describe the original source. Disabling JPEG
restores the existing PNG→WebP90→WebP82 policy and alpha preservation.

Schema1 preview stores migrate transactionally to schema2, preserving complete
old PNG/WebP rows, digests, encoded bytes and expiry. An injected copy failure
rolls back both DDL and rows. Existing JPEG links also survive disabling the
option. No stored artifact is re-encoded. See the
[operator migration and rollback guidance](../../image-viewing.md#jpeg-output-and-store-migration).

## Deterministic MCP measurements

Measured on2026-11-14 through FastMCP discovery/invocation and the production HTTP
handler with synthetic originals; no game data, bearer URLs or billed tokens are
included. The ordinary comparison makes five image-tool calls plus one discovery
call; the map comparison makes eleven calls and transfers the original once.
All selected results and note-legend reads complete. Tests retain the existing
paginated journal/map workflow checks independently of encoding choice.

| Scenario | PNG response JSON bytes | JPEG response JSON bytes | PNG image bytes | JPEG image bytes |
| --- | ---: | ---: | ---: | ---: |
| Tiny31×17 default preview |385|386|125|397|
| Tiny11×9 crop |383|384|106|332|
| Plain500×500 map |392|393|1864|3263|
| Annotated500×500 map |937|938|2748|3767|
| Annotated200×200 crop |941|942|1254|1259|

JPEG does not always produce fewer bytes than PNG, especially for small images
or flat-color fixtures. These artifacts use lossy encoding and are not an
equal-pixel-content savings claim. The public URL-tool discovery record grows
from15827B before the change to16135B afterward (+308B); image-info remains6212B.
The post-change synthetic catalog has46 tools and322886 compact JSON bytes.
Full MCP result sizes for map outputs increase by2B (plain1012→1014B,
annotated2170→2172B, annotated crop2178→2180B). Binary pixels remain outside the
MCP JSON response.

Focused evidence covers native PNG/WebP/JPEG sources, white compositing, original
MIME preservation, crop geometry, quality80 reduction policy, real noisy-image
size reduction, native annotation rendering, metadata stripping, strict settings,
legacy mode, malformed containers, migration rollback/persistence, MIME/suffix
matching, anonymous GET/HEAD, and existing permission/revision/cancellation gates.

## Completed local verification

On2026-11-14,244 preview tests and120 map tests passed, followed by the full
`./scripts/test.sh` Python/JavaScript run (795 JavaScript tests, zero failures).
The final MIME/suffix model assertions passed separately after being added.
All40 Compose/document examples passed with synthetic values, covering unset,
true, false and empty JPEG settings with enabled/disabled preview origins.

The existing bounded `scripts/image-preview-live-check.py` passed against the
localhost `test` world and ready GM with temporary loopback TLS/private storage.
It made20 MCP calls (cap60), reconstructed a journal across four source fragments,
reused the staged source handle, and issued five distinct preview capabilities.
Five JPEG artifacts were decoded/fetched with matching MIME/size and15 successful
HTTPS GET/query/HEAD checks, zero redirects and empty HEAD bodies. Image sizes
were2590B (512×384 overview),511B (160×120 crop),284B (1×1 crop),2590B
(browsed-image selector), and3356B (SVG-origin preview). The live catalog had47
tools/323740B, including the development-only execution tool; this differs from
the synthetic46-tool catalog above. All native source/runtime checks completed.
Existing document fingerprints were unchanged, exact-marker journal/assets were
cleaned up, local settings were restored, and server/GM health returned normally.

No production deployment, release or remote configuration was performed. Actual
ChatGPT visual ingestion, public HTTPS delivery and configured S3 remain outside
this local evidence. JPEG output is not proof those client paths work.
