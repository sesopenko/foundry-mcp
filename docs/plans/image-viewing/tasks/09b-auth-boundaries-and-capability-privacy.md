# 09b — Authentication boundaries and capability privacy

Points: **5** — auth regression matrix and actual access/evaluation-log redaction.
Split from original task 09, estimated at 13 points.

Dependencies: [09a](09a-http-delivery-and-configuration.md).
Intended commit: `fix(images): isolate anonymous delivery and redact preview capabilities`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design](../../../prompts/foundry-image-previews-plan.md),
[plan index](../README.md), and this task. Reconcile dependency commits and test
evidence. Follow the index's execution and commit protocol.

Read production auth, OAuth policy/discovery, evaluation tracing, Uvicorn logging,
and 09a's configuration/policy interface. Do not alter Auth0 or auth exclusivity.

## Implementation and interfaces

- Verify that anonymous image reading is limited to the explicit preview route,
  including path variants/queries; retain existing MCP, GM-WebSocket, and PDF
  protection. Basic/OAuth and existing authenticated development may issue;
  plain-none mode cannot. Missing origin blocks URL issuance early while info
  and discovery remain available under their existing authentication contracts.
- Complete narrow policy plumbing as necessary; keep authority from trusted
  authentication/configuration, not supplied headers or capability ownership.
  Task 11 must depend on this task before registering URL issuance.
- Scrub capability paths/URLs from actual Uvicorn access records and application
  diagnostics for successes and errors, retaining useful counts/status. Ensure
  evaluation records contain only approved aggregates/fingerprints and no bearer
  links, source bytes, signed S3 URLs, credentials, or private paths. Do not
  weaken logging globally merely to hide one sensitive route.
- Document capability-safe logging and auth boundaries. Task 13 supplies proxy
  examples; local checks must pass before any live fixture generates links.

## Tests and acceptance

Add `tests/test_image_preview_privacy.py` through the production app, existing
auth fixtures, and actual emitted access/evaluation logs. Cover Basic, OAuth,
authenticated development, plain-none mode, invalid/duplicate credentials,
protected routes, anonymous preview success, malformed/expired/query variants,
missing origin, and captured failure diagnostics. Assert secrets are absent
without printing them on test failures. Reuse offline JWT checks; no real OAuth
login/refresh is required for unchanged upstream authentication dependencies.

Run outside the sandbox:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_privacy.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_http.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_evaluation.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_production_auth.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_oauth*.py' -v
./scripts/test.sh
```

Accept when auth separation and secret-free actual diagnostics are demonstrated.
Commit policy/logging changes, focused tests, and privacy documentation together.

## Completion record

- Implementation: not started.
- Dependency commit SHA(s): pending.
- Commit: pending (`this commit` when completed).
- Focused/full checks, auth matrix and log evidence: not run.
- Exact pending deployment prerequisites: pending.
