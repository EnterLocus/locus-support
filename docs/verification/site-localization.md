# Eight-language website localization verification

Baseline: `f6edd40` (current website main, including the visionOS 27 / Xcode 27 Mac Virtual Display article). Refreshed main again before delivery; no source delta remained.

The build stages 28 English source pages into 224 routes across en, zh-Hans, zh-Hant, ja, ko, de, fr and es. Each translated catalog contains the current 1,735 extracted source keys, with no missing/extra keys, marker leakage or broken Apple Vision Pro compounds. Source HTML, IDs, download paths, binaries, versions and authored English claims remain intact. Code/preformatted blocks and upstream technical menu names are preserved. Missing/blank future entries fall back to English.

## Validation

- `python3 -m unittest tests/test_site.py tests/test_search_site.py tests/test_site_localization.py`: 39 passed.
- `npm run build`: 8 Pagefind languages and 224 indexed pages.
- `npm run test:search`: 13 passed, covering persisted language, unsupported System fallback, Chinese script precedence, denied storage, explicit language URLs, translated search, failure links, FAQ anchors and existing media/search behavior.
- `git diff --check` passed; compileall passed for the localization, generator and preview-server helpers.
- Staged local links resolved to existing files. Desktop 1440×1000 and phone-width 390×844 homepages in all eight languages had no horizontal overflow.

## Copy and visual review

On-device Translation.framework drafts were reconciled with App feature labels and official resource names, then reviewed in context. Homepage, privacy, Mac Virtual Display and reported feature/technical paths received focused review, including gesture/direction/negation, import formats, versions, units and licensing boundaries. Full native-speaker proofreading of every archived paragraph remains unperformed.

Actual Chromium screenshots were inspected and shown in the task conversation. Poster-fallback captures keep the existing media visible without asserting third-party playback acceptance. Existing image/video bytes and the English App Store badge were retained. No physical-device or Vision Pro browser acceptance is claimed.

The original/translation comparison is outside Git: `.scratch/website-translations.html`, `.md`, and `website-translation-pairs.json`. Screenshots are also excluded; hashes below identify the reviewed evidence.

| Evidence | SHA-256 |
| --- | --- |
| zh-Hans-home-final.png | `c6d62c1467c999ace8e243867d74a0cf48eff9c32cab151b9c44fb7d614ff184` |
| zh-Hans-home-mobile-final.png | `5956da59cefe56a1b6a84faa87cf0b24b7a0c5b839eaece08d5a8ffcd3275900` |
| zh-Hant-mvd-final.png | `80cb5e89d74dbcbde2692b9823af5a8d967ead3a4be0c4f2517dc2ee0370cfc3` |
| de-home-final.png | `cbfa78e9ef40ad5180824c047bcba869a2b764169450ba24855859643b152ab2` |
| fr-home-final.png | `bb2787706fbae50cadb8d5e5c1fe9ab06cce2f6b0748c640553bdf4c7a432132` |
| es-home-mobile-final.png | `820563ff74ecc6f313bd8c31a8e164669ae30e98c791d7bd0cb9c8afdf7bd0d1` |
| zh-Hans-mvd-final.png | `5310d59ac7d945dd1d9de177ac515200e01fcadba2cd51bab17f28de8433a71c` |

## Delivery and recovery

Merge is separate from publication. Confirm the Pages workflow deployment succeeds, then read back all eight language URLs and a representative localized tutorial/search asset over HTTPS. Recovery is a revert of the localization PR and a successful Pages redeploy; the original English sources and shared media remain available.

## Archived control-copy follow-up

The comparison-report visual review found five source paragraphs whose drafts treated named controls as showroom furniture, attached the immersion setting to the physical keyboard, or reversed the default-off condition. All seven translated catalogs now use the App control labels and retain the intended off-until-enabled and standing-up-is-insufficient behavior. English sources are unchanged.

The existing 39 Python contracts passed again, and the build indexed 224 pages in eight languages. The Chinese 1.1.5 article and corrected searchable comparison report were inspected in Chromium; all seven report selections showed 1,735 source rows with zero missing translations, and filtering worked. Prior browser behavior checks remain applicable because this follow-up changes five catalog values per language only.

- archived-controls-chinese.png: `69a0254ae50be4ed5b71c2f8c6e5db59a5093ca2112c913c7edae2e588f8a1e8`

- website-translations-review.png: `36d17ce1411e2eb9b62f9337803fe5051c8c694cd10b3e57ab5d69b3c5843d1a`
