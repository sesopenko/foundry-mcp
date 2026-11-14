# Image information, map crops and seven-day previews

Version 4.0.0 can read portraits and map files through the connected GM
browser, stage an original privately, and issue bounded image previews or
exact crops. It also browses world Scene folders, reads grid/level file metadata
and optionally draws compact map-note keys. Public-host and target-ChatGPT
visual acceptance remain separate verification gates.

## Configure delivery

Use either [Basic Compose](../deploy/compose.yaml) or the separate
[OAuth Compose](../deploy/compose.oauth.yaml), with its environment template.
Set `FOUNDRY_MCP_IMAGE_PREVIEW_ORIGIN=https://mcp.example.com` to the canonical
externally reachable HTTPS origin. No trailing slash, path, query, fragment or
credentials are accepted. This variable is independent of OAuth's
`FOUNDRY_MCP_PUBLIC_URL`; Basic never requires OAuth configuration. Empty origin
disables URL issuance before source work, while authenticated image info remains
available. Plain unauthenticated mode cannot issue links.

## JPEG output and store migration

Version 4.0.0 defaults `FOUNDRY_MCP_IMAGE_PREVIEW_JPEG` to `true` when unset.
All new previews, crops and annotated maps use baseline JPEG at fixed quality80
with 4:4:4 chroma sampling. Transparency is composited onto white. URLs end in
`.jpg`; both MCP `mime_type` and HTTP `Content-Type` are `image/jpeg`.
Original-image info still reports the original MIME and dimensions.

Set `FOUNDRY_MCP_IMAGE_PREVIEW_JPEG=false` to restore the PNG-first, then
WebP90/82 policy and alpha preservation. Only literal `true`/`false` are valid;
empty values fail startup. Compose templates pass this variable explicitly;
adding it to `.env` alone does not change an older Compose file. Recreate the
container after changing it, or restart the native server. Refresh client
discovery for the expanded response MIME enum. JPEG does not establish that
ChatGPT can fetch the URL or receive its pixels; target-client acceptance is
still separate.

On startup, the private derivative database migrates transactionally from schema1
to schema2 to admit JPEG. Existing PNG/WebP rows, bytes, capability digests and
expiry timestamps are preserved; previously issued URLs never change format.
Setting the option to false affects only new issuance and does not disable
existing JPEG links. Before upgrading a populated store, stop the server and
back up its SQLite state. An older schema1-only binary cannot reopen schema2;
rollback requires the pre-upgrade consistent backup (newer links then disappear).
No originals or game assets are modified or reparsed.

See [JPEG contracts and measured payloads](plans/image-viewing/jpeg-output.md)
for focused verification evidence and the PNG/JPEG size tradeoff.

Both templates mount the private named `image-previews` volume at
`/data/image-previews`. The image creates that directory for UID/GID10001 with
0700 permissions; SQLite files are0600. Keep the volume across upgrades and
container recreation. Do not run `docker compose down --volumes` on a deployment
whose links must remain readable. For backups, stop the MCP service before
copying SQLite state; preserve expiry timestamps. Originals and decoder scratch
are ephemeral private temporary directories, separate from the derivative store.

Upgrade the server and companion module together, reload the dedicated GM
browser, and reconnect MCP discovery. Use `get_bridge_versions` to inspect the
loaded pair. No Foundry server provisioning or asset migration is needed.

Anyone holding an issued URL can read its selected pixels until exactly seven
days after publication, including after GM disconnect or server restart. Issued
images are immutable; changing a note or file does not revoke their pixels.
Only the exact preview GET/HEAD route is anonymous. MCP, browser bridge and PDF
authorization remain independently protected.

## HTTPS proxy and private diagnostics

Route `/image-previews/` directly to the MCP service, preserving its path/query.
Do not add authentication, redirects, HTML wrappers, compression transforms or
caching to this prefix. GET and HEAD must preserve Content-Type, Content-Length,
`Cache-Control: private, no-store` and `X-Content-Type-Options: nosniff`.
The query is ignored for lookup: the canonical URL and its `?probe=1` variant
must return the same bytes without following redirects.

For an existing Nginx HTTPS server with a host-local upstream, the dedicated
location can use:

```nginx
location ^~ /image-previews/ {
    auth_basic off;
    access_log off;
    error_log /dev/null crit;
    proxy_cache off;
    proxy_redirect off;
    proxy_intercept_errors off;
    proxy_pass http://127.0.0.1:8000;
}
```

