# Uploading images into Foundry User Data

Version 3.3.1 adds `create_image_directory` and `upload_image`. They use the
existing MCP authentication and ready GM browser on Foundry14, with no new
environment variables or endpoints. Deploy matching server/module builds,
refresh the GM browser and refresh client discovery. These tools work across
game systems; Core Data and S3 remain read-only through them.

## Workflow

1. Use `browse_journal_images` to select an existing User Data directory. Current
   location and directory nodes expose `capabilities` containing `can_upload`,
   `can_create_directory`, and `reasons`. These combine public FilePicker policy
   with our User Data-only scope; server permissions can still reject a write.
   User Data root permits folder creation but not uploads.
2. If needed, call `create_image_directory` with `directory` (existing parent,
   empty for root) and `name` (one child). No recursive creation or privacy changes.
   The receipt returns `status:created|already_exists`, `world_id`, `user_id`,
   `location`, `capabilities` and `next_call` for browsing the folder. Reuse occurs
   only after verifying an existing directory; a failed browse proves no absence.
3. Call `upload_image` with `file`, `directory`, `filename` **without extension**,
   and optional `overwrite` (default false).
4. Pass the returned `image` directly to `write_journal`'s `embed_image` action.
   No additional image discovery is required. Normal writing guidance, permission,
   page-revision and current image membership/loading checks still apply.

```json
{
  "file": {
    "download_url": "https://image-host.example/temporary-authorized-image",
    "file_id": "opaque-chatgpt-file-id"
  },
  "directory": "Generated portraits",
  "filename": "Goblin scout",
  "overwrite": false
}
```

These URL/ID values are placeholders. ChatGPT supplies them through tool metadata
`_meta["openai/fileParams"]=["file"]`; never construct an endpoint from a file ID.
The file schema declares four string properties: required `download_url` and
`file_id`, optional `mime_type` and `file_name`. IDs are ChatGPT identities, not
Foundry document IDs. Supplied MIME/name hints do not control the saved file.
Actual decoded content adds `.jpg`, `.png`, or `.webp`.

Names allow spaces and Unicode, at most200 characters/240 UTF-8 bytes, without
paths, controls, reserved characters or leading/trailing whitespace. Filename
stems ending in a supported image extension are rejected instead of rewritten.
Directories are existing source-relative selectors, up to2,048 characters;
neither tool accepts a host filesystem path or a source override.

## Image validation and transfer

Python downloads and fully validates static JPEG, PNG or WebP using pinned
Pillow13.0.0. Limits:10MiB,8,192 pixels per axis,32 million pixels total.
Malformed, animated and unsupported images fail. Decoded content determines MIME;
HTTP/ChatGPT hints are advisory. Original bytes are preserved without conversion
or metadata stripping.

Retrieval allows HTTPS port443, public addresses and up to three redirects.
Every destination is checked; connections pin a validated address while TLS
authenticates the original hostname. No ambient proxy, cookie or application
credential forwarding. Download has a30-second process deadline; decoding has
a10-second deadline and memory/CPU limits. Workers are killed/reaped and staging
removed on completion, failure or cancellation. Deployment needs outbound DNS/HTTPS.

One image operation runs at a time. Validated bytes cross the existing authenticated
GM WebSocket as one private base64 payload (up to about14MiB); they never enter an
LLM tool result. Proxies must permit that frame size. Existing browser-to-server
response limits are unchanged. Upload has a60-second RPC deadline; allow roughly
120 seconds for the whole tool call including retrieval and decoding.

The browser uses public FilePicker `implementation`, `sources`, `activeSource`,
`canUpload`, `canCreateFolder`, `browse`, `createDirectory`, and `upload`, plus
standard browser File/fetch/crypto/Image APIs. It rechecks the exact socket,
world, GM and permissions before mutation. An uncached read verifies saved bytes,
checksum and image loading before success. Native listings load a complete
directory; more than10,000 paths/2MiB is rejected after loading.

Successful receipts are below8,000 compact JSON bytes: `status:"uploaded"`,
`world_id`, `user_id`, `filename`, `mime_type`, `width`, `height`, `size_bytes`,
`sha256`, `overwritten`, and `image:{source:"data",directory,src}`. Preserve the
whole image record; `src` is a file location, not a UUID. GM loading does not
establish player access. Signed source URLs and bytes are excluded from results
and diagnostic logs.

## Replacement and recovery

`overwrite:false` rejects an existing destination with `FileExists`; choose
another name. `overwrite:true` **permanently replaces the exact file**, without
backup or undo. Existing journals/tokens using that path may display the replacement.
Those documents are not modified. Format-derived extensions mean a JPEG upload
does not replace a same-stem PNG.

