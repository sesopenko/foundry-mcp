# Private-answer target ChatGPT acceptance

Implementation and local HTTP/pixel verification are separate from actual
ChatGPT visual acceptance. The external gate is **pending**: no target ChatGPT
session or publicly reachable trusted preview HTTPS origin is available here.
Neither the agent's image inspection nor a successful curl response satisfies it.

## Exact prerequisites

Use the existing authorized `test` world and dedicated GM profile, with matching
server/module source builds and refreshed client discovery. The target ChatGPT
must connect to an operator-provided authenticated Basic/OAuth MCP deployment
whose configured preview origin is publicly reachable over trusted HTTPS.
The current loopback-only development service/TLS fixture is not that deployment.
Keep MCP/WS/PDF authentication intact and configure the preview prefix for direct
anonymous uncached GET/HEAD with capability-safe logs. Do not publish a deployment,
alter Auth0 tenants or provision another Foundry instance merely to satisfy this
gate. See [image-viewing operations](../../image-viewing.md).

## Prepare without revealing the answer

The existing verification script provides these modes:

```bash
.venv/bin/python scripts/image-preview-live-check.py --visual-handoff
.venv/bin/python scripts/image-preview-live-check.py --prepare-visual-fixture
.venv/bin/python scripts/image-preview-live-check.py --visual-handoff-status
.venv/bin/python scripts/image-preview-live-check.py --cleanup-visual-fixture
```

The first mode creates an ignored private bundle at
`.local/image-preview-visual-handoff/` with0700 directory/0600 files. It refuses
to overwrite an existing bundle. `expected.json` contains randomized answers;
never paste it, display the original challenge to the agent/client, or copy it
into tracked records. The opaque-named PNG has no textual metadata. Only pixels
inside original rectangle`{x:720,y:500,width:240,height:200}` contain its random
label/symbol/color pair. Outside is a neutral field. Filenames, captions, alt
text, journal prose, prompts, note legends and public reports contain no answer.

Preparation uses the existing authenticated local GM connection, a new exact
marker-owned User Data image directory, and one marked journal/page through
`write_journal`. It does not issue a public URL. Concrete journal and named
map-folder prompts are written privately to `prompts.json`. This is the file to
use with the target client after its real endpoint/bridge prerequisites exist.
The private `fixture.json` records readiness/identity for exact cleanup.

The retained private bundle is a handoff artifact; its initial prompt templates
are not usable world selectors. Run preparation before a real trial. After
cleanup, readiness is false and prompts reset to templates so deleted selectors
cannot be mistaken for a ready fixture. Preparation can be repeated from the
same private pixel bundle. Keep only one prepared fixture per bundle and clean
it after all controlled trials, including failures.

## Four distinct observations

1. **Journal pixel workflow.** In a fresh ChatGPT context, use the private
   journal prompt: read its actual page, call image info, request the exact
   original rectangle, fetch the returned URL and report the short label, its
   color and the neighboring symbol color from pixels. Keep the expected answer outside every prompt,
   filename, caption, alt text, legend and tool result. Record actual observed
   calls/fetch and answer; a model's description of what it did is insufficient.
2. **Exact-link comparison.** Privately retain that issued crop URL. In a
   separate fresh context ask the same nonrevealing image question using the
   exact URL. Record client-fetch success/failure and its pixel answer.
3. **Query comparison.** In an equivalent third fresh context use only that
   same capability with`?probe=1` appended. Do not issue a different image or
   reuse the prior conversation's answer. Record its outcome separately. Both
   trials must use the same bytes/path, equivalent questions, and separate traces.
4. **Map/key workflow.** In a fourth fresh context use the private named map and
   ancestry prompt, without supplying a preselected file/source handle. Observe
   folder browsing, explicit level selection,`map_notes:true`, image fetch,
   reading a visible key from pixels, exact revision-bound legend pagination,
   and the correct linked journal/page follow-up. Record omissions/partial scope
   and obstruction honestly. Request detail if a desired key was omitted.
   A legend lookup does not establish the hidden-label answer in the other test.

The private prompt templates are:

> Read journal page `<actual page UUID>`. Inspect its image region with original
> top-left coordinates720,500 and extent240,200. Read the short label, its color
> and the neighboring symbol color from image pixels. Use image information and an exact crop,
> then fetch the returned image URL.

> Browse the map named `<actual map name>` under `<named folder ancestry>`.
> Use discovered next calls to choose its explicit level background. Request an
> annotated crop, fetch it, identify a visible note key from pixels, and follow
> its exact revision-bound legend to the linked journal/page. Report omissions.

## Reviewed evidence and truthful status

Default status is pending for all four scenarios. Optional private
`observations.json` has up to four keys:`hidden_workflow`,`exact_link_trial`,
`query_link_trial`,`map_workflow`. Values use the strict `ReviewedTrial` contract
in `foundry_mcp_server/image_preview_visual_handoff.py`: provenance must be
`reviewed_target_client_trace`,client`ChatGPT`,distinct context IDs and64-hex
trace SHA256 fingerprints, observed fetched URL, actual client-fetch boolean,
and answer. Retain and inspect the corresponding original private traces before
entering these records. Shape checks and a typed provenance field do not
authenticate who produced a supplied record; this is reviewed operator evidence,
not automated proof of ChatGPT provenance.

The journal record also needs observed info call and exact requested rectangle.
Map evidence needs observed browse/level selection/annotation flag, a key read
from pixels, matching rendered-key legend and journal/page follow-up; positive
omissions require explicit reporting. Exact/query records need the same issued
canonical capability, only`probe=1` on the query trial, and distinct fresh
contexts/traces. Missing evidence stays pending; failed observed behavior is
failed. The status command returns failure for failed acceptance and prints only
statuses/prerequisites, never answers, URLs or trace contents. Unit fixtures can
test a passed state; they do not make the real gate passed.

## Cleanup and current evidence

The cleanup mode reuses14a's exact journal request-marker checks and file owner
validation. It removes only the bundle's new game fixture, verifies no marked
journal/folder remains, and preserves the private challenge bundle for handoff.
Existing game documents/assets and other private bundles are never cleanup targets.
Deleting an original does not revoke a published derivative: real client-issued
links keep their seven-day lifetime. This local preparation issues none.

Focused handoff10 tests pass, including answer/crop/metadata isolation, private
permissions, fresh exact/query equivalence, strict observed states, honest map
omissions, failed-preparation cleanup and readiness reset. Full regression and
native preparation/cleanup evidence is recorded at task completion. A reuse
regression proved that a fresh fixture lifecycle needs fresh operation IDs:
the browser correctly retains prior write receipts after document deletion.
Each new preparation now uses a fresh generation within the same cleanup-marker
prefix; the unchanged retained-receipt test and native repeat preparation pass.
Final full1053 Python tests (1 existing skip)/795JS pass148.844s for Python.
Native preparation5 calls/exact cleanup1 passed, with0 public URLs issued and
all game fixtures removed. Private bundle readiness is false; it is retained
for the operator's future trial, and dedicated browser readiness/console0 passed.
Real visual
acceptance remains pending until the four actual target-client observations
above exist, regardless of local test results.
