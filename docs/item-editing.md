# Editing PF2e Items from the GM sheet

Use `read_item` to inspect a weapon as the GM sees it, `get_item_field_options`
to find a legal choice, and `edit_item` to preview and apply that choice. The
sheet and authoring interface requires a ready GM on Foundry **14.370** with
PF2e **8.7.0**. Run matching server and module builds, reload the GM's Foundry
tab, and refresh the MCP client's tool discovery. Existing identity, `select`
and `sections` reads retain contract version 2 and their wider supported
runtime range. [Selective reads](selective-reads.md) · [Runtime compatibility](runtime-compatibility.md)

## Change the first property rune

1. Copy the canonical `item_uuid` from Item discovery, for example the
   `read_item` follow-up in `list_actor_items`. Keep the returned `token_uuid`
   on every call for an individual unlinked token. Inspect the returned
   `slot`, `source`, `display_label` and `editable` for the first slot.

   ```json
   {"item_uuid":"<canonical Item UUID>","sheet":{"fields":["material_and_runes.property_runes"]}}
   ```

2. Call `get_item_field_options` with the first slot's returned
   `options.arguments`. Add a query to narrow the list. Codes and localized
   labels support literal, case-insensitive substring matching. Use the
   returned `value` with `available: true`. A slot depends on the target's
   material, potency, variant rules and preceding slots. Supply
   `proposed_changes` to look up choices for a prospective configuration.

   ```json
   {"item_uuid":"<canonical Item UUID>","field":"material_and_runes.property_runes","slot":1,"query":"wounding"}
   ```

3. Call `edit_item` with the matching code. Preview is the default. Inspect
   `identity` and each labeled `changes` row before applying.

   ```json
   {"item_uuid":"<canonical Item UUID>","changes":{"material_and_runes":{"property_runes":[{"slot":1,"value":"wounding"}]}}}
   ```

4. Repeat the same call with `"mode":"apply"` and `"expected_revision"` set
   to the preview's `revision`. A successful change returns `applied` after
   the GM browser re-reads the stored fields. An already matching Item returns
   `unchanged`. Execute `next_call` to inspect the resulting form. To see a
   change in displayed damage dice, also select `damage.base` after changing
   `material_and_runes.striking_rune`.

## Read the form

`sheet={}` returns applicable controls in GM sheet order, omitting long
descriptions. Select `sheet.groups` or individual qualified `sheet.fields`
to narrow the response or include prose. When both filters are present, every
field must belong to a selected group. Compound fields also accept leaf
selectors, such as `damage.base.type`. Choose one of `sheet`, `select` or
`sections` per request. Use a GM-private client for source and identified text.

| Sheet group | Qualified fields begin with the group ID |
| --- | --- |
| `header` | `image`, `name`, `display_name`, `level`, `rarity`, `traits` |
| `weapon_summary` | `quantity`, `hands`, `bulk`, `size`, `price` |
| `details` | `category`, `group`, `base`, `range` |
| `material_and_runes` | `precious_material`, `potency_rune`, `striking_rune`, `property_runes`, `specific_magic_weapon` |
| `damage` | `base`, `splash`, `persistent` |
| `other_tags` | `tags` |
| `publication` | `title`, `authors`, `license`, `remaster` |
| `description` | `text` |
| `mystification` | `identification_status`, `unidentified_name`, `unidentified_description` |

Contract version 3 returns `identity`, `runtime`, `revision`,
`unsupported_groups`, `records` and `pagination`. Each control has its field
and group IDs and labels. `present` distinguishes missing source data from a
stored null, zero, false or empty string. `display_basis` identifies the GM's
stored input, transformed Item data, public document name or an unavailable
display witness. Read `reason` for a locked control and `display_reason` for
a missing display. PF2e can adjust the title, price, level, traits or damage
dice independently of their source inputs.

