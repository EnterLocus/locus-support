# Spatial website design

The approved Sites homepage design now supplies the public site's visual language: neutral charcoal, warm white, restrained bronze, lighter Onest headings, generous spacing, and product imagery with minimal framing. Gallery, tutorials, FAQ, release history, support, privacy and format references share the new shell and content styling. Reading pages retain normal document flow rather than fixed screen-height sections.

The homepage keeps the original official App Store badge unchanged. Its film is an explicit YouTube link; historical release-film playback is unchanged. The existing eight language routes, Follow system behavior, saved preference, search and FAQ anchors remain available. The language globe appears in desktop navigation; narrow screens expose the full native language selector inside the keyboard-accessible menu. New homepage copy and image alternatives are translated in all seven non-English catalogs.

## Validation

- `npm run build`: generated 1,088 HTML pages across eight languages, including 43 authored source pages and current Gallery Place/Series pages.
- Python: 48 public-site tests and 23 localization/search/Gallery/Markdown-reference tests passed.
- Browser: all 44 applicable Playwright cases have passing results. Passing unaffected results from the initial run were retained; changed or initially failing cases were rerun. Coverage includes menu focus and dismissal, language persistence and denied storage, localized search, FAQ anchors, Gallery filters and photo dialogs, Series return context, release navigation, Room examples, no-JavaScript links, release video fallback, and small-phone download actions.
- Visual review: default states for nine page families at 1440 and 390px; desktop German and mobile Simplified Chinese homepages; mobile menu and selected scenery. Gallery spacing was tightened to show the first image above 700px. Reference pages use one layer of top padding.
- `git diff --check` and JavaScript syntax checks passed.

Browser assertions that assumed old homepage media, an older latest release, eight Series, four Room-example raster images, or mandatory photos on newer Room revisions were updated to the current public content. No Gallery catalog or photo provenance data was changed. Current-revision cover-only albums remain valid; existing multi-photo native albums are still exercised separately.

The design preview remains owner-private on Sites. These are local browser results, not field performance measurements. Existing CDN images and Google Fonts remain external dependencies. The shared CSS reaches every generated page; individual visual review sampled the page families above rather than all 1,088 pages.

## Screenshots

[Desktop homepage](site-spatial-design/home-desktop.jpg) · [Mobile homepage](site-spatial-design/home-mobile.jpg) · [Mobile menu and language](site-spatial-design/mobile-menu.jpg) · [Gallery](site-spatial-design/gallery-mobile.jpg) · [Tutorials](site-spatial-design/tutorials-desktop.jpg) · [Format reference](site-spatial-design/reference-desktop.jpg)

## Public rollout

The source change is prepared as a PR, with the complete site staged separately on Sites for review. The public enterlocus.com deployment is unchanged. A public rollout can use the existing Pages deployment after merge; reverting the PR restores the previous source and theme. The prior private Sites version remains available in version history.
