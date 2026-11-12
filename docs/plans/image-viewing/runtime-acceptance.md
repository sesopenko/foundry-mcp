# Existing-world preview acceptance

Task14a's bounded check uses the existing root-Compose Foundry14.369 `test`
world, dedicated GM browser and managed MCP user service. Run offline tests
before invoking the fixture verifier:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_live_check.py' -v
./scripts/test.sh
.venv/bin/python scripts/image-preview-live-check.py
./scripts/actor-tools.sh refresh
./scripts/actor-tools.sh browser
```

The harness creates one random-marker image directory and one marked journal
with one text page. It reads the page through actual MCP continuations, proves
the stored image tag spans fragments and reconstructs the exact HTML. Bare src,
browse selector, repeated source-handle overview/crops and core SVG requests
exercise the production tools, browser transfer and native decoder.

Private support helpers own assets, the60-call/1200-second MCP budget, TLS/curl
checks and temporary service configuration separately. The reserved cleanup
call shares that60-call ceiling and has30 seconds beyond the operation deadline.
The file fixture refuses deletion if its exact ownership marker changes, a
symlink appears or another file enters its directory. Journal cleanup reuses
the existing tested `journalWrites` request-marker checks and rejects unmarked
documents inside marked folders. Existing document fingerprints must agree.

Only a temporary loopback TLS proxy is added. It forwards canonical preview
GET/HEAD paths to the existing service, not MCP, PDF, health or arbitrary URLs.
A generated localhost certificate is trusted only with curl's explicit
`--cacert`; system/browser trust and authentication remain unchanged. Ignored
`.env.mcp` receives only temporary preview origin/store settings and is restored
byte-for-byte before the existing service restarts. Concurrent edits are
preserved and cause explicit failure rather than being overwritten.

Curl receives the issued capability in private stdin configuration, with no
reader credential and no `-L`. Exact HTTPS GET and only-`?probe=1` GET must have
status200, zero redirects, matching MIME/length/cache/nosniff headers and equal
SHA256/decodable dimensions. HEAD uses the same endpoint, matching headers and
an empty body. Only aggregate results are printed; neither capability paths,
source selectors nor game content enter tracked evidence.

The TLS fixture's real-curl regression caught an abrupt TLS EOF during HEAD
verification. Bounded clean shutdown with public
[SSLSocket.unwrap](https://docs.python.org/3.12/library/ssl.html#ssl.SSLSocket.unwrap)
made the same test pass without changing curl assertions or production image
code. Fixture journal deletion/getFlag were rechecked in Grounded Docs14 and
the fresh official [JournalEntry API](https://foundryvtt.com/api/v14/classes/foundry.documents.JournalEntry.html);
these are public methods with no internal/protected annotation. Creation uses
the already verified authenticated journal-writing tool.

## Retained independent evidence

The [large-map measurements](large-map-measurements.md) prove actual10000-square
and10000x5000 source-region fidelity without rerunning a broad benchmark:
square overview1536²/1638691B, sampledRSS351961088B/scratch301645824B/0.445672s;
wide overview2048x1024/921407B, RSS200380416B/scratch150925312B/0.299555s.
Budgets remain1GiB/2GiB/90s. This sampling does not claim an instantaneous hard
memory cap or provider token measurement.

[Store/HTTP tests](http-delivery.md) retain injected-clock enforcement immediately
before and exactly at604800 seconds with pruning paused.
[Packaged verification](../../image-viewing.md) retains anonymous exact/query/
HEAD and identical bytes across same-volume container recreation asUID10001.
Those dependencies have not changed; these checks need no redundant restart or
another Foundry instance.

## Native results

Focused helpers12 passed1.401s, including actual curl/TLS, cleanup deadlines and
private config restoration. Final offline suites passed1032 Python tests
(1 existing skip)/794JS in135.075s for the Python suite. The native command
passed20 MCP calls under its60-call/1200-second guard; native wall time was not
separately captured. It reconstructed the exact stored img tag across4 fragments,
issued3 distinct previews using one returned source handle, followed the browse
selector directly, and decoded the core SVG. The fresh catalog contains47
tools/323516 compact SDK-model bytes; info6219B,URL15834B,browse9907B and
journal-reader7002B discovery records.

All five derivative workflows passed anonymous exact/query GET plus HEAD through
the real existing service and local TLS proxy:15 curl requests, status200,
zero redirects, matching MIME/length/cache/nosniff headers, equal query hashes,
decodable dimensions and empty HEAD. The512x384 overview was1454B;160x120 detail
382B;1x1 border crop90B; browse-selector overview1454B; core SVG raster16862B.
Source-info structured results were193B (fixture) and196B (SVG). URL results
were381–390B; browse898B. Four journal fragments totaled3839 structured bytes
and8680 MCP-result bytes. These are bytes, not measured provider tokens.

Existing journal/folder/user fingerprints agreed. Exact marked journal and image
directory cleanup succeeded; original private service settings were restored
byte-for-byte, temporary TLS/certificate/store files removed, and existing
service/GM readiness restored. Fixture derivatives were disposable private test
state; cleanup does not introduce a general early-revocation feature for issued
seven-day links.

## Remaining evidence

Loopback TLS acceptance does not establish externally reachable public HTTPS or
target-ChatGPT visual acceptance. The latter needs an operator-provided public
origin and the actual client with refreshed tool discovery. Live S3 additionally
needs an existing configured browser-readable bucket/CORS; live route-prefix
acceptance needs an existing prefixed deployment. Mocks remain separate evidence.
