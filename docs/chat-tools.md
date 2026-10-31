# Chat reading and sending

WISH-006 and WISH-007 are included in v2.4.0.
Four tools use explicit Pydantic request/response schemas at the existing FastMCP
boundary. Unknown inputs and conflicting selectors are rejected before RPC.
Chat requires a connected, ready GM on core 14; the writing-guide lookup also
works without Foundry. No deletion or clearing operation is exposed.

## Read history and poll

Call `read_chat_messages` with `{}` or `{"request":{}}`. Defaults: ten entries,
8000 compact UTF-8 JSON bytes. Bounds: 1–100 entries, 2000–48000 bytes.

| Response field | Meaning |
| --- | --- |
| `messages` | Entries with `id`, `timestamp`, `author`, `speaker`, `whisper`, `blind`, `names_truncated`, `content`, `content_available_separately` |
| `cursor` | Opaque continuation, returned even for empty history; copy unchanged |
| `has_more` | More visible content remains after this page in this observation |
| `scope` | `loaded_visible_history`; no claim about archived/unavailable history |

`id` is a ChatMessage document ID, not a UUID/name. `timestamp` is stored
milliseconds. `author` has nullable `id`/`name`; a deleted author may be absent.
`speaker` has nullable `actor`/`scene`/`token` IDs and `alias`, separate from the
author. Names/aliases are clipped to 128 Unicode characters with
`names_truncated=true`; IDs remain exact. `whisper` contains recipient User IDs;
`blind` is the stored flag. Both public `visible` and `isContentVisible` must
permit the connected GM to read a message. Empty results mean no newer loaded
visible content, not proof that no messages exist elsewhere.

Pass `{"request":{"cursor":"<returned cursor>"}}` for another page. After
`has_more=false`, reuse that cursor to poll for arrivals without replaying
history. Alternatively, `{"request":{"after_id":"<returned message id>"}}`
starts exclusively after an existing message. The selectors cannot be combined.

The browser keeps an ID-only observation sequence: the initial batch sorts by
timestamp then lexical ID; newly visible/loaded batches append, each sorted the
same way. Equal-timestamp and backdated arrivals therefore stay reachable.
Already observed edits do not replay/reorder messages; content is current at
each read, not a historical snapshot. Messages created and removed between
observations cannot be recovered. More than 50000 observed IDs yields
`HistoryTooLarge`, not silent truncation.

Cursors survive anchor deletion and changed page bounds. Browser reload, world
or GM changes invalidate them: on `InvalidCursor`, restart history or use an
existing `after_id`. Missing/invisible IDs yield `MissingAnchor`; saved cursors
remain usable within their original session. An oversized identity yields
`ResponseTooLarge`: increase `max_bytes`. No anchor is silently substituted.

## Oversized content

An oversized first entry returns its identity with `content=null` and
`content_available_separately=true`; pagination advances past it. Call
`read_chat_message_content` with `{"message_id":"<id>","offset":0}`.
It returns `message_id`, exact stored `content`, SHA-256 `revision`, and
`next_offset` (null when complete). Fragments contain at most 1000 UTF-16 units,
never split surrogate pairs, and fit 8000 JSON bytes. Pass returned offset and
revision unchanged; concatenate fragments. Nonzero offsets require revision.
On `StaleContent`, discard accumulated fragments and restart at zero without
revision. Missing/invisible content yields `DocumentNotFound`.

Stored HTML may differ from submitted notation. On14.369/PF2e8.6.1,
`[[/r 1]]` becomes a persisted HTML link labelled `1`; check notation remains
source for later enrichment. Readers preserve the stored representation and
never reverse-convert it or render it again.

## Send HTML

Example `send_chat_message` input:

```json
{"request":{"request_id":"unique-send-key-001","mode":"self only","content":"<h2>Notice</h2><p><strong>Keep watch.</strong></p>"}}
```

Author is always the connected GM. Audience and speaker are separate:

| Exact `mode` | Audience | Speaker/presentation |
| --- | --- | --- |
| `Public as User` | Public | GM name, OOC |
| `private to game masters` | All GM users, including inactive GMs | GM name, OOC |
| `blind to game masters` | GM users, `blind=true` | GM name, OOC; a GM author still sees it |
| `self only` | Connected GM only | GM name, OOC |
| `public as character` | Public | Selected character name/Actor ID, IC |

Only the character choice accepts/requires `actor_id`. Discover named world
characters with `search_actors` (`types:["character"]`) or `get_actor_tree`;
use `nodes[].identity.id`, not UUID/name/token/compendium ID. Missing actors
yield `DocumentNotFound`, denied OWNER access `PermissionDenied`, other types
`UnsupportedCharacterType`. No character assignment or token is changed.
Discovery currently requires PF2e; chat otherwise uses core APIs without system
interpretation. More than 100 GM recipients is rejected before creation.

Success returns `id`, `timestamp`, `author`, `speaker`, `whisper`, `blind`,
`names_truncated`, `mode`, `request_id`, within 8000 bytes. Use the ID with either
reader. Content and the guide are absent; read back persisted formatting if needed.

### HTML and inline source

Non-whitespace input is bounded to 16000 UTF-8 bytes. Allowed tags:

```text
p br h1 h2 h3 h4 h5 h6 div span strong b em i u s sub sup blockquote
pre code ul ol li table caption colgroup col thead tbody tfoot tr th td hr
```

Only `style` is generally accepted, limited to literal values for `text-align`,
`font-size`, `font-family`, `font-weight`, `font-style`, `text-decoration`,
`color`, `background-color`. `th`/`td` additionally accept `colspan`/`rowspan`
1–100. Images, links, scripts, events, class/data attributes and unsupported
styles yield `InvalidHTML` before creation. Browser parsing normalizes markup;
Foundry sanitizes the persisted HTMLField. This supports the requested editor
categories without promising arbitrary editor HTML round trips.

