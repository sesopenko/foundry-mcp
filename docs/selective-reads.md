# À la carte reads (WISH-003)

Introduced in version 2.0.0. Nine MCP tools publish version-two
typed input/output schemas. Pydantic 2.12.5 validates both directions at the
existing FastMCP boundary; no PydanticAI dependency or extra model call is used.
Other tools retain their existing contracts. Restart the Python service, refresh
the GM module and reconnect clients to refresh cached discovery when upgrading.

Version 2.1.0 also registers the new typed `get_party_members` tool
through this boundary. It has compact bounded membership entries, without a
`select` expansion, and does not change the nine migrated interfaces. See
[party contracts](party-tools.md).

Version 2.2.0: `read_actor` also accepts `wealth`, `bulk`, `wealth.items` and
`bulk.items`. Summaries are separate from inventory detail. Runtime values
report `available` or `potentially_missing`; see [metric contracts](character-inventory-metrics.md).

## Request only the needed details

Object reads default to identity, runtime and limitations. Collection reads
default to ten entries; journal text defaults to 2,000 UTF-16 code units.
JSON responses default to 8,000 UTF-8 bytes, explicitly adjustable to 48,000.
These are byte limits, not token guarantees. Optional fields are omitted when
unrequested; their absence does not mean an empty source value.

| Tool | Optional selection |
| --- | --- |
| `read_actor` | `select.details`: source, description, build, statistics, skills, strikes, abilities, spellcasting, inventory, state, effective; named refinements below |
| `read_item` | source, description, rules, relationships, effective; source groups below |
| `list_actor_items` | `select.context`, relationships, follow_up, limitations; existing type/name filters |
| `list_actor_compendiums` | context, follow_up, limitations; existing type/name filters |
| `get_actor_types` | selected actor_types, item_types, actor_sections, item_sections; all, limits, evidence |
| `get_journal_contents` | headings, categories, presentation, folder_path |
| `search_journals` | excerpts, counts, folder_path |
| `read_journal_page` | references, source_metadata, folder_path |
| `search_pdf_documents` | snippet, entries, context (requires entries) |

Actor statistics refinements are `statistics.attributes`, `armor_class`,
`hit_points`, `saves`, `perception`, `movement`, `senses`, `languages`, and `iwr`
(each prefixed `statistics.`). `spellcasting.prepared` selects recorded prepared
uses plus unresolved preparation diagnostics; `spellcasting.options` includes
other contextual options. `inventory.summary` selects identities, quantities
and containment. Item source refinements are `source.definition`, `activation`,
`attack`, `damage`, `defenses`, `casting`, `preparations`, `physical`, `traits`,
and `publication` (each prefixed `source.`). The published enums are authoritative.

```json
{"actor_uuid":"Actor.<id>","select":{"details":["statistics.armor_class"]}}
```

```json
{"actor_uuid":"Actor.<id>","select":{"details":["spellcasting.prepared"],"entry_uuids":["Actor.<id>.Item.<entry-id>"]},"limit":10}
```

```json
{"item_uuid":"Actor.<id>.Item.<item-id>","select":{"details":["source.attack","source.damage"],"evidence":true},"max_bytes":48000}
```

Selectors come from discovery, never invented names or paths. Actor reads accept
exactly one actor_uuid or token_uuid. Item reads retain the token_uuid for token
context. `item_uuids` narrows Actor inventory/build/abilities, `entry_uuids` narrows
casting, and `skill_names` narrows serialized skill keys. Scope diagnostics remain
visible. `sections` is an explicit coarse shorthand for details; combining it
with `select` is rejected. Unknown fields, enums, duplicate selections and invalid
bounds fail before a bridge read. No feature support is added for other systems;
existing Foundry14.369/PF2e8.6.1 runtime and permission guards remain in force.

## Response and continuation

