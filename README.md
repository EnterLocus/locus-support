# Locus support and documentation

This is the official public home for Locus support, feedback, documentation,
privacy information, launch copy, and the public Place-package authoring tools.
The site is published at <https://enterlocus.com/>.

The Locus application source is maintained in a separate private repository.
Making this support repository public does **not** publish or license the app
source.

This repository uses scoped licenses rather than one blanket license:

- the public Room authoring skill, tools, and schemas are available under
  Apache License 2.0;
- the Locus-authored parts of the three downloadable demo Rooms are available
  under Creative Commons Attribution 4.0 International;
- the Cloud Fan Pavilion animation sample keeps its Locus-authored parts
  reserved under the statement published on the Asset rights page;
- embedded Poly Haven textures retain their CC0 1.0 dedication; and
- site content, Locus branding, and everything not expressly listed remain
  reserved.

See [LICENSE.md](LICENSE.md) for exact paths and
[Asset rights](https://enterlocus.com/asset-rights/) for Room attribution and
third-party notices.

The repository includes a tool-agnostic Room integration guide and an optional
Room-building skill at `.agents/skills/build-original-locus-room/`. Complete
Package v2 is the recommended feature-complete import format in Locus 1.2.1
and later. Use `tools/pack_locusplace.py` and `tools/validate_locusplace.py`
with [the complete-package guide](reference/locusplace-format.md) for stable
IDs, updates, localized metadata, and supported current View and Room fields.
The older flat packer, validator, scaffolder, and downloadable Room examples
remain intentionally available for simple compatibility archives; they cannot
carry complete-package-only fields. The flat validator supports Room contracts
through v10; the downloadable demo Rooms intentionally remain historical v5 examples. A flat archive does
not expose every current feature.
The skill bundles an offline Room reference, design language, metadata
scaffolder, packer, validator, and delivery checks. For automated authoring from
a blank brief, it defaults to headless Blender Python with saved render review;
creators can still use their preferred professional 3D workflow. No open
Blender window or MCP connection is required for that default route. The free Cloud Fan Pavilion
download demonstrates experimental Room animation playback.

Experimental Room animation metadata, playback controls, speed, and replay
intervals are documented at
<https://enterlocus.com/experimental-room-animations/>. They are not presented
as a stable production authoring contract.

Use the Bug form for reproducible product problems. Ask questions and share
what you made on [r/EnterLocus](https://www.reddit.com/r/EnterLocus/). Bring
structured feature requests to GitHub Discussions. Send private or
security-sensitive reports to support@enterlocus.com.

A reproducible one-seat walkthrough is available in the [Room integration guide](https://enterlocus.com/build-a-room/#minimal-room). `tools/build_minimal_room.py` creates its geometry, source file, review renders and public metadata from scratch. The [runtime interaction reference](https://enterlocus.com/reference/locus-asset-format/#how-locus-uses-a-room) documents seats, safety, collision and quality bookkeeping, and actual model budgets. The [Markdown source](reference/locus-asset-format.md) remains available for download and AI-assisted authoring.

`tools/black_hole/` holds the Python 3.9+ tools (NumPy and Pillow) behind the
[black hole View tutorial](https://enterlocus.com/make-a-black-hole-view/): a
sky composer, a Schwarzschild lens and baker, and a complete Package v2 packer
and validator for `locus.view.black-hole.v1` Views, which need Locus 1.3.4 or
later. See its [README](tools/black_hole/README.md).

## Community

[Community](https://www.reddit.com/r/EnterLocus/) — Share creations, ask
questions, and discover environments made by other Locus users on Reddit.
Structured feature proposals and technical discussion stay on
[GitHub Discussions](https://github.com/EnterLocus/locus-support/discussions).

## Static search and local preview

Run `npm ci` and `npm run build`, then
`python3 tools/serve_site.py`. Pagefind generates a same-origin
search index from each public page's `data-pagefind-body`. GitHub Pages deploys
`.site/`, including the index. Dependencies and local evidence are excluded.

Search supports Command/Ctrl-K and Escape. FAQ questions have stable heading
IDs; links to them open the matching answer. Keep existing IDs when editing
question wording. Add the shared search assets and indexed main element when
adding a public page.

## Localized static pages

English remains at its existing URLs. The build generates the same public pages
under `/zh-Hans/`, `/zh-Hant/`, `/ja/`, `/ko/`, `/de/`, `/fr/`, and `/es/`, while
assets, downloads, schemas, and source files remain at their one root URL. Each
generated page adds its canonical URL and all language alternates; the staged
sitemap includes the translated routes too.

Catalogs live in `localization/<tag>.json` and have this shape:

```json
{
  "language": "fr",
  "strings": {
    "Search Locus": "Rechercher dans Locus"
  }
}
```

Keys are exact decoded, trimmed English text or user-facing attribute values.
Missing keys deliberately fall back to English. Keep `{count}` and other
interpolation tokens unchanged in translations. `tools.localization.extract_sources(ROOT)`
returns deterministic `strings` and per-page `pages` references for catalog
authoring. It excludes code, preformatted text, scripts, and styles. Translate
prose around inline filenames and technical literals; do not skip a sentence
because it contains a path or slash. Preserve those literals, named interpolation
tokens and their multiplicity while allowing grammatical token reordering.
Machine drafts require contextual review, especially feature/resource names,
spatial directions, units, privacy promises and version thresholds. Keep App
feature names aligned with the reviewed native catalog. Fetch current main
before extracting copy that another agent may have edited.

The native Language selector stores a chosen language when browser storage is
available. System follows the first browser language, with Chinese script and
region handling; a localized URL always wins when opened directly. Pagefind
uses each generated document's `html lang`, so search results stay in the
current language without a second index or duplicated assets.

## What’s New articles

`whats-new/` is the public release-story archive. Keep its cards in descending
version order, with the newest release first. Every public release gets an
article; size it to the release, so a small one is a few short sections rather
than a missing page.

Each new article should focus on that release's leading feature, use verified
product media when available, link into the previous/newer release sequence,
and be added to the archive and site regression test.

The homepage What’s New section always names the latest release. By default,
point the one-line `whats-new-latest` strip above the leading block at the new
article and leave the block alone, as 1.1.4 did beneath the 1.1.3 story.
Replace the leading block itself (headline, film, grid) only when the owner
decides the release takes over the homepage, and drop the strip then.

Every page carries its own copy of the header and footer navigation. The site
test pins one shared set of links and their order, so copy both from an existing
page when adding one, and change the expected lists in `tests/test_site.py`
together with every page when the navigation itself changes.

After building, run `npx playwright install chromium` and `npm run test:search`.
Browser tests serve the real built site and cover desktop/mobile results, FAQ
links, keyboard focus, empty queries and unavailable search assets. The full
Python suite runs on macOS with Xcode and `usd-core` for Room binding tests.

The complete authoring guide is localized with the site. Its JSON keys, enum
values, paths, capability IDs and executable code remain unchanged in every
language; translate the explanations around them. `tests/test_authoring_localization.py`
checks complete-guide coverage and exact code/identifier preservation.

## Gallery catalog snapshot

`/gallery/` is generated from `data/gallery.json`; it does not contact the Library
or App Store in a visitor's browser. Place titles, captions, translations, preview
images and Series membership come from the public **Production** revision catalog.
Only preview metadata is exported: no install artifacts, grant credentials or
Place-package download links. Built-in Places are included separately using the
reviewed App Store release's metadata and thumbnails.

Place cards are newest first using `max(addedAt, updatedAt)` from Production,
matching the Library's Recent semantics. Substantive revisions rise naturally;
maintenance revisions retain their content date. Undated built-ins follow dated
Places. Filters and Series member grids preserve this order in every language.

Series share the All Places, Views and Rooms grids with individual Places. On
the default Recent grid they fold at the newest visible member's content date;
search and narrowing filters reveal matching members instead. A Series needs
two visible members of one kind. Its curated covers lead the card collage.

Reviewed native photos are registered in `data/gallery-photos.json` by exact
package ID and content version. Synchronization validates local image hashes,
dimensions and capture kind, then attaches photos only to the selected public
revision. Never use a newer revision's photos for an older Place. Detail pages
offer thumbnails and a keyboard-accessible large viewer; their Simulator caption
distinguishes these captures from physical-headset evidence. The canonical card
thumbnail remains the public catalog preview.

Run `python3 tools/sync_gallery.py` to refresh the snapshot, or add `--check` to
check for drift without writing. The command reads the marketed US App Store
version, verifies the descriptor/archive byte count and SHA-256, checks Production
snapshot identity, and verifies the chosen thumbnails inside that archive. Those
selected public previews are copied byte for byte into `assets/gallery/` (the
catalog's internal thumbnail paths are not independent HTTP endpoints). It
selects the App's newest visible revision using both audience/watermark and the
reviewed reader's App, OS and capability requirements. Selected previews that
would only offer “Update App” are omitted, without advertising a superseded
download. It never reads the Dev catalog or downloads
Place packages.

`data/gallery-reader.json` pins the reviewed public reader profile and four built-in
Places. Update it from the next immutable release tag during release closeout,
including that tag's exact supported/Animated capability sets, bundled metadata,
translations and thumbnails. Do not derive a reader profile from development main
or raise its App version before public availability. A newer public App leaves the
older reviewed profile conservative until that update; an unpublished profile
causes synchronization to fail. The website's normal build uses the committed
snapshot, so a network outage does not remove the Gallery.

The **Refresh public Gallery** workflow checks Production daily and on manual
request. Changes go to an `automation/gallery` pull request for review; the
workflow never merges or publishes them. If repository policy disallows Actions
from creating pull requests, the job retains the refreshed review branch and
provides a compare link in its summary without changing repository permissions.
Content changes do not require hand-editing Gallery pages;
new reader capabilities and built-in assets still require release review. Site
build, localization, Pagefind and browser checks apply to these pages as they do
to the rest of the website.
