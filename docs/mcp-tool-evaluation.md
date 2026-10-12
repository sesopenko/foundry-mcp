# Budgeted MCP tool evaluation

Use this process for journal tools and subsequent features. The objective is
enough evidence to guide the next implementation decision, while reserving GPT
usage for building. The recorder and summary command are implemented; an
automated agent runner and answer grader are not yet implemented.

## What counts as enough

Run focused deterministic tests first. They cover schema validation, exact data,
errors, pagination, and transport without consuming GPT usage. Use live LLM
evaluation when requested or when actual agent usability remains uncertain;
do not rerun a large benchmark after every edit.

For an ordinary iteration:

1. State the uncertainty and select **one smallest representative GM task**
   capable of exposing it. Define answer criteria before looking at results.
2. Run that task **twice**, in separate fresh agent contexts, with unchanged
   world data, model/settings, prompt, tool catalog, and resource limits.
3. Stop when both answers meet the criteria, there are no critical failures,
   and the measured work fits the declared budget. This is a provisional
   development pass, not a statistical reliability guarantee.
4. A **third run** is warranted only if the first two disagree or a specific
   essential risk remains unchecked. Do not continue sampling until something
   happens to pass. A confirmed failure goes back to implementation.

One task goes to one agent. Do not bundle several questions: shared reads make
per-question cost attribution unreliable. Do not ask the agent to audit the
entire world unless that is the actual task being evaluated.

For a performance comparison, use two baseline and two candidate attempts of
the same task. Reuse a recorded baseline only when its world snapshot,
model/settings, prompt, harness, and budgets still match. Four attempts are the
ordinary comparison cap, not an invitation to run a full task matrix. Record
the individual results and their ranges; two attempts cannot establish a
stable percentile or significant improvement.

Every run has a declared call cap and elapsed-time cap. Initial examples are
8 calls/2 minutes for a small lookup and 40 calls/5 minutes for a bounded
multi-page investigation. These are starting budgets, not universal targets.
Choose a smaller task rather than silently increasing caps. The future runner
must enforce them; the server recorder currently observes calls and does not
enforce agent limits. Budget exhaustion is a measured outcome, not a pass.
Do not expand into larger test campaigns without an explicit request.

Account quota and billed GPT tokens are not observable from this MCP server.
Record model token usage only when the agent harness actually supplies it;
otherwise use null. Tool bytes, call counts, and durations are resource proxies,
not a percentage of the user's remaining GPT allowance.

## Tasks and references

Maintain a small reusable catalog drawn from GM goals: orientation, fact lookup,
chapter comprehension, character/faction threads, clue connections, chronology,
prerequisites, player knowledge, consequences, and next-session preparation.
Also include ambiguity, missing evidence, and unsupported-content cases.

The original five journal questions are useful exploratory tasks, but are not
the whole evaluation set. Avoid choosing only tasks with known names that favor
literal search. Include discovery questions where the GM does not know the
relevant names. Do not require a particular tool path when several are valid.
Publisher layout and naming are variables, not evaluation assumptions.

Use a small synthetic fixture for cheap iteration and a real adventure for
occasional transfer checks. Prepare independent GM-reviewed references once;
the model's previous answer is not ground truth. Evidence keys should identify
essential facts, source pages, ambiguities, acceptable inference, and unavailable
information. Mark cases without reviewed references as exploratory/ungraded.
Keep references and evaluation rubrics out of the tester's input.

Store a case with: task ID, exact user prompt, goal family, world/fixture version,
allowed operations, critical answer criteria, source references, review status,
and fixed run limits. A prompt paraphrase is a new version of the case.

## Isolating a run

Use a fresh context (`fork_turns="none"` for subagents), supplying only the user
task, scope, allowed operations, and resource limits. The tester learns usage
from actual MCP discovery descriptions/schemas and responses. It must not read
repository instructions containing task solutions, implementation, expected
answers, prior runs, or browser/database data. Restrict access where the harness
supports it; otherwise record this as an instruction-only isolation limitation.

Only supply setup instructions necessary to reach MCP. Keep native discovery
and a Python-client fallback as different harness profiles when comparing runs.
Do not coach a tester mid-run; record necessary intervention and treat the run
as assisted. Run sequentially by default to avoid contention on the single GM
bridge and confusion between agent latency and server latency.

Capture a manifest containing run/task/attempt IDs, code commit and dirty state,
tool catalog hash, model and reasoning settings (unknown if unavailable), exact
prompt, harness profile, Foundry/system/module versions, fixture identity or
snapshot fingerprint, resource caps, start/end times, and final outcome.
Future mutation tools must use disposable fixtures with reset/verification;
journal evaluations are read-only. Model changes need a separate comparison.

## Enable server recording

Set this in the local, gitignored `.env.mcp`, then restart the existing service:

