# PF2e Item editing work tracker

**Authoritative plan:** [PF2e Item editing and the weapon Details sheet](prompts/item-editing-plan.md). Read the entire plan before starting, after compaction and when moving to a different environment. Carry both files in the branch. Task scope, acceptance and the Mermaid dependency diagram live in the plan.

**P0–P17 complete.** The existing test world migrated without backup as authorized. After first GM login the authenticated bridge reported Foundry 14.370, PF2e/world system 8.7.0 and world schema 0.961, the pinned release's migration target. The final dedicated GM tab reported ready with zero console errors.

| ID | Points | Depends on | Status | Evidence or next action |
| --- | ---: | --- | --- | --- |
| P0 | 1 | — | Done | Plan and tracker saved in this checkout. Include both paths in handoffs. |
| P1 | 3 | P0 | Done, offline | One in-memory FastMCP tools/list, 42 tools, 264,631 compact bytes. read_item 13,168 bytes, input 2,222 and output 5,995. Synthetic runed weapon on actual JS handlers: identity 1 call/730 bytes, damage 1/1,236, damage evidence 1/3,635, complete description 4/7,453. All traversals complete. Limit 40 RPCs and 60 seconds per scenario suite. Reproduce with test_item_editing.py. |
| P2 | 5 | P1 | Done | [Control matrix and public API evidence](item-sheet-controls.md). P14 verifies the rendered form. |
| P3 | 5 | P2 | Implemented | Typed contracts in item_sheet.py. FastMCP discovery and pre-RPC unknown/nested key and selector rejection pass in test_item_editing.py. P13 rechecks integrated output. |
| P4 | 5 | P3 | Offline passed | item-sheet-target.test.js covers runtime, permissions, direct membership, pack, party/loot, synthetic and linked token selectors. |
| P5 | 5 | P3 | Offline passed | item-sheet-options.test.js covers world choices, localized query, prospective slots, null, empty, pagination and stale cursors. |
| P6 | 5 | P4, P5 | Offline passed | item-sheet-read.test.js checks all controls and distinct display/source witnesses. |
| P7 | 5 | P4, P5 | Offline passed | item-sheet-read.test.js exercises absent/occupied/free slots, damage, alternate fields and complete multibyte prose reconstruction. |
| P8 | 5 | P4, P5 | Offline passed | item-sheet-proposal.test.js verifies all nine physical types, artwork membership, usage, price basis, prose escaping and alternate image preservation. |
| P9 | 5 | P4, P5 | Offline passed | Classification/range/tag constraints, both licenses, false Remaster and unknown historical data covered in proposal tests. |
| P10 | 8 | P4, P5 | Offline passed | Proposal tests cover prospective capacity, explicit clears, ABP, wrong-family runes, grades and specific snapshot on/off. |
| P11 | 5 | P4, P5 | Offline passed | Damage proposal tests cover flat/dice/cleared persistent, 0 splash, bleed restrictions, source modifier and independent rune preservation. |
| P12 | 8 | P6–P11 | Passed | Browser tests count updates and exercise stale/concurrent proposals, no-ops, oversized receipts and uncertain readback. Actual MCP tests cover a lost acknowledgment, socket disconnect, malformed reply and mismatched readback fields. |
| P13 | 5 | P12 | Passed | Full suite ran 725 Python tests (one skip) and 755 JavaScript tests. The packaged module includes the new scripts. Authenticated transport and payload measurements appear below. |
| P14 | 5 | P13, GM bridge | Passed | `item-edit-gm` used 90 calls to compare 32 controls on standalone and loot-owned weapons. Verified six menu domains and editability, specific baseline through a fundamental upgrade, source siblings, reload and exact cleanup. |
| P15 | 5 | P13, GM bridge | Passed | `item-edit-player` used 28 calls. The unlinked loot copy survived reload. Base and sibling retained their original values. The linked alias supplied the shared selector. An ordinary player opened the marked inventory, expanded the Item, and saw both the alternate and subsequently revealed presentation. Marker cleanup passed. |
| P16 | 5 | P14, P15 | Passed | 106 calls across three rooms, three inventories and nine inventory pages. Two compendium definitions supplied reference evidence. Of 23 unique Items, 20 received verified edits and three were mundane. Eight report rows retain both Armory and Gallery. The Sealed stair ledger named no custodian. The 20-row, five-column GM report was generated after exact fixture cleanup with file mode 0600. Token roles are checked by base Actor and link state with a regression test for reordered creation results. |
| P17 | 3 | P16 | Done | [Item editing guide](item-editing.md), selective-reader compatibility, public README and Docker Hub overview updated. Reviewed the rendered README section, checked documentation links, packaged the module and verified the final private GM report. |

## MCP measurements

Values are compact UTF-8 JSON bytes across complete calls. On the same live
Dogslicer reference, the legacy workflows retained identical call counts and
payload sizes before and after implementation.

| Live legacy selection | Calls | Bytes |
| --- | ---: | ---: |
| Default identity | 1 | 820 |
| Source damage | 1 | 1,330 |
| Source damage with evidence | 1 | 4,133 |
| Complete source | 3 | 8,682 |
| Complete description | 2 | 2,589 |

On authenticated development HTTP, the complete catalog grew from 43 tools
and 265,169 bytes to 45 tools and 289,849 bytes. The synthetic catalog grew
from 42 tools and 264,631 bytes to 44 tools and 289,311 bytes. In both
transports the published `read_item` grew from 13,168 to 15,416 bytes.
Its final input schema is 2,841 bytes and output schema 10,694 bytes.

| Synthetic weapon workflow | Calls | Bytes |
| --- | ---: | ---: |
| Default sheet | 3 | 11,005 |
| First property rune field | 1 | 938 |
| All controls, including long prose | 4 | 18,666 |
| Wounding option query | 1 | 594 |
| Complete property menu, 89 runes and clear | 9 | 12,272 |
| Preview, apply and readback | 3 | 2,127 |

Reproduce the synthetic measurements with `tests/test_item_editing.py`. The
four fixed `./scripts/actor-tools.sh item-edit-*` commands run against the
existing migrated localhost world. Each run allows 140 tool calls and 240
seconds. The chapter report is a private, owner-readable local file. This
evidence qualifies the new form and editing on Foundry 14.370/PF2e 8.7.0.
