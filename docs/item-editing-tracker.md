# PF2e Item editing work tracker

**Authoritative plan:** [PF2e Item editing and the weapon Details sheet](prompts/item-editing-plan.md). Read the entire plan before starting, after compaction and when moving to a different environment. Carry both files in the branch. Task scope, acceptance and the Mermaid dependency diagram live in the plan.

**Resume at P1.** P0 saves the plan and tracker. Implementation and fixture work have yet to start. Planning confirmed that the local MCP server and development Foundry container are healthy. The GM bridge had no connected client. The last observed launch of the existing test world required migration before login. Recheck current state when resuming. This dependency applies to live evidence, and offline work can proceed.

| ID | Points | Depends on | Status | Evidence or next action |
| --- | ---: | --- | --- | --- |
| P0 | 1 | — | Done | Plan and tracker saved in this checkout. Include both paths in handoffs. |
| P1 | 3 | P0 | Ready | Measure existing discovery and bounded Item reads. Record call/time limits and the runtime available for verification. |
| P2 | 5 | P1 | Pending | Map all visible controls and Rules exclusions to versioned evidence. |
| P3 | 5 | P2 | Pending | Publish and test the sheet, option and edit contracts. |
| P4 | 5 | P3 | Pending | Verify target/owner/token resolution and authorization. |
| P5 | 5 | P3 | Pending | Verify choice domains, dependencies, labels and pagination. |
| P6 | 5 | P4, P5 | Pending | Verify header, summary, classification, tags and publication reads. |
| P7 | 5 | P4, P5 | Pending | Verify runes, damage and mystification reads. |
| P8 | 5 | P4, P5 | Pending | Verify common, header, summary and mystification edits. |
| P9 | 5 | P4, P5 | Pending | Verify classification, range, tags and publication edits. |
| P10 | 8 | P4, P5 | Pending | Verify material grades, rune slots and specific-weapon transitions. |
| P11 | 5 | P4, P5 | Pending | Verify base, splash and persistent damage edits. |
| P12 | 8 | P6–P11 | Pending | Verify preview, apply, readback, conflicts and uncertain outcomes. |
| P13 | 5 | P12 | Pending | Record offline regression and MCP measurements. |
| P14 | 5 | P13, GM bridge | Pending | Verify read/write parity against the GM sheet on marked fixtures. |
| P15 | 5 | P13, GM bridge | Pending | Verify token isolation, player presentation and fixture cleanup. |
| P16 | 5 | P14, P15 | Pending | Run a bounded multi-room discovery-to-edit rehearsal and reconcile coverage. |
| P17 | 3 | P16 | Pending | Verify contracts, operator guidance, user summaries and final evidence. |

At each task boundary, update its status and evidence with the relevant file, commit or reproducible check, and update the resume line. Record the exact blocker and outstanding assertion if a check cannot run. Carry across diagnosis attempts as required by AGENTS.md. Use fixture labels and aggregate measurements in tracked evidence; keep campaign contents and credentials private.
