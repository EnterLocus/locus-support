# Spatial website design

The approved Sites homepage design now supplies the public site's visual language: neutral charcoal, warm white, restrained bronze, lighter Onest headings, generous spacing, and product imagery with minimal framing. Gallery, tutorials, FAQ, release history, support, privacy and format references share the new shell and content styling. Reading pages retain normal document flow rather than fixed screen-height sections.

The homepage keeps the original official App Store badge unchanged. Its film is an explicit YouTube link; historical release-film playback is unchanged. The existing eight language routes, Follow system behavior, saved preference, search and FAQ anchors remain available. The language globe appears in desktop navigation; narrow screens expose the full native language selector inside the keyboard-accessible menu. New homepage copy and image alternatives are translated in all seven non-English catalogs.

## Validation

- `npm run build`: generated 1,088 HTML pages across eight languages, including 43 authored source pages and current Gallery Place/Series pages.
- Python: 48 public-site tests and 23 localization/search/Gallery/Markdown-reference tests passed.
- Browser: all 46 applicable Playwright cases have passing results. Passing unaffected results from the initial run were retained; changed or initially failing cases were rerun. Coverage includes menu focus and dismissal, language persistence and denied storage, localized search, FAQ anchors, Gallery filters and photo dialogs, Series return context, release navigation, Room examples, no-JavaScript links, release video fallback, and small-phone download actions.
- Visual review: default states for nine page families at 1440 and 390px; desktop German and mobile Simplified Chinese homepages; mobile menu and selected scenery. Gallery spacing was tightened to show the first image above 700px. Reference pages use one layer of top padding.
- `git diff --check` and JavaScript syntax checks passed.

Browser assertions that assumed old homepage media, an older latest release, eight Series, four Room-example raster images, or mandatory photos on newer Room revisions were updated to the current public content. No Gallery catalog or photo provenance data was changed. Current-revision cover-only albums remain valid; existing multi-photo native albums are still exercised separately.

The design preview remains owner-private on Sites. These are local browser results, not field performance measurements. Existing CDN images and Google Fonts remain external dependencies. The shared CSS reaches every generated page; individual visual review sampled the page families above rather than all 1,088 pages.

## Screenshots

[Desktop homepage](site-spatial-design/home-desktop.jpg) · [Mobile homepage](site-spatial-design/home-mobile.jpg) · [Mobile menu and language](site-spatial-design/mobile-menu.jpg) · [Gallery](site-spatial-design/gallery-mobile.jpg) · [Tutorials](site-spatial-design/tutorials-desktop.jpg) · [Format reference](site-spatial-design/reference-desktop.jpg)

## Public rollout

[PR #151](https://github.com/EnterLocus/locus-support/pull/151) was merged as `c686fc2b5c619e5323d582ba8d6eea13563c1269` and published to enterlocus.com on November 6, 2026 through the existing Pages deployment. The private Sites preview remains available with the approved design. Reverting the PR restores the previous source and theme.

## Design follow-up

The homepage closing section now uses neutral graphite with white headings and cool-neutral secondary text, replacing the olive cast. The release archive removes the narrow `16ch` title cap and gives every release a product-image cover. New Room cover images are representative current public catalog previews, not historical headset-capture evidence. Existing release copy, ordering, destination URLs and image provenance remain unchanged.

Follow-up checks: six focused Python checks and five browser release checks passed, including all 17 covers loading on Chinese desktop and English mobile. The latest Chinese title fits one line at 1440px; narrower layouts wrap naturally. Desktop/mobile closing-section renders confirm a neutral graphite background and white heading text.

[Graphite closing section](site-spatial-design/closing-desktop.jpg) · [Mobile closing section](site-spatial-design/closing-mobile.jpg) · [Illustrated archive](site-spatial-design/release-archive-desktop.jpg) · [Mobile archive](site-spatial-design/release-archive-mobile.jpg)

## Remaining-page audit

All 1,088 generated HTML pages include the shared stylesheet and navigation script. The first browser sweep covered all 136 English routes at 1440 and 390px, plus all 43 authored routes in each of the seven other languages at 390px: 573 page/viewport combinations. Every route returned HTTP 200 with the shared brand, search, and language control. The sweep found mobile horizontal overflow on the asset-rights page in seven languages and on the German privacy page. Long inline texture filenames and an unbroken translated heading caused those failures. Documentation now allows long words to wrap, with automatic hyphenation for page headings; command blocks retain their own scrolling behavior. A regression case checks the actual content at both 320 and 390px.

Additional visual review covers the Room integration guide, View authoring guide, Locus 1.0 release, a Gallery Place, a Gallery Series, asset notices, and German privacy. These reading pages use document flow; their sections are not forced to viewport heights. The taste skill's `assets/layout/check.mjs` could not evaluate this documentation structure (missing landing-page section data causes a checker exception), so it is not reported as a passing check. Screenshots use the skill's headless `shoot.mjs`; route and overflow checks use the repository's real staged site in Chromium.

The additional sweep of translated Gallery pages found five German Place titles that expanded the mobile grid: dusk-mountain, jungle-terraces, moonlit-volcanic-lake, rainwashed-terraces, and tropical-shallow-bay. Gallery headings now hyphenate long words and its mobile grid can shrink within the viewport. A regression case exercises all five at 320 and 390px.

The Package v2 complete guide had 22 missing translation fragments in six catalogs and 21 in German before the redesign. Those 153 catalog entries are now supplied, with zero missing guide fragments in all seven translations. Technical field names, code examples, schemas, and the public Room-building skill remain unchanged. The separate, much larger field reference (`reference/locus-asset-format/`) still contains substantial English fallback prose in translated routes; that older translation backlog is separate from shared design coverage.

Final checks: 29 focused Python checks and 10 Playwright cases passed. All 136 English routes at 1440, 1024, 768, and 390px, plus every other-language route at 390px, passed the browser shell/overflow sweep: 1,496 combinations, all HTTP 200 and none with horizontal page overflow. The built 1,088 pages have no missing local link targets. This is automated route coverage with sampled human visual review, not a claim that every translated line was manually proofread. The German complete-guide mobile screenshot is capped at 32,000px by the screenshot tool, so it does not show that long page's end/footer.

[Audit summary](site-spatial-design/audit-summary.json) · [Asset notices](site-spatial-design/audit-asset-rights-mobile.jpg) · [German privacy](site-spatial-design/audit-privacy-de-mobile.jpg) · [German Gallery title](site-spatial-design/audit-gallery-de-mobile.jpg) · [Room integration](site-spatial-design/audit-build-a-room-1440.jpg) · [View authoring](site-spatial-design/audit-make-a-view-390.jpg) · [Early release](site-spatial-design/audit-whats-new-1-0-390.jpg) · [Place](site-spatial-design/audit-gallery-place-aegean-terrace-estate-390.jpg) · [Series](site-spatial-design/audit-gallery-series-mansions-1440.jpg)

## Social preview follow-up

The generic Open Graph and Twitter cover now uses a 1200 x 630 JPEG composed from the actual Winter Garden homepage image with centered Locus branding, replacing the old generated green concept cover. The versioned image URL is `https://enterlocus.com/assets/social-preview-spatial-20261106.jpg`; it is 85 KiB. The older file remains available. Existing article-specific covers are retained: 1,024 built routes use the new generic cover, while 64 retain their specific cover.

The homepage social summary reuses its translated product description. Image alternative metadata is also localized in all eight homepage routes; generation tests cover those metadata fields. Landscape and 210px square-crop renders were visually reviewed. These checks verify the published asset/metadata contract; actual WhatsApp client rendering and cache refresh are not verified.
