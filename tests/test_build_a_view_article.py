"""Public tutorial follows the frozen comparison and its disclosed boundaries."""
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_site
import external_assets
import localization


class ArticleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []
        self.links = []
        self.code = []
        self.in_code = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'img':
            self.images.append(attrs)
        if tag == 'a':
            self.links.append(attrs.get('href', ''))
        if tag == 'code':
            self.in_code = True

    def handle_endtag(self, tag):
        if tag == 'code':
            self.in_code = False

    def handle_data(self, data):
        if self.in_code:
            self.code.append(data)


class BuildAViewArticleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'build-a-view/index.html').read_text()
        cls.comparison = json.loads((ROOT / 'examples/skybox-comparison/comparison.json').read_text())
        cls.parser = ArticleParser()
        cls.parser.feed(cls.source)

    def test_exact_source_prompt_is_public_and_stays_verbatim_in_every_locale(self):
        original = (ROOT / 'examples/skybox-comparison/prompt.txt').read_text().strip()
        self.assertIn(original, self.parser.code)
        for locale in localization.TRANSLATED_LOCALES:
            catalog = localization.load_catalog(ROOT, locale)
            translated = build_site._translate_document(self.source, Path('build-a-view/index.html'), locale, catalog)
            parser = ArticleParser()
            parser.feed(translated)
            with self.subTest(locale=locale):
                self.assertEqual(parser.code, self.parser.code)
                self.assertFalse([key for key in localization._sources_in_html(self.source)
                                  if not localization.has_translation(key, catalog)])

    def test_displayed_images_are_registered_external_derivatives_with_layout_dimensions(self):
        urls = {asset['url'] for asset in external_assets.load_manifest().values()}
        self.assertEqual(len(self.parser.images), 7)
        for image in self.parser.images:
            with self.subTest(image=image['src']):
                self.assertIn(image['src'], urls)
                self.assertTrue(image['src'].startswith('https://media.enterlocus.net/tutorials/build-view/'))
                self.assertGreater(int(image['width']), 0)
                self.assertGreater(int(image['height']), 0)
                self.assertTrue(image['alt'])
                candidates = dict(part.strip().rsplit(' ', 1)[::-1]
                                  for part in image['srcset'].split(','))
                self.assertEqual(set(candidates), {'672w', image['width'] + 'w'})
                self.assertTrue(set(candidates.values()).issubset(urls))
                self.assertIn('calc(100vw - 48px)', image['sizes'])
        cover = self.parser.images[0]
        self.assertEqual(cover['fetchpriority'], 'high')
        self.assertNotIn('loading', cover)
        self.assertIn(cover['src'], self.source.split('</head>')[0])
        for file in ['source.png', 'global-restoration.jpg', 'native-face-crops.jpg',
                     'repair-before-after.jpg', 'final-panorama.jpg', 'same-angle.jpg',
                     'gpt-image26-7322x3661.jpg', 'nano-banana-pro-10418x5209.jpg',
                     'gpt-image26-intermediates.zip', 'nano-banana-pro-intermediates.zip',
                     'review-evidence.zip']:
            self.assertIn(self.comparison['assets'][file]['url'], self.parser.links)

    def test_measurements_and_costs_match_the_frozen_comparison_without_invoice_claim(self):
        for route in self.comparison['routes'].values():
            self.assertIn('×'.join(str(n) for n in route['final_size']), self.source)
            self.assertIn(route['api_model'], self.source)
            self.assertEqual(route['paid_output_count'], 9)
        for value in ['1.614237', '1.471502', '1.587014', '3.201251']:
            self.assertIn('$' + value, self.source)
        for text in ['1774×887', '102°', '6° context', '0.25°', 'B + G + F + R + E',
                     'B=0, G=1, F=6, R=2, E=0', '18 total', 'not reconciled provider invoices',
                     'not verified', 'no motion, depth or parallax', 'not native 12K',
                     'Residual tokens at text rate', 'Conservative accounting']:
            if text == 'not native 12K':
                self.assertIn('Neither result is native 12K', self.source)
            else:
                self.assertIn(text, self.source)
        self.assertNotIn('$1.471502–$1.587014', self.source)
        self.assertNotIn('$5', self.source)
        for internal in ['/Users/', '/Volumes/', 'LOCUS_SIGNING', 'creator_combined_cap']:
            self.assertNotIn(internal, self.source)

    def test_tutorial_pair_make_order_home_and_contextual_routes(self):
        hub = (ROOT / 'tutorials/index.html').read_text()
        featured = re.search(r'<section class="tutorial-feature-grid".*?</section>', hub, re.S).group()
        self.assertEqual(re.findall(r'class="tutorial-feature" href="([^"]+)"', featured),
                         ['../make-a-room/', '../build-a-view/'])
        make = hub[hub.index('id="make-heading"'):hub.index('id="supplementary-heading"')]
        self.assertEqual(re.findall(r'class="tutorial-card" href="([^"]+)"', make)[:2],
                         ['../make-a-room/', '../build-a-view/'])
        self.assertIn('href="../first-place/"', hub[hub.index('id="start-heading"'):hub.index('id="make-heading"')])
        self.assertIn('href="./build-a-view/"', (ROOT / 'index.html').read_text())
        for page in ['make-a-room', 'make-a-view', 'build-a-room']:
            self.assertIn('href="../build-a-view/"', (ROOT / page / 'index.html').read_text())
        self.assertIn('https://enterlocus.com/build-a-view/', (ROOT / 'sitemap.xml').read_text())
        self.assertIn('id="basic"', (ROOT / 'make-a-view/index.html').read_text())


if __name__ == '__main__':
    unittest.main()