PF2e check/damage/embed/deferred-roll source from the
[inline builders](pf2e-inline-builders.md) is accepted as text. Immediate inline
rolls are rejected because rendering could evaluate them. The writer does not
click links, evaluate dice or infer Actor/target mechanics. Foundry/PF2e handles
destination enrichment and may change stored notation. Publisher embed contents
can themselves include formatting/images; image authoring is outside this tool.

### Retry behavior

Use a unique 16–64 character `request_id` of letters/digits/hyphens. Identical
concurrent attempts coalesce. Up to 1000 attempts are retained per browser,
including uncertain creation failures. Persisted flags also reconcile loaded
messages after reload using a digest of world, author, mode, original content
and Actor. Changed input under an existing key yields `RequestConflict`.

This is not an exactly-once guarantee across deleted/archived messages or
separate browser contexts. A timeout/disconnect may mean creation completed:
inspect chat and retain the same key before considering a retry. Never issue a
fresh key merely because acknowledgment was lost. A browser cannot establish
absence of a prior send when its message is no longer loaded. `SendLedgerFull`
requires reconciliation before reloading. The server never automatically resends.

## Writing guide

`get_pathfinder_writing_style_guide` takes `{}` and returns `text` plus
`attribution_status`, preserving the supplied four paragraphs verbatim. It is
separate from PF2e wiki inline syntax and absent from send responses/discovery.

Research points to *Core Rulebook*, “Format of Rules Elements,” p.17
([secondary transcription](https://pathfinder2.dragonlash.com/rules/introduction/format-of-rules-elements/)).
Wording/punctuation differ from the supplied passage; exact edition-level
attribution remains unverified, reported as
`user_supplied_publication_unverified`. The passage's p.628 reference belongs to
its original book, not every Pathfinder publication.

## Evidence and compatibility

Grounded Docs matched `foundry-vtt@14` and fetched official documentation on
2026-10-30. Public dependencies are documented on
[ChatMessage](https://foundryvtt.com/api/v14/classes/foundry.documents.ChatMessage.html):
`visible`, `isContentVisible`, `author`, document/schema fields, `toObject(true)`,
`getFlag`, and configured `ChatMessage.implementation.create`. The current
schema uses `author`; the older ChatMessageData interface's `user` field was
not used. Speaker data follows
[ChatSpeakerData](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.ChatSpeakerData.html),
styles follow
[CHAT_MESSAGE_STYLES](https://foundryvtt.com/api/v14/variables/CONST.CHAT_MESSAGE_STYLES.html),
and server sanitization follows
[HTMLField](https://foundryvtt.com/api/v14/classes/foundry.data.fields.HTMLField.html).
Tools use no private methods, DOM scraping or monkey-patching.

Live acceptance: Foundry14.369/PF2e8.6.1, existing localhost `test` world.
Other14 builds/systems remain untested; core outside14 is rejected. The module's
minimum13 does not imply chat support on 13. Offline tests cover the core-only
non-PF2e boundary and denied access.

`scripts/chat-live-check.py` passed in41 calls/0.51 seconds under a 60-call,
180-second cap. Actual MCP discovery/invocation verified all five choices,
recipients/blind flags separately from author/speaker, IC/OOC presentation,
connected-GM visibility, no recorded roll results, rich HTML/invalid HTML,
duplicate reconciliation, exclusive anchors, complete incremental paging,
empty polling, exact oversized reconstruction, guide lookup, invalid mode and
missing character. Cleanup removed exactly six marked messages and one marked
character; no existing documents changed. Player-session visibility was not
separately automated; hidden-content behavior is covered by public visibility
getters and deterministic permission tests.

Offline regression also covers equal/backdated arrivals, deleted anchors,
stale browser cursors, edits, Unicode, byte budgets, clipped names, concurrent
retries, persisted conflicts, denied characters, unknown inputs and typed
output validation. A focused regression reproduced the false failure caused by
expecting literal roll notation in persisted HTML before correcting that test.
Final `./scripts/test.sh` passed both suites, including632 JavaScript tests.
The sandboxed run stalled in an unchanged evaluation test; that test and the
full runner passed outside sandbox isolation without a code workaround.

## Payload measurements

Compact UTF-8 JSON bytes are not billed tokens. No model calls were used.
The released baseline has no chat API; this is a new capability, not a claimed
optimization of an older chat endpoint.

| Scenario | Calls | Bytes/coverage |
| --- | ---: | --- |
| Final live catalog | 1 | 30 tools, 138262 bytes; four chat tools 12388 bytes |
| Default initial read | 1 | 6117 bytes, five existing messages |
| Repeat full history after five arrivals, limit 2 | 5 | 12121 bytes, ten messages |
| Incremental from saved boundary, same limit 2 | 3 | 5814 bytes, five new messages only |
| Empty poll | 1 | 194 bytes |
| Five send results | 5 | 303/330/327/316/344 bytes |
| Oversized default page | 1 | 492 bytes, identity/separate-content indicator |
| Exact oversized expansion | 12 | 12760 bytes, reconstructed exactly |
| Explicit guide lookup | 1 | 1185 bytes |

The incremental comparison omits five previously read messages; it is not
equal-content compression. Final catalog/schema discovery and default read/guide
invocation passed a separate three-call read-only HTTP check after the final
response constraints were loaded. Focused in-memory discovery measured 12391 bytes
for the four chat tools (minor transport/schema serialization differences).
Refresh client discovery after installing matching server/module source.
