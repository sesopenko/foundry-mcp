# Unattended build-agent goal and kickoff prompt

Start the build agent with this goal, then supply the complete kickoff prompt below.

## Persistent goal

```text
/goal Implement the complete Foundry image-viewing system specified by docs/plans/image-viewing/README.md and docs/prompts/foundry-image-previews-plan.md. Work through all 30 tasks in dependency order until the implementation is complete, each task has meaningful passing unit tests, the full required regression suites pass, and each task has its own local commit. Deliver image information, bounded previews and crops, persistent preview URLs, map-folder browsing, grid and level-image metadata, and readable map-note overlays with identity lookup. Preserve the original assignment on disk and reread it after every compaction or resume. Diagnose failures at their root, prove each defect with a failing unit test, fix the system under test, and verify the unchanged test passes. Continue without routine requests for intervention. Complete all available local, packaged, MCP, and runtime verification; explicitly document unavailable external acceptance checks without claiming they passed. Do not push, release, publish, or modify existing game assets.
```

## Build-agent kickoff prompt

```text
Implement the complete plan in docs/plans/image-viewing/README.md.

Work autonomously through the entire dependency graph. Finish each task’s implementation, meaningful unit tests, required regression checks, documentation, and separate local commit before starting another task. Continue directly after each commit without asking whether to proceed.

The checkout currently contains a 30-task, 200-point implementation plan. Treat task statuses and Git history as the source of truth for what remains. Historical 14-task and 22-task breakdowns are superseded.

1. Preserve this assignment before starting

Save this entire received assignment, including the persistent goal and every instruction in this kickoff prompt, verbatim to:

docs/prompts/foundry-image-viewing-build-agent.md

Do this before implementation or extensive exploration. If the file already exists, reconcile it with this assignment without discarding later user instructions.

Add a link to this saved execution prompt in the plan index’s context-recovery instructions. Include the saved prompt in the first task’s commit.

This is the feature implementation assignment. The older task-breakdown prompt preserves the history of creating the planning documents; its historical planning-only scope does not replace this execution assignment.

Establish or retain the persistent goal above using the environment’s goal mechanism. Inspect an existing goal before creating another. Do not mark it complete merely because a task, session, or context window has ended.

2. Recover context after every compaction or resume

Immediately after EVERY automatic compaction, session resume, or handoff, reopen and reread these files IN FULL before choosing another action:

- docs/prompts/foundry-image-viewing-build-agent.md
- docs/prompts/foundry-image-previews-plan.md
- docs/prompts/foundry-image-viewing-task-breakdown-plan.md
- docs/plans/image-viewing/README.md
- docs/plans/image-viewing/map-browsing-notes-research.md
- The current task file.
- The durable progress record described below.

Follow AGENTS.md and its required reading. A compressed conversation summary does not replace reading the saved instructions.

Reconcile the persistent goal, current branch, working-tree diff, recent commits, task statuses, and recorded test results. Resume the current unfinished task; do not restart completed work or silently change the design.

3. Maintain durable progress

Create and maintain:

docs/plans/image-viewing/build-progress.md

Record:
- Current task ID and task-file path.
- Current stage: baseline, implementation, diagnosis, verification, or commit.
- Last completed task and its commit SHA.
- Exact focused/full test commands and observed outcomes.
- Current failure, evidence, root-cause hypothesis, reproducing test, and unsuccessful attempt count.
- Important implementation decisions and their evidence.
- Any external verification gap and its exact prerequisite.
- The next concrete action.

Update this record after meaningful milestones and before switching tasks. Keep secrets, capability URLs, credentials, bulk game data, and private visual answers out of tracked records.

A task’s own commit may identify itself as “this commit”; resolve its SHA through Git history in the next checkpoint rather than repeatedly amending commits.

4. Execute one task at a time

Choose the first unfinished task in the index whose implementation dependencies have been completed and committed.

For each task:
a. Read its complete requirements, dependency evidence, relevant current source, and required public API documentation.
b. Establish the relevant baseline and tests for existing behavior.
c. Implement only that task’s cohesive scope, adding meaningful unit tests alongside the behavior.
d. Run focused checks after meaningful changes.
e. Complete required discovery, schema, payload, packaging, browser, and runtime checks appropriate to the task.
f. Run ./scripts/test.sh and resolve failures.
g. Review the diff, update task/index/progress evidence, stage only intended changes, and commit.
h. Immediately continue to the next ready task.

Do not accumulate multiple unfinished implementations or defer their unit tests to an integration task. Keep every executable task below 13 points. If genuine scope growth requires splitting a task, preserve its requirements, test ownership, dependencies, and commit checkpoints.

If an external prerequisite is unavailable, finish independently testable work and record the precise verification gap. Do not build dependent work on an unfinished implementation or failing tests.

5. Diagnose root causes before fixing failures

When behavior is unexpected:
a. Reproduce it and gather evidence.
b. Identify the failing layer and causal mechanism.
c. Add a focused unit test against the system under test.
d. Run that test before the correction and observe it fail for the expected reason.
e. Correct the system under test.
f. Run the same test unchanged and observe it pass.
g. Run the relevant focused regressions and full required suites.

Do not substitute speculative retries, swallowed errors, permissive fallbacks, arbitrary limit increases, disabled assertions, or changed expected behavior for a demonstrated correction.

If a root cause cannot yet be reproduced by a unit test, the investigation remains incomplete. Do not claim a speculative change fixed it.

After THREE unsuccessful diagnosis or fix attempts for the same issue, follow AGENTS.md: stop development, report the evidence, attempts, unresolved cause, and required input, and wait. Preserve this count across compactions and resumes. Do not switch tasks to evade this stop requirement.

6. Verification and operating boundaries

Run all tests and test-running hooks outside the agent sandbox using require_escalated from the first invocation, as AGENTS.md requires. Keep existing approval protections.

Use short, readable commands and existing fixed runners. Put necessary reusable verification logic in readable, tested files; avoid large inline programs in approval requests.

Use documented public Foundry APIs and the prescribed Grounded Docs workflow. Runtime observations alone do not establish public API support.

Reuse the existing development instance, test world, credentials, and dedicated browser. Run offline checks before fixture verification. Follow development-browser refresh, readiness, and console-inspection requirements for module changes.

Use only authorized, marked temporary fixtures with bounded cleanup. Preserve existing game documents and assets. Do not create another Foundry instance for convenience.

Do not weaken authentication, alter Auth0 tenants, bypass credentials, expose private data, push commits, tag, release, or publish deployments.

Routine implementation decisions and authorized local task commits do not require another confirmation. Request intervention only for a genuine missing decision, denied required permission, action outside authorization, or the mandatory three-attempt stop.

7. Finish against the complete design

The goal is a working implementation of the whole plan, not merely committed code.

Verify actual MCP discovery and invocation, typed schemas, browser RPC behavior, real decoder output, packaged fonts/codecs, HTTP delivery, persistence, quotas, identity isolation, crop geometry, map browsing, annotation placement, and complete legend workflows as required by the tasks.

Keep implementation completion, local verification, and target-ChatGPT visual acceptance distinct. Unavailable external client/public-HTTPS checks require an exact pending handoff; they do not excuse unfinished code or failing unit tests.

Before reporting completion:
- Reconcile every task and source-design acceptance criterion with evidence.
- Confirm all required unit/regression suites pass.
- Confirm each task has its separate local commit.
- Complete available runtime/package checks and fixture cleanup.
- Report any remaining external acceptance gaps honestly.
- Inspect the final Git state and identify any remaining changes.

Provide a concise final report listing task commits, test results, material measurements, demonstrated workflows, cleanup status, and exact remaining external prerequisites.

Continue until this goal is achieved or a genuine stop condition requires user input.
```
