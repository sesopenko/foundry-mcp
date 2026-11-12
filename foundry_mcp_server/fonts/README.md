# Preview note font

`DejaVuSans.ttf` is the unmodified DejaVu Sans 2.37 binary from Debian's
`fonts-dejavu-core` version `2.37-8` (`/usr/share/fonts/truetype/dejavu/`).
SHA-256: `57f73e11f51999432bf7ab22ce55b6f945d5eca1bf824404cfa9ec2e3718c84e`.
Its packaged copy is verified before text rendering. No operating-system font
installation is required. The worker uses the adjacent isolated Fontconfig file
and explicitly supplies this fontfile and family to libvips/Pango.

Upstream: [DejaVu 2.37](https://github.com/dejavu-fonts/dejavu-fonts/releases/tag/version_2_37).
The adjacent [license](LICENSE.txt) preserves Bitstream/Arev notices from the
[upstream license](https://github.com/dejavu-fonts/dejavu-fonts/blob/version_2_37/LICENSE).
No TeX Gyre math font is included. DejaVu modifications are public domain;
the base font license permits redistribution with its notices.
