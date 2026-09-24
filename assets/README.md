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
source roots are `Locus Demo/Promo Draft 1` and `Locus Demo/Promo Draft 2`
(moved on 2026-09-11 to `Locus Launch Media/v1.0.0/working/Promo Draft 1` and
`…/Promo Draft 2`).
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

Since September 11, 2026 the homepage's "New in Locus 1.1" section embeds
the Locus 1.1.3 promo instead (see "Locus 1.1.3 launch media" below). This
master and its poster stay published at their original URLs.

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

## Locus 1.1.3 launch media

`locus-1.1.3-promo-24s.mp4` is the video embedded in the homepage's
"New in Locus 1.1" section (the hero keeps the 1.1.1 promo above). It is
copied byte for byte from
`Locus Launch Media/v1.1.3/video/Locus-1.1.3-Promo-1080p-24s.mp4`
in Dropbox. (The original working folder for this cut,
`promo-video-2026-09-11`, moved to
`Locus Launch Media/v1.1.3/working/promo-video-2026-09-11/` and now holds only
source material, not the delivered file.) It is 24.000 seconds, 1920 × 1080,
30 fps H.264 High Profile Level
4.0, AAC-LC 192 kb/s stereo, with fast-start layout. It carries the app's own
ambient sound; the What's New card embeds it muted with `controls` shown and
no autoplay, so sound stays opt-in for anyone who unmutes it.

Every product pixel is a native 3840 × 2160 visionOS Simulator 26.5 capture of
Locus Dev built from private Locus source commit `12b75d8`, recorded with a
capture-only DEBUG camera-sweep patch that is not part of the product code.
The edit shows three animated Views, each inside one full loop cycle, followed
by the retained Locus end card from the 1.1.1 master: Floating Above a Seaside
Cliff 1.2.0 in Winter Garden, Emerald Grotto 1.5.0 in Courtyard Gallery (View
brightness raised +1.0 EV through the app's own brightness setting, not a
capture-time override), and Hidden Oasis in a Desert Canyon 1.5.0 in Atrium
Loft. Emerald Grotto and Hidden Oasis are Dev-only animated View candidates at
the time of writing; they are not yet in the shipping catalog.

The audio track is the app's own ambient mix, captured live from the Simulator
for each View — ocean waves and seabirds for the seaside cliff, the grotto
waterfall and forest birds for Emerald Grotto, and the canyon waterfall and
birds for Hidden Oasis — normalised in the edit. There is no music, narration,
generative fill, invented UI, or competitor material.

`locus-1.1.3-promo-poster.jpg` is a 1920 × 1080 JPEG export of the
8.80-second frame of the companion 4K App Preview master
(`Locus Launch Media/v1.1.3/media-release/app-preview/01-Locus-1.1.3-App-Preview-4K-24s.mp4`,
same capture session), showing the
Winter Garden sunset with the garden table and plant in the foreground and no
caption on screen. Source PNG SHA-256
`4942cd182dce1fa3c65be0f9dd7f231f8cd43a2dde5c370b648ac5f670bfaa0c`, website
SHA-256
`4131719643adafa062d50174d6ba88247b739e14a2fdfbb14e984f4de6413794`.

| Website file | Source SHA-256 | Website SHA-256 |
| --- | --- | --- |
| `promo/locus-1.1.3-promo-24s.mp4` | `df39fede8e8c44ac18050df033e88908b88c22d1badbcda912aa7c730e58e9cb` | `df39fede8e8c44ac18050df033e88908b88c22d1badbcda912aa7c730e58e9cb` |
| `promo/locus-1.1.3-promo-poster.jpg` | `4942cd182dce1fa3c65be0f9dd7f231f8cd43a2dde5c370b648ac5f670bfaa0c` | `4131719643adafa062d50174d6ba88247b739e14a2fdfbb14e984f4de6413794` |

`locus-1.1.5-poster.jpg` is the poster for the Locus 1.1.5 release film and the
What's New card: a 1920 × 1080 JPEG export (Lanczos downscale) of the native
3840 × 2160 visionOS Simulator capture of Winter Garden Breeze from its Sofa
Center seat with Sunlit Cloud Walkway and no UI on screen, taken from the 1.1.5
release candidate (`Locus Launch Media/v1.1.5/working/screenshots-2026-09-18/extras/winter-garden-sofa-center-no-ui.png`).
Source PNG SHA-256 `f1b3055d68c4461fb96b19987d5ac4f981845cbe7f561cf86fdd8a13d2639ac4`, website SHA-256 `233c6f7852e21344a300734ad9b42b2363ead99a08c25bd53b6379587beb83e6`.
The film itself is the owner's Apple Vision Pro recordings, published on YouTube
(see the YouTube delivery table).

