# Codex discovery regression investigation

Current stage: local commit. Unsuccessful verification attempts: **2**
(test-fixture mistakes, explained below). The original production defect is
resolved by the first correction; no further production changes were attempted.

Codex CLI 0.169.0 reports `foundry-vtt: failed (0 tools)` although the local
Python service is healthy and a current FastMCP Python client lists 47 tools.
The configured endpoint is localhost; systemd runs this checkout with `uv run
--locked`, not a released Docker image. The caller credential is present.

Codex's logs show successful initialization with MCP version `2025-06-18`,
followed by `-32603: Handler returned an invalid result`. The server identifies
`tools/list` serialization failures for `write_journal` and `upload_image`:
their union output schemas omit the required top-level `type` field. Both
response unions contain objects exclusively. Existing discovery tests use the
new SDK's newer default protocol and did not cover this negotiated version.

Plan:

1. Add a focused regression test against the complete application HTTP mount,
   authenticating normally and negotiating `2025-06-18` exactly as Codex does.
   Observe `tools/list` fail for the recorded serialization error before edits.
2. Trace the union schema generation and the SDK's version-specific serializer.
   Correct the response contract at its owning models; preserve alternatives,
   validation, response fields and authentication. Keep the test unchanged.
3. Verify the complete catalog across supported protocol versions, both union
   response branches and invalid-response rejection. Run focused and full suites.
4. Restart the existing service and verify real HTTP discovery under Codex's
   protocol. Verify Codex visibility when the client reconnects; do not claim a
   Python client proves visibility inside the active Codex conversation.

Stop after three unsuccessful diagnosis/correction attempts and await user
advice. Do not change credentials, suppress schema validation, remove tools,
force a different client protocol or raise timeouts to hide this failure.

The new test was run before the correction with:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_mcp_discovery_protocols.py' -v
```

It failed at the assertion that `tools/list` has no error, with the exact
`-32603` result and the two missing `outputSchema.type` validation errors.
The handshake had succeeded and confirmed `2025-06-18`. The application and
SDK serializer ran normally; neither the catalog nor transport was mocked.

The pinned SDK's public `mcp_types.methods.serialize_server_result` validates
against different wire schemas by negotiated version. Its pre-2026 schema
requires an object-typed output schema; its 2026 schema permits general JSON
Schema. Pydantic emits only `anyOf`/`oneOf` for the two RootModel unions. New
Python clients default to the latter protocol, explaining the passing checks.
This is a server response-contract defect, not an authentication/timeout defect.

Correction attempt 1 declares `type: object` in the two response models'
generated schemas. Every existing alternative is already an object, so this
expresses their actual contract without wrappers or changing wire responses.
No dependency, credential, client protocol, tool registration or serializer
validation is changed.

The first verification removed the serialization error, then reached a mistake
in the new test: it expected the development-only console in a production Basic
fixture. The test's required catalog was corrected to the six unconditional
tools. Production code was fully restored, and this corrected test was observed
failing at the original `-32603` assertion (0.138s). The same schema correction
was then reapplied, and the corrected test passed **unchanged** (0.141s).
The expected production catalog was corrected, not a production assertion or
response-validator policy. The original schema failure was demonstrated twice.

Additional coverage validates the entire published catalog against every
protocol version supported by the pinned SDK's public serializer and verifies
that both unions retain their alternatives, object restrictions, required
status and rejection of invalid responses.

The first supplemental matrix used a reconstructed list-only envelope, which
omitted the 2026 protocol's mandatory cache metadata. It was corrected to use
the full real `ClientSession.list_tools()` result, including that metadata;
no production behavior or original reproducing test was changed. The complete
three-test file then passed (0.109s), including all five SDK protocol versions.
This second test-fixture mistake is retained in the attempt record. There is
no unresolved failure; a third unsuccessful attempt on this issue would require
stopping and awaiting advice.

Focused checks (all outside the sandbox):

| Command | Result |
| --- | --- |
| `.venv/bin/python -m unittest discover -s tests -p 'test_mcp_discovery_protocols.py' -v` | 3 pass; original corrected reproducer unchanged between red and green |
| `.venv/bin/python -m unittest discover -s tests -p 'test_journal_authoring.py' -v` | 18 pass, including both mutation-result branches |
| `.venv/bin/python -m unittest discover -s tests -p 'test_image_uploads.py' -v` | 13 pass, including success/unknown outcomes and malformed receipts |
| `.venv/bin/python -m unittest discover -s tests -p 'test_oauth_application.py' -v` | 3 pass; actual application discovery parity across Basic/OAuth/none |

Bounded live baseline before service restart, one authenticated `tools/list`
with the newer Python client: 47 tools, 320839 compact UTF-8 JSON bytes for
the catalog array; `write_journal` output schema 5292 bytes; `upload_image`
2798 bytes. No game documents, credentials or capability URLs were printed.

## Final verification

`./scripts/test.sh > /tmp/foundry-mcp-discovery-regression.log 2>&1` passed:
**1056 Python tests in 150.967s (one existing skip), 795 JavaScript tests**.
All tests ran outside the sandbox. `git diff --check` passed.

After `./scripts/server.sh restart`, the same localhost service was verified
over real HTTP using the legacy handshake pinned to `2025-06-18`. Discovery
returned all **47 tools**, including `execute_javascript`, `browse_maps`,
`get_map_info`, `get_foundry_image_info` and `get_foundry_image_url`.
`get_bridge_versions` succeeded with `module_status: connected`.
The only patched value in that read-only verifier was the Python client's
offered handshake version; the server, serializer, transport and credential
validation were real and unchanged.

The matching newer-client post-restart measurement is 47 tools / **320755**
catalog bytes, `write_journal` schema **5308** bytes, `upload_image` **2698**
bytes. The two explicit object constraints add 16 bytes each; naming the upload
response class also replaces its long generic schema title. Response fields,
alternatives and actual game behavior are unchanged. These are bytes, not
billed tokens; no game-data pagination workflow changed.

After the user restarted Codex, the local `mcp__foundry_vtt` tools appeared in
this conversation, including both image tools, both map tools and the console.
A direct native `get_bridge_versions` call succeeded with the GM module
connected and matching source versions 3.3.1 (source builds correctly retain
comparison=unverified). This establishes actual Codex discovery and invocation.
The restart interrupted the first local commit hook; no commit or host test
process remained. The local commit was restarted with the required hook.
No fixtures or game assets were created or modified. No publication or
dependency/version change was made.

## Contract references

- [MCP 2025-06-18 tools and structured output](https://modelcontextprotocol.io/specification/2025-06-18/server/tools).
- Pinned MCP SDK2.3.0 `mcp_types.methods.serialize_server_result` (supported public
  API) and its version-specific `SERVER_RESULTS` table establish the exact
  serializer behavior reproduced by the test.
- [Codex active-server diagnostics](https://learn.chatgpt.com/docs/developer-commands?surface=cli#list-mcp-tools-with-mcp)
  distinguish `/mcp verbose` from configuration-only `codex mcp list`.
