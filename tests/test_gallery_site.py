"""Gallery rendering contracts for the public static site."""
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class GallerySiteTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / "data" / "gallery.json").read_text())

    def test_build_writes_localized_place_and_series_pages_with_seo(self):
        from tools import build_site
        with tempfile.TemporaryDirectory() as directory:
            old_output = build_site.OUTPUT
            try:
                build_site.OUTPUT = Path(directory) / ".site"
                build_site.build()
                for locale in ("en", "fr", "zh-Hans"):
                    prefix = build_site.OUTPUT if locale == "en" else build_site.OUTPUT / locale
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
                sitemap = (build_site.OUTPUT / "sitemap.xml").read_text()
                self.assertIn("https://enterlocus.com/gallery/", sitemap)
                first = self.manifest["places"][0]
                self.assertIn(f'https://enterlocus.com/fr/gallery/place/{first["slug"]}/', sitemap)
            finally:
                build_site.OUTPUT = old_output

    def test_detail_keeps_public_attribution_and_no_install_or_deep_link(self):
        from tools import render_gallery
        place = next(item for item in self.manifest["places"] if item["title"] == "Event Horizon: Ring")
        rendered = render_gallery.place_page(place, self.manifest, "en")
        self.assertIn("NASA, ESA, CSA, and STScI", rendered)
        self.assertIn("https://esawebb.org/images/weic2212a/", rendered)
        self.assertIn("Get Locus on the App Store", rendered)
        self.assertNotIn("locus://", rendered)
        self.assertNotIn("Download", rendered)