| Website file | Source SHA-256 | Website SHA-256 |
| --- | --- | --- |
| `promo/locus-1.1.5-poster.jpg` | `f1b3055d68c4461fb96b19987d5ac4f981845cbe7f561cf86fdd8a13d2639ac4` | `233c6f7852e21344a300734ad9b42b2363ead99a08c25bd53b6379587beb83e6` |

The 1.1 What's New video, the 1.1.1 promo, and all earlier promotional media
URLs remain available; nothing in `promo/` or `screenshots/` was removed. These files are Simulator
evidence of Locus 1.1.3 layout and behavior. They are not physical Apple
Vision Pro validation and not evidence that an App Preview video was
submitted or approved in App Store Connect.

## YouTube delivery — September 13, 2026

The homepage hero film since 2026-09-18 is the 1.1.1 main film with its still
"Find your kind of focus" cliff replaced by the 1.1.3 living-water shots and
their captured ambience (Winter Garden + Floating Coastal Cliff, Courtyard
Gallery + Emerald Grotto), 38.3 s, 4K, uploaded byte-for-byte from
`Locus Launch Media/v1.1.5/working/hero-film-2026-09-18/Locus-Hero-Film-4K-38s-draft1.mp4`
(SHA-256 `fa9d4bd6f1e51c0a2bfd16cb12999cdcf486a034aece81b214c2545194b7365b`); the edit recipe is `edit/assemble.zsh` beside it. The
desk and walls sections are Apple Vision Pro recordings; the middle is
visionOS Simulator capture.

Website films now use local posters and YouTube privacy-enhanced embeds that load when 25% visible, autoplay muted, and loop. Native controls and direct Watch on YouTube links remain available when autoplay is blocked.
All four videos are Unlisted in EnterLocus (`UCuVsVMtpw1NejBaWBXFId4g`) with embedding enabled.
The main film and Animated Views upload use the approved 4K originals; archive films use the previously published 1080p files.
Existing MP4 files remain available at their old direct URLs for compatibility, but HTML pages no longer request them. New promotional videos should be uploaded to YouTube; keep originals in the versioned Dropbox launch-media archive.

| Film | YouTube watch URL | Uploaded source SHA-256 |
| --- | --- | --- |
| Main film (homepage hero since 2026-09-18, public) | https://www.youtube.com/watch?v=bJln-6GMXlQ | `fa9d4bd6f1e51c0a2bfd16cb12999cdcf486a034aece81b214c2545194b7365b` |
| Main film until 2026-09-18 (retired from the site) | https://www.youtube.com/watch?v=q7mVdPEqJ2o | `062985a8a3969ad4ab5a1e353d829b4cee835ccc92a47e7ebb10f078e46728e6` |
| Animated Views 1.1.3 (1.1.3 article only; retired from the homepage 2026-09-18) | https://www.youtube.com/watch?v=XfSBNZlIKw4 | `651c9da2cc48a816291d7bbb51d3e95d1765ddba3860af0f3b0263ae560f8c10` |
| What’s New 1.1 | https://www.youtube.com/watch?v=77sy7ONjdCU | `a8eb882e95cf22df34b75be2737eb5cee53b1596a645572afabee88f23decb6b` |
| Locus 1.1.5 release film (public) | https://www.youtube.com/watch?v=RPbFXq5-KVE | `191ab82da1417cfe7b651efd8fcc0af40c98c3ae09d2fdef06f8005486c1dfc9` |
| Introduction 1.0 | https://www.youtube.com/watch?v=zg7WsyTJT4Q | `7fe19092d03a2e43cdf795ee0f6c7f8c1667e33da439324b17f5b4699865117a` |

## Locus 1.2.0 UI refresh — September 24, 2026

