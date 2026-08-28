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
