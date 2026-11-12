# Anonymous pixels, authenticated issuance, private diagnostics

Anonymous access is confined to the preview GET/HEAD prefix. A capability selects
one already stored derivative; it cannot select original bytes, crops, sources,
MCP sessions or browser operations. Reader authorization does not depend on a
GM connection. Issuance still requires a configured origin and authenticated
Basic/OAuth/development context plus the later image-tool GM checks. Plain-none
mode can read a configured existing store but cannot issue.

Actual fresh production applications verify the existing Basic/OAuth/development/
none boundaries. Missing/invalid/duplicate MCP credentials are rejected in the
authenticated modes, including private PDF tool calls. Offline signed OAuth
tokens exercise valid access, invalid key/subject, missing scope and rejection
of Basic in OAuth. Preview paths cannot authenticate the actual GM WebSocket
route. No tenant, login, refresh or production credential changes are involved.

The matrix exposed a development-auth defect: converting headers to a dictionary
collapsed duplicates. A required401 assertion failed. The development branch
now admits exactly one Authorization header, bounded to8192 bytes, before the
existing local-peer/credential checks; the same unchanged assertion passes.
This matches Basic's bounded-header policy without imposing credential-strength
or credential-distinctness requirements. OAuth retains its independent boundary.

## Diagnostic policy

`image_preview_privacy` installs narrow standard logging filters on Uvicorn,
application/evaluation/development execution and HTTP-client loggers, plus
their configured handlers. Installation is idempotent and repeated at app startup
after Uvicorn logging configuration. Other route names, methods and statuses
remain visible; logging is not disabled globally.

Filters remove preview paths/URLs and their query/fragment values, including
encoded-prefix classification, and credential-bearing/signed URLs. Exception
text is scrubbed before handlers format it. Uvicorn's five access arguments are
preserved so its real AccessFormatter retains method/version/status information.
Production code uses standard logging APIs; Uvicorn internals appear only in
the focused protocol test, pinned to installed0.40.0.

`TraceRecorder.emit` independently replaces sensitive strings/field names with
redaction markers and SHA256 fingerprints before JSONL encoding. Existing input
fingerprints, call counts, success/error categories, timings and actual response
byte measurements remain. Model-visible tool results are unchanged. Neither
the URL response body nor source bytes are logged. New image arguments already
use the default redacted argument policy; the final trace boundary also protects
capabilities embedded in otherwise allowed query/metadata fields.

Configured private logging remains necessary. Reverse proxies and external
clients are separate processes: their logs are not scrubbed by these Python
filters. For the preview prefix, proxy access formats must omit the URI, query,
Referer, Authorization and cookies, retaining only safe route/status/count data.
Do not expose a login wrapper, redirect, or cache for that prefix. Task13 owns
the final capability-safe proxy examples and deployment guidance.

## Verified evidence

Captured access/application/evaluation tests initially found the fixture nonce
in emitted output. The same unchanged tests pass after narrow redaction.
Malformed encoded-URL and unpaired-surrogate JSON regressions also failed first,
then passed after corrections, without changing expected behavior.

The real Uvicorn H11 request/response cycle drives the production ASGI app over
a memory transport and emits actual200/query200/404/503 access records. Captured
formatted logs contain no bearer nonce; /health and statuses remain readable.
This needs no second listening server or Foundry instance. ASGI route tests also
verify exact expiry, malformed paths, matching HEAD and query equivalence.

The auth probe is bounded to four fresh processes,30 seconds each and at most16
calls per process. Final aggregate measurements count HTTP requests, including
discovery, denied calls and anonymous pixel reads. Catalog bytes are compact
UTF8 JSON of `tools/list.result.tools`, not billed tokens or the older audit's
whole-response representation. No equal-content savings claim is made.

| Mode | Calls | Tools | Catalog bytes | Anonymous pixels | Issuance policy |
| --- | ---: | ---: | ---: | --- | --- |
| Basic |9|42|259253|Passed|Authenticated only|
| OAuth |13|42|261857|Passed|Authenticated only|
| Development |9|43|259741|Passed|Authenticated local only|
| None |4|42|259253|Passed|Disabled|

The development-only execution tool accounts for its additional catalog entry.
OAuth adds2604 metadata bytes across42 tools. No preview issuance stub appears
in discovery. Public image-tool registration remains task11. Tests keep fixture
capabilities, signing keys and bytes out of transcripts/tracked evidence; only
the bounded aggregates above are printed.

Exact focused/full/package outcomes are in
[task09b](tasks/09b-auth-boundaries-and-capability-privacy.md). Real Auth0
login/refresh retains its existing operator gates; public HTTPS and target-client
visual acceptance remain later gates. Offline JWT/access-log evidence does not
claim those deployment/client checks passed.
