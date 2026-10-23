# Feat verification — October 22, 2026

This ledger records rules, pinned schema and exploratory source observations for
[ITEM-feat](stories/ITEM-feat.md). It does not establish that the new type reader
has been live verified; its implementation verification is a separate step.

## Rules actually read

`list_pdf_documents` and four `read_pdf_pages` calls read Player Core Remaster,
revision/SHA-256 `9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22`.
Printed pages 249, 253, 41 and 91 were physical pages 250, 254, 42 and 92.
Each returned complete text with null continuation. Extraction warns that
reading order and table structure are unverified; conclusions use prose.

| Printed page | Evidence and reader consequence |
| --- | --- |
| 249 | General feats require satisfying prerequisites; skill feats form the general-feat subcategory with the skill trait. A category/trait definition does not establish eligibility or acquisition. |
| 253 | Battle Medicine is a one-action level1 feat with Medicine training prerequisite. Its prose requires holding/wearing a healer's toolkit, uses Treat Wounds DC/healing rules, leaves wounded intact and gives target-specific immunity for one day, separately from Treat Wounds. Structured activation/prerequisites alone omit material rules. Preserve exact bounded description without executing its action/link notation. |
| 41 | Ancestry special abilities are ancestry benefits; ancestry feats are level-bounded choices with possible prerequisites. Heritage and ancestry feats are distinct. An offered definition is not evidence of a selected/acquired document. |
| 91 | Class entries describe class features and future advancement as well as other benefits. Class-feature definitions and future progression are not current acquired character benefits. |

## Pinned schema and persisted relationship allowlist

The research checkout HEAD is PF2e8.6.1 commit
`28d9d156f252d084371d994dc359509b49eadf18`.
[feat/data.ts](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/feat/data.ts)
defines category, nominal level and optional nullable taken level, activation,
prerequisite strings, nullable location, frequency, limits, selfEffect and
subfeatures. Subfeatures include key-attribute options, language slots/grants,
proficiency rank/nullable attribute, senses with nullable range and conditional
special clauses, and suppressed-feature UUID claims. These are source
configuration, not applied statistics, active suppression or acquired benefits.

[base/data/system.ts](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/system.ts#L70-L104)
separately declares persisted `ItemSourceFlagsPF2e`. The proposed bounded
allowlist is:

| Source path | Declared contract and safe meaning |
| --- | --- |
| `flags.pf2e.itemGrants.<key>.id` | String Item ID claimed as granted; not a UUID or a name. |
| `flags.pf2e.itemGrants.<key>.onDelete` | Optional cascade/detach/restrict source policy; report only, never perform it. |
| `flags.pf2e.itemGrants.<key>.nested` | Optional boolean/null presentation claim; not ownership evidence. |
| `flags.pf2e.grantedBy` | Optional nullable source object with id and optional onDelete as above; preserve null versus absent. |

Resolve claimed IDs only against the actual owning Actor's readable Items,
retain selected token context and canonical target identity, and distinguish
missing/unowned/denied targets. A reciprocal flag, when examined, is additional
source evidence; an existing target alone does not prove reciprocal consistency,
rule evaluation, active benefit or eligibility. Do not fabricate UUIDs by
combining arbitrary owner/ID strings. The explanatory upstream GrantItem
implementation writes reciprocal embedded IDs, but its private method is not an
external API and must never be called by the reader.

`rulesSelections` is declared as an arbitrary keyed string/number/object record.
That declaration does not authorize an unrestricted object/flag dump. Exclude it
from default extraction; a future selection reader needs a narrower dedicated
contract. Arbitrary flags and `system.rules` execution remain excluded. A
GrantItem rule in a definition is not a persisted acquired grant relationship.

## Read-only runtime observations

Existing authenticated development GM browser: Foundry14.369/PF2e8.6.1.
Public pack `getIndex` selected three readable Item packs: Feats6366 entries,
Ancestry Features55, Class Features881. Only four selected definitions were
hydrated through public async `foundry.utils.fromUuid`, checked with
`testUserPermission`, and read with `toObject(true)`. Public core contracts are
inherited from [shared evidence](evidence.md#public-foundry-api). Selectors and
reproducible source probe remain in ignored `.local/feat-selector.js`.

| Definition | Observed source |
| --- | --- |
| Battle Medicine | feat/category skill; nominal1; action/1; training prerequisite; toolkit/Treat Wounds/immunity prose retained in source; empty rule list. |
| Awakened Mind | feat/category ancestryfeature; nominal1; passive/null action count; empty rule list. |
| Quick-Tempered | feat/category classfeature; nominal1; passive/null; a GrantItem rule definition but empty flags. No acquired grant was inferred. |
| Versatile Legend | feat/category classfeature; nominal19; passive/null; source proficiency ranks advanced3, fighter3, martial4, simple4, unarmed4 with null attributes. This high-level definition is not a currently acquired feature. |

All four had location null, onlyLevel1 false, maxTakable1, empty source flags,
empty senses and suppressed-feature arrays. Battle Medicine, Awakened Mind and
Quick-Tempered had empty proficiency records. Their serialized snapshots omitted
frequency, selfEffect, taken level, keyOptions and languages. A separate Battle
Medicine probe established those keys were own properties with `undefined`
values, rather than persisted nulls; JSON omits them. Do not invent prepared
null/default values to fill these gaps. These observations do not establish the
shape of every feat in the packs.

A bounded world audit inspected actual readable Items on172 in-scope world
Actors. It found zero feat Items, nonempty itemGrants, grantedBy or nonempty
rulesSelections. Thus there is no representative existing embedded feat/grant
fixture for live reciprocal relationship verification. No world fixture was
created to fill that gap. This audit did not import, create, update, roll,
activate, execute rule elements, enrich descriptions or send chat. It did not
use bulk compendium document loading.

## Remaining verification limits

The observations verify source shapes only, not the new MCP reader. Live
embedded/token feat context, grant IDs/reciprocity, optional/null frequency,
selfEffect, selection objects, sense branches, suppression references and
world feat fixtures remain unverified here. Deterministic coverage should keep
those branches and unsupported/non-PF2e behavior explicit. No v13, future PF2e
version, eligibility, advancement, automatic acquisition or effective character
statistics are established.

## Source reader live checkpoint

After loading the source reader, a fresh authenticated MCP client verified the
four selected definitions with limit7 pagination:19 pages and124 records.
Independent public-source expectations matched raw paths/presence/values,
category mappings, exact complete description hashes and unchanged source
fingerprints. The full existing live regression check passed, and the dedicated
GM browser had zero console errors. No grant or selection relationship was read
or inferred. Full offline suites passed:307 Python tests (one skipped),377
JavaScript tests. This establishes selected-source support, not story completion.