Locus 1.2.0 replaced Library, Controls, Quick Settings, Teleport, and the 1.1 bar
with unified Places, Current Place settings, Seats, and a five-button bar. Every
page that showed the old interface now uses new captures from Locus Dev (built
from the 1.2.0 development source) on the visionOS 26.5 Simulator. The 3840 × 2160
PNG masters are in `Locus Launch Media/v1.2.0/screenshots/website/`. Full frames
were downsampled to 1920 × 1080 once; the crops are native-pixel windows so panel
text stays readable. `still-02-seat-v120.jpg` and `lamp-cafe-v120.jpg` are single
frames of the native 4K café takes for the 1.2 release film (Seats open with per-seat markers, and one
lamp switched on in a dark Room); their 3840 × 2160 frame grabs are in the same
website master folder.
The older files stay published at their existing URLs.

| Website file | Source master | Export | Source SHA-256 | Website SHA-256 |
| --- | --- | --- | --- | --- |
| `screenshots/place-picker-v120.jpg` | `place-picker-v120.png` | full frame | `59f2f11d19b6e7be997a57bad1ec206f3892e414bfc8eedac97eed35e726423a` | `147c0a03f6b6d7fff5ffbae05e0a4349e78d700554bcb5b6bd0ee23efa77ed6f` |
| `screenshots/snowbound-before-v120.jpg` | `snowbound-before-v120.png` | full frame | `19e423793a245d40c84c906a1b2648a84c37534b8048134886ffff1d3fb96e61` | `27e2214310d44fec27f97ba1185b033fcd3b547e960b234f1f49e06301d219e5` |
| `screenshots/snowbound-turn-view-sunlight-v120.jpg` | `snowbound-turn-view-sunlight-v120.png` | full frame | `3ad5d1cc4f73ecb4545c032eababd080a9f001f1f00466a802cc2797157604b9` | `b06e40116351bcbafdcd1065e77b041a0a544da38643089f186d3ff3412010cf` |
| `screenshots/bar-closeup-v120.jpg` | `snowbound-before-v120.png` | 900 × 340 crop around the bar | `19e423793a245d40c84c906a1b2648a84c37534b8048134886ffff1d3fb96e61` | `37e6645f41270e7fe9b82af0a8d0ea98904b76374a504fe0ef85c076a839ab47` |
| `screenshots/current-place-v120.jpg` | `current-place-v120.png` | 1920 × 1080 crop | `5565e7f0cd8e710285cb17b09d8043e5ad46e52dadb05e3d168978e498b91711` | `f003867d2b4af48ef61483404c2b193ec8a4747b8e80c92c72ba3be6ad146e8f` |
| `screenshots/light-and-picture-v120.jpg` | `light-and-picture-view-v120.png` | 1920 × 1080 crop | `e8293d75731c8909cad107b596178b0ac71c544402130b72e484e1a5faf57144` | `dd9529aa26ad5772c8f895f3fb4b9bcea124020c832050f2fa149afcffe60893` |
| `screenshots/seats-picker-v120.jpg` | `seats-picker-v120.png` | 1920 × 1080 crop | `1884e03b7d333616f4d8b765eff5eb6a07b42b0da36c203b5ef94d47361568bd` | `2eed65a814ea1a5470feb14636dcd5bd2ed995ff4143a69054956a2b71529748` |
| `screenshots/personal-seat-v120.jpg` | `personal-seat-move-turn-v120.png` | 1920 × 1080 crop | `c979da671068755490facea70074279cbf926dd9aed981a1e1dd08c9f2b02e91` | `9d60f796296d1b640257fa29ca99a57aac99c7626bd4e321c676f5011f5ee589` |
| `screenshots/imports-v120.jpg` | `imports-v120.png` | full frame | `8a0d0fed0e01035af1c7d7f6bd2c3c390c6b07a13d77886502e34f463bbb37bf` | `dff9ceedae45c027e75d582f106d0d78f95a70f23f01fa78f0561b57e1bba46f` |
| `screenshots/saturn-winter-garden-v120.jpg` | `saturn-winter-garden-v120.png` | full frame | `4c9acde7263c832c349a124a89a299d56a4e12369e17b085d5dd2ad642d08201` | `44ffa9ad8d225a4aa874bec41c1a81f729331d40f7f30a8e3db39baaf9ae56fa` |
| `screenshots/milky-way-winter-garden-v120.jpg` | `milky-way-winter-garden-v120.png` | full frame | `ea3927f02c2ec4618c566f0a96013068b05b8aacbf04e7c67cdd7395c4f836a7` | `874810a5bfbd5f290a68220d6d797daa6a70fbd8054d6fd10581a4252b1ebb2f` |
| `screenshots/floating-islands-winter-garden-v120.jpg` | `floating-islands-winter-garden-v120.png` | full frame | `d5185cb0362c323afc2d80b405d9a5b7bbeeb58cc9d1a285f852cbf890ea1991` | `e5129809db6f055ae36b78a8a6e0a1583e3edcfad4334496f014eb000305118c` |
| `promo/still-01-canyon-v120.jpg` | `canyon-oasis-winter-garden-v120.png` | full frame | `cb383dd54dabc6ddf012cce0996635f55b6a2423cf80776c5b4b71150bf7b174` | `8972e7f83568ccd17ce7aab7d25b4c4dbf491dc9745c09eb231ee23712d959be` |
| `promo/still-02-seat-v120.jpg` | `cafe-seats-open-v120.png` | full frame (Seats open, markers shown) | `df95467a7ab5855101256ab96b538ef86c06e32fe3bbc560fb4c63bc8d63c826` | `7b9efcde352f6dc2702efed88b22a6035d7e553108d604e2cc2604712facbde6` |
| `promo/lamp-cafe-v120.jpg` | `cafe-lamp-on-v120.png` | full frame (one lamp switched on) | `5e7e03b8d28d2507882adeb61d6db8b3b21adc4f29b2dc6f9c4c0518f73d7cc1` | `98bf448a83053f683d33f946dad5ab27531eea9672ffc4e335d44bf603d39a29` |
| `promo/still-03-browser-v120.jpg` | `browser-winter-garden-v120.png` | full frame | `ec86d3d378da87ef9c1bf94b5321a6d7258c84265b06035edfe6858683a0725c` | `c208dc8bf49d1e6b1b3f8b7e44c1356f73132d2f7dbe5eacc3569b7a012afe6f` |
| `promo/still-05-own-view-v120.jpg` | `save-as-view-v120.png` | 1920 × 1080 crop | `fd1182b4f71aad32101652cb38f0f11df2df5d871797fc75df02fc67eaf7da38` | `23963b9530b15a3ead9c6542299704286b0c46b29a2d4417e9d554f0487c7324` |
| `promo/still-06-room-lights-v120.jpg` | `room-lights-aurora-v120.png` | 1920 × 1080 crop | `fce29fb408651603b4e66728787f847a33725cd4bed4f449441898a17fa9c299` | `1c6ef83c93f87a27743e814681b735195e9d9e4821d7ae90fb450f2dc1fbb9c0` |
| `promo/locus-1.2-places-v120.jpg` | `places-views-rooftop-garden-v120.png` | full frame | `88f4c343f22987dfafda7f8984d47b6613d7f411a1edf5a388b641515182aa03` | `4204e3b47ccc8247955304dd9122781c8908d4bc0f9a3a32d30d0383f16c194f` |

