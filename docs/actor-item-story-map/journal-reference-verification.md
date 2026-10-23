# Journal reference verification — October 22, 2026

CORE-journal now separates exact journal source reading from explicit selected
Actor/Item resolution. The new `resolve_journal_reference` MCP tool calls the
`resolveJournalReference` RPC and returns canonical identity and next-reader
arguments only after origin and target permission checks.

## Public API and boundaries

Grounded Docs verified official v14
[async fromUuid](https://foundryvtt.com/api/v14/functions/foundry.utils.fromUuid.html)
with `relative: Document`, returning a Document or null asynchronously. No
undocumented strict option is passed to this async API. Existing legacy journal
reference fields retain their earlier behavior. Public document permissions,
parent/compendium and Actor.token context reuse the audited Actor/Item boundary.
PF2e-specific target admission is constrained to core14.369/PF2e8.6.1, without
interpreting source or effective statistics. Ordinary journal reading stays
independent of that target-reader admission.

## Deterministic verification

Existing journal, bridge and Actor reader tests pass alongside new resolver
tests. Cases cover lazy metadata without async target hydration; relative and
absolute targets; compendium and embedded Item identities; token and synthetic
contexts; duplicate labels/targets; anchors including an empty fragment; exact
HTML/Markdown membership; split, truncated and over20-reference metadata;
missing/denied/unsupported/outside-scope/unverified targets; source/permission
changes across awaits; unchanged exact source and cursors; and no target source,
import, write, enrichment or roll execution. Python validates singleton shape,
echoed origin/target/source, canonical typed next calls, named identity, response
bytes and actual MCP discovery schemas/read-only annotations.

Plain names remain bounded discovery candidates using search_actors or selected
pack search, never automatic identity resolution. Source metadata completeness
is fragment-scoped; split notation must be reconstructed from exact fragments.

## Existing development runtime

Foundry14.369/PF2e8.6.1, authenticated GM in the existing development world.
Public journal search selected The Violated Grave, an existing adventure page.
Its actual notation linked a world NPC and compendium deity Items. The reusable
live runner verified the new tool's discovery description/schema, followed one
Actor and one Item resolve_next_call, read both returned identities, and followed
the Actor to an actual owned Item. Journal content and revision matched before
and after. No fixtures, imports or game writes were created. Browser console:
zero errors. Full live regression checks passed.

Live relative, denied, stale and synthetic journal targets were not manufactured;
their deterministic coverage is separate from the observed world/pack cases.
Other system/version target support and live v13 journal-reference resolution
remain unverified. This does not claim complete Actor statistics or acquisition.

Final regression suites passed:322 Python tests (one skipped),396 JavaScript
tests. Story-map dependency/status validation and whitespace checks passed.
