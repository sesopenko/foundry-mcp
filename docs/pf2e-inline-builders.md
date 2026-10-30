# Typed PF2e inline builders

Implemented in the source tree after v2.2.0 (WISH-008); not yet released.
`create_pf2e_inline_roll`, `create_pf2e_inline_check` and
`create_pf2e_inline_embed` construct insertable notation from structured
mechanics. Every invocation requires the existing authenticated, ready GM
browser on **Foundry 14.369 / PF2e 8.6.1**. Other systems and versions fail
explicitly. These tools never send chat, write documents, roll dice or apply
effects. They do not interpret prose or choose mechanics for the caller.

Each success has one MCP text block containing only notation and matching
structured output:

```json
{
  "text": "@Check[reflex|dc:20|basic]",
  "runtime": {
    "core_version": "14.369",
    "system_id": "pf2e",
    "system_version": "8.6.1"
  }
}
```

There is no `select`, pagination, detail expansion or hidden continuation.
Dedicated Pydantic models publish nested input/output schemas, defaults,
enums, a roll discriminator and examples through FastMCP discovery. Unknown
fields, coercible but incorrect primitive types and conflicting combinations
are rejected before RPC. Response source and runtime are validated before
delivery. Refresh client discovery after updating both server and module.

## Roll tool

The `roll` field contains one discriminated object. For example:

```json
{
  "roll": {
    "kind": "damage",
    "damage": [
      {"type": "fire", "amount": {"dice": [{"count": 2, "faces": 6}], "modifier": 3}}
    ],
    "label": "Flaming burst"
  }
}
```

This emits `@Damage[(2d6+3)[fire]]{Flaming burst}`. Each damage instance
has a base `amount`, type, optional `persistent` flag and optional `precision`
and `splash` amounts of that same type. Precision/splash components are grouped
inside the instance; persistent is mutually exclusive with those components.
Separate instances are comma-separated. Damage permits an optional `options`
list and label; visibility and flavor fields are rejected.

`kind: "non_damage"` takes `amount`, optional label/flavor and `visibility`:
`public` (default `/r`), `gm` (`/gmr`), `blind` (`/br`) or `self` (`/sr`).
This controls the eventual roll's audience, independently of its containing
message. An amount with no dice is a constant, including zero or a negative
integer. Multiple dice terms are additive; modifiers retain their signs.
No formula strings, advanced expressions or data references are accepted.

## Check tool

`statistic` accepts one standard save, `perception`, `flat`, a full standard
skill slug, or a slug ending in `-lore`. Lore existence is not verified.
Custom statistics and multiple buttons per call are deferred.

Choose at most one of `dc` (integer 1–10,000), `against` (named opposing DC)
or `defense` (named target defense). Allowed named statistics are published
as enums. `roller_role` requires `against`; matching system defaults are
omitted (target for saves, origin otherwise). `basic` requires a save.
Optional `show_dc`, `adjustment`, `immutable`, `name`, `traits`, `options`,
`override_traits` and `label` follow the upstream guide's ordering; optional
defaults are omitted. For example:

```json
{"statistic": "reflex", "against": "class-spell", "basic": true}
```

This produces `@Check[reflex|against:class-spell|basic]`. It does not establish
that a future origin has a class/spell DC or that a target exists. The rolling
wiki describes default DC visibility as owner; the pinned implementation
chooses visibility from Actor ownership/metagame settings when `showDC` is
omitted. Set `show_dc` explicitly when that distinction matters. Actor/Item
traits and modifiers can alter eventual checks and damage. A `secret` trait
can request an eventual blind check; no check occurs during generation.

## Embed tool

Use `list_actor_compendiums` and `search_compendium_actors` on Item packs to
obtain a canonical `Compendium.package.pack.Item.<16-character-ID>` UUID.
`item_uuid` accepts that identity, never a name, world Item, local ID or anchor.
The browser checks pack and Item OBSERVER access, resolves with public async
`fromUuid`, verifies canonical identity and rechecks runtime/access after awaits.
It returns no document body. `suppress_hr: true` adds `hr=false`; `inline` is
always emitted. Missing and denied documents are distinct errors.

## Bounds and errors

