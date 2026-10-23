# Direct exploratory tool pass — October 22, 2026

Requested task: after the current unit, explore the tools built so far through
direct read-only tool calls. The pass is complete; no further sampling is planned.

User-requested exploration after committing the recorded-selection unit.
Code commit `4826d3b6feb9e5e70ed26dac6fe96d982a30e326`; worktree clean at start. Existing authenticated GM
world: Foundry14.369/PF2e8.6.1. No game writes, rolls, imports or fixture creation.
This was direct primary-agent exploration, not a fresh-agent benchmark or a
statistical reliability evaluation. No model token usage was measured.

## Scope and criteria

The declared cap was18 game-tool calls. Check whether published contracts and
returned selectors support capability discovery, world Actor navigation to owned
Items, literal compendium feat search, continuation and error recovery. Successful
navigation must retain canonical identities and context. Partial/unsupported and
empty results must remain explicit; an incomplete page must not support an
exhaustive answer. Root implementation knowledge limits independence of this
exploration; conclusions are scoped to the exercised paths.

## Observations

- Native `get_actor_types` failed with HTTP400/no valid session after the service
  restart. A fresh authenticated SDK client succeeded. This is the known client
  session-lifecycle issue, not evidence that Foundry or the application was down.
- The registry reported compatibility and staged support. Its serialized response
  was32544 bytes; useful detail carries a noticeable discovery cost.
- Literal world search returned named NPC identities and usable read selectors.
  Following a returned continuation produced the next distinct Actor.
- Owned Item discovery returned named identities and usable `read_item` selectors;
  its continuation retained scope. Embedded Items explicitly do not enumerate all
  possible abilities. A small selected read stayed partial with pagination.
- A selected Actor read marked state/effective unsupported and authored source
  partial with pending/pagination reasons. No current effective-statistic claim
  was made. The coarse source-pending reason reflects the existing unfinished
  Actor story, not a new completeness claim.
- Pack discovery supplied the Feats search scope. Literal substring search for
  Battle Medicine returned both Battle Medicine and Paragon Battle Medicine with
  distinct canonical identities. This matches the published search semantics;
  the exact named candidate was selected before full reading.
- Feat source/description/relationships continuation worked without reconstructed
  cursors. Changing the page limit while retaining a cursor returned the expected
  CursorMismatch. Restarting without cursor returned38 records with null next
  cursor and complete selected source/description/relationships; effective stayed
  unsupported. Stored prose retained toolkit, Treat Wounds and immunity details.
- A literal `a.*` world query returned no matches in a completed searched scope;
  it was not interpreted as a regex or evidence of global absence.

No new application defect was found in these exercised paths. Do not extrapolate
this to all tools, types, permissions or runtime versions. Synthetic/linked-token
exploration, denied scopes, concurrent changes, populated grants/selections,
book/affliction limitations and complete Actor statistics were not exercised here.
Prior focused deterministic/live evidence remains separate.

## Measured calls

One native transport failure plus14 fresh-client calls =15 game-tool attempts,
within the declared18-call cap. SDK calls included one intentionally invalid
cursor test;13 returned successful payloads. Approximate serialized response/error
bytes total78635; this uses local JSON
serialization, not wire-byte instrumentation. Summed SDK call durations were
1.228 seconds, excluding client setup,
agent reasoning, approval latency and the native transport attempt. End-to-end
elapsed time was not instrumented; no elapsed-budget or throughput claim is made.

| SDK call | Tool | Outcome | Serialized bytes | Call seconds |
| --- | --- | --- | --- | --- |
| 1 | `get_actor_types` | success | 32544 | 0.017 |
| 2 | `search_actors` | success | 1465 | 0.008 |
| 3 | `list_actor_compendiums` | success | 831 | 0.004 |
| 4 | `search_actors` | success | 1608 | 0.015 |
| 5 | `read_actor` | success | 2702 | 0.006 |
| 6 | `list_actor_items` | success | 1254 | 0.004 |
| 7 | `search_compendium_actors` | success | 1563 | 0.037 |
| 8 | `read_item` | success | 2862 | 0.015 |
| 9 | `list_actor_items` | success | 1255 | 0.005 |
| 10 | `read_item` | success | 4088 | 0.007 |
| 11 | `read_item` | success | 4216 | 0.007 |
| 12 | `read_item` | CursorMismatch | 138 | 1.078 |
| 13 | `read_item` | success | 23666 | 0.019 |
| 14 | `search_actors` | success | 443 | 0.006 |

Selectors and raw responses remain in ignored local files. No private document
IDs, credentials or book text are included in this record. Stop this pass here;
resume implementation with the original remaining story requirements intact.

Repository verification before committing this record passed: 316 Python tests
(one skipped), 390 JavaScript tests, story-map consistency and whitespace checks.
