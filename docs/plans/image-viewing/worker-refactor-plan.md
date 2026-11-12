# Task05b supervisor component refactor

Status: planned before implementation,2026-11-11. This supplements task05b,
retains its8-point scope and all production budgets, and follows the user's
explicit request to separate responsibilities, test each component, migrate
callers/mocks, and then resolve the isolated failure. User input authorizes
resumption after the recorded three-attempt stop; historical attempts remain.

## Boundaries and ownership

| Module/component | Owns | Must not own | Focused test file |
| --- | --- | --- | --- |
| image_preview_admission.PreviewAdmission | One active permit,8 waiters,90s queue timeout, cancellation-safe permit release | Processes, files, image formats | test_image_preview_admission.py |
| image_preview_workspace.PreviewWorkspace |700 scratch directory, codec temp environment, credential exclusion, synchronous directory cleanup | Child killing/reaping, admission, measuring usage | test_image_preview_workspace.py |
| image_preview_child.PreviewChild | Fixed production command, spawn ownership, bounded stdin/stdout exchange, pipe draining, kill/reap and cancellation-safe close; owned completion evidence | Resource budgets, directory deletion, queue policy, image metadata | test_image_preview_child.py |
| image_preview_resources.ResourceMonitor | Bounded Linux RSS/scratch observations, unique inode/open-unlinked accounting, aggregate private metrics and limit decisions | Starting/killing/waiting for children, admission, metadata validation | test_image_preview_resources.py |
| image_preview_supervisor.PreviewSupervisor | Coordinate those components under the processing deadline; map internal failures to fixed categories | Implement procfs traversal, subprocess piping, directory cleanup or semaphore bookkeeping | test_image_preview_worker.py |
| image_preview_process.probe_image | Validate operation input/output and original byte count | Child lifecycle or resource implementation details | test_image_preview_probe.py |

No general plugin framework or unrelated upload refactor. Use constructor
injection at these concrete boundaries for tests. Test doubles implement the
component contract instead of inheriting supervisor internals or patching an
unrelated module's asyncio object. Production executable remains fixed; no MCP
argument chooses commands, paths outside staging, environments or test fixtures.

## Ordered steps and checks

1. **Baseline and call-site inventory.** Inspect graph/references and source,
   run probe/upload baselines and the current worker suite outside sandbox.
   Preserve successful-recovery, real resource-failure and stdout-flood assertions.
2. **Extract admission/workspace.** Add meaningful component tests for FIFO/
   serial bounds, queue cancellation/deadline, release after exceptions, private
   directory lifecycle, environment policy and unchanged original files. Wire
   these into the coordinator with the other extracted components at step5,
   initially preserving resource-failure semantics.
3. **Extract child ownership.** Move spawn/exchange/settle/terminate into the
   child component. Prove real bounded output, nonzero exit, spawn failure,
   cancellation during spawn/close, idempotent close and killed pipe draining.
   Child completion is owned wait completion, not just a numeric PID/existence
   check. Scratch removal must happen after close completes.
4. **Extract measurement.** Move procfs/file traversal and budget accounting
   unchanged into ResourceMonitor. Test RSS, aggregate/logical scratch, open
   unlinked files, symlink/source exclusion, scan bounds, exited-process reads,
   and genuine permission denial independently. Do not swallow PermissionError.
5. **Isolate and correct the exit race.** Mechanically wire the independently
   tested components, preserving the old measurement/error policy, then add a deterministic failing regression
   using an exited, unreaped real child (Linux/nonroot) plus controlled component
   handoffs. Record the exact kernel/ownership and denial evidence before fixing
   coordinator policy. On an unavailable measurement, the coordinator may accept
   only completion corroborated by its owned child, within one existing monitor
   interval; otherwise fail closed and kill/reap. No measurement retries or
   fabricated zero measurements. Check final named scratch after child
   close before accepting success; preserve previously observed peaks. Live denied workers must fail.
   This bounded handoff accommodates the existing sampled-monitor cadence; it
   does not promise instantaneous enforcement or increase a resource budget.
6. **Migrate all usage and mocks.** Keep probe_image and supervisor.run callers
   compatible; inject components in coordinator tests and inject the supervisor
   in image-adapter tests. Move lower-level fake-process tests to child tests.
   Remove diagnostic-only30-call retries once deterministic evidence owns the
   defect; retain end-to-end recovery and real resource-exhaustion coverage.
7. **Acceptance.** Run every component suite, probe/upload regressions, full
   `./scripts/test.sh`, production Docker build and read-only/network-disabled
   UID10001 supervised smoke. Review diff/docs/contracts and task evidence,
   commit completed05b locally with hooks. No push/release/game mutations.

## Invariants and completion evidence

Production stays1GiB RSS,2GiB scratch,90s processing,25ms sampled monitoring,
one active operation,4096 returned stdout bytes. Queue policy remains separate.
Only the child owns killing/reaping; only the workspace owns directory removal;
only admission owns its permits. Timeout/cancellation must unwind in that order.
Metadata/error results never include scratch paths, credentials, stderr or metrics.
Measured peak/time values remain private to bounded developer checks.

No claim of completion until each component and the composed real decoder pass.
Record actual commands/outcomes per step in build-progress.md. Unexpected
behavior still requires a failing unchanged regression before correction; stop
again after three unsuccessful attempts, preserving the historical count.

## Execution checkpoints

- Step1: complete; worker11 baseline reproduced the same errno13 recovery
  failure, probe8/upload13 passed; graph/exact usages inspected.
- Step2: complete; admission4/workspace3 tests passed before wiring.
- Step3: complete; child6 real-process/pipe/cancellation tests passed.
- Step4: complete; resource7 tests passed including real unreaped zombie,
  stateZ/root-owned fd directory/errno13; one additional real RSS budget test
  added for final verification.
- Step5: complete; deterministic coordinator exit regression failed against
  the mechanically extracted old policy, then passed unchanged after owned
  completion reconciliation. Existing real-exhaustion recovery passes; live
  monitor denial remains rejected. No unsuccessful correction after resumption.
- Step6: complete; caller imports, injected component factories, fixture adapter
  and probe supervisor mocks migrated. No supervisor subclass or global asyncio
  patch remains. Probe9/coordinator7 passed. The combined timeout/scratch test
  initially retained its deliberate100ms timeout for a100ms healthy fixture;
  restored the production timeout for the separate final-scratch phase, keeping
  its expected ImageScratchLimit assertion unchanged. No production change.
- Step7: focused74/full770 Python (1 existing skip)/749 JavaScript passed;
  production build and read-only/no-network UID10001 smoke passed. Diff/whitespace
  reviewed; task05b local commit/hook is the final checkpoint in this commit.
