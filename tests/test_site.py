import hashlib
import html.parser
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
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
        self.videos = []
        self.sources = []
        self.tracks = []
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
        elif tag == "video":
            self.videos.append(values)
        elif tag == "source":
            self.sources.append(values)
        elif tag == "track":
            self.tracks.append(values)
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
        self.assertIn("does **not** publish or license the app", readme)
        self.assertIn("does not publish the private Locus app source", package_page)

        license_map = " ".join((ROOT / "LICENSE.md").read_text().split())
        for scoped_path in [
            ".agents/skills/build-original-locus-room/**",
            "tools/**",
            "schemas/**",
        ]:
            self.assertIn(scoped_path, license_map)
        for reserved in [
            "website's text and media", "Locus application source",
            "names, logos, app icons",
        ]:
            self.assertIn(reserved, license_map)
        apache = (ROOT / "LICENSES" / "Apache-2.0.txt").read_text()
        self.assertIn("Apache License", apache)
        self.assertIn("Version 2.0, January 2004", apache)
        self.assertIn("END OF TERMS AND CONDITIONS", apache)

    def test_homepage_states_download_and_free_core_boundary(self):
        homepage = (ROOT / "index.html").read_text()
        self.assertIn("Available now for Apple Vision Pro.", homepage)
        self.assertIn("Core features are free to use", homepage)
        self.assertIn("with optional in-app purchases.", homepage)
        self.assertNotIn("not yet available", homepage)
        self.assertNotIn("not currently available for purchase", homepage)

    def test_online_view_guide_leads_with_the_direct_use_resolution_gate(self):
        guide_path = ROOT / "online-views" / "index.html"
        self.assertTrue(guide_path.is_file())
        guide = guide_path.read_text()
        homepage = (ROOT / "index.html").read_text()
        faq = (ROOT / "faq" / "index.html").read_text()

        for text in [guide, homepage, faq]:
            self.assertIn("4,096 × 2,048", text)
            self.assertIn("2:1", text)

        self.assertLess(
            guide.index("Only a complete panorama"),
            guide.index("Know what to look for"),
        )
        for required in [
            "Use this 360° image as a View?",
            "fills its own Browser tab",
            "200 MB",
            "enter a place first",
            "Apply Preview",
            "Save as View…",
            "does not use an import allowance",
            "uses an available import",
            "temporary storage",
            "Original file",
            "filename is the suggested name",
            "applies it immediately",
            "Get More Imports",
        ]:
            self.assertIn(required, guide)

        # The in-page "Use as View" corner mark was removed in Locus 1.1;
        # only an image that is the whole tab can become a View, so the public
        # site must not describe a control that no longer exists.
        for text in [guide, homepage, faq]:
            self.assertNotIn("Use as View", text)
        self.assertIn("Why does a 360° image not show the View prompt?", faq)
        self.assertIn("Command-N", faq)
        self.assertIn('href="./online-views/"', homepage)
        self.assertIn('href="../online-views/"', faq)
        self.assertIn(
            "https://enterlocus.com/online-views/",
            (ROOT / "sitemap.xml").read_text(),
        )

    def test_faq_explains_the_missing_window_move_bar_workaround(self):
        faq = (ROOT / "faq" / "index.html").read_text()

        for required in [
            "Why is the move bar below a window sometimes missing?",
            "The window remains usable",
            "still works even when it is not visible",
            "Look just below the window",
            "pinch and drag where the bar normally appears",
        ]:
            self.assertIn(required, faq)

    def test_online_view_guide_has_a_tryable_example_and_current_instructions(self):
        guide_path = ROOT / "online-views" / "index.html"
        guide = guide_path.read_text()
        parser = PageParser()
        parser.feed(guide)

        example_href = "../assets/online-views/autumn-hill-view-4k.jpg"
        self.assertIn(example_href, parser.links)
        for required in [
            "Open the 4K example",
            "far right of the Download controls",
            "8K Tonemapped JPG",
            "Do not choose HDR or EXR",
            "Locus supports SDR JPEG, PNG, and HEIC panorama images",
            "HDR and EXR are not supported",
            "Blockade Labs Skybox AI",
            "Resolution 8K",
            "Equirectangular",
            "Download JPG",
            "Download PNG",
            "Export Status",
            "same-site <code>blob:</code> and <code>data:</code> downloads",
        ]:
            self.assertIn(required, guide)

        expected = {
            "autumn-hill-view-4k.jpg":
                "2bb008620de63b75cfdd7d66a04090a7c9695379a035df3bb9fc9cf6c2a568f6",
            "locus-browser-view-actions.png":
                "157047df17a9d8cc3b524f4ba3e989bc6bfae6961b3c1e36611f13da60f754ce",
            "poly-haven-tonemapped-menu.jpg":
                "a366481e9e669aa0b56d613d7ae7cdf43e6edba0db74d9cd48d8393b540dfbd5",
        }
        asset_root = ROOT / "assets" / "online-views"
        self.assertEqual(
            {path.name for path in asset_root.iterdir() if path.is_file()},
            set(expected) | {"README.md"},
        )
        asset_record = (asset_root / "README.md").read_text()
        for filename, digest in expected.items():
            with self.subTest(filename=filename):
                self.assertEqual(
                    hashlib.sha256((asset_root / filename).read_bytes()).hexdigest(),
                    digest,
                )
                self.assertIn(filename, asset_record)
                self.assertIn(digest, asset_record)

        guide_images = {
            pathlib.Path(image["src"]).name: image
            for image in parser.images
            if image["src"].startswith("../assets/online-views/")
        }
        self.assertEqual(set(guide_images), set(expected))
        for image in guide_images.values():
            self.assertTrue(image.get("alt", "").strip())
            self.assertTrue(image.get("width", "").isdigit())
            self.assertTrue(image.get("height", "").isdigit())

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

    def test_homepage_uses_authentic_promotional_media(self):
        expected = {
            "locus-1.1-whats-new-33s.mp4":
                "a8eb882e95cf22df34b75be2737eb5cee53b1596a645572afabee88f23decb6b",
            "locus-1.1-whats-new-poster.jpg":
                "2d6138f23bab8209ef0b45ebf5675bb07543f52ff877614206c7dc1a18a2d597",
            "locus-promo-31s-v2.mp4":
                "7fe19092d03a2e43cdf795ee0f6c7f8c1667e33da439324b17f5b4699865117a",
            "locus-promo-31s.mp4":
                "aeb2f37eb4e5e365cde6e4c534f819abc2bca68189861c243d901754444a8e95",
            "locus-promo-poster.jpg":
                "484899e0aa9ce36ab301ab2d3292a12f95b558e88f4f824a86de88e7724fe49c",
            "still-01-change-view.jpg":
                "91955d07b15323bf04819ab0b257820d9a93ee2ffb69a76ce848ff15016f190b",
            "still-02-desk.jpg":
                "2f995e767ed0d4b5a89d063df961c66ad2c9f8ad42d8c8e588652db7db49fc73",
            "still-03-browser.jpg":
                "42352f05732727e173d696add5f44f938c392f185c2b948fb85da29da3ac0f28",
            "still-04-walls.jpg":
                "cf52c51dd6fdbbfeafcbacbaf65f368532b5895a165cf0b30cbb67e0c3c327b6",
            "still-05-own-view.jpg":
                "a7772cc62b43eb8ce618c5bed69d06157883d1669b41c3bff6a43a0a8ac82bbe",
            "still-06-import-room.jpg":
                "6989b8c373eae26ba82f8578f022d4ff0041e8fe507b750be034c10a1a1900e5",
        }
        promo_root = ROOT / "assets" / "promo"
        self.assertEqual(
            {path.name for path in promo_root.iterdir() if path.is_file()},
            set(expected),
        )

        homepage = (ROOT / "index.html").read_text()
        parser = PageParser()
        parser.feed(homepage)
        self.assertEqual(len(parser.videos), 2)
        videos_by_class = {video.get("class"): video for video in parser.videos}
        hero_video = videos_by_class["hero-video"]
        for attribute in ["controls", "autoplay", "muted", "loop", "playsinline"]:
            self.assertIn(attribute, hero_video)
        self.assertEqual(hero_video.get("preload"), "metadata")
        self.assertEqual(hero_video.get("width"), "1920")
        self.assertEqual(hero_video.get("height"), "1080")
        self.assertEqual(
            hero_video.get("src"),
            "./assets/promo/locus-promo-31s-v2.mp4",
        )
        self.assertEqual(
            hero_video.get("poster"),
            "./assets/screenshots/virtual-space-desk-wide.jpg",
        )
        self.assertEqual(parser.sources, [])
        self.assertEqual(parser.tracks, [])
        self.assertEqual(
            parser.links.count("./assets/promo/locus-promo-31s-v2.mp4"),
            1,
        )
        self.assertNotIn("./assets/promo/locus-promo-31s.mp4", homepage)
        self.assertNotIn("Watch the video directly.", homepage)
        self.assertIn(
            "Keyboard passthrough is provided by visionOS, not Locus.",
            homepage,
        )
        self.assertNotIn("video transcript", homepage)
        self.assertNotIn("See Locus in motion", homepage)
        stylesheet = (ROOT / "assets" / "site.css").read_text()
        self.assertIn("@media (prefers-reduced-motion: reduce)", stylesheet)
        self.assertNotIn("@media (hover: none) and (pointer: coarse)", stylesheet)
        self.assertIn(".hero-video-mobile { display: block; }", stylesheet)
        self.assertNotIn(".hero-shot video", stylesheet)
        self.assertIn(
            ".hero-video { display: block; width: 100%; height: auto; "
            "border-radius: 1rem; }",
            stylesheet,
        )
        hero_shot_rule = re.search(r"^\.hero-shot \{([^}]*)\}", stylesheet, re.MULTILINE)
        self.assertIsNotNone(hero_shot_rule)
        self.assertNotIn("transform", hero_shot_rule.group(1))

        # Keep the static MP4 within Apple's maximum-compatibility H.264
        # envelope for iPhone browsers. Chrome on iOS uses the platform media
        # stack, so a desktop-playable encode can still fail on a phone when
        # its declared AVC level is unnecessarily high.
        for movie_name in ["locus-promo-31s-v2.mp4", "locus-1.1-whats-new-33s.mp4"]:
            with self.subTest(movie=movie_name):
                movie = (promo_root / movie_name).read_bytes()
                avcc = movie.index(b"avcC")
                self.assertEqual(movie[avcc + 4], 1)  # AVCDecoderConfigurationRecord
                self.assertEqual(movie[avcc + 5], 100)  # High Profile
                self.assertLessEqual(movie[avcc + 7], 41)  # Level 4.1 or lower
                self.assertLess(movie.index(b"moov"), movie.index(b"mdat"))

        promo_images = [
            image for image in parser.images
            if image["src"].startswith("./assets/promo/still-")
        ]
        self.assertEqual(len(promo_images), 6)
        for image in promo_images:
            self.assertEqual(image.get("width"), "1920")
            self.assertEqual(image.get("height"), "1080")
            self.assertEqual(image.get("loading"), "lazy")
            self.assertEqual(image.get("decoding"), "async")
            self.assertTrue(image.get("alt", "").strip())

        for filename, digest in expected.items():
            with self.subTest(filename=filename):
                self.assertEqual(
                    hashlib.sha256((promo_root / filename).read_bytes()).hexdigest(),
                    digest,
                )

        asset_record = (ROOT / "assets" / "README.md").read_text()
        for filename in expected:
            self.assertIn(filename, asset_record)

    def test_homepage_faq_and_guide_announce_locus_1_1(self):
        homepage = (ROOT / "index.html").read_text()
        parser = PageParser()
        parser.feed(homepage)

        # The 1.1 section leads with the approved What's New master and the
        # same four highlights the app shows in its own What's New sheet.
        self.assertIn('id="whats-new"', homepage)
        self.assertIn('href="#whats-new"', homepage)
        self.assertIn("New in Locus 1.1", homepage)
        self.assertIn("More ways to make your workspace yours.", homepage)
        for highlight in [
            "Bring panoramas from the web",
            "Organize every Place",
            "Shape the light",
            "Keep favorite sites close",
        ]:
            self.assertIn(highlight, homepage)

        videos_by_class = {video.get("class"): video for video in parser.videos}
        whats_new = videos_by_class["whats-new-video"]
        for attribute in ["controls", "muted", "playsinline"]:
            self.assertIn(attribute, whats_new)
        for attribute in ["autoplay", "loop"]:
            self.assertNotIn(attribute, whats_new)
        self.assertEqual(whats_new.get("preload"), "metadata")
        self.assertEqual(whats_new.get("width"), "1920")
        self.assertEqual(whats_new.get("height"), "1080")
        self.assertEqual(
            whats_new.get("src"), "./assets/promo/locus-1.1-whats-new-33s.mp4")
        self.assertEqual(
            whats_new.get("poster"),
            "./assets/promo/locus-1.1-whats-new-poster.jpg",
        )
        self.assertTrue(whats_new.get("aria-label", "").strip())
        self.assertEqual(
            parser.links.count("./assets/promo/locus-1.1-whats-new-33s.mp4"), 1)
        stylesheet = (ROOT / "assets" / "site.css").read_text()
        self.assertIn(".whats-new-grid", stylesheet)

        faq = (ROOT / "faq" / "index.html").read_text()
        for question in [
            "How do I turn on Room Lights?",
            "How do I rename, favorite, tag, and filter my Places?",
            "How do Browser Favorites and the Start Page work?",
        ]:
            self.assertIn(question, faq)
        self.assertIn("2,000 K to 6,500 K", faq)
        self.assertIn("Favorites First", faq)
        self.assertIn("star", faq)

        # Locus Skies is an experimental gallery, linked only from the web
        # guide and FAQ, never from the home page or app-facing copy.
        skies = "https://skies.enterlocus.com/"
        guide = (ROOT / "online-views" / "index.html").read_text()
        self.assertIn(skies, guide)
        self.assertIn(skies, faq)
        self.assertNotIn(skies, homepage)
        self.assertLess(
            guide.index("Only a complete panorama"), guide.index("Browse Locus Skies."))
        self.assertLess(
            guide.index("Browse Locus Skies."), guide.index("Know what to look for"))
        for required in [
            "Experimental",
            "Open full image",
            "experimental playground",
            "added, replaced, and removed without notice",
            "CC BY 4.0",
        ]:
            self.assertIn(required, guide)

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
            "does not generate a thumbnail",
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
            "This is a sample skill", "professional 3D workflow",
            "thumbnail.jpg", "teleport-points.json", "aiGenerated",
            "aiProvider", "luminaireGroups", "nearTeleportIDs",
            "bakedIndirect.entities", "pack_locus_asset.py",
            "validate_locus_asset.py", "scaffold_locus_room.py",
            "references/room-interface.md", "references/design-language.md",
            "Do not stop after producing metadata", "SHA-256",
            "write an opaque USD PreviewSurface",
            "not the DCC, renderer, exporter",
            "try every declared seat on Apple Vision Pro",
            "Declare optional experimental animations", "ambientAnimations",
            "[0, 0]", "may change",
        ]:
            self.assertIn(required, flat_skill)
        for private_detail in ["/Users/", "Dropbox", "Locus Dev", "Blender MCP"]:
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
        self.assertLess(
            guide.index("Try three complete Rooms"),
            guide.index("Bring your own Room"),
        )
        self.assertIn(
            "https://github.com/EnterLocus/locus-support/tree/main/"
            ".agents/skills/build-original-locus-room",
            guide,
        )
        room_guide = (ROOT / "build-a-room" / "index.html").read_text()
        for required in [
            "Build with an AI assistant", "create an original Room",
            "scaffold the five delivery files", "cannot operate a suitable 3D tool",
            "Offline Room contract", "scaffolder", "delivery checks",
        ]:
            self.assertIn(required, room_guide)

    def test_sample_skill_references_are_portable_and_public_safe(self):
        source = ROOT / ".agents" / "skills" / "build-original-locus-room"
        with tempfile.TemporaryDirectory(prefix="locus-skill-offline-") as directory:
            root = (pathlib.Path(directory) / source.name).resolve()
            shutil.copytree(source, root)
            links_checked = 0
            for path in root.rglob("*.md"):
                content = path.read_text()
                with self.subTest(path=path.relative_to(root)):
                    for private_detail in [
                        "/Users/", "Dropbox", "Locus Dev", "model-preview/",
                        "--simulator-head-pose",
                    ]:
                        self.assertNotIn(private_detail, content)
                    self.assertNotRegex(
                        content, r"github\.com/EnterLocus/locus(?:/|[)#\s]|$)"
                    )
                targets = re.findall(r"\[[^\]]+\]\(([^)]+)\)", content)
                targets += re.findall(
                    r"`((?:references|scripts)/[^`\s]+|\.\./SKILL\.md)`", content
                )
                for target in targets:
                    parsed = urllib.parse.urlsplit(target)
                    if parsed.scheme or parsed.netloc or not parsed.path:
                        continue
                    resolved = (path.parent / urllib.parse.unquote(parsed.path)).resolve()
                    with self.subTest(path=path.relative_to(root), target=target):
                        self.assertTrue(resolved.is_relative_to(root), target)
                        self.assertTrue(resolved.is_file(), target)
                    links_checked += 1
            self.assertGreater(links_checked, 0)

    def test_sample_skill_scaffolds_packs_and_validates_a_lit_room(self):
        root = ROOT / ".agents" / "skills" / "build-original-locus-room"
        scaffold = root / "scripts" / "scaffold_locus_room.py"
        packer = root / "scripts" / "pack_locus_asset.py"
        validator = root / "scripts" / "validate_locus_asset.py"
        interface = (root / "references" / "room-interface.md").read_text()
        design = (root / "references" / "design-language.md").read_text()
        for required in [
            "One-seat Room v3 example", "Three glazed sides",
            "emissive fixture bodies", "Exact delivery gates",
            "valid USDZ may still contain opaque glass",
            "seatWorldZ - boundsMinZ", "place the visitor under a lamp",
        ]:
            self.assertIn(required, interface)
        for required in [
            "quiet contemporary pavilion", "three glazed sides",
            "visibly on whenever its Locus control is enabled",
        ]:
            self.assertIn(required, design)

        with tempfile.TemporaryDirectory(prefix="locus-public-skill-test-") as directory:
            temporary = pathlib.Path(directory)
            with zipfile.ZipFile(ROOT / "examples" / "atrium-loft-room.zip") as archive:
                scene = temporary / "source.usdz"
                thumbnail = temporary / "source.jpg"
                scene.write_bytes(archive.read("scene.usdz"))
                thumbnail.write_bytes(archive.read("thumbnail.jpg"))

            room = temporary / "room"
            archive = temporary / "room.zip"
            result = subprocess.run([
                sys.executable, str(scaffold), str(room),
                "--scene", str(scene),
                "--thumbnail", str(thumbnail),
                "--display-name", "Skill Fixture Pavilion",
                "--caption", "A one-seat packaging fixture.",
                "--creator", "EnterLocus.com",
                "--requested-credit", "Locus",
                "--modification-notes", "Test metadata around an existing public fixture.",
                "--ai-provider", "OpenAI Codex",
                "--license-id", "LicenseRef-EnterLocus-Proprietary",
                "--license-name", "EnterLocus proprietary asset license",
                "--license-url", "https://enterlocus.com/asset-rights/",
                "--seat-id", "ground-work-desk",
                "--seat-title", "Work Seat",
                "--wall-entity", "Rear_Plaster_Wall",
                "--roof-entity", "Floating_Roof",
                "--desk-entity", "Ground_Work_Desk_Top",
                "--light-id", "ground-work-pendant",
                "--light-name", "Ground Work Pendant",
                "--light-body", "Work_Pendant_Glow",
                "--light-anchor", "Work_Pendant_Glow",
            ], check=False, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                {path.name for path in room.iterdir()},
                {"space.json", "provenance.json", "teleport-points.json",
                 "scene.usdz", "thumbnail.jpg"},
            )
            metadata = json.loads((room / "space.json").read_text())
            self.assertEqual(metadata["formatVersion"], 2)
            self.assertEqual(len(metadata["lighting"]["luminaireGroups"]), 1)
            self.assertNotIn("nearTeleportIDs", metadata["lighting"]["luminaireGroups"][0])

            # Re-run the public scaffolder with explicit v5 author roles.
            command = result.args + [
                "--light-direction", "0.6", "-0.8", "0",
                "--softened-reflection-entity", "Panel_927",
                "--ui-fade-entity", "Furniture_406",
            ]
            room = temporary / "room-v5"
            command[2] = str(room)
            authored = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(authored.returncode, 0, authored.stderr)
            metadata = json.loads((room / "space.json").read_text())
            self.assertEqual(metadata["formatVersion"], 5)
            self.assertEqual(metadata["rendering"], {
                "softenedReflectionEntities": ["Panel_927"],
                "uiFadeEntities": ["Furniture_406"],
            })
            self.assertEqual(metadata["lighting"]["luminaireGroups"][0]["proxy"]["direction"], [0.6, -0.8, 0])

            packed = subprocess.run(
                [sys.executable, str(packer), str(room), str(archive)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(packed.returncode, 0, packed.stderr)
            checked = subprocess.run(
                [sys.executable, str(validator), str(archive), "--json"],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertEqual(json.loads(checked.stdout), {
                "displayName": "Skill Fixture Pavilion",
                "kind": "room",
                "seats": 1,
            })

    def test_three_demo_rooms_are_flat_pinned_current_and_valid(self):
        expected = {
            "atrium-loft-room.zip": {
                "display_name": "Atrium Loft",
                "size": 8_176_551,
                "sha256": "588c14c5b1226ec677fada112df1346bb105f0cbdb0344db9d1e1be03b3b9ff1",
                "seats": 2,
                "light_groups": 2,
            },
            "courtyard-gallery-room.zip": {
                "display_name": "Courtyard Gallery",
                "size": 8_510_411,
                "sha256": "1d4be79f0c69c6d34e285729c02bd1870bf11133497277a1f1d94d7b0dd9f21f",
                "seats": 3,
                "light_groups": 3,
            },
            "horizon-atelier-room.zip": {
                "display_name": "Horizon Atelier",
                "size": 8_644_903,
                "sha256": "dd3551316cae67c01a114a6130db37823f03dcebcec703f15a8fedf7dc291fe7",
                "seats": 3,
                "light_groups": 5,
            },
        }
        examples = ROOT / "examples"
        self.assertEqual(
            {path.name for path in examples.glob("*.zip")},
            set(expected) | {
                "demo-room.zip", "coffee-atrium-experimental-room.zip",
            },
        )
        readme = (examples / "README.md").read_text()
        for filename, details in expected.items():
            demo = examples / filename
            with self.subTest(filename=filename):
                self.assertEqual(demo.stat().st_size, details["size"])
                self.assertEqual(
                    hashlib.sha256(demo.read_bytes()).hexdigest(),
                    details["sha256"],
                )
                self.assertIn(filename, readme)
                self.assertIn(details["sha256"], readme)
                with zipfile.ZipFile(demo) as archive:
                    self.assertEqual(set(archive.namelist()), {
                        "space.json", "provenance.json", "teleport-points.json",
                        "scene.usdz", "thumbnail.jpg",
                    })
                    room = json.loads(archive.read("space.json"))
                    teleports = json.loads(archive.read("teleport-points.json"))
                    provenance = json.loads(archive.read("provenance.json"))
                    self.assertEqual(room["formatVersion"], 3)
                    self.assertEqual(room["displayName"], details["display_name"])
                    self.assertNotIn("id", room)
                    self.assertEqual(len(teleports["points"]), details["seats"])
                    self.assertEqual(
                        len(room["lighting"]["luminaireGroups"]),
                        details["light_groups"],
                    )
                    self.assertEqual(
                        room["lighting"]["bakedIndirect"]["entities"],
                        ["Locus_BakedIndirect"],
                    )
                    self.assertTrue(provenance["aiGenerated"])
                    self.assertEqual(
                        provenance["license"]["identifier"],
                        "CC-BY-4.0",
                    )
                    self.assertEqual(
                        provenance["license"]["url"],
                        "https://creativecommons.org/licenses/by/4.0/",
                    )
                    self.assertEqual(
                        provenance["sourcePageURL"],
                        "https://enterlocus.com/asset-rights/",
                    )
                    self.assertEqual(
                        provenance["requestedCredit"],
                        f'{details["display_name"]} by EnterLocus.com',
                    )
                    self.assertIn(
                        "Embedded Poly Haven texture files retain CC0 1.0",
                        provenance["modificationNotes"],
                    )
                result = subprocess.run(
                    [sys.executable, str(ROOT / "tools" / "validate_locus_asset.py"), str(demo)],
                    check=False, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(
                    f'VALID: room "{details["display_name"]}"',
                    result.stdout,
                )

        self.assertEqual(
            (examples / "demo-room.zip").read_bytes(),
            (examples / "atrium-loft-room.zip").read_bytes(),
        )
        for page in [
            ROOT / "build-a-room" / "index.html",
            ROOT / "create-your-own-place" / "index.html",
            ROOT / "package-format" / "index.html",
        ]:
            text = page.read_text()
            for filename in expected:
                self.assertIn(f"../examples/{filename}", text)

    def test_experimental_animation_demo_is_pinned_valid_and_clearly_labeled(self):
        filename = "coffee-atrium-experimental-room.zip"
        demo = ROOT / "examples" / filename
        self.assertEqual(demo.stat().st_size, 8_316_240)
        self.assertEqual(
            hashlib.sha256(demo.read_bytes()).hexdigest(),
            "c83b3be2f5d29737e418f898fb442b8ded61488b4f32b613195dc0ecab27d42d",
        )
        with zipfile.ZipFile(demo) as archive:
            self.assertEqual(set(archive.namelist()), {
                "space.json", "provenance.json", "teleport-points.json",
                "scene.usdz", "thumbnail.jpg",
            })
            room = json.loads(archive.read("space.json"))
            provenance = json.loads(archive.read("provenance.json"))
        self.assertEqual(room["formatVersion"], 4)
        self.assertEqual(room["displayName"], "Coffee Atrium POC")
        self.assertEqual(
            [animation["id"] for animation in room["ambientAnimations"]],
            ["coffee-break", "ceiling-fan"],
        )
        self.assertEqual(
            room["ambientAnimations"][0]["defaultIntervalRangeSeconds"],
            [8, 20],
        )
        self.assertEqual(
            room["ambientAnimations"][1]["defaultIntervalRangeSeconds"],
            [0, 0],
        )
        self.assertNotIn("license", provenance)
        self.assertEqual(
            provenance["rights"]["url"],
            "https://enterlocus.com/asset-rights/",
        )
        self.assertIn(
            "No separate reuse or redistribution license is granted",
            provenance["rights"]["statement"],
        )
        self.assertEqual(
            provenance["sourcePageURL"],
            "https://enterlocus.com/asset-rights/",
        )
        self.assertEqual(
            provenance["requestedCredit"],
            "Coffee Atrium POC by EnterLocus.com",
        )
        self.assertIn(
            "Embedded Poly Haven texture files retain CC0 1.0",
            provenance["modificationNotes"],
        )

        checked = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "validate_locus_asset.py"), str(demo)],
            check=False, capture_output=True, text=True,
        )
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertIn('VALID: room "Coffee Atrium POC"', checked.stdout)

        page = (ROOT / "experimental-room-animations" / "index.html").read_text()
        for required in [
            "All animation features shown here are experimental",
            "experimental speed and interval settings",
            "Controls → Ambient Animations",
            "Quick Settings → Room",
            "0–0", "8–20 seconds", "may change",
            f"../examples/{filename}",
            "reserved-rights statement",
            "Embedded Poly Haven textures retain CC0 1.0",
        ]:
            self.assertIn(required, page)
        for path in [
            ROOT / "README.md",
            ROOT / "LICENSE.md",
            ROOT / "examples" / "README.md",
            ROOT / "package-format" / "index.html",
            ROOT / "create-your-own-place" / "index.html",
            ROOT / "build-a-room" / "index.html",
            ROOT / "reference" / "locus-asset-format.md",
            ROOT / ".agents" / "skills" / "build-original-locus-room" / "SKILL.md",
            ROOT / ".agents" / "skills" / "build-original-locus-room" / "references" / "room-interface.md",
        ]:
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text()
                self.assertIn("experimental", text.lower())

        sitemap = (ROOT / "sitemap.xml").read_text()
        self.assertIn(
            "https://enterlocus.com/experimental-room-animations/",
            sitemap,
        )

    def test_room_guide_is_tool_agnostic_and_documents_runtime_contracts(self):
        guide = (ROOT / "build-a-room" / "index.html").read_text()
        for required in [
            "professional tools you already know", "does not prescribe",
            "meter-scale", "+Y up", "-Z as forward", "viewOpenings",
            "anchorXZ", "sourceFloorOffset", "wallEntities", "roofEntities",
            "deskEntitiesByTeleportID", "luminaireGroups", "nearTeleportIDs",
            "bakedIndirect.entities", "2^overallEV", "12 authored proxies",
            "4 active proxies", "1 shadow-casting proxy", "10,000 lumens",
            "-4…+1 EV", "every seat on Apple Vision Pro",
            "Experimental ambient animations", "ambientAnimations",
            "0–0", "may change",
        ]:
            self.assertIn(required, guide)
        for modeling_instruction in ["Blender MCP", "Create original geometry"]:
            self.assertNotIn(modeling_instruction, guide)

    def test_asset_rights_page_matches_first_party_provenance(self):
        rights = (ROOT / "asset-rights" / "index.html").read_text()
        for term in [
            "Apache-2.0", "Apache License 2.0", "CC-BY-4.0",
            "Creative Commons Attribution 4.0 International",
            "LicenseRef-EnterLocus-Proprietary", "EnterLocus.com",
            "Laminate Floor 02", "Charlotte Baglioni", "Dario Barresi",
            "Plywood", "White Plaster 02", "Rob Tuytel", "CC0 1.0",
            "names, logos, app icons", "private app source",
            "AI disclosure", "aiGenerated", "aiProvider",
            "Coffee Atrium experimental demo", "animation artwork",
            "experimental-animation-demo-notices",
        ]:
            self.assertIn(term, rights)
        for source in [
            "https://polyhaven.com/a/laminate_floor_02",
            "https://polyhaven.com/a/plywood",
            "https://polyhaven.com/a/white_plaster_02",
            "https://polyhaven.com/license",
            "https://creativecommons.org/licenses/by/4.0/",
            "https://www.apache.org/licenses/LICENSE-2.0",
        ]:
            self.assertIn(source, rights)
        schema = json.loads((ROOT / "schemas" / "provenance-v1.schema.json").read_text())
        self.assertEqual(
            schema["$id"], "https://enterlocus.com/schemas/provenance-v1.schema.json"
        )
        self.assertNotIn("license", schema["required"])
        self.assertIn("rights", schema["properties"])
        rights_choice = schema["allOf"][0]["oneOf"]
        self.assertEqual(
            {choice["required"][0] for choice in rights_choice},
            {"license", "rights"},
        )
        self.assertIn("https://enterlocus.com/asset-rights/", (
            ROOT / "sitemap.xml"
        ).read_text())


if __name__ == "__main__":
    unittest.main()