Actor/Item reads return `contract_version:2`, canonical `identity`, `runtime`,
`revision`, `sections`, `entries`, `limitations`, and `pagination`. Entries have
`section`, response-local `key`, and `values`. Values contain `concept`, `value`,
and source/transformed/mixed/none `basis`; single-contributor values also retain
`present`. Missing source is `present:false` with null value, distinct from a
present null, zero or false. Exact text retains fragment offsets. `select.evidence`
adds the validated original raw/mapped/provenance record to each value.

Selection occurs before pagination. AC values/notes, individual skills, Strikes,
inventory Items, casting options, and source preparation positions are semantic
units; a limit is not a primitive-field count. Repeated prepared spell uses stay
separate positions with recorded expenditure and spell/entry identity. Neither
configuration nor expenditure establishes castability. Unsupported/partial section
reasons and essential source limitations are retained even without evidence.

Copy `pagination.next_cursor` (Actor/Item/list) or `next_cursor` (journal) with
every original input, including selection, limits and budget. Selection/bound
changes invalidate the cursor; a changed revision requires restarting and
discarding accumulated pages. Completion applies only to the requested scope.
One indivisible unit exceeding a budget returns ResponseTooLarge; increase the
budget or narrow details. PDF search retains offset continuation and its existing
2,000-candidate cap; indexing can shift offsets, so restart after library changes.

The browser privately supplies selected source witnesses and group sizes to
Python. Python reuses the existing record validators, independently checks the
selection/grouping/identity and recomputes the compact result. Only that validated
result crosses MCP. The internal packet is bounded to 60,000 bytes. This reduces
LLM output volume; broad snapshot extraction can still cost browser CPU.

## Migration and verification

This is a breaking response contract for the nine tools. Consumers reading
`records` must use `entries[].values[]`, optionally requesting evidence. Consumers
relying on former defaults must select their details explicitly. There is no
public legacy response switch. Old v1 live verification scripts which inspect
`records` need migration; use the v2 audit and fixture checks below for this
interface. Existing v1 proof tests continue to validate underlying source readers.

The bounded Python `scripts/selective-read-audit.py` replays the private planning
audit's selectors without printing game content. `scripts/selective-fixture-check.py`
uses the existing localhost `test` world, creates one marked temporary character,
checks current AC and two repeated prepared uses, verifies unchanged source/current
fingerprints, then cleans up the exact marker. It has a 30-call/180-second bound.
Run offline tests before this fixture check; it must never target production.

On October 28, 2026, the live test runtime was Foundry14.369/PF2e8.6.1 with
172 NPCs and no PCs/familiars. The original audit used 24 calls plus discovery;
the final v2 comparison used 38 plus discovery, including opt-in details and a
complete owned-Item traversal. All comparison calls succeeded.

| Sample | Before bytes | After bytes |
| --- | ---: | ---: |
| Capability default | 40,076 | 150 |
| Actor compendium default | 21,791 | 2,101 |
| Owned Item default | 23,036 | 2,056 |
| Casting entry default | 31,362 | 1,015 |
| Actor statistics section | 29,374 | 7,381 |
| Targeted NPC AC (one complete group) | — | 2,330 |
| Journal contents default | 12,587 | 2,780 |
| Journal page default | 15,488 | 3,065 |
| Journal search default | 21,518 | 3,607 |
| PDF search default | 12,919 | 3,377 |

Several defaults intentionally return less content or fewer entries. These are
first-response comparisons, not equal-content full-traversal savings. The complete
tool catalog decreased from 109,583 to 96,131 compact JSON bytes in that run.
All 44 owned Items were enumerated over five default pages totaling 9,319 bytes,
compared with the former complete 23,036-byte default page. This trades four
additional calls for smaller individual responses and 59.5% less returned JSON;
it is not evidence of lower total billed context across those calls. Explicit
expanded PDF search returned 12,940 bytes under its requested 48,000-byte budget.
The marked PC check passed in ten calls, with two separately paginated prepared
positions, unchanged source/current fingerprints and confirmed cleanup. Its AC
response was 2,395 bytes. Source builds were used; this is not verification of a
released version or billed/provider TPM. No private character data is committed.
