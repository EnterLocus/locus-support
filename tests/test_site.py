import html.parser
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
import urllib.parse


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
    def test_every_page_has_basic_accessibility_and_social_metadata(self):
        self.assertGreaterEqual(len(html_files()), 6)
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
                self.assertEqual(
                    parser.meta.get("og:image"),
                    "https://enterlocus.com/assets/og.png",
                )
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

    def test_feedback_forms_repeat_the_public_privacy_boundary(self):
        forms = ROOT / ".github" / "ISSUE_TEMPLATE"
        for name in ["bug.yml", "feature.yml", "wishlist.yml"]:
            text = (forms / name).read_text()
            with self.subTest(form=name):
                self.assertIn("public", text.lower())
                self.assertIn("room", text.lower())
                self.assertIn("credentials", text.lower())
                self.assertIn("receipts", text.lower())
                self.assertIn("order", text.lower())
                self.assertIn("personal information", text.lower())
                self.assertIn("support@enterlocus.com", text)

    def test_public_repo_does_not_claim_the_private_app_is_open_source(self):
        self.assertFalse((ROOT / "LICENSE").exists())
        readme = (ROOT / "README.md").read_text()
        self.assertIn("private repository", readme)
        self.assertIn("does **not** publish the app source", readme)
        self.assertIn("does not publish the private Locus app source", (
            ROOT / "package-format" / "index.html").read_text())

    def test_homepage_keeps_pricing_details_out_of_product_story(self):
        homepage = (ROOT / "index.html").read_text()
        self.assertIn('href="./support/">Get support</a>', homepage)
        self.assertIn("Bring your own scenery and architecture.", homepage)
        self.assertNotIn("one custom View and one custom Room for free", homepage)
        self.assertNotIn("Planned for V1", homepage)
        self.assertNotIn(">Explore Locus</a>", homepage)

    def test_pricing_page_is_removed_and_faq_covers_product_boundaries(self):
        self.assertFalse((ROOT / "pricing" / "index.html").exists())
        faq = (ROOT / "faq" / "index.html").read_text()
        for answer in [
            "Mac Virtual Display",
            "passkey sign-in",
            "Why does importing more of my own content cost money?",
            "What is the Supporter subscription for?",
            "Blender MCP",
            "What custom files can I import?",
            "What does a skybox or View image need?",
            "12,288 × 6,144",
            "Where do my browsing and imported-place data go?",
        ]:
            self.assertIn(answer, faq)

        sitemap = (ROOT / "sitemap.xml").read_text()
        self.assertIn("https://enterlocus.com/faq/", sitemap)
        self.assertNotIn("/pricing/", sitemap)
        for path in html_files():
            text = path.read_text()
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertNotIn("/pricing/", text)
        self.assertEqual((ROOT / "index.html").read_text().count('href="./faq/"'), 1)

    def test_homepage_uses_five_real_simulator_captures(self):
        parser = PageParser()
        parser.feed((ROOT / "index.html").read_text())
        self.assertEqual(len(parser.images), 5)
        for image in parser.images:
            source = image.get("src", "")
            with self.subTest(source=source):
                self.assertTrue(source.startswith("./assets/screenshots/"))
                self.assertEqual(image.get("width"), "1920")
                self.assertEqual(image.get("height"), "1080")
                self.assertTrue((ROOT / source.removeprefix("./")).is_file())

    def test_typography_keeps_headings_readable(self):
        site_css = (ROOT / "assets" / "site.css").read_text()
        docs_css = (ROOT / "assets" / "docs.css").read_text()
        self.assertIn("clamp(3rem, 5.8vw, 5.4rem)", site_css)
        self.assertIn("line-height: 1", site_css)
        self.assertIn("clamp(2.75rem, 5.2vw, 4.7rem)", docs_css)
        self.assertIn("max-width: 70ch", docs_css)
        self.assertNotIn("7.9rem", site_css)
        self.assertNotIn("6.5rem", docs_css)

    def test_custom_domain_is_the_only_published_site_origin(self):
        self.assertEqual((ROOT / "CNAME").read_text().strip(), "enterlocus.com")
        legacy = "enterlocus.github.io" + "/locus-support"
        for path in ROOT.rglob("*"):
            if not path.is_file() or ".git" in path.parts:
                continue
            if path.suffix not in {".html", ".json", ".md", ".txt", ".xml", ".yml", ".py"}:
                continue
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertNotIn(legacy, path.read_text(errors="ignore"))

    def test_author_guide_uses_the_published_provenance_field_names(self):
        schema = json.loads((
            ROOT / "schemas" / "locusplace-provenance-v1.schema.json"
        ).read_text())
        guide = (ROOT / "create-your-own-place" / "index.html").read_text()
        for field in schema["required"]:
            self.assertIn(field, guide)
        for field in ["license.identifier", "license.name", "license.url"]:
            self.assertIn(field, guide)
        for stale_field in ["licenseName", "licenseURL", "requiredCredit"]:
            self.assertNotIn(stale_field, guide)

    def test_author_guide_matches_current_product_import_entry_points(self):
        guide = (ROOT / "create-your-own-place" / "index.html").read_text()
        reference = (ROOT / "reference" / "locusplace-format.md").read_text()
        for supported in [
            "Import a View",
            "Import a Room",
            ".heic",
            "at least one Room",
            "No catalog import",
        ]:
            self.assertIn(supported, guide)
        self.assertIn("There is no product entry point for a raw `catalog/`", reference)
        self.assertIn("View-only archive", reference)

    def test_schemas_have_one_published_source_of_truth(self):
        self.assertFalse(list((ROOT / "reference").glob("schemas/*.json")))
        reference = (ROOT / "reference" / "locusplace-format.md").read_text()
        self.assertIn("../schemas/locusplace-v1.schema.json", reference)
        self.assertIn("../schemas/locusplace-provenance-v1.schema.json", reference)

    def test_reproducible_examples_pass_the_published_validator(self):
        with tempfile.TemporaryDirectory() as directory:
            built = pathlib.Path(directory) / "examples"
            subprocess.run(
                [sys.executable, str(ROOT / "examples" / "build_examples.py"), str(built)],
                check=True,
                capture_output=True,
                text=True,
            )
            for name in [
                "view-only.locusplace",
                "room-only.locusplace",
                "combined.locusplace",
            ]:
                result = subprocess.run(
                    [sys.executable, str(ROOT / "tools" / "validate_locusplace.py"), str(built / name)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("VALID ", result.stdout)


if __name__ == "__main__":
    unittest.main()