```dotenv
FOUNDRY_MCP_TRACE_PATH=/absolute/path/to/foundry-mcp/.eval-runs/mcp.jsonl
```

```bash
./scripts/server.sh restart
curl -fsS --max-time 3 http://127.0.0.1:8000/health
```

Logging is disabled when the variable is absent. When enabled, health includes
`evaluation_logging.write_failures`; it must remain zero for a valid capture.
An unwritable sink prevents startup. Mid-run write failures are reported without
changing tool outcomes. Files are private (0600), directories created by the
recorder use 0700, and `.eval-runs/` is ignored by Git. Retention is a 5 MB current
file plus two rotations. Preserve all files for a run before later rotation.

Tag requests through MCP request metadata, without changing tool arguments:

```python
await client.call_tool("search_journals", {"query": "Ripnugget"}, meta={
    "evaluation": {"run_id": "baseline-01", "task_id": "npc-thread", "attempt_id": "1"}
})
```

HTTP clients can instead use `X-Foundry-Eval-Run`, `X-Foundry-Eval-Task`, and
`X-Foundry-Eval-Attempt`. Metadata takes precedence. Labels accept letters,
numbers, underscores, periods, colons, and hyphens, up to 128 characters.
Native clients unable to tag requests retain a hashed session identifier;
associate that session with a single-task manifest if possible. Shared sessions
without task tags are unattributed: do not invent per-task counts.

## What gets recorded

- Discovery: exact advertised tool descriptions/schemas and catalog hash.
- Calls: unique call ID, instance/sequence, timestamp, MCP request ID, hashed
  session, run/task/attempt tags, argument fingerprint, start and finish events.
- Arguments: known journal selectors, queries, limits, and cursors are retained
  in the private trace. Unknown fields and development JavaScript source are
  replaced with hashes; oversized values are explicitly clipped. No auth
  headers, credentials, response bodies, or hidden model reasoning are logged.
- Results: outcome/error category, duration, compact UTF-8 MCP result bytes,
  structured-result bytes, returned counts, continuation/completeness flags,
  source positions/lengths, revision, and Foundry version where present.

Durations measure server tool execution/processing, not model thinking or full
agent elapsed time. Response bytes exclude HTTP/SSE/JSON-RPC framing. Structured
and text representations may duplicate data in MCP responses; their combined
size matters. Failed calls may have no measurable response bytes because the SDK
forms their final error response after middleware exits.

The pinned FastMCP 2.14.1 hook records dispatched tool calls, including tool
schema validation failures and unknown tools. Malformed protocol envelopes or
authentication failures rejected before dispatch remain ordinary server errors,
not recorded tool calls. Direct Python function calls bypass MCP middleware.

## Summarize and review

```bash
.venv/bin/python -m foundry_mcp_server.evaluation_stats \
  .eval-runs/mcp.jsonl --run baseline-01 --task npc-thread --calls
```

Supply `.jsonl.1` and `.jsonl.2` too if rotation occurred. The command uses no
network or GPT. It reports per-session run/task/attempt counts by tool, outcomes,
errors, repeated argument calls, continuations, partial results, bytes, source
volume, and median/max duration. `--calls` includes chronological safe arguments
and outcomes. Missing sequences, write failures, unmatched starts, and orphaned
finishes make incomplete capture visible. Repeated arguments are not necessarily
waste: retries, verification, and changed data can justify them.

Save the final answer verbatim and brief observable decision notes separately
from the server trace. Preserve exact source payloads locally only when needed
for a specific diagnosis. Do not print large response batches into agent context.
Do not use hidden chain-of-thought or self-reported arithmetic as metrics.

Score separately: correctness, essential coverage, citation support, uncertainty
handling, contract usability, and efficiency. A cheap incorrect answer is a
failure. A supported statement that requested information is unavailable can
pass a missing-evidence case. GM review is the initial answer grader; an LLM
grader is optional later, with a fixed rubric and human spot-checks, not another
automatic agent swarm.

Record the smallest proposed change, affected case, before/after evidence,
quality tradeoff, and stop decision. Change one factor at a time (description,
schema, response shape, or feature). Extend the catalog only for a new recurring
GM need or observed failure, rather than adding cases after every successful run.

## Current evidence status

The earlier two-agent journal exercise demonstrated discoverability but bundled
questions, lacked instrumented traces, and was not repeated. It is an exploratory
pilot, not a measured baseline. Reconstructed reports corrected counts to 37
and 87 calls (124 total); those corrections illustrate why instrumentation is
required. Do not reuse the original 126 total or attribute all calls to Ripnugget.

Process references: [OpenAI evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices)
and [FastMCP middleware](https://gofastmcp.com/servers/middleware). Consult the
installed pinned middleware when newer documentation describes different hooks.
