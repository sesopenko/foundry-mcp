# Character wealth and Bulk

Introduced in v2.2.0. Released v2.1.0 does not offer
these selections. Both server and Foundry module must be updated together;
refresh the GM browser and reconnect LibreChat to refresh MCP discovery.

Use `get_party_members` to select the official party, then read its resolved
character members. Party stash is excluded. For each character:

```json
{"actor_uuid":"Actor.<id>","select":{"details":["wealth","bulk"]}}
```

These selections are supported for PF2e characters on Foundry 14.369/PF2e 8.6.1.
NPC/familiar metric sections are explicitly unsupported. Other systems or
versions fail the existing actionable admission checks. Default reads still
return identity only. Coarse `sections: ["wealth", "bulk"]` means summaries.

| Section | Concept | Meaning/unit |
| --- | --- | --- |
| wealth | total_currency | Current system currency value, copper pieces |
| wealth | total_wealth | Full current owned value including currency, copper pieces |
| wealth | non_currency_value | Wealth minus currency when both are available and consistent |
| bulk | carried_bulk | Current aggregate, light units (10 light = 1 Bulk) |
| bulk | encumbered_after | System threshold, whole Bulk |
| bulk | maximum_bulk | System maximum, whole Bulk |
| bulk | is_encumbered, is_over_max | System-reported booleans |
| bulk | until_encumbered | Additional light units to cross the encumbrance threshold; zero if already crossed |

100 cp equals 1 gp. Valuation is the GM-visible current system calculation,
not resale proceeds. Aggregate Bulk delegates stacking, container, size and
character adjustments to PF2e. PF2e compares **normal Bulk > threshold**:
5 Bulk 9 light at threshold 5 requires one additional light unit to cross.
The gap is computed only when the carried value, threshold and system flag agree.

## Availability and defensive access

Each runtime value has `basis: "runtime"` and explicit availability:

```json
{"concept":"total_currency","value":0,"basis":"runtime","availability":"available","unit":"cp"}
```

```json
{"concept":"total_wealth","value":null,"basis":"runtime","availability":"potentially_missing","reason":"getter_failed","unit":"cp"}
```

Reasons are `missing_api`, `invalid_value`, `getter_failed`, `items_denied`,
`item_limit`, `dependency_unavailable`, or `inconsistent_value`. Unknown is
never zero or false. Each getter is guarded independently; one failure does
not erase unrelated values. Thrown exception messages, live objects and
nonfinite numbers are never returned. Affected sections are `partial` with
`potentially_missing`; typed responses and independent browser proof validation
reject invalid values, units, reasons and misleading complete statuses.

Owner-wide calculations require every owned Item to be readable and at most
12,000 owned Items. Denial withholds totals before invoking inventory getters.
Permission/version/resolution failures still use the existing actionable tool
errors; they are not silently converted into successful empty responses.

## Optional details and comparisons

Select `wealth.items` or `bulk.items` explicitly for `item_count` and named
actual owned physical Item groups. Each has `item_uuid`, `item_name`, `quantity`,
and either `asset_value` (cp) or `item_bulk` (light units). UUIDs are canonical
`read_item` selectors; entry keys are grouping identifiers. Names over the bound
are potentially missing, not unbounded. Item UUID filters restrict details,
never aggregate totals. Empty readable inventory returns available count zero.
Follow `read_item` or `inventory.summary` for source/container context.

Per-item Bulk is **not additive**. Attached subitems are already handled by
PF2e valuation and are not invented as separate owned documents. These details
are context, not a locally reconstructed explanation of all system modifiers.

Selection happens before pagination. Defaults remain ten entries and 8,000 UTF-8
JSON bytes; maximums are 100 and 48,000. Each summary and each item group is
atomic. Return `pagination.next_cursor` unchanged with original selections and
bounds. Revisions cover selected runtime values; `ContentChanged` requires
discarding prior pages and restarting. Character reads are sequential, not an
atomic party snapshot; recheck roster membership after a group investigation.

For each-PC worth or richest, compare available `total_wealth`, preserving ties.
For spread, report sorted values, min/max/range and mean/median. For near
encumbrance, list already encumbered characters first, then increasing available
`until_encumbered`. Name excluded unknowns and incomplete membership; never
claim a complete-party ranking from partial data or page inventories repeatedly
to guess a missing aggregate. These workflows are in actual MCP discovery.

## Scoped API exception

On October 28, 2026 the user authorized bypassing the unresolved external API
evidence requirement for wealth/Bulk, conditional on defensive programming and
potentially missing fields. This does not establish public API support or relax
the rule for unrelated code. No monkey-patching, preparation, sheets or DOM
access is used. The narrow adapter is `actorInventoryMetrics.js`.

Pinned PF2e implementation dependencies:
[inventory.currency/totalWealth](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/inventory/index.ts),
[InventoryBulk](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/inventory/bulk.ts),
[physical Item quantity/assetValue/bulk](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/physical/document.ts),
[Bulk normal/light](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/physical/bulk.ts),
and [Coins copperValue](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/physical/coins.ts).
These are runtime-derived values, not source document paths. Future versions
remain unverified; field detection does not promise compatibility.

## Verification, October 28

Full offline runner passed: 566 Python tests (one skipped) and 616 JavaScript
tests. Focused tests cover independent thrown/missing/invalid getters, preserved
zero/false, permissions, unsupported systems/types, strict threshold crossing,
stale pagination, item filters, actual MCP discovery/calls and typed validation.
Packaging checks include the new module helper.

`scripts/inventory-metrics-live-check.py` passed against the existing localhost
test world: 18 tool calls plus one discovery, bounded to 30 calls/180 seconds
plus reserved cleanup. Two marked characters and one party were removed with
exact-marker cleanup. Current getters matched MCP values; the populated PC had
10 gp currency and 16 gp total wealth, the other had genuine zeroes. Source
fingerprints remained unchanged by reads. No production documents were touched.

| Scenario | Calls | Compact JSON bytes | Complete |
| --- | ---: | ---: | --- |
| Populated character wealth + Bulk | 1 | 2,543 | yes |
| Empty character wealth + Bulk | 1 | 2,535 | yes |
| Default identity | 1 | 1,115 | yes |
| Summary with evidence | 1 | 5,497 | yes |
| Two-item details, both sections | 1 | 3,776 | yes |
| Same item details, one group per page | 6 | 12,788 | yes |

Smaller pages increase total bytes; this is not an equal-content savings claim.
Follow-up disclaimer fix: character-source boilerplate now appears only when
`source` is selected. A fresh live run passed with exact-marker cleanup and
unchanged sources: populated/empty summaries fell to 2,026/2,018 bytes, default
identity to 599, evidence to 4,980, item details to 3,259 and the six-page
workflow to 9,686. The summary saves 517 bytes (20.3%) without dropping values
or availability information. Regression tests retain the disclaimer for source
and combined source/wealth requests, and omit it for identity/wealth/Bulk.
The pre-change catalog was 104,170 bytes/23 tools; initial post-change catalog
was 108,281 bytes/23 tools. Metrics were absent before, so there is no equivalent
previous summary response. Bytes are not measured provider tokens.

Live verification covers world characters and basic currency/equipment, not
every container/size/attachment/magic-item combination or synthetic-token metric
case. The implementation delegates those calculations to the same guarded
system getters. Throwing/malformed-getter cases are deterministic tests, not
runtime monkey-patching. No claim of a fresh LLM or production LibreChat run.
