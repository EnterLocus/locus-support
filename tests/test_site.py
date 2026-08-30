import hashlib
import html.parser
import json
import pathlib
import subprocess
import sys
import unittest
import urllib.parse
import zipfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
COMMUNITY_URL = "https://github.com/EnterLocus/locus-support/discussions"
BUG_URL = "https://github.com/EnterLocus/locus-support/issues/new?template=bug.yml"
IDEAS_URL = (
    "https://github.com/EnterLocus/locus-support/discussions/new"
    "?category=ideas-requests"
)
HELP_URL = (
    "https://github.com/EnterLocus/locus-support/discussions/new?category=help"
)
APP_STORE_URL = "https://apps.apple.com/app/id6802168265"


class PageParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.images = []
        self.h1_count = 0
        self.title_depth = 0
        self.title = ""
        self.lang = None
        self.has_viewport = False
        self.has_skip_link = False
        self.meta = {}
        self.head_links = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "html":
            self.lang = values.get("lang")
        elif tag == "a":
            href = values.get("href")
            if href:
                self.links.append(href)
            if values.get("class") == "skip-link" and href == "#main":
                self.has_skip_link = True
        elif tag == "img":
            self.images.append(values)
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "title":
            self.title_depth += 1
        elif tag == "meta":
            if values.get("name") == "viewport":
                self.has_viewport = True
            key = values.get("property") or values.get("name")
            if key:
                self.meta[key] = values.get("content", "")
        elif tag == "link":
            self.head_links.append(values)

    def handle_endtag(self, tag):
        if tag == "title":
            self.title_depth -= 1

    def handle_data(self, data):
        if self.title_depth:
            self.title += data


def html_files():
    return sorted(ROOT.glob("**/*.html"))


