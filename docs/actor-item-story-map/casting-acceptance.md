# CORE-casting acceptance audit

This audit preserves the original [story](stories/CORE-casting.md) requirements.
The delivered interface reads source configuration, contextual options and selected
current resources. It does not evaluate legal casting, final cast rank or complete
availability. Those limitations must remain visible after story acceptance.

| Original requirement | Implementation and deterministic evidence | Runtime evidence |
| --- | --- | --- |
| Join spell assignments and indexed preparations within the selected owner; preserve unresolved claims | `actorCasting.js`, `actorCastingOptions.js`; `actor-casting.test.js`, `actor-casting-options-readers.test.js`; strict `test_actor_casting_options.py` | Source joins verified in [casting verification](casting-verification.md); independent option key sets/source comparisons passed, including unresolved entries. |
| Distinguish base/configured/slot ranks, repeated preparations and expenditure flags | Option fields `base_rank`, `configured_rank`, `slot_rank`, `preparation_index`, `expended`; `cast_rank` explicitly null. Prepared repeats remain separate even with a zero generic counter. | Independent rank/preparation mapping passed with repeated preparations and zero generic counters. Expenditure booleans were absent; fixtures cover true/false separately. |
| Distinguish repertoire/shared slots, individual innate uses, shared focus and cantrips | Explicit `context`, `resource_scope`, `uses`, `cantrip`; separate source slot/focus and transformed resource records. Missing counters remain unknown. Two-entry fixture verifies shared Actor focus. | All four common option modes passed; cantrips and missing innate uses were observed. Innate cantrips retain deterministic evidence. |
| Respect character source focus maximum exclusion and creature focus exceptions | `actorCasting.js`, `actorCastingCurrent.js`, option helper; character source selects value only, current maximum has transformed provenance, NPC optional source maximum remains distinct, familiar Actor current focus excluded. | Existing NPC source/current focus verified. Character/familiar current casting resources remain unverified. |
| Preserve specialized modes with explicit partial boundaries | Flexible, ritual, item and unknown modes report `unsupported_casting_mode`; ritual source uses closed scalar witnesses. No generic fallback invents supported semantics. | Deterministic unsupported-boundary coverage; specialized live behavior is not advertised. |
| Cover legacy preparation shapes, signature exceptions, innate cantrips and absent entries | Focused helper/reader/Python tests retain safe siblings, canonical unresolved identities and independent signature/auto-heighten fields. Signature configuration never invents feature entitlement or rank alternatives. | Special-case live fixtures are absent; these boundaries retain deterministic evidence and explicit limitations. |
| Read without casting, preparation, rolls or expenditure | Selected public document extraction; pure detached selectors; strict read-only MCP description/schema and DTO checks. Default/source requests do not request current serialization. | Actual discovery and full source/current fingerprints passed, including independent option verification. |
| Verify a representative live entry per supported mode before claiming complete current availability | No complete-availability claim: section stays partial and every option has `availability: not_evaluated`. Independent option verification must still prove the behavior actually advertised. | Complete availability remains unsupported; the conditional gate is not represented as passed. |

Test paths above are under `tests/js/` or `tests/`. The exact implemented record
contracts are [source joins](casting-fields.md), [contextual options](casting-options-contract.md)
and [current resources](casting-current-contract.md). Pinned rulebook/schema
evidence remains in [casting verification](casting-verification.md).

Computing signature alternatives or complete castability is not substituted for
the original requirement to preserve and distinguish recorded configuration.
Conversely, a passing resource comparison alone cannot prove the option joins.
That independent runtime check passed on October 25: 58 options, 663 unique
source witnesses and all four common modes on two existing NPCs. The
[runtime record](casting-options-contract.md#independent-live-verification--october-25)
reports exact counts, byte-limit recovery and unobserved cases. CORE-casting is
Complete for its declared reading contract; the advanced limitations above remain.
