# Fixed map-note glyphs

M04a supplies worker-only typography. `map_note_glyphs.rasterize_keys` accepts
1–100 distinct generated ASCII aliases matching `N[1-9][0-9]{0,14}` and returns
private measured `NoteGlyph(key,width,height,image)` records. Each native image
is nonpremultiplied 8-bit sRGB RGBA. There is no caller-selectable text, font,
path or size; journal labels, bodies, UUIDs and Pango markup never enter it.
The glyph rasterizer preserves input order; M04b owns numeric ordering, layout,
leaders, collision/area budgets and recomposition after encoding reductions.

## Font and native contract

The packaged [DejaVu Sans 2.37](../../../foundry_mcp_server/fonts/README.md)
has its own redistribution notices and fixed binary hash. Missing, symlinked,
wrong-size or changed font files fail with `ImageProcessingFailed` before the
native text operation. The worker sets `FONTCONFIG_FILE` before process/native
initialization to a packaged configuration with no system/user font directories
or includes. Fontconfig caches use the existing private worker scratch root.
The file is supplied explicitly along with family `DejaVu Sans` to Pango.

The target is a 16-pixel em: 12 points at explicit 96 DPI, with wrapping disabled
and no automatic box fitting. This does not promise 16 pixels of visible ink.
The actual Pango mask gets a one-pixel transparent border and a 3×3 maximum
filter for the dark `(24,24,24)` outline. White fill is alpha-composited over
that outline without resizing. Antialias coverage is retained. The final box
includes all outlined ink; height above 20 or width above 192 fails instead of
shrinking/clipping the key. A maximum-length alias fits within these bounds.

Primary native evidence:

- [libvips 8.18 text](https://www.libvips.org/API/current/ctor.Image.text.html):
  one-band antialiased masks, explicit font/family, DPI and no-wrap support.
- [Pinned 8.18.7 text source](https://github.com/libvips/libvips/blob/v8.18.7/libvips/create/text.c):
  fontfile admission can warn and continue, which is why fallback is prevented
  through independent byte verification and isolated font discovery.
- [Rank filter](https://www.libvips.org/API/current/method.Image.rank.html) and
  [source-over composition](https://www.libvips.org/API/current/method.Image.composite2.html).
- [Fontconfig configuration](https://fontconfig.pages.freedesktop.org/fontconfig/fontconfig-user.html):
  directory/include discovery and XDG cache paths.

## Private verification boundary

The worker's private `glyphs` operation accepts only `{operation,keys}`. It
creates fixed `glyphs.png` in owned scratch, returns at most 100 size pairs and
compact atlas dimensions/length, and shares existing stdout/request, admission,
RSS, scratch and processing limits. `map_note_glyph_probe.probe_glyphs` verifies
strict JSON metadata and the bounded PNG container after reaping and before
cleanup. No MCP tool, game document or source image is involved.

The atlas is at most 192×2000 pixels and 1,601,536 bytes (bounded read based on
maximum raw RGBA plus PNG overhead). It uses the existing encoder's generated
96-DPI/no-source-metadata contract. Size pairs use strict JSON arrays; booleans,
floats, extra coordinates and out-of-bound geometry are rejected. Neither atlas
bytes nor native image objects appear in repr or public tool results.

## Verification evidence

`test_map_note_glyphs.py` passes 12 tests on the host and 12 in the shipped
application image as UID 10001 (0.960s). Tests cover actual native antialiasing,
white/dark contrast, independent scalar one-pixel outline/alpha equations, exact
ink boxes, repeated real workers, all 100 maximum-length keys, unsafe inputs,
missing/corrupt/symlink fonts, overheight rejection, strict JSON metadata,
resource/time rejection and cleanup. Existing worker8/upload13 checks pass.

Measured sample boxes including outline:

| Key | Width | Height |
| --- | --- | --- |
| N1 | 22 | 14 |
| N12 | 32 | 14 |
| N100 | 43 | 14 |
| N999999999999999 | 163 | 14 |

Docker build and read-only/no-network standalone smoke pass. The runtime image
has no `/usr/share/fonts` directory and mounts no host fonts. Its 2374-byte
sample PNG SHA-256 matches the host exactly:
`16e2e34041c0fdc35c88e5b3142a95270642c8700ad56781eb085d985356b8f6`.
Standalone packaged sample: sampled RSS 37,384,192B, scratch 4096B, 0.13532s;
these are measurements, not raised limits or a universal performance promise.

Two defects were proven with focused failing tests then corrected with the
same tests unchanged: JSON arrays were rejected by strict tuple validation;
atlas default resolution wrote 1000 rather than required 3780 pixels/metre.
Strict JSON size validation and reuse of the existing encoder correct those
respective boundaries. No monitoring or artifact assertions were weakened.

Exact packaged unit command:

```bash
docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=128m --user 10001:10001 --volume /home/sean/src/github.com/sesopenko/foundry-mcp/tests:/checks:ro --entrypoint python foundry-mcp-image-preview-check:local -m unittest discover -s /checks -p test_map_note_glyphs.py -v
```

Only tests were mounted read-only. No application override, game data, live
fixture, new Foundry instance or publication was used. Final annotated images
and target-client readability remain separate M04b/M05/M06/14b requirements.