class PublicSiteTests(unittest.TestCase):
    def test_every_page_links_to_the_public_community(self):
        for path in html_files():
            parser = PageParser()
            parser.feed(path.read_text())
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertIn(COMMUNITY_URL, parser.links)

        home = (ROOT / "index.html").read_text()
        self.assertGreaterEqual(home.count(COMMUNITY_URL), 3)
        self.assertIn("Made with Locus", home)
        self.assertIn("Share your skyboxes, spaces, and environments", home)
        self.assertIn("Explore the Community", home)

        readme = " ".join((ROOT / "README.md").read_text().split())
        self.assertIn(COMMUNITY_URL, readme)
        self.assertIn("Share creations, ask questions", readme)

    def test_bugs_and_community_requests_use_distinct_routes(self):
        support = (ROOT / "support" / "index.html").read_text()
        for required in [BUG_URL, IDEAS_URL, HELP_URL]:
            self.assertIn(required, support)
        for obsolete in ["template=feature.yml", "template=wishlist.yml"]:
            self.assertNotIn(obsolete, support)

        self.assertTrue((ROOT / ".github" / "ISSUE_TEMPLATE" / "bug.yml").is_file())
        self.assertFalse((ROOT / ".github" / "ISSUE_TEMPLATE" / "feature.yml").exists())
        self.assertFalse((ROOT / ".github" / "ISSUE_TEMPLATE" / "wishlist.yml").exists())
        issue_config = (
            ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml"
        ).read_text()
        self.assertIn(IDEAS_URL, issue_config)
        self.assertIn(HELP_URL, issue_config)

        for path in html_files():
            parser = PageParser()
            parser.feed(path.read_text())
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertNotIn(
                    "https://github.com/EnterLocus/locus-support/issues/new/choose",
                    parser.links,
                )
                self.assertIn(BUG_URL, parser.links)

    def test_every_page_has_accessibility_and_social_metadata(self):
        self.assertGreaterEqual(len(html_files()), 7)
        for path in html_files():
            parser = PageParser()
            parser.feed(path.read_text())
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertEqual(parser.lang, "en")
                self.assertTrue(parser.has_viewport)
                self.assertTrue(parser.has_skip_link)
                self.assertEqual(parser.h1_count, 1)
                self.assertTrue(parser.title.strip())
                self.assertTrue(parser.meta.get("description"))
                self.assertTrue(parser.meta.get("og:title"))
                self.assertTrue(parser.meta.get("og:description"))
                self.assertEqual(parser.meta.get("og:type"), "website")
                relative = path.relative_to(ROOT)
                route = "/" if relative == pathlib.Path("index.html") else (
                    f"/{relative.parent.as_posix()}/"
                )
                canonical = f"https://enterlocus.com{route}"
                self.assertEqual(parser.meta.get("og:url"), canonical)
                relations = {
                    link.get("rel"): link.get("href")
                    for link in parser.head_links
                }
                self.assertEqual(relations.get("canonical"), canonical)
                self.assertIn("icon", relations)
                self.assertIn("apple-touch-icon", relations)
                for image in parser.images:
                    self.assertIn("alt", image)

    def test_header_brand_uses_the_production_app_icon(self):
        stylesheet = (ROOT / "assets" / "site.css").read_text()
        self.assertIn('url("./app-icon.png")', stylesheet)
        self.assertNotIn(".brand-mark::before", stylesheet)
        self.assertTrue((ROOT / "assets" / "app-icon.png").is_file())

        for path in html_files():
            with self.subTest(path=path.relative_to(ROOT)):
                page = path.read_text()
                self.assertIn('class="brand"', page)
                self.assertIn('aria-label="Locus home"', page)

    def test_local_links_resolve_inside_the_published_tree(self):
        for path in html_files():
            parser = PageParser()
            parser.feed(path.read_text())
            for href in parser.links:
                parsed = urllib.parse.urlsplit(href)
                if parsed.scheme or href.startswith("#"):
                    continue
                target = (path.parent / urllib.parse.unquote(parsed.path)).resolve()
                if parsed.path.endswith("/") or target.is_dir():
                    target = target / "index.html"
                with self.subTest(page=path.relative_to(ROOT), href=href):
                    self.assertTrue(target.is_relative_to(ROOT.resolve()))
                    self.assertTrue(target.is_file(), target)

    def test_private_app_source_boundary_remains_explicit(self):
        self.assertFalse((ROOT / "LICENSE").exists())
        readme = (ROOT / "README.md").read_text()
        package_page = (ROOT / "package-format" / "index.html").read_text()
        self.assertIn("private repository", readme)
        self.assertIn("does **not** publish the app source", readme)
        self.assertIn("does not publish the private Locus app source", package_page)

    def test_homepage_states_download_and_free_core_boundary(self):
        homepage = (ROOT / "index.html").read_text()
        self.assertIn("Available now for Apple Vision Pro.", homepage)
        self.assertIn("Core features are free to use", homepage)
        self.assertIn("with optional in-app purchases.", homepage)
        self.assertNotIn("not yet available", homepage)
        self.assertNotIn("not currently available for purchase", homepage)

    def test_homepage_uses_the_official_app_store_download_badge(self):
        homepage = (ROOT / "index.html").read_text()
        parser = PageParser()
        parser.feed(homepage)
        self.assertIn(APP_STORE_URL, parser.links)

        badges = [
            image for image in parser.images
            if image.get("src") == "./assets/download-on-the-app-store.svg"
        ]
        self.assertEqual(len(badges), 1)
        self.assertEqual(badges[0].get("alt"), "Download on the App Store")

        badge_path = ROOT / "assets" / "download-on-the-app-store.svg"
        self.assertEqual(
            hashlib.sha256(badge_path.read_bytes()).hexdigest(),
            "a26fc5b38380272c92e9019a2eb8b45542a66814b3e2b203772db8904b9fb99f",
        )
        asset_record = (ROOT / "assets" / "README.md").read_text()
        self.assertIn("App Store marketing guidelines", asset_record)
        self.assertIn(APP_STORE_URL, asset_record)

    def test_homepage_uses_current_launch_media(self):
        expected = {
            "imports-virtual-space.jpg":
                "4195481daae7b2fa03da26a779abe15ccd900f1c98f66f74656050da488113cc",
            "place-picker.jpg":
                "fdb4556a77c82b924b001d2212dc7459db787bfb08e8ae22113453623e52d4ee",
            "virtual-space-desk-wide.jpg":
                "204fad0f6d3b5a977268cc4365a4e74db32ed8c3695be09ed988a8dc9187726c",
            "virtual-space-room-turn.jpg":
                "5e7bc4e4aa2719a0441efc9cc5512fed19016c7a905da92d2eb5f066dee732a3",
        }
        screenshot_root = ROOT / "assets" / "screenshots"
        self.assertEqual(
            {path.name for path in screenshot_root.glob("*.jpg")},
            set(expected),
        )
        homepage = (ROOT / "index.html").read_text()
        parser = PageParser()
        parser.feed(homepage)
        screenshot_images = [
            image for image in parser.images
            if image["src"].startswith("./assets/screenshots/")
        ]
        homepage_sources = {
            pathlib.Path(image["src"]).name for image in screenshot_images
        }
        self.assertEqual(homepage_sources, set(expected))
        for image in screenshot_images:
            self.assertEqual(image.get("width"), "1920")
            self.assertEqual(image.get("height"), "1080")
            self.assertTrue(image.get("alt", "").strip())
            filename = pathlib.Path(image["src"]).name
            if filename == "virtual-space-desk-wide.jpg":
                self.assertEqual(image.get("fetchpriority"), "high")
            else:
                self.assertEqual(image.get("loading"), "lazy")
                self.assertEqual(image.get("decoding"), "async")
        for filename, digest in expected.items():
            with self.subTest(filename=filename):
                self.assertEqual(
                    hashlib.sha256((screenshot_root / filename).read_bytes()).hexdigest(),
                    digest,
                )
        capture_guide = (ROOT / "docs" / "capturing-product-screenshots.md").read_text()
        asset_record = (ROOT / "assets" / "README.md").read_text()
        for filename in expected:
            self.assertIn(filename, capture_guide)
            self.assertIn(filename, asset_record)
        self.assertNotIn("five 16:9 master captures", capture_guide)

    def test_flat_public_format_replaces_the_old_envelope(self):
        paths = [
            ROOT / "create-your-own-place" / "index.html",
            ROOT / "package-format" / "index.html",
            ROOT / "reference" / "locus-asset-format.md",
            ROOT / ".agents" / "skills" / "build-original-locus-room" / "SKILL.md",
        ]
        for path in paths:
            text = path.read_text()
            with self.subTest(path=path.relative_to(ROOT)):
                for obsolete in [
                    ".locusplace", "locusplace.json", "catalog/",
                    "experience.json", "packageID", "contentHash",
                    "teleportCatalog",
                ]:
                    self.assertNotIn(obsolete, text)

        guide = paths[0].read_text()
        for required in [
            "my-room.zip", "space.json", "provenance.json",
            "teleport-points.json", "scene.usdz", "thumbnail.jpg",
            "All five files are required", "displayName",
            "assigns each imported asset a UUID", "Names are display text and may repeat",
            "does not take a thumbnail",
        ]:
            self.assertIn(required, guide)

        for removed in [
            ROOT / "schemas" / "locusplace-v1.schema.json",
            ROOT / "tools" / "validate_locusplace.py",
            ROOT / "tools" / "pack_locusplace.py",
            ROOT / "examples" / "generated" / "room-only.locusplace",
        ]:
            self.assertFalse(removed.exists())

    def test_view_appearance_controls_are_documented(self):
        guide = (ROOT / "create-your-own-place" / "index.html").read_text()
        reference = (ROOT / "reference" / "locus-asset-format.md").read_text()
        faq = (ROOT / "faq" / "index.html").read_text()
        for field in [
            "initialYawDegrees", "skyGainEV", "exposureEV",
            "horizonPitchDegrees", "colorGrade.contrast",
            "colorGrade.saturation", "directSun",
        ]:
            self.assertIn(field, guide + reference)
        for label in [
            "View Brightness", "Contrast", "Color", "Room Lighting",
            "Add Sunlight", "Sun Position", "Sunlight Strength", "Turn the View",
        ]:
            self.assertIn(label, guide + faq)
        self.assertIn("0.5", guide)
        self.assertIn("2.0", guide)

    def test_sample_skill_is_public_safe_and_includes_its_tools(self):
        root = ROOT / ".agents" / "skills" / "build-original-locus-room"
        skill = (root / "SKILL.md").read_text()
        flat_skill = " ".join(skill.split())
        self.assertTrue(skill.startswith("---\n"))
        for required in [
            "This is a sample skill", "Blender MCP", "thumbnail.jpg",
            "teleport-points.json", "aiGenerated", "aiProvider",
            "pack_locus_asset.py", "validate_locus_asset.py",
            "try every declared seat on Apple Vision Pro",
        ]:
            self.assertIn(required, flat_skill)
        for private_detail in ["/Users/", "Dropbox", "Locus Dev"]:
            self.assertNotIn(private_detail, skill)
        self.assertEqual(
            (root / "scripts" / "validate_locus_asset.py").read_bytes(),
            (ROOT / "tools" / "validate_locus_asset.py").read_bytes(),
        )
        self.assertEqual(
            (root / "scripts" / "pack_locus_asset.py").read_bytes(),
            (ROOT / "tools" / "pack_locus_asset.py").read_bytes(),
        )
        guide = (ROOT / "create-your-own-place" / "index.html").read_text()
        self.assertLess(guide.index("Try a complete Room"), guide.index("Use the sample Room skill"))
        self.assertIn(
            "https://github.com/EnterLocus/locus-support/tree/main/"
            ".agents/skills/build-original-locus-room",
            guide,
        )

    def test_demo_room_is_flat_pinned_and_valid(self):
        demo = ROOT / "examples" / "demo-room.zip"
        self.assertEqual(demo.stat().st_size, 8_024_506)
        self.assertEqual(
            hashlib.sha256(demo.read_bytes()).hexdigest(),
            "bab6c4f6847513bc697e7a00b1b943611d9c9f0cf6757173f451f4121bb9a16d",
        )
        with zipfile.ZipFile(demo) as archive:
            self.assertEqual(set(archive.namelist()), {
                "space.json", "provenance.json", "teleport-points.json",
                "scene.usdz", "thumbnail.jpg",
            })
            room = json.loads(archive.read("space.json"))
            provenance = json.loads(archive.read("provenance.json"))
            self.assertEqual(room["displayName"], "Demo Room")
            self.assertNotIn("id", room)
            self.assertTrue(provenance["aiGenerated"])
            self.assertEqual(
                provenance["license"]["identifier"],
                "LicenseRef-EnterLocus-Proprietary",
            )
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "validate_locus_asset.py"), str(demo)],
            check=False, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('VALID: room "Demo Room"', result.stdout)
        for page in [
            ROOT / "create-your-own-place" / "index.html",
            ROOT / "package-format" / "index.html",
        ]:
            text = page.read_text()
            self.assertIn("first Room included with Locus", text)
            self.assertIn("not a new Room design", text)

    def test_asset_rights_page_matches_first_party_provenance(self):
        rights = (ROOT / "asset-rights" / "index.html").read_text()
        for term in [
            "LicenseRef-EnterLocus-Proprietary", "EnterLocus.com",
            "AI disclosure", "aiGenerated", "aiProvider",
        ]:
            self.assertIn(term, rights)
        schema = json.loads((ROOT / "schemas" / "provenance-v1.schema.json").read_text())
        self.assertEqual(
            schema["$id"], "https://enterlocus.com/schemas/provenance-v1.schema.json"
        )
        self.assertIn("https://enterlocus.com/asset-rights/", (
            ROOT / "sitemap.xml"
        ).read_text())


if __name__ == "__main__":
    unittest.main()
