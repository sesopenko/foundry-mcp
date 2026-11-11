# 08 — Persistent preview store

Points: **8** — transactional publication, expiry, concurrent quotas, and persistence.

Dependencies: [01](01-contracts-and-baseline.md).
Intended commit: `feat(images): persist immutable seven-day preview capabilities`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design](../../../prompts/foundry-image-previews-plan.md),
[plan index](../README.md), and this task. Reconcile dependency commits and test
evidence. Follow the index's execution and commit protocol.

Read the full publication design, existing private SQLite/runtime lifecycle
patterns, and Docker service-user storage conventions. Consume task 01's limits;
this store needs no browser, decoder, or public route yet.

## Implementation and interfaces

- Add an image-preview-specific private SQLite store with injected clock and
  production defaults. Atomically persist complete validated derivative bytes,
  MIME, size, cryptographic token digest, and absolute UTC expiry. Store image
  bytes transactionally as BLOBs so metadata and pixels cannot diverge across
  failures. Do not store original sources in this public-derivative table.
- Generate a fresh cryptographically random UUIDv4 per successful issuance,
  including identical pixels/crops. Return the opaque path token only for the
  caller to mint the URL; persist its digest rather than the bearer token.
  Bind extension to actual `png` or `webp` MIME. Lookup accepts token plus
  extension and returns only that immutable derivative; no source/region access.
- Set expiry exactly 604,800 seconds after atomic publication. Every lookup must
  enforce `now < expires_at` regardless of pruning progress. Prune expired rows
  at startup and periodically; task 09a connects lifecycle. Handle clock injection
  consistently for issuance, lookup, pruning, and tests.
- In the issuance transaction, prune expired rows, then enforce <=1 GiB live
  bytes and <=4,096 live rows including the new derivative. Reject over-quota
  issuance without deleting valid links. Serialize competing admission checks
  through SQLite transactions so concurrent requests cannot exceed either quota.
- Preserve valid rows across process/container restarts. Use a private directory
  and restrictive database/sidecar permissions, with clean shutdown and bounded
  operations. Expose a typed internal quota/storage failure for tool translation;
  never echo SQL, filesystem paths, or capability tokens to logs.

## Tests and acceptance

Add `tests/test_image_preview_store.py`. Use temporary databases and an injected
clock to verify immutable bytes/MIME/size, UUIDv4 uniqueness, digest-only token
storage, extension mismatch, unknown token, one derivative per capability,
just-before/exact expiry with pruning disabled, startup/periodic pruning, both
quotas at and above their boundaries, concurrent admission, failed transactions,
permissions, clean reopening, and valid links after restart. Quota tests may
inject small limits; separately assert production constants. Existing links must
remain readable after failed new issuance.

Run outside the sandbox:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_store.py' -v
./scripts/test.sh
```

Accept when publication is atomic, lookup independently enforces expiry and
format, concurrent quotas hold, and reopening preserves valid derivatives.
Commit store, tests, and persistence/expiry documentation together.

## Completion record

- Implementation: not started.
- Dependency commit SHA(s): pending.
- Commit: pending (`this commit` when completed).
- Focused/full checks and persistence/quota results: not run.
- Pending environment evidence: none assessed yet.
