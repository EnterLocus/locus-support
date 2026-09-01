# iPhone Chrome embedded-video playback

## Conclusion

The linked-poster fallback is justified and should remain the default on the
home page. Apple explicitly recommends providing a direct link to the media
file when a site has a custom media presentation, so this is a supported iOS
delivery pattern rather than an undocumented workaround.[^apple-direct-link]

The observed result does not identify a codec or hosting failure: the same MP4
plays when opened directly in the same iPhone Chrome, while only the inline
`<video>` remains at `0:00`. Chrome on iOS wraps `WKWebView` and uses WebKit,
not Blink, for page rendering and media.[^chrome-ios-webkit][^chromium-wkwebview]
The strongest current classification is therefore an iOS WebKit/WKWebView
inline-media loading failure or stale player state. No primary-source issue was
found that exactly matches a normal Chrome tab, a static HTTPS MP4, correct
byte-range responses, and successful playback after direct navigation.

`0:00` is consistent with the element not reaching loaded metadata; it does not
prove that the file itself has zero duration. The HTML Standard says duration
is unavailable until the user agent has obtained enough metadata, and requires
the duration to be known before the element reaches `HAVE_METADATA`.[^html-duration]
Autoplay cannot repair that state because it asks the same inline element to
play before its media pipeline has become ready.

## What the evidence rules in and out

- **Video-only MP4 is valid.** Apple recommends H.264 MP4 for static video and
  explicitly allows video with no audio track to autoplay. Adding a silent AAC
  track is therefore not an evidence-based fix; it would instead make autoplay
  depend on the element remaining muted.[^apple-delivery][^webkit-autoplay]
- **The autoplay attributes are correct but best-effort.** `autoplay muted
  playsinline` is the documented combination for silent inline playback on
  iPhone. WebKit begins autoplay only while the element is visible, and iOS Low
  Power Mode can suppress automatic playback.[^webkit-autoplay][^webkit-low-power]
  A user tap should satisfy the gesture rule, so a tapped player that still
  shows `0:00` is not explained by autoplay policy alone.
- **`src` and child `<source>` are both supported.** The HTML Standard defines
  both resource-selection forms, and WebKit's own autoplay example uses child
  `<source>` elements.[^html-media][^webkit-autoplay] The failing deployment
  already used a direct `src`, so changing between these forms is not a
  supported root-cause theory.
- **Byte ranges are important, but the live host passes the relevant checks.**
  Apple requires media servers to support byte-range requests, and WebKit has a
  documented playback failure where malformed range handling broke playback
  and seeking.[^apple-direct-link][^webkit-range-bug] On 2026-08-31 Pacific,
  live GET probes for the first, middle, and final 1,024 bytes of the Locus MP4
  each returned `206 Partial Content`, the correct `Content-Range`, and exactly
  1,024 bytes. The response also supplied `Content-Type: video/mp4` and
  `Accept-Ranges: bytes`. GitHub Pages is therefore not implicated by its
  observed behavior here.
- **The captions track is not a demonstrated cause.** The deployed VTT returned
  `Content-Type: text/vtt; charset=utf-8`, and no matching WebKit issue was found
  in which a same-origin VTT track made an otherwise playable MP4 report zero
  duration. Removing the transcript and track simplifies the page and satisfies
  the product decision, but it should not be described as the technical fix.
- **The direct link is the reliable escape hatch.** It is both confirmed on the
  affected device and recommended by Apple. A poster image linked directly to
  the MP4 also avoids depending on inline-player initialization while preserving
  a single obvious tap target.[^apple-direct-link]

## Similar upstream reports

WebKit has accepted closely related reports, but none is an exact match:

- WebKit bug 300115 reports an iOS 26 `<video>` that accepts a tap but remains
  stuck with time not advancing after a Home Screen web app is relaunched. It
  is scoped to standalone/PWA mode, not a normal Chrome tab.[^webkit-pwa-video]
- WebKit bug 232076 documents iOS video playback and seeking failures caused by
  malformed range responses. It supports checking ranges, but the Locus server
  does not exhibit that failure.[^webkit-range-bug]
- WebKit bug 219889 records that Low Power Mode can prevent muted inline
  autoplay. It does not explain failure after a deliberate tap or the missing
  duration metadata.[^webkit-low-power]

These reports establish that the symptom family exists in iOS WebKit, while the
device observation and live header checks justify using the direct system-player
path now instead of continuing to alter a known-playable MP4.

## Recommended site behavior

Use the promotional poster as a normal link to the MP4 and label the fallback
`Watch the video directly.` Do not promise autoplay on iPhone. Keep the H.264
Level 4.0 fast-start encode and byte-range checks, and publish future video
revisions under a new filename so a mobile cache cannot mix old media bytes with
new page markup.

If inline playback is revisited, first capture `video.error.code`, `currentSrc`,
`networkState`, `readyState`, and the `loadstart`, `loadedmetadata`, `error`, and
`stalled` events from the affected iPhone through Web Inspector. That evidence
would distinguish a source-selection failure from a WebKit media-process or
cache-state defect and would be suitable for a minimal upstream report.

[^apple-direct-link]: [Apple, *Creating Video*](https://developer.apple.com/library/archive/documentation/AppleApplications/Reference/SafariWebContent/CreatingVideoforSafarioniPhone/CreatingVideoforSafarioniPhone.html) requires byte-range support and recommends a direct media-file link for iOS users when a site has a custom player.
[^apple-delivery]: [Apple, *Delivering Video Content for Safari*](https://developer.apple.com/documentation/webkit/delivering-video-content-for-safari) recommends H.264 MP4 for static video and documents metadata loading, autoplay, muting, and inline playback.
[^chrome-ios-webkit]: [Google, *The Chromium Chronicle #28: Getting started with Chrome on iOS*](https://developer.chrome.com/blog/chromium-chronicle-28) explains that Chrome on iOS uses WebKit and the iOS platform networking APIs rather than Blink and Chromium's normal network stack.
[^chromium-wkwebview]: [Chromium source, `ios/web`](https://chromium.googlesource.com/chromium/src/+/main/ios/web/) states that the iOS rendering layer wraps `WKWebView`; [its configuration provider](https://chromium.googlesource.com/chromium/src/+/main/ios/web/web_state/ui/wk_web_view_configuration_provider.mm) enables inline media playback.
[^html-duration]: [WHATWG HTML Standard, media elements](https://html.spec.whatwg.org/multipage/media.html#dom-media-duration-dev) defines duration and `HAVE_METADATA` behavior.
[^html-media]: [WHATWG HTML Standard, media elements](https://html.spec.whatwg.org/multipage/media.html#the-source-element) defines direct `src` and child `<source>` resource selection.
[^webkit-autoplay]: [WebKit, *New `<video>` Policies for iOS*](https://webkit.org/blog/6784/new-video-policies-for-ios/) documents no-audio and muted autoplay, visibility conditions, user gestures, and `playsinline`.
[^webkit-low-power]: [WebKit bug 219889](https://bugs.webkit.org/show_bug.cgi?id=219889) records autoplay suppression for muted inline video while iOS Low Power Mode is enabled.
[^webkit-range-bug]: [WebKit bug 232076](https://bugs.webkit.org/show_bug.cgi?id=232076) contains a reduced iOS case where malformed partial responses prevent playback and seeking.
[^webkit-pwa-video]: [WebKit bug 300115](https://bugs.webkit.org/show_bug.cgi?id=300115) reports stuck `<video>` playback with no time advance after relaunching an iOS 26 Home Screen web app.
