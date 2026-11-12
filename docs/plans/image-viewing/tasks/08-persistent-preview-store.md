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

- Implementation: complete; [store/lifetime contracts](../preview-store.md).
- Dependency commit SHA:01 `b0cc01e`.
- Commit: this commit.
- Focused command above:15 passed outside sandbox. `./scripts/test.sh` passed
  both suites, exit0;749JS and1 existing Python skip. Hook repeats required checks.
- Production image build passed UID10001 native/supervised smokes. Additional
  `docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=128m --user 10001:10001 --volume /home/sean/src/github.com/sesopenko/foundry-mcp/tests:/checks:ro --entrypoint python foundry-mcp-image-preview-check:local -m unittest discover -s /checks -p test_image_preview_store.py -v`
  passed15/0.071s against shipped application/SQLite. No app-source override,
  game volume, capability URL, network, release or publication.
- Eight competing requests across four store instances admit exactly2 under
  2-row/two-artifact-byte quotas;6 receive fixed quota failures. Existing bytes
  remain readable after rejection/SQL abort. Exact seven-day boundary holds with
  pruning paused; reopen retains valid records and prunes expired records.
- Database/active journal600 and directory700 verified. Digest-only persisted
  tokens, immutable PNG/WebP, format/UUID binding, invalid artifacts, corruption/
  symlink/closed-state failures and production limits covered. No unexpected
  defect or unsuccessful correction attempt; no unavailable store-local check.
- HTTP/runtime periodic cleanup and deployed-volume persistence belong to09a/13;
  no route or MCP tool is exposed by this task.
