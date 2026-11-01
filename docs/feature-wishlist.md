# Feature wishlist

Feature ideas and requests with work still to do. Wishlist status does not mean
implemented or scheduled. Completed requests are in
[the finished wishlist](feature-wishlist-finished.md).

## How to maintain this wishlist

- When asked to “add to the wishlist” or record a feature idea, add it here.
  Recording a request does not authorize implementation.
- Read both wishlist files before adding an entry. Extend an existing request
  when the idea overlaps; otherwise append a new `## WISH-### — Title` entry.
  Use one more than the highest ID across both files (currently `WISH-012`);
  never renumber or reuse IDs, including after moving entries.
- Include **Status**, **Requested** (the request date as `YYYY-MM-DD`) and
  **Scope**, followed by the user need and desired behavior. Add acceptance
  direction, evidence or design decisions when useful. Preserve the user's
  intent and distinguish proposed behavior from verified implementation.
- Keep unfinished and partially implemented requests here. For partial work,
  state what shipped, link its contract/verification and identify what remains.
- Once the whole request is implemented and verified, record the implemented
  version and link its contract/verification, then move the complete entry to
  `feature-wishlist-finished.md` in ID order. Preserve its ID, request date,
  requirements and evidence; remove it from this file and update any links to
  its old location. Keep relative links valid in both files.
- Reopened requests return here under their existing ID, with the remaining
  work and prior implementation history explained. Keep one entry per ID across
  the two files.

## WISH-012 — Embed images in journal text

- **Status:** Requested; not implemented
- **Requested:** 2026-10-31
- **Scope:** Add image embedding to journal text authoring.
- **Depends on:** WISH-010 (journal writing) and WISH-011 (image browsing).

Let the GM select an existing Foundry image and ask the LLM to insert it at a
specified location in a journal text page, with **source**, **alt description**,
**width** and **height**. Reuse the browser's canonical image source and the
journal reader/writer's page identity; preserve surrounding text and GM writing
constraints. Publish dimension units, defaults/aspect-ratio behavior, bounds and
escaping/source validation. Report unsupported or inaccessible sources explicitly.
This extends text-page HTML; standalone image-type journal pages, uploads and
image generation are not required by this item.

### API feasibility and acceptance direction — 2026-10-31

The documented core [page text schema](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.JournalEntryPageTextData.html)
can store HTML content through the public document updates identified in WISH-010.
Standard HTML `img` provides `src`, `alt`, `width` and `height`; these are HTML
attributes, not invented JournalEntry schema fields. No PF2e-specific mutation
API is needed. Actual Foundry sanitization, attribute retention, rendering and
player asset access remain implementation/live-verification gates; do not claim
that a GM-visible file automatically becomes player-accessible through ownership.

Verify browse → select → embed → read back and render using safe marked fixtures
in the existing test world after offline tests. Check alt text, dimensions,
escaping, inaccessible files, stale pages and unchanged surrounding content.
Apply WISH-010's GM-access, guidance, retry and response-budget requirements.