- 16 damage instances; 16 additive dice terms per amount; 1–100 dice per term.
- Standard faces: 4, 6, 8, 10, 12, 20, 100; damage restricts faces to 4–12.
- Integer modifiers/adjustments within ±10,000; 32 traits/options per list.
- Label, flavor and name: 1–200 characters. Inline/HTML delimiters, `&`,
  backslashes and control characters are rejected, not escaped. Traits/options
  use bounded lowercase alphanumeric slugs with hyphens/colon namespaces.
- Generated notation: 8,000 UTF-8 bytes maximum; reject rather than truncate.

`InvalidRequest` identifies fields to correct. `BridgeUnavailable`/`NotReady`
require reconnecting/waiting for the ready GM. `UnsupportedSystem` and
`UnsupportedVersion` require the verified pairing. `PermissionDenied` requires
authorized access. `DocumentNotFound` requires rediscovering the Item UUID;
`DocumentAccessFailed` requires checking pack availability. `InvalidFormula`
means public `Roll.validate` rejected generated arithmetic, without evaluation.
`SourceTooLarge` requires fewer terms/options. `InvalidFoundryResponse` requires
checking matched server/module code and typed output.

## API evidence and verification

Syntax follows the rolling upstream [Style Guide](https://github.com/foundryvtt/pf2e/wiki/Style-Guide),
read through `pf2e-wiki` Grounded Docs on 2026-10-29. Versioned damage vocabulary
comes from [PF2e8.6.1 damage values](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/system/damage/values.ts).
The pinned [check parser](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/system/text-editor.ts),
[creature](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/creature/document.ts)
and [character](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/character/document.ts)
definitions explain supported named statistics; production does not invoke
those parser internals or Actor statistic methods.

Grounded Docs `foundry-vtt@14` confirms public
[`Roll.validate`](https://foundryvtt.com/api/v14/classes/foundry.dice.Roll.html#validate),
[`fromUuid`](https://foundryvtt.com/api/v14/functions/foundry.utils.fromUuid.html),
[document identity/access](https://foundryvtt.com/api/v14/classes/foundry.documents.Item.html)
and [`TextEditor.implementation.enrichHTML`](https://foundryvtt.com/api/v14/classes/foundry.applications.ux.TextEditor.html).
Only the verifier calls detached enrichment; generation never enriches or
evaluates source. Runtime checks admit the exact audited versions only.

The deterministic [live harness](../scripts/inline-live-check.py) is capped at
30 MCP calls / 180 seconds. On 2026-10-29 it completed **14 calls**, including
discovery, 11 builder invocations and two read-only exploration calls. All 11
sources enriched in each of three detached contexts: standalone chat content,
an existing journal page and an existing compendium Item description. Message,
journal and world Item counts were unchanged. No messages/documents were
created, no buttons clicked, and no effects or roll evaluation requested.
The browser console contained one core `foundry.mjs` error with no inline-module
stack; this remains an unclassified runtime diagnostic, not a clean-console claim.

Detached enrichment proves source acceptance, not UI placement or eventual
Actor/target automation. Live destination listeners, future document access,
owner-specific modifiers, targeting and future versions remain unverified.

Two earlier 14-call verifier runs stopped on the same overly narrow markup
assertion: core returns a `document-embed` custom element for Item embeds.
A focused regression reproduced that failure and passed after the verifier
recognized the correct element. The accepted run above is separate from those
diagnostic runs (42 MCP calls across all three runs). Offline acceptance:
`./scripts/test.sh` passed 588 Python tests (one existing skip) and 623
JavaScript tests.

| Measurement (compact UTF-8 JSON) | Bytes |
| --- | ---: |
| Baseline production discovery, 22 tools | 107,789 |
| Production discovery after change, 25 tools | 124,545 |
| Discovery increase | 16,756 |
| Live development catalog (also includes execution tool), 26 tools | 125,037 |
| Non-damage roll responses, text plus structured output | 202–234 |
| Damage responses | 256–378 |
| Check responses | 234–482 |
| Embed responses | 306–324 |

All responses completed in one call. There are no pagination or equal-content
savings claims for these new tools. Bytes include both notation representations;
they are not billed tokens. Provider token usage was not measured. Focused
Python/JavaScript tests cover exact source, constants, signed/multiple dice,
damage categories, visibility, check combinations, schemas, strict inputs,
byte limits, runtime/bridge/access failures and output validation. Packaging
includes `inline.js` and the container smoke catalog includes all three tools.
