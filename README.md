# Locus support and documentation

This is the official public home for Locus support, feedback, documentation,
privacy information, launch copy, and the public Place-package authoring tools.
The site is published at <https://enterlocus.com/>.

The Locus application source is maintained in a separate private repository.
Making this support repository public does **not** publish or license the app
source.

This repository uses scoped licenses rather than one blanket license:

- the public Room and skybox authoring skills, tools, and schemas are available under
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
Room-building skill at `.agents/skills/build-original-locus-room/`. Its default
workflow has four steps: choose a concept image (ChatGPT, another image model,
or a supplied picture); ask the agent for a metric floor plan and seat layout;
model from both image and layout, export and check an importable Package v2
archive; then import on Apple Vision Pro and feed observations back to the
agent for revisions. Use only these public docs, skill, and tools; Locus app
source and a Simulator are not required. The agent reviews the model and every
seat, derives seats from exported USDZ bounds, and runs `tools/check_room.py`
with an explicit render directory before each device iteration. No API key is required; paid generation is
optional. Complete Package v2 is the recommended feature-complete import
format in Locus 1.2.1 and later. Use `tools/pack_locusplace.py` and
`tools/validate_locusplace.py` with [the complete-package guide](reference/locusplace-format.md)
for stable IDs, updates, localized metadata, and supported current View and
Room fields.
The older flat packer, validator, scaffolder, and downloadable Room examples
remain intentionally available for simple compatibility archives; they cannot
carry complete-package-only fields. The flat validator supports Room contracts
through v10; the downloadable demo Rooms intentionally remain historical v5 examples. A flat archive does
not expose every current feature.
The skill bundles offline references, a Package v2 seat conversion helper, and
compatibility tools. For automated authoring from a blank brief, it defaults to
headless Blender Python with saved render review; creators can still use their
preferred professional 3D workflow. No open Blender window or MCP connection is
required for that default route. The free Cloud Fan Pavilion download
demonstrates experimental Room animation playback.

For a complete, candid worked record—including the creator brief, concept,
editable source, exact import archive, Apple Vision Pro screenshots, rights,
and unresolved lamp defects—see the [Alpine Scriptorium Sol 1.1.1 public
example](examples/gothic-mountain-library/README.md). It preserves an older
combined Room/View/Experience package; new work should follow the separate
Package v2 workflow above.

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

**Publish GitHub Pages** builds and deploys the site on pushes to `main` or a
manual dispatch. It runs one Ubuntu deployment job. Run the applicable Python,
Blender/RealityKit and browser checks locally before merging; those checks are
not part of the deployment Action. The separate **Verify public support surface**
and **Refresh public Gallery** workflows remain disabled.

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
snapshot identity, and verifies the chosen thumbnails inside that archive. Gallery
previews are immutable objects at `https://media.enterlocus.net/gallery/`; their
paths, URLs, sizes and SHA-256 values live in `data/external-assets.json`, not in
this repository. It
selects the App's newest visible revision using both audience/watermark and the
reviewed reader's App, OS and capability requirements. Selected previews that
would only offer “Update App” are omitted, without advertising a superseded
download. It never reads the Dev catalog or downloads
Place packages.

When a Production refresh introduces a new catalog thumbnail, first stage it
outside Git, for example
`python3 tools/sync_gallery.py --asset-output .scratch/gallery-upload`. Upload
each staged JPEG/PNG with Wrangler to `locus-site-media/gallery/<filename>` using
immutable cache headers, for example `wrangler r2 object put
locus-site-media/gallery/<filename> --file .scratch/gallery-upload/<filename>
--remote --content-type image/jpeg --cache-control 'public, max-age=31536000,
immutable'` (use `image/png` for PNG). The staged directory contains a candidate
`external-assets.json`; run `python3 tools/external_assets.py --manifest
.scratch/gallery-upload/external-assets.json --verify` for HTTPS size/SHA-256
readback, install that verified manifest, then rerun `sync_gallery.py` to write
metadata. Until that second run, `data/gallery.json` is unchanged. Never copy
these objects back to `assets/gallery/`; the command accepts staging only below
ignored `.scratch/`. Existing photo registry entries may be reviewed from a
temporary local directory, but committed Gallery metadata always uses the remote
immutable URL.

`python3 tools/external_assets.py --verify` downloads and verifies every external
asset, including Release downloads. `--hydrate examples/atrium-loft-room.zip`
downloads only that declared fixture into ignored `.scratch/external-assets/` for
local tools and tests. It never restores a binary to its old tracked path.

The five current public example downloads use the immutable
`site-downloads-2026-11-05` GitHub Release. The three frozen historical Room
downloads use its `legacy-` assets. Source links were updated accordingly; GitHub
Pages cannot provide HTTP redirects for removed binary URLs, and this site does
not create HTML placeholders at those binary paths.

An owner-reviewed `data/gallery-preview-releases.json` may name an exact future
Room revision for an upcoming-release Gallery preview. Each entry pins the Place
ID, content version and required App version; synchronization accepts it only
when the Production catalog's public preview and install metadata match that
contract. It exports no package or artifact data and marks the Place with its
upcoming release version. The reviewed reader profile, watermark and ordinary
selection stay unchanged; once a Room is normally selectable, that ordinary
record wins and the upcoming-release marker is omitted.

`data/gallery-reader.json` pins the reviewed public reader profile and four built-in
Places. Update it from the next immutable release tag during release closeout,
including that tag's exact supported/Animated capability sets, bundled metadata,
translations and thumbnails. Do not derive a reader profile from development main
or raise its App version before public availability. A newer public App leaves the
older reviewed profile conservative until that update; an unpublished profile
causes synchronization to fail. The website's normal build uses the committed
snapshot, so a network outage does not remove the Gallery.

The **Refresh public Gallery** workflow is manual-only. It must not be scheduled:
a newly extracted immutable thumbnail requires the documented local upload and
HTTPS readback before metadata publication. When manually run for an already
published asset set, changes go to an
`automation/gallery` pull request for review; the
workflow never merges or publishes them. If repository policy disallows Actions
from creating pull requests, the job retains the refreshed review branch and
provides a compare link in its summary without changing repository permissions.
Content changes do not require hand-editing Gallery pages;
new reader capabilities and built-in assets still require release review. Site
build, localization, Pagefind and browser checks apply to these pages as they do
to the rest of the website.

## Build a 12K skybox

The public [build-a-view skill](.agents/skills/build-a-view/SKILL.md) and
[skybox workflow](.agents/skills/build-a-view/references/skybox-workflow.md)
cover full-sphere generation, pixel density, overlap faces, narrow blending,
and local defect repair. The generated 12K route requires a high-resolution
image API and its credentials; Nano Banana Pro at native 4K is the previously
tested baseline. Other models need native-size, fidelity and seam validation.
Codex built-in images may supply concepts or a low-resolution base, but the
failed Maldives trial does not qualify them as the final enhancement route.
No private app source, Blender, or macOS is required for skybox authoring.
Import the final accepted panorama into Locus separately.

The target is 12,288 × 6,144 SDR. That is an output size, not a guarantee of
resolved detail: review the generated face sizes, enlargement factors, seams,
and perspective crops before accepting a result. This first workflow covers
static skyboxes only.
