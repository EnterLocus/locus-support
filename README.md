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
Package v2 is the canonical feature-complete import format in Locus 1.2.1 and
later. The current public packer, validator, skill, and three Room examples use
the legacy/simple flat ZIP compatibility format; they do not yet author or
validate complete Package v2 archives. The examples show the current public
lighting and spatial contracts.
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

A reproducible one-seat walkthrough is available in the [Room integration guide](https://enterlocus.com/build-a-room/#minimal-room). `tools/build_minimal_room.py` creates its geometry, source file, review renders and public metadata from scratch. The [runtime interaction reference](reference/locus-asset-format.md#how-locus-uses-a-room) documents seats, safety, collision and quality bookkeeping, and actual model budgets.

## Community

[Community](https://www.reddit.com/r/EnterLocus/) — Share creations, ask
questions, and discover environments made by other Locus users on Reddit.
Structured feature proposals and technical discussion stay on
[GitHub Discussions](https://github.com/EnterLocus/locus-support/discussions).

## Static search and local preview

Run `npm ci` and `npm run build`, then
`python3 -m http.server 4186 --directory .site`. Pagefind generates a same-origin
search index from each public page's `data-pagefind-body`. GitHub Pages deploys
`.site/`, including the index. Dependencies and local evidence are excluded.

Search supports Command/Ctrl-K and Escape. FAQ questions have stable heading
IDs; links to them open the matching answer. Keep existing IDs when editing
question wording. Add the shared search assets and indexed main element when
adding a public page.

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