Integrate this into the operator's existing TLS configuration and verify its
complete effective configuration, including inherited rewrites/error handlers.
If an installed authorization-subrequest module is inherited, also set
`auth_request off` in this location; the module is optional in Nginx builds.
The snippet does not configure certificates or change MCP/WS/PDF locations.
Disable preview request/error logging at every upstream proxy/load balancer too;
never log capability paths, query strings, Referer, cookies or credentials.
Python access/evaluation logs redact preview capabilities, but cannot scrub
other processes' logs. Keep private expected visual answers and real example
URLs outside tracked reports. See [privacy evidence](plans/image-viewing/capability-privacy.md).
Directive contracts: official [proxy configuration](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)
and [optional auth_request module](https://nginx.org/en/docs/http/ngx_http_auth_request_module.html).

## Choose images and crops

For journal HTML, follow `read_journal_page.next_cursor` until an entire `img`
tag is reconstructed. Pass its stored `src` directly to
`get_foundry_image_info`, or pass the exact `image` returned by
`browse_journal_images`. There is no directory crawl or arbitrary-URL fetch.
Configured S3 needs picker membership and browser CORS; signed references stay
private. A fresh info call stages current bytes and returns seven technical
fields, including original display-oriented dimensions and a caller-bound
`source_id` valid for30 minutes. Reuse that handle for repeated crops without
another transfer; replaced bytes at the same path require fresh info.

URL accepts exactly one of `image`, `src`, `map` or `source_id`; info accepts the
first three. Optional `crop:{x,y,width,height}` uses zero-based integer original
display pixels, with exclusive right/bottom edges. The entire positive rectangle
must fit; no clipping/padding occurs. Missing crop selects the whole original.
Use returned `region` and actual output dimensions when selecting a tighter
crop from a preview: floor the mapped left/top, ceil the exclusive right/bottom.

Source limits are128MiB compressed,32768 pixels per edge and128 million pixels.
Delivered JPEG/PNG/WebP is at most2048 per edge,2359296 pixels and2MiB, preserving
aspect and skipping enlargement. The isolated worker permits one operation,
1GiB sampled resident memory,2GiB scratch and90 seconds. JPEG80 is the default;
disabled JPEG mode prefers PNG then WebP90/82. Oversized candidates trigger15%
dimension reductions, without reducing JPEG quality. Source EXIF/GPS/comments
are removed. JPEG,PNG/APNG,WebP,AVIF,BMP,GIF,TIFF and bounded self-contained SVG
are supported; animation/multipage content uses the first displayable frame/page.
The store admits at most1GiB/4096 live derivatives after expiry pruning.

`SourceUnavailable`/`SourceContextLost` requires restoring the intended GM and
staging fresh info. `InvalidCrop` supplies valid original dimensions.
`UnsupportedImage`/`ImageTooLarge` requires supported/smaller content.
`PreviewNotConfigured` requires the origin/private-store setup above; quota or
worker-limit failures do not invalidate previously issued URLs.

## Browse maps and follow rendered notes

`browse_maps` returns immediate world Scene folders/maps with UUIDs, named
ancestry and next calls, retaining duplicate names. It does not activate a Scene
or search image contents. Follow `get_map_info` for geometry/grid, explicit
levels and separate background/foreground roles; Tile inventory is a separate
section. Scene/grid dimensions are configuration, not decoded file dimensions.
Videos, missing files and unavailable scopes remain explicit. A role image is
not a composite of fog, lights, tokens, walls, Tiles or foregrounds.

Pass the exact returned `map:{scene_uuid,level_id,role}` selector to image info.
Then request URL using its bound `source_id`, optional crop and `map_notes:true`.
The strict boolean defaults false and adds no result section when false.
Annotations currently support default background placement on Foundry14.369;
foregrounds remain fetchable as ordinary files. Unverified builds/nondefault
transforms and Tile composition return `UnsupportedMapMapping` for annotations.
Raw files never infer map identity; use the returned map selector instead.

Generated N1/N2/... keys target16px final em with white fill/dark1px outline,
at most20px ink,100 labels and5% label-box area. Dense/edge/tiny cases honestly
report omissions and suggest tighter crops; keys are never shrunk to conceal
crowding. Labels/leaders can obscure underlying features despite those bounds.
The typed `map_notes` result distinguishes rendered completeness, permission
scope and legend pagination. Follow its exact Scene/level/revision-bound
`legend_next_call` and returned cursors to completion to resolve keys to Note,
journal and page identities. No journal bodies are read to draw keys.
`MapContextChanged` requires fresh map info/source staging and discarding old
alias joins. See [complete map contracts](plans/image-viewing/map-image-tools.md).

## Verify the shipped artifact

After offline tests, build locally and run the fixed package harness:

```bash
docker build --pull=false -t foundry-mcp-image-preview-check:local .
.venv/bin/python scripts/image-preview-package-check.py
.venv/bin/python scripts/image-preview-compose-check.py
```

The harness creates only one freshly named, marked MCP container and volume,
checks the shipped codecs/font/annotation asUID10001, reads anonymously through
its actual listener, recreates the container with the same volume and compares
bytes. It prints only aggregate results and cleans its exact owned resources.
It mounts no repository/native library, provisions no Foundry instance and
publishes no host port. Target-client visual acceptance and operator HTTPS
routing remain separate from packaged listener success.

Verified locally on2026-11-12 with image
`sha256:c41bca108db260560aa74fc3115541bec9f7a7b0bb2a5db43e021b621fd5d566`:
UID10001,pyvips3.2.0/libvips8.18.7/Pillow13.0.0, all nine advertised format
families and unsafe-SVG rejection passed. Repeated annotation bytes agreed;
the500-square annotated PNG was2760B. Measured N1/N12/N100 boxes were22x14,
32x14 and43x14 pixels. Anonymous exact/query GET and HEAD agreed before and
after same-volume container recreation; owned container/volume cleanup passed.
The ten enabled/disabled-origin Compose examples validated. This establishes
packaged HTTP/persistence behavior, not external HTTPS or ChatGPT image access.