Tool writes are serialized and checked immediately before upload. Foundry's public
API offers no atomic create-only operation: external writers can race the
browse/upload interval. No undocumented overwrite flag or filesystem bypass is used.

Timeouts, disconnects, failed verification or invalid receipts can occur after
storage. `upload_outcome_unknown` returns `candidate_path`, `world_id`, `user_id`,
`error_code` and `message`, not a successful image selector. Inspect the
destination before retrying, especially replacements. There is no automatic
retry or rollback. Folder timeouts similarly require browsing the parent.
`Busy` permits a later retry; `BrowseFailed` is missing/denied/unavailable, not
proof of absence. Download failures need a fresh URL or smaller valid image.

## Verification and remaining ChatGPT acceptance

The user confirmed that the Python-generated checkerboard rendered in the
Foundry14.369 test-world journal. That experiment sent bytes over WebSocket,
saved them using public `FilePicker.upload`, and verified identical SHA-256.

Offline tests cover actual MCP discovery/invocation, strict typed inputs/outputs,
file metadata, isolated decoding, HTTPS address pinning, redirects/limits,
secret-free errors, permissions, collisions, replacement, concurrency and
disconnects. The full suites also check module packaging and production discovery.

`scripts/image-upload-live-check.py` uses at most35 calls/180 seconds plus bounded
journal cleanup in the existing localhost test world. Public sample images go
into a unique marked folder and the upload selector is embedded directly.
Its temporary journal is deleted; image folders remain for manual cleanup because
there is no public FilePicker deletion API in use. Existing game assets are never
overwritten. `scripts/journal-images-live-check.py` measures default, filtered,
expanded and complete paginated browsing. JSON bytes are not billed tokens.

After release, test a ChatGPT-attached image, a newly generated image without
reattachment, and an earlier generated image. Record release/client/model, prompt,
actual invocation, result and stored path. Generated-image handoff is still a
ChatGPT acceptance gap; manual reattachment is a separate assisted result.

References: [OpenAI file inputs](https://developers.openai.com/plugins/reference),
[Foundry14 FilePicker](https://foundryvtt.com/api/v14/classes/foundry.applications.apps.FilePicker.html),
[Pillow validation](https://pillow.readthedocs.io/en/stable/reference/Image.html).

## Verification record — November 1, 2026

Both full offline suites passed after the final behavior changes (715 JavaScript
tests; the Python suite retains one pre-existing skip). Actual Basic/OAuth HTTP
discovery tests verify preservation of `openai/fileParams` alongside OAuth
security metadata. This is offline OAuth coverage, not a new login/refresh test.

On Foundry14.369, the successful live upload verifier used19 calls plus discovery.
It created/reused a Unicode folder, accepted real PNG/JPEG/WebP bytes despite an
incorrect supplied MIME hint, rejected an existing filename by default, replaced
only its own marked file with explicit overwrite, and embedded the returned
selector directly in a new journal. Journal cleanup succeeded; console errors
were zero. Three marked `mcp-upload-verify-*` directories remain for manual file
cleanup, including the two earlier diagnostic runs; the user's checkerboard
journal is retained separately.

The first two live attempts stopped after five calls each. FilePicker returns
URI-encoded file **and directory** paths. Focused tests reproduced the failures
before correcting comparisons and preserving exact browser-returned selectors.
Regression coverage also prevents a failed native upload from being counted as
successful merely because an older destination has identical bytes.

| Successful scenario | Compact JSON bytes | Complete |
| --- | ---: | --- |
| Create directory receipt | 337 | Yes |
| PNG upload, Unicode directory/name | 431 | Yes |
| Explicit overwrite receipt | 430 | Yes |
| JPEG upload receipt | 387 | Yes |
| WebP upload receipt | 389 | Yes |
| Journal embedding receipt | 573 | Yes |

Before registering the upload tools, actual discovery measured41 tools/250,770
bytes (the directory capability fields were already present in this baseline).
Final discovery measured43 tools/262,218 bytes; the two new tool records were
3,730 and7,153 bytes. One final discovery-only call verified the published
filename byte bounds and file metadata after the prose update.

The browser verifier passed before and after, using19 calls plus discovery each.
Equal-content public SVG scenarios were unchanged: default page2,096 bytes,
explicit100-entry expansion15,051 bytes, literal selection751 bytes, complete119
images across12 pages25,373 bytes. User Data root grew from2,131 to3,106 bytes
because the experiment added folders; that is not an equal-content comparison.
This feature adds functionality, not a claim of token savings. No provider token
usage was measured. ChatGPT-generated image handoff remains the release-time
user acceptance test.
