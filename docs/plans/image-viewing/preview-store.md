# Immutable derivative store

`image_preview_store.PreviewStore` is a private SQLite store for already decoded,
validated PNG/WebP derivatives. It stores no Foundry selectors, original files,
crop coordinates, caller credentials or source handles. Browser/HTTP/runtime
wiring is owned by later tasks; this module registers no MCP tool or route.

`publish(data,mime_type)` repeats bounded container/MIME/size/geometry validation
and returns a `PublishedPreview` with token,extension,mime_type,size_bytes and
absolute UTC `expires_at` (Unix seconds). Every successful issuance gets a fresh
cryptographically random UUIDv4. Only its SHA256 digest, complete BLOB, MIME,
byte count, publication timestamp and expiry are persisted. Token and pixel
fields are excluded from internal dataclass reprs.

Publication begins an IMMEDIATE transaction, samples the injected UTC clock,
deletes expired records, checks live row and byte quotas including the new
derivative, then inserts metadata and bytes together. Successful commit precedes
receipt return. SQLite serializes competing writers even across store instances/
threads/processes. A rejected new issuance commits expired-row cleanup without
deleting any valid derivative. A SQL failure rolls back the operation and emits
only a fixed `StoreFailure` category, never SQL, a path or a token.

Production limits are1GiB live encoded bytes and4096 live rows. These are live
payload quotas, not a cap on SQLite file/journal size: freed pages are reusable,
and rollback journaling can temporarily use extra private disk. Each artifact
remains bounded to2MiB. SQL connection lock waits are bounded to5 seconds; length
limits bound individual SQLite values to4MiB. Synchronous FULL and DELETE journal
mode provide the existing SQLite durable-commit semantics without persistent
WAL sidecars. There are no long-lived connections or background tasks here.

Expiry is exactly604800 seconds after the publication clock sample. Every
`lookup(token,extension)` independently requires `now < expires_at`; it returns
None for expired, unknown, noncanonical/non-v4 tokens or mismatched extensions.
Cleanup can be paused without extending a link. `prune()` removes expired rows;
construction runs it at startup, and09a owns the periodic runtime call. Closing
the store prevents new database operations;09a drains active runtime work first.
Reopening the same private directory preserves valid links.

The private directory is700; the database is precreated600 before SQLite opens
it. Known SQLite sidecars must also be regular600 files, and directory/database/
sidecar symlinks or database hardlinks are rejected. The active rollback journal
inherits private mode, verified while a publication transaction is open. Runtime
configuration must point only at the server's dedicated private preview storage;
these permissions are never applied to Foundry game assets.

Internal failures are `PreviewQuotaExceeded` (wait for expiry or ask the operator
to provide preview capacity), `PreviewStorageUnavailable` (operator must restore
private writable storage), or `InvalidPreviewArtifact` (do not publish; inspect
server/module processing compatibility). Tool integration maps these through its
allowlisted error boundary; no raw exception string is public recovery evidence.

The transaction design follows Python's
[connection context-manager contract](https://docs.python.org/3.12/library/sqlite3.html#how-to-use-the-connection-context-manager)
and SQLite's [IMMEDIATE transactions](https://www.sqlite.org/lang_transaction.html)
and [atomic commit](https://www.sqlite.org/atomiccommit.html). Original snapshots
and native scratch retain their separate lifetimes and resource budgets.

`test_image_preview_store.py` verifies real PNG/WebP, unique tokens, digest-only
storage, exact expiry without cleanup, startup/periodic pruning, restart,
independent quota boundaries, eight competing issuances across four connections,
SQL abort rollback, rejected-artifact admission, private active journal mode,
unsafe storage, closed-state errors and production constants. Exact final
focused/full/package outcomes are recorded in [task08](tasks/08-persistent-preview-store.md).
