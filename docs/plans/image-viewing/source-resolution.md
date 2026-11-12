# Preview source resolution — task 02

Internal browser helper `resolvePreviewSource({image}|{src}, isCurrent)` in
`journalImages.js` selects sources but fetches no bytes and registers no MCP/RPC
placeholder. Existing browsing/embedding contracts remain unchanged.

Canonical images use `resolveJournalImage` for fresh exact membership. Bare
references inspect only their referenced parent in configured data/public
sources or up to100 configured S3 buckets. They compare once-decoded segments,
reject dot traversal and encoded separators, and preserve the exact selector
returned by FilePicker. A single readable match gets a second membership check;
multiple positively verified matches return AmbiguousSource with a bounded
browse call. No match returns ImageNotFound only if every relevant listing
succeeded; any failed listing makes zero matches BrowseFailed, not absence.

A failed configured parent does not veto a verified readable object in another
source. That case retains `scope_status:partial` and a fixed limitation in the
private selection context. This describes coverage, not file existence in the
failed source. It does not silently choose the first of multiple readable
matches. This policy is necessary because core public references commonly have
no User Data parent, and FilePicker combines missing/denied/unavailable failures.

Local references remain on the Foundry origin and public `getRoute('')` prefix.
The local cache keys v/version/t/cache/cb/cacheBust/_ may carry bounded harmless
values; other local queries and fragments are rejected. S3 uses only a fresh
picker-selected object's exact host/path; signed query data is private and the
selected fetch policy is `credentials:omit`. Local policy is `same-origin`.
Standard URL parsing does not authorize unrelated absolute references. Host
filesystem protocols, Windows paths and traversal never become fetch targets.

Private return fields are `image`, `fetch_url`, `credentials`, `world_id` and
`user_id`, plus partial coverage when applicable. Never serialize that object to
MCP or logs. World/GM/readiness and the supplied exact-socket guard are checked
across every await. Byte transfer and redirect enforcement belong to tasks
03a/03b; this helper does not establish byte identity.

## Public API and runtime evidence

The existing FilePicker public-contract evidence is in [baseline](baseline.md).
Grounded Docs foundry-vtt@14 search and fresh official
[getRoute page](https://foundryvtt.com/api/v14/functions/foundry.utils.getRoute.html)
confirm public `getRoute(path: string, prefix?: string|null): string`, without
private/protected annotation. The helper uses the default configured prefix,
never a private setting or UI DOM. The index remains the completed
2026-10-12T22:52:58Z v14 index (1,978 URLs/17,801 chunks).

After focused offline checks, `./scripts/actor-tools.sh refresh` loaded the
module; `./scripts/actor-tools.sh browser` reported ready GM, world test,
Foundry14.369, zero console errors. The bounded read-only
`.venv/bin/python scripts/image-preview-sources-live-check.py` passed one MCP
development invocation covering canonical public SVG, bare reference and
absolute local reference with harmless cache suffix. No asset/document mutation,
fixture or cleanup was needed.

The first live probe found canonical success but bare/absolute BrowseFailed:
the initial implementation demanded successful listings from every plausible
source. A unit test reproduced the mixed-availability failure before correction;
the same test passed after selecting the sole verified readable match while
retaining partial coverage. The original zero-match failure/empty distinction
and multiple-readable-match ambiguity remain covered. No arbitrary retry or
limit increase was used. Unsuccessful correction attempts: zero.

Mock coverage verifies configured/path-style S3, signed targets, URI escaping,
route prefixes, fresh checks, oversized lists and world/GM/socket changes.
Live S3 requires a configured browser-readable bucket; none was used. Live
nonempty route prefixes require an existing prefixed deployment; local evidence
covers the default empty prefix only. These are precise remaining compatibility
checks, not claims established by mocks.
