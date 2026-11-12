# Full-size map fidelity and payload evidence

Task12b uses the12a production MCP/JS/RPC/cache/native/store/HTTP harness. The
separate bounded command is:

```bash
.venv/bin/python scripts/image-preview-measurements.py
```

It generates actual10000x10000 and10000x5000 RGB PNGs in a private temporary
directory, with opaque filenames and distinct small center/far-edge marks. A
streaming writer caches16 rows (480000 bytes at10000px), plus bounded working
rows/zlib/chunk buffers; it creates no giant parent raster. The critical chunk,
filter0/zlib and CRC format follows the [W3C PNG specification](https://www.w3.org/TR/png/).
An independent scalar oracle computes only selected source-region pixels,
without reading/cropping the large original. Small tests compare the writer,
oracle and independent Pillow decoder, and exercise bounds/report failures.

## Real full-size results

Final command:17 actual MCP requests/11 anonymous HTTP fetches; both maps complete,
with one original transfer per map and no retransfer for repeated crops. Two
expected InvalidCrop calls are reported separately from successful streams.
The command is capped at80 calls/1200s; underlying per-map harness also enforces
40 calls/600s. No limits were raised.

| Source | Original bytes | Private chunks | Overview | Encoded overview bytes | Calls | Transfers |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
|10000x10000|11811013|361|1536x1536 PNG|1638691|8|1|
|10000x5000|5916747|181|2048x1024 PNG|921407|9|1|

Both overviews and reduced3000x3000 source crops are independently decoded from
their HTTP response and checked against actual dimensions/MIME/length/budgets.
Native32x32 bottom-right,17x17 center and one-pixel corner crops match scalar
source pixels exactly. The wide map also passes the specified
`(7200,3100,1280,960)` native crop. Pixel/capability/seed values remain private.
Mirrored/rotated/transparency workflows are covered by the rerun12a fixtures;
these full-size resource cases are RGB, not a claim about all format/channel
combinations. Lossless PNG comparisons use exact bytes; no lossy tolerance is
needed for these generated cases. Existing lossy/native codec tests remain in
the full suite.

| Measured overview | Peak RSS bytes | Peak scratch bytes | Elapsed seconds | Samples |
| --- | ---: | ---: | ---: | ---: |
|10000x10000|351961088|301645824|0.445672|19|
|10000x5000|200380416|150925312|0.299555|13|

The same maxima bound all5/6 successful renders per map. Across11 renders,
total worker elapsed was2.727889s. These measurements cover render operations;
header-info probes are separately tested but are not included in this aggregate.
Defaults remain1GiB RSS/2GiB scratch/90s, with one render at a time. Resource
sampling is25ms plus scheduling/scan latency, with final scratch checks; the
numbers are observations, not instantaneous cgroup memory guarantees or latency
percentiles. Generation, transport, queueing and client time are not worker time.

| Full-size tool stream | Calls square/wide | Structured JSON bytes square/wide | MCP result bytes square/wide | Complete |
| --- | --- | --- | --- | --- |
| get_foundry_image_info |1 /1|200 /198|610 /606|Yes|
| Successful get_foundry_image_url |5 /6|1999 /2395|5138 /6158|Yes|
| Expected invalid crop |1 /1|0 /0|364 /363|Expected error|

Each map also makes one discovery request:44 production tools/272552 compact
catalog bytes. This representation is raw `tools/list.result.tools` JSON and is
kept distinct from the SDK-model catalog serialization below.

## Comparable live replay

After offline checks, the existing localhost14.369/test GM remained connected.
The read-only command `.venv/bin/python -m foundry_mcp_server.image_preview_audit`
passed23 calls/0.947s, reusing ignored private baseline selectors. Initial journal
navigation's two calls were unnecessary because those exact selectors persisted.
No existing document, file or Scene was changed.

Every comparable structured/protocol byte count matches the
[task01 baseline](baseline.md):

| Scenario | Calls | Structured bytes | MCP result bytes | Complete |
| --- | ---: | ---: | ---: | --- |
| Default data root |1|3106|6760|Yes|
| Default public SVG page |1|2096|4676|No|
| Literal SVG filter |1|751|1764|Yes|
| Expanded100-entry/48000B page |1|15051|32746|No|
| Complete SVG traversal |12|25373|56524|Yes|
| Journal contents default |1|911|2118|Yes|
| Journal contents expanded |1|1605|3584|Yes|
| Journal page default |1|590|1428|Yes|
| Journal page expanded |1|902|2088|Yes|
| Complete journal page |1|590|1428|Yes|

The rerun12a regression also reconstructs a journal reference and exercises
browse-to-fetch through actual MCP/HTTP in10 calls. Its complete small-fixture
payloads remain identical to the [recorded workflow table](workflow-integration.md);
these are separately identified synthetic inputs, not substitutes for live
baseline content or full-size resource evidence.

Live SDK-model discovery is45 development tools/275617 bytes, versus43/262218
at baseline:two image tools add13399 bytes. The extra development execution tool
and catalog representation explain its difference from the production table.
This adds capability/discovery cost; no equal-content savings or billed-token
claim is made. Baseline small journal completeness does not establish behavior
for all large pages; the three-fragment synthetic workflow supplies that check.

The final large+live evaluation totals40 calls. An initial17-call large run
preceded independent HTTP-decoder/per-map resource reporting improvements;
57 full-size/live evaluation calls in all, below the80-call campaign cap.
No extra passing samples were collected after those assertions passed.

Failure-accounting regression initially reported0 calls after discovery plus a
failed info call. The unchanged2-call assertion passes after including active
workflow counts/partial aggregates. Failed measurements stay failed and retain
only technical statistics, never tool bodies, paths, source handles or URLs.

All generated maps, snapshots, private stores and Node subprocesses are cleaned
on exit. No live game fixture, externally reachable capability, public deployment
or model call was used. Final local tests are recorded in
[task12b](tasks/12b-large-map-and-payload-measurements.md). Live S3/prefixed host,
packaging/font/map extensions and public target-client acceptance retain their
separate later prerequisites; these passing pixels do not replace those gates.
