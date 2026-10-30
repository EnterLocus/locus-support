"""Gallery rendering contracts for the public static site."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))


class GallerySiteTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / "data" / "gallery.json").read_text())

    def test_build_writes_localized_place_and_series_pages_with_seo(self):
        from tools import build_site, render_gallery
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            shutil.copyfile(ROOT / 'sitemap.xml', output / 'sitemap.xml')
            catalogs = {locale: build_site.load_catalog(ROOT, locale) for locale in build_site.LOCALES}
            render_gallery.build(ROOT, output, catalogs, build_site._translate_document)
            for locale in build_site.LOCALES:
                prefix = output if locale == "en" else output / locale
                gallery = (prefix / "gallery" / "index.html").read_text()
                self.assertIn('data-gallery', gallery)
                self.assertIn('data-gallery-search', gallery)
                from tools.render_gallery import PREVIEW_COPY
                self.assertIn(PREVIEW_COPY[locale]["still"], gallery)
                self.assertIn(f'hreflang="{locale}"', gallery)
                for place in self.manifest["places"]:
                    self.assertTrue((prefix / "gallery" / "place" / place["slug"] / "index.html").is_file())
                for series in self.manifest["series"]:
                    self.assertTrue((prefix / "gallery" / "series" / series["id"] / "index.html").is_file())
            sitemap = (output / "sitemap.xml").read_text()
            self.assertIn("https://enterlocus.com/gallery/", sitemap)
            first = self.manifest["places"][0]
            self.assertIn(f'https://enterlocus.com/fr/gallery/place/{first["slug"]}/', sitemap)

    def test_detail_keeps_public_attribution_and_no_install_or_deep_link(self):
        from tools import render_gallery
        place = next(item for item in self.manifest["places"] if item["title"] == "Event Horizon: Ring")
        rendered = render_gallery.place_page(place, self.manifest, "en")
        self.assertIn("NASA, ESA, CSA, and STScI", rendered)
        self.assertIn('href="https://creativecommons.org/licenses/by/4.0/"', rendered)
        self.assertIn("https://esawebb.org/images/weic2212a/", rendered)
        self.assertIn("Get Locus on the App Store", rendered)
        self.assertNotIn("locus://", rendered)
        self.assertNotIn("Download", rendered)

    def test_folded_series_use_first_owner_and_recent_mixed_order(self):
        from tools import render_gallery
        def place(identifier, title, kind, date):
            return {"id": identifier, "slug": identifier, "type": kind, "title": title,
                    "description": "", "image": {"url": "/image.jpg", "width": 4, "height": 2},
                    "access": "free", "addedAt": date, "searchTerms": [], "localizations": {}}
        places = [place("one", "First", "view", "2026-10-04T00:00:00Z"),
                  place("two", "Second", "view", "2026-10-03T00:00:00Z"),
                  place("three", "Third", "room", "2026-10-05T00:00:00Z"),
                  place("four", "Fourth", "room", "2026-10-02T00:00:00Z")]
        series = [{"id": "first", "title": "Alpha", "members": ["one", "two"], "localizations": {}},
                  {"id": "duplicate", "title": "Duplicate", "members": ["one", "two"], "localizations": {}},
                  {"id": "mixed", "title": "Mixed", "type": "view", "members": ["one", "three"], "localizations": {}},
                  {"id": "rooms", "title": "Rooms", "members": ["three", "four"], "localizations": {}}]
        groups = render_gallery.eligible_series(places, series)
        self.assertEqual([group["series"]["id"] for group in groups], ["first", "rooms"])
        order = render_gallery.collection_order(places, series)
        self.assertEqual([item.get("series", {}).get("id") or item["place"]["id"] for item in order],
                         ["rooms", "first"])
        rendered = render_gallery.gallery_page({"places": places, "series": series}, "en")
        self.assertEqual(rendered.count('data-gallery-series-card'), 2)
        self.assertIn('data-series-member="true"', rendered)
        self.assertIn('data-search="first alpha"', rendered)

    def test_series_card_prefers_curated_cover_members(self):
        from tools import render_gallery
        members = [
            {"id": "newest", "image": {"url": "/newest.jpg", "width": 4, "height": 2}},
            {"id": "cover", "image": {"url": "/cover.jpg", "width": 4, "height": 2}},
            {"id": "older", "image": {"url": "/older.jpg", "width": 4, "height": 2}},
            {"id": "last", "image": {"url": "/last.jpg", "width": 4, "height": 2}},
        ]
        self.assertEqual([member["id"] for member in render_gallery.card_cover_members(
            {"cover": ["cover", "older"]}, members)], ["cover", "older", "newest"])

    def test_localized_series_title_is_searchable_from_its_member_cards(self):
        from tools import render_gallery
        rendered = render_gallery.gallery_page(self.manifest, "de")
        self.assertIn('bei nacht', rendered.lower())
        # The App accepts every author-provided Series title in any UI locale.
        self.assertRegex(rendered, r'data-search="[^"]*after dark[^"]*bei nacht[^"]*"')

    def test_series_detail_keeps_members_in_newest_first_order(self):
        from tools import render_gallery
        first = {"id": "first", "slug": "first", "type": "view", "title": "First", "description": "",
                 "image": {"url": "/first.jpg", "width": 4, "height": 2}, "access": "free", "addedAt": "2026-10-01T00:00:00Z"}
        newest = {**first, "id": "newest", "slug": "newest", "title": "Newest", "image": {"url": "/newest.jpg", "width": 4, "height": 2}, "updatedAt": "2026-10-02T00:00:00Z"}
        rendered = render_gallery.series_page({"id": "test", "title": "Test", "members": ["first", "newest"]}, [first, newest], "en")
        self.assertLess(rendered.index("Newest"), rendered.index("First"))

    def test_recent_sort_normalizes_timestamp_offsets(self):
        from tools import render_gallery
        older = {"id": "older", "title": "Older", "addedAt": "2026-10-02T00:30:00+01:00"}
        newer = {"id": "newer", "title": "Newer", "addedAt": "2026-10-01T23:45:00Z"}
        self.assertEqual([item["id"] for item in render_gallery.newest_first([older, newer])], ["newer", "older"])

    def test_photo_gallery_uses_only_exported_captures(self):
        from tools import render_gallery
        place = next(item for item in self.manifest["places"] if item["title"] == "Event Horizon: Ring").copy()
        place["photos"] = [
            {"url": "/assets/gallery/capture-front.jpg", "width": 1000, "height": 800,
             "sha256": "a" * 64, "label": "front", "captureKind": "visionos-simulator"},
            {"url": "/assets/gallery/capture-left.jpg", "width": 1000, "height": 800,
             "sha256": "b" * 64, "label": "left", "captureKind": "visionos-simulator"},
        ]
        rendered = render_gallery.place_page(place, self.manifest, "en")
        self.assertIn('data-gallery-photos', rendered)
        self.assertIn('/assets/gallery/capture-front.jpg', rendered)
        self.assertIn('Rendered in Locus · Simulator', rendered)
        self.assertIn('data-gallery-photo-dialog', rendered)
        self.assertIn('data-template="Photo {current} of {total}"', rendered)
        self.assertIn('data-template="Open photo {current} of {total}"', rendered)
        card = render_gallery.place_card(place, "en")
        self.assertIn('/assets/gallery/capture-front.jpg', card)
        self.assertNotIn(place["image"]["url"], card)
        series_card = render_gallery.series_card({"id": "test", "title": "Test"}, [place], place["type"], "en")
        self.assertIn('/assets/gallery/capture-front.jpg', series_card)
        self.assertNotIn(place["image"]["url"], series_card)
        no_photos = place.copy()
        no_photos.pop("photos")
        self.assertNotIn('data-gallery-photos', render_gallery.place_page(no_photos, self.manifest, "en"))
