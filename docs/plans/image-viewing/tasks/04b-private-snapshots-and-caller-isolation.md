# 04b — Private snapshots and caller isolation

Points: **8** — authenticated principal binding, cache leases, and snapshot validity.
Split from original task 04, estimated at 13 points.

Dependencies: [04a](04a-python-transfer-assembly.md).
Intended commit: `feat(images): stage caller-bound immutable source snapshots`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design](../../../prompts/foundry-image-previews-plan.md),
[plan index](../README.md), and this task. Reconcile dependency commits and test
evidence. Follow the index's execution and commit protocol.

Read current connection-manager correlation, image-upload orchestration, Basic
and development HTTP authentication, OAuth policy, and
[OAuth verification gates](../../../oauth-verification.md). Verify the pinned
FastMCP public authenticated-context API before using it. Do not change Auth0.

## Implementation and interfaces

- Wrap 04a's verified private staged-file/digest/context result in a snapshot
  service used by the future tools. Take ownership of a complete file only;
  failed transfers must never create valid source handles. Transfer assembly
  and per-chunk fault tests remain in 04a.
- Store opaque `source_id` handles for exactly 30 minutes from staging, within
  a 512-MiB private compressed-source cache. Prune expired unleased snapshots
  before admission; reject new staging when capacity remains insufficient,
  rather than evicting valid handles. Lease files during probe/render so cleanup
  cannot remove an active input; deny new use at expiry. Clear ephemeral state
  on process restart; public preview persistence is task 08's separate concern.
- Bind each handle to authenticated caller, GM, world, and exact selector, with
  digest kept private. For OAuth use verified issuer/subject/client context;
  for Basic use the verified configured account; for authenticated development
  use the verified development caller. Never use supplied identity headers,
  session IDs alone, client arguments, or raw bearer strings as authority.
  A refreshed OAuth token for the same authorized principal need not create a
  new identity. Missing validated context fails closed.
- Provide snapshot lookup/lease and current-authorization/membership recheck for
  task 11. A changed socket invalidates in-progress work; lost authorized context
  rejects later handle use with typed recovery. Revalidated same-principal,
  same-world/GM handles retain their staged bytes. Replacement contents at an
  unchanged path do not modify an existing snapshot; fresh info stages anew.
- Sanitize errors; no source paths, hashes, signed URLs, or transfer bytes enter
  model results/logs. Add only narrowly scoped authenticated-context plumbing
  where existing public interfaces are insufficient; preserve auth exclusivity.

## Tests and acceptance

Add `tests/test_image_preview_sources.py`. Test transfer-result admission,
failed staging cleanup, changed socket/world/GM, worker-file leases, capacity,
exact expiry, replacement bytes, concurrent cache use, and cleanup. Test two
verified OAuth principals/clients and forged context
against the actual authentication boundary, plus Basic/development identity.
Never accept in-memory invocation without trusted context in production paths.

Run outside the sandbox:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_sources.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_connection.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_production_auth.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_oauth*.py' -v
./scripts/test.sh
```

Accept when cross-principal access demonstrably fails, immutable reuse works,
and snapshot lifecycle tests pass. Commit services, auth-context
plumbing, tests, and snapshot recovery documentation together.

## Completion record

- Implementation: not started.
- Dependency commit SHA(s): pending.
- Commit: pending (`this commit` when completed).
- Focused/full checks, cache/lease/expiry measurements: not run.
- Auth-context API evidence and pending live prerequisites: pending.