These are Simulator captures. They verify interface state only, not Apple Vision
Pro rendering, brightness, seat placement, tracking, or comfort.

## YouTube delivery — September 24, 2026 (Locus 1.2)

Both films are Simulator captures of Locus 1.2, uploaded byte for byte from the
4K masters in `Locus Launch Media/v1.2.0/video/` to EnterLocus
(`UCuVsVMtpw1NejBaWBXFId4g`, verified with `channels.list(mine=true)`),
**Unlisted** with embedding enabled until 1.2.0 is released.

| Film | Video ID | Source SHA-256 | Local poster | Poster SHA-256 |
| --- | --- | --- | --- | --- |
| 1.2 release film, 29.6 s (homepage What's New, `whats-new/1-2/`) | `nO2B7MP0uzI` | `0b3af8bc7a0a268de9af5fa45f16ee42bc08b2820630a08a3f43c1148c757c5b` | `promo/locus-1.2-poster.jpg` (frame at 14.0 s) | `8b47852af2e4ae698b8dacb014648323ad64c979ecd7224c7632368075e594cc` |
| Homepage hero film, 37 s | `NJuKWTs2BRw` | `fb697854e036ac1e7fecf864aba9c894ee7873e60dc81eaa0b80dbcddfa51092` | `promo/locus-1.2-hero-poster.jpg` (frame at 18.6 s) | `f7765e855f0384ddeced37d27a5678508bb1fbebab41b78582feba35dabb04f2` |

After upload both reported `processed` / `succeeded`, `unlisted`, embeddable, with no
rejection or failure reason; the watch and embed URLs returned 200 and oEmbed resolved the
title and channel. The previous hero film `bJln-6GMXlQ` stays on YouTube; the 1.1.5
article keeps `RPbFXq5-KVE`.