Property slots have one-based ordinals, an occupied/free/derived `slot_state`
and independent editability. The specific-weapon checkbox includes its stored
`specific_baseline`. A finite-choice control supplies `options`, and a compound
control can supply `choice_fields` for its leaves. Use currency denominations,
numbers, booleans or prose directly where the input schema specifies them.
An empty filtered menu means the query matched no choices on that target.

Reads and option lookups default to 10 records and 8,000 compact JSON bytes per
page. The maxima are 100 records and 48,000 bytes. Pass
`pagination.next_cursor` back as `cursor` with every original argument until
`pagination.complete`. If inputs, locale or revision change, restart the
traversal. For long text, reassemble each field's `source` and `display`
fragments independently using their `text` and `display_text` UTF-16 offsets.

## Author unidentified treasure

Weapons, armor, shields, equipment, consumables, ammunition, backpacks, books
and treasure share source name, true description, identification status and
alternate name/description editing. Absolute quantity is 1–999,999 on the
eight types with editable quantity. The complete Details form applies to weapons.

```json
{
  "item_uuid": "<canonical Item UUID>",
  "changes": {
    "mystification": {
      "unidentified_name": "Notched Knife",
      "unidentified_description": "A green stain circles the pin nearest the hilt."
    }
  }
}
```

Preview and apply the clue independently of identification status. When the
alternate record is missing or null, supply both strings to initialize it
with the schema's empty image. Subsequent text edits preserve the existing
alternate image. An empty alternate description clears the override. Set
`identification_status` to `unidentified` to show the clues to players or
`identified` to reveal the true presentation. Names allow 256 Unicode code
points and descriptions allow 2,000. Prose is HTML-escaped on write and inline
rolls and document-link notation are rejected.

## Changes, permissions and recovery

- Standalone world Items and direct inventory members of supported character,
  NPC, familiar, world-party or loot Actors require GM update permission. A
  linked token shares its Actor's inventory. Use its canonical Actor-owned
  Item UUID without the token selector. Compendiums supply read-only references.
- Submit just the changed leaves. Price accepts `pp`, `gp`, `sp` and `cp`
  and preserves its per-quantity basis. Artwork takes the image selector
  returned by `browse_journal_images`. Rules, flags, embedded arrays and raw
  document paths have no writable input. [Control sources and choice domains](item-sheet-controls.md)
- Submit dependent changes together. Reducing rune capacity requires explicit
  clears for affected occupied slots. A slot clear uses `{"slot":2,"value":null}`.
  Enabling Specific Magic Weapon snapshots the resulting source material and
  runes. While enabled, property slots are locked and material choices depend
  on the existing material type. Disabling the checkbox clears the baseline.
- Persistent damage takes an amount, faces and damage type. Use null faces
  for flat damage or `"persistent":null` to clear the record. A Wounding rune
  can coexist with an empty persistent-damage record. OGL and ORC are the
  publication license choices, and Remaster is an independent boolean.
- An invalid combination rejects the whole proposal before dispatch. Preview
  and apply receipts are limited to 8,000 bytes and mark prose excerpts. Split
  oversized proposals into independently valid changes. On `ContentChanged`,
  read the target and preview again. The bridge serializes its own writes per
  owner, rechecks the source and current choices, and dispatches one Foundry
  update with normal hooks. An external Foundry client can still write after
  the final check. On `WriteOutcomeUnknown`, read the original Item and
  selected fields before deciding whether a new preview is needed.

## Verification

The development workflow uses marked, temporary Items, Actors, users, journals
and scenes in the migrated localhost `test` world. The GM check compares
stored and adjusted values to rendered weapon controls before and after reload.
The player check opens the loot inventory as an ordinary player before and
after identification. The chapter rehearsal reads room evidence, paginates
inventories, checks compendium definitions, and verifies each edit before
writing the five-column GM report under the ignored `.local/` directory.
[Measured calls, payloads and test results](item-editing-tracker.md)
