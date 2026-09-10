# Public-site asset record

`og.png` is a 1200 x 630 social preview generated specifically for Locus with
OpenAI ImageGen on August 24, 2026. It contains no third-party source image,
private room capture, account data, or product screenshot. SHA-256:
`4765b28b4dfdf666ea78ca5988b8c8d22d7a60839bf4d75dab3d8f3a9222bc49`.

This provenance record does not declare an open-source license for the image,
this public support repository, or the private Locus application.

`app-icon.png`, `favicon.png`, and `apple-touch-icon.png` are flattened and
resized exports of the production `LocusAppIcon` image stack from private Locus
source commit `5e6a640cf7bf2144296e8bfa6f2f9f96c9d2c824`. They are product identity
assets, not a grant of permission to reuse the Locus mark.

`download-on-the-app-store.svg` is the unmodified, preferred black English
badge supplied by Apple through its
[App Store marketing tools](https://tools.applemediaservices.com/api/badges/download-on-the-app-store/black/en-us?size=250x83),
downloaded August 30, 2026. It links to the canonical Locus product page at
`https://apps.apple.com/app/id6802168265` and is used under Apple's
[App Store marketing guidelines](https://developer.apple.com/app-store/marketing/guidelines/).
SHA-256: `a26fc5b38380272c92e9019a2eb8b45542a66814b3e2b203772db8904b9fb99f`.

The original four JPEG files in `screenshots/` are 1920 x 1080 web exports of
3840 x 2160 Simulator masters. Three remain from the approved Locus 1.0 launch
media; `place-picker.jpg` was refreshed on September 10, 2026 for the current
Places layout. They contain only Locus UI and built-in content:

- `place-picker.jpg` from master SHA-256
  `8b34e3f9840fc111e14f70c9130c16ca4f9c8c5e41d14354d47c46c6c90a5c78`;
- `virtual-space-desk-wide.jpg` from master SHA-256
  `dcebf5db181f1b66e64ad2d1056d3f38a7dd9791314b1bcacf75a249e17ea5cb`;
- `virtual-space-room-turn.jpg` from master SHA-256
  `1b596f9ac5cc31959e8422eef2e84dcb559e712502d89f1da05e219309d5a78b`;
- `imports-virtual-space.jpg` from master SHA-256
  `a3c34eac8b4f8795343d07aa0c2cb517014c7f609857c053d05666375d2622bd`.

These images are visual records of app layout and deterministic simulator
states. They are not evidence for physical room tracking, passthrough,
occlusion, presence, performance, or comfort on Apple Vision Pro.

## September 10, 2026 tutorial UI refresh

The current tutorial screenshots were captured at 3840 x 2160 in Locus Dev on
visionOS Simulator 26.5 from private Locus source commit `d85c48fc`. The app
loaded the published `space.atrium-loft` and
`destination.snowbound-forest-paths` packages. Website files are uncropped
1920 x 1080 JPEG exports made with `sips` at quality 90; there is no
compositing, generative fill, or image relighting.

The after frame uses the same runtime settings as Quick Settings: a +35° View
direction offset and Add Sunlight enabled at the product's default 5,000 lux.
A DEBUG-only launch fixture staged those session values so the two captures do
not depend on unreliable Simulator pointer input. It did not alter the
panorama, Room, or production UI and is not part of this public repository.

| Website file | Source PNG SHA-256 | Website SHA-256 |
| --- | --- | --- |
| `screenshots/place-picker.jpg` | `8b34e3f9840fc111e14f70c9130c16ca4f9c8c5e41d14354d47c46c6c90a5c78` | `15049a2e73ec0dd65c2963425919cd45c00b5791d246c5f0ac9b8b1338534dc0` |
| `screenshots/snowbound-before.jpg` | `d6b987a1b3fd0aecb2824aacd8332ca78e68aaf6bbb8104cb7a76927ae6b85c1` | `e71574054fecc85d6c5b6b4fbaafb17fa762ea46c0d5d622653537a6895c56e1` |
| `screenshots/snowbound-turn-view-sunlight.jpg` | `bb6efc69c3cdcdd3fde1bca90d53666b644f72af493dc968f78f075f4ae24192` | `02a377f22ebf8ee221adf271736db5f062a050f75a38bf49023f779cc0bec28b` |

These are Simulator illustrations of current layout and settings behavior, not
physical Apple Vision Pro validation of placement, lighting, or comfort.

## Promotional website media

The files in `promo/` are public-site derivatives of the authentic Locus
promotional packages produced on August 31 and September 1, 2026. The Dropbox
source roots are `Locus Demo/Promo Draft 1` and `Locus Demo/Promo Draft 2`.
Product pixels are native Locus Simulator captures or physical Apple Vision
Pro Developer Capture recordings. No ImageGen,
generative fill, synthetic reflection, relighting, replacement exterior,
invented UI, or competitor screenshot appears in these files.

`locus-promo-31s-v2.mp4` is the previous website cut, retained for existing links. It moves the complete
eight-second **Your desk, virtually.** section to the opening, followed by the
original opening, View change, Browser, open-wall, and end-card sections. No
shot, title, or product pixel was otherwise changed. It is a silent 31-second,
1920 x 1080, 30 fps H.264 High Profile Level 4.0 encode with 8-bit 4:2:0 Rec.
709 pixels, two-second keyframe intervals, and fast-start layout. Its source
rough-cut SHA-256 is
`2c46ed54989a0eb8eadbc363e9cc9fe1eb7d28e774b7a25c1d5a5a5daa318dcd`;
the website derivative SHA-256 is
`7fe19092d03a2e43cdf795ee0f6c7f8c1667e33da439324b17f5b4699865117a`.

The original `locus-promo-31s.mp4` remains available so previously published
direct URLs do not break. It is a silent 1920 x 1080, 30 fps H.264 High Profile,
Level 4.0 web encode of `Locus-Promo-Rough-Cut-v1.mp4`. It uses the `avc1`
sample entry, 4:2:0 8-bit pixels, a two-second keyframe interval, and a
fast-start MP4 layout for iPhone browser compatibility. The source SHA-256 is
`121543db58691469fd02e97d9da684b1654ab76a89d55569c30ec24b2afb9fcd`;
the web derivative SHA-256 is
`aeb2f37eb4e5e365cde6e4c534f819abc2bca68189861c243d901754444a8e95`.
`locus-promo-poster.jpg` is a 1920 x 1080 frame from that web encode, SHA-256
`484899e0aa9ce36ab301ab2d3292a12f95b558e88f4f824a86de88e7724fe49c`.

The six 1920 x 1080 JPEG stills are downsampled web exports of the frozen 3840
x 2160 PNG layouts. Source and derivative SHA-256 values are:

| File | Source PNG SHA-256 | Website SHA-256 |
| --- | --- | --- |
| `still-01-change-view.jpg` | `7d4c34fb5c98b0b610604193985f62db4f4a3f7898ca79c1966a55715b3b1c37` | `91955d07b15323bf04819ab0b257820d9a93ee2ffb69a76ce848ff15016f190b` |
| `still-02-desk.jpg` | `fcf6d1054e3a47c95b2736e6c2cefe3c3f42e387f6d7dd40837a055b51d24758` | `2f995e767ed0d4b5a89d063df961c66ad2c9f8ad42d8c8e588652db7db49fc73` |
| `still-03-browser.jpg` | `247fbc8fa598ba07b5b489d28daf5c932e97b9feb31f902d2c8029e895bc4046` | `42352f05732727e173d696add5f44f938c392f185c2b948fb85da29da3ac0f28` |
| `still-04-walls.jpg` | `5bc102061239a3fac2fb7146e0f269668d7eb901986420f60af80d354dbf0df0` | `cf52c51dd6fdbbfeafcbacbaf65f368532b5895a165cf0b30cbb67e0c3c327b6` |
| `still-05-own-view.jpg` | `2d78c16ae2d19ddd135ea4afc8fc499ce183ae0252d4fa963cdac3b916e00055` | `a7772cc62b43eb8ce618c5bed69d06157883d1669b41c3bff6a43a0a8ac82bbe` |
| `still-06-import-room.jpg` | `c20d866face6a97cf532ffdfc35f9cdc3c7d9c7cbe0e73cf132d92661adffa26` | `6989b8c373eae26ba82f8578f022d4ff0041e8fe507b750be034c10a1a1900e5` |

The Browser media shows Locus's shipped default favorites and no visited-site
content. The View-import still uses Poly Haven's Hochsal Forest panorama,
which Poly Haven publishes under CC0. The browser page itself is obscured by
the native Locus `Save as View` sheet. These are product demonstrations, not
endorsements by the displayed services.

The physical desk shot demonstrates keyboard passthrough provided by visionOS;
keyboard passthrough is not a Locus feature.

These website assets are not evidence that an App Preview video was submitted
or approved in App Store Connect. Device capture supports the visible desk and
Room Portal demonstrations only; it does not establish broader performance,
comfort, or unshown people-visibility claims.

## Locus 1.1 What's New video

`locus-1.1-whats-new-33s.mp4` is the owner-approved Locus 1.1 What's New
master (Draft 7, revision 7, approved September 3, 2026), copied byte for byte
from the Dropbox launch-media root `Locus Launch Media/v1.1.0/video/`. It is a
silent 33.6-second, 1920 x 1080, 30 fps H.264 High Profile Level 4.0 encode
with 8-bit 4:2:0 pixels and a fast-start layout. SHA-256:
`a8eb882e95cf22df34b75be2737eb5cee53b1596a645572afabee88f23decb6b`.

Every product pixel is a native Locus Simulator capture of the development app
built from private Locus source commit
`091372309b1c7642cccbe8477061c55716509daf`, recorded as one continuous take in
Horizon Atelier with the Autumn Hill View and the Tokyo Skyline at Night View.
The Tokyo panorama is an EnterLocus-published Locus Skies image (CC BY 4.0).
Title cards and the end card are rendered overlays; no ImageGen, generative
fill, invented UI, or competitor material appears in the video.

`locus-1.1-whats-new-poster.jpg` is a 1920 x 1080 JPEG export of the
17.0-second QA frame of that master (Room Lights on over the Tokyo night View),
source PNG SHA-256
`f7c0749b50778e3cd2434f8002b3f7a764f30644b67f581ce08b2de57ad2e763`, website
SHA-256
`2d6138f23bab8209ef0b45ebf5675bb07543f52ff877614206c7dc1a18a2d597`.

These files are Simulator evidence of Locus 1.1 layout and behavior. They are
not physical Apple Vision Pro validation and not evidence that an App Preview
video was submitted or approved in App Store Connect.

## Locus 1.1.1 launch media

The active homepage video is `locus-1.1.1-promo-30s.mp4`, copied byte for byte from the approved 1.1.1 1080p promotional master. It is 30 seconds, 1920 × 1080, 30 fps H.264 Level 4.0 with fast-start layout. The 1.1 What’s New video remains its approved original. Previous media URLs remain available.

Six screenshots are 1920 × 1080 Lanczos JPEG web exports of the native 3840 × 2160 PNGs in `Locus Launch Media/v1.1.1/screenshots/`. There is no crop, compositing, or lighting adjustment. Captured in Locus Dev on visionOS Simulator 26.5 from source snapshot `6376a2b6`; these are marketing captures, not physical Vision Pro validation. The video retains its existing physical desk and Room Portal sections.

| Website file | Source SHA-256 | Website SHA-256 |
| --- | --- | --- |
| `screenshots/saturn-winter-garden-v111.jpg` | `1eefc1ebd7319decc87714effc469783f39533d1d1c669b8a8b865879c5bfc99` | `c22f2a95cd80a7b0580b70c4286205381617c23805242edfdccebacf565c9a55` |
| `promo/still-01-canyon-v111.jpg` | `c6bdf118ea9fc65751fd9ee4fb2431ea183c9e80c1934175f139954a786e595f` | `e9293663a186eaaec5a5289f6584176831383e0d9eaa798b7e5b12e0516b9b5c` |
| `screenshots/milky-way-winter-garden-v111.jpg` | `4d524f68d7f0b64003bec4958dea31cdc8ec0a9359a93073ab5871cfcadc4878` | `5a119ab993deb7945a8bbb1984d971da8c8e080c4017e206c9e23dcb4cf2426a` |
| `promo/still-03-browser-v111.jpg` | `94ced152f2911f786eea9c3b19f40978387978ccdd04c0204a9799e0e2fc3b30` | `bc68bd8b7f86b4b4badf2ab31c5d69eb2089ca7938c43791852f89360a60148e` |
| `promo/still-06-room-lights-v111.jpg` | `b1e0e365fba1113f95683becbf42b200d74edde304b544b5cafaa7fa71b3b0ef` | `eba256f879e02c453ec441fdf013e3096053fe66b8e0a06bed7a911cd96ea344` |
| `screenshots/floating-islands-winter-garden-v111.jpg` | `52859f373754f0177d3f214566309f6575a0b8a7665cbfbf59872a9b517b10c6` | `cc8a547049876800f364d1baaf307dd720d0c5cba6a23bf90283626f12f681bb` |
| `promo/locus-1.1.1-promo-30s.mp4` | `96f14c7771e288a4f7e7b452971f2740f112e03430e544eb630b97ef9dee14a7` | `96f14c7771e288a4f7e7b452971f2740f112e03430e544eb630b97ef9dee14a7` |
