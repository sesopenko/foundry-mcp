# Foundry MCP rejects publisher classes during journal edits

Foundry MCP rejects an authorized journal replacement that preserves the publisher’s existing HTML and adds a read-aloud paragraph using the publisher’s own `read-aloud` class. This prevents matching the adventure module’s presentation and placing the narration directly below the room heading. A class-free append succeeds, but produces a different appearance and places the paragraph at the end of the page.

## Environment

| Component | Observed value |
| --- | --- |
| Foundry VTT | 14.369 |
| Foundry MCP server | 3.1.0 |
| Foundry MCP browser module | 3.1.0 |
| Server and module build revision | `0273074300ff39cc2e3f53f30ad2b4fd845c9f3b` |
| Version comparison | Match; GM module connected |
| Adventure | Seven Dooms for Sandpoint, official Foundry module |
| Target | Chapter 3, C1. Ground Level |
| Formatting reference | Chapter 3, D1. Hall of Threats |

The GM explicitly authorized this edit to the otherwise protected adventure material. The request included `gm_authorized: true` and the current writing-guidance timestamp.

## Steps to reproduce

1. Start with C1’s original HTML, or a test copy retaining the same publisher markup. The live C1 page now includes the fallback described below, so account for that addition when reproducing.
2. Call `get_writing_guidance` and retain its complete `timestamp`. Read D1 and C1 using `read_journal_page`. D1 places a single `<p class="read-aloud">` immediately after its room heading and before the GM explanation. C1 begins with `<h2 class="no-toc">C1. Ground Level</h2>`.
3. Call `get_journal_write_context` for the target page and retain its returned `revision`.
4. Build replacement HTML from the complete C1 source. Preserve the original content and insert the approved narration as `<p class="read-aloud">…</p>` immediately after the existing heading.
5. Call `write_journal` with `action.operation: "update_page"`, the target `page_uuid`, the fresh `expected_revision`, the replacement `content`, `gm_authorized: true`, the guidance timestamp, and a unique valid `request_id`. Omit `mode` to use the documented replacement default.
6. Inspect the error, then read C1 again to check whether the rejected request changed the page.

Relevant portion of the rejected HTML, with the narration and remaining body abbreviated:

```html
<h2 class="no-toc">C1. Ground Level</h2>
<p class="read-aloud">A worn path threads between scattered boulders…</p>
<!-- Complete original GM text follows, unchanged. -->
```

The actual failed request contained the full approved paragraph and the complete original C1 body; this abbreviated excerpt is not a separately tested minimal reproduction.

Page selectors used in the observed case:

```text
C1: JournalEntry.pf2ap20003whistl.JournalEntryPage.03groundlevel000
D1: JournalEntry.pf2ap20003whistl.JournalEntryPage.03hallofthreat00
```

## Expected results

The authorized edit should provide a supported way to:

- Insert the read-aloud paragraph directly after C1’s heading, before the GM notes.
- Apply the publisher’s read-aloud presentation, matching D1.
- Preserve C1’s existing publisher markup, text, links, and inline checks.
- Save the update and allow readback to verify its content, position, and markup.

Supporting this workflow need not mean accepting arbitrary HTML. A narrowly supported class or a structured read-aloud authoring operation could satisfy it.

## Actual results

`write_journal` rejected the replacement with `isError: true`.

Structured error:

```json
{
  "error_code": "INVALID_ARGUMENT"
}
```

Exact accompanying message:

```text
InvalidHTML: Unsupported text attribute, link or style; no event/class/data attributes.; Correct the input and retry.
```

Readback after the failed attempt confirmed that C1’s source was unchanged. The error reported an HTML-validation failure, not `PermissionDenied` or a writing-guidance change.

The rejected request contained both the existing `class="no-toc"` heading and the new `class="read-aloud"` paragraph. The message explicitly rejects class attributes, but does not identify the first offending element. These two class values were not tested separately.

## Impact and successful workaround

The writer cannot round-trip this publisher HTML as part of the requested replacement. Preserving the existing heading resubmits its class attribute, while reproducing D1’s presentation requires adding another class attribute.

A subsequent `update_page` request with `mode: "append"` succeeded when supplied only the following class-free structure:

```html
<p><strong>Read Aloud</strong></p>
<blockquote><p>The complete approved narration.</p></blockquote>
```

The actual append contained the full approved narration, not the placeholder above. The tool returned `status: "updated"`. Readback confirmed that the original C1 source remained intact and the approved paragraph appeared exactly once.

This fallback has two limitations: the paragraph uses a generic labeled blockquote, and it appears at the end of C1. The documented text writer offers replacement or append, with no text insertion operation for placing a fragment after an existing heading. That insertion gap is a separate capability limitation; no unsupported insertion request was attempted.

## Acceptance criteria

- An authorized edit can place the paragraph immediately after C1’s heading and reproduce D1’s read-aloud presentation.
- Existing publisher content and markup remain intact, including `no-toc`, UUID links, and inline checks.
- Readback confirms the paragraph’s correct location, markup, and single occurrence.
- Unsupported active content remains rejected; fixing this issue does not require unrestricted HTML.
- Rejected writes continue to leave the document unchanged.

## Evidence

This report is based on the observed `get_bridge_versions`, `get_writing_guidance`, `get_journal_write_context`, `read_journal_page`, and `write_journal` results from this session. The class-bearing replacement failed; the class-free append succeeded. No new Foundry edits were made to prepare this report.
