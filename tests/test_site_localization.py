"""Focused contracts for generated, source-preserving site localizations."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_site
import localization


PAGE = '''<!doctype html><!-- Translator note --><html lang="en"><head><title>Welcome</title>
<meta name="description" content="A description"><link rel="canonical" href="https://enterlocus.com/"></head>
<body><header class="site-header"><nav aria-label="Primary navigation"><a href="./faq/">FAQ</a></nav></header>
<main data-pagefind-body id="main"><p>Hello <strong>world</strong>.</p><img src="./assets/pic.png" alt="A picture">
<a href="./.agents/skills/example.md">Skill</a><code>example-file.zip</code><pre>do not translate</pre></main></body></html>'''


class SiteLocalizationTests(unittest.TestCase):
    def build_fixture(self, catalog=None):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / 'assets').mkdir()
        (root / 'index.html').write_text(PAGE)
        (root / 'faq').mkdir()
        (root / 'faq' / 'index.html').write_text(PAGE.replace('Welcome', 'FAQ'))
        (root / 'sitemap.xml').write_text(
            '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            '<url><loc>https://enterlocus.com/</loc></url></urlset>')
        if catalog is not None:
            (root / 'localization').mkdir()
            (root / 'localization' / 'fr.json').write_text(json.dumps({
                'language': 'fr', 'strings': catalog}, ensure_ascii=False))
        previous_root, previous_output = build_site.ROOT, build_site.OUTPUT
        build_site.ROOT, build_site.OUTPUT = root, root / '.site'
        self.addCleanup(setattr, build_site, 'ROOT', previous_root)
        self.addCleanup(setattr, build_site, 'OUTPUT', previous_output)
        self.addCleanup(temporary.cleanup)
        return root

    def test_generator_preserves_source_and_localizes_public_links_and_seo(self):
        root = self.build_fixture({
            'Welcome': 'Bienvenue', 'A description': 'Une description', 'Hello': 'Bonjour',
            'world': 'monde', 'A picture': 'Une image', 'Language': 'Langue', 'System': 'Système',
        })
        original = (root / 'index.html').read_bytes()
        build_site.build()
        generated = (root / '.site/fr/index.html').read_text()
        self.assertEqual((root / 'index.html').read_bytes(), original)
        self.assertIn('<html lang="fr">', generated)
        self.assertIn('<title>Bienvenue</title>', generated)
        self.assertIn('content="Une description"', generated)
        self.assertIn('href="/fr/faq/"', generated)
        self.assertIn('src="/assets/pic.png"', generated)
        self.assertIn('href="/.agents/skills/example.md"', generated)
        self.assertIn('<code>example-file.zip</code>', generated)
        self.assertIn('<pre>do not translate</pre>', generated)
        self.assertIn('<!-- Translator note -->', generated)
        self.assertIn('hreflang="zh-Hant" href="https://enterlocus.com/zh-Hant/"', generated)
        self.assertIn('hreflang="x-default" href="https://enterlocus.com/"', generated)
        self.assertIn('href="https://enterlocus.com/fr/"', generated)
        self.assertIn('aria-label="Langue"', generated)
        self.assertIn('https://enterlocus.com/fr/', (root / '.site/sitemap.xml').read_text())

    def test_blank_catalog_values_fall_back_and_extraction_skips_opaque_text(self):
        root = self.build_fixture({
            'Welcome': 'Bienvenue', 'Hello': '   ', 'A picture': ' ', 'Search': ' ',
            'Translator note': 'Ne pas traduire', 'doctype html': 'doctype traduit',
        })
        build_site.build()
        generated = (root / '.site/fr/index.html').read_text()
        self.assertIn('Hello <strong>world</strong>.', generated)
        self.assertIn('alt="A picture"', generated)
        self.assertIn('"Search": "Search"', generated)
        self.assertIn('<!-- Translator note -->', generated)
        extracted = localization.extract_sources(root)
        self.assertEqual(extracted, localization.extract_sources(root))
        self.assertIn('Try {first}, {second}, or {third}.', extracted['strings'])
        self.assertNotIn('example-file.zip', extracted['strings'])
        self.assertNotIn('Translator note', extracted['strings'])
        self.assertNotIn('doctype html', extracted['strings'])

    def test_catalog_allows_reordered_interpolation_tokens_but_rejects_changed_tokens(self):
        root = self.build_fixture({'Try {first}, {second}, or {third}.': '{third}、{first}、{second}'})
        self.assertIn('Try {first}, {second}, or {third}.', localization.load_catalog(root, 'fr'))
        root = self.build_fixture({'{count} result': '{nombre} résultat'})
        with self.assertRaisesRegex(ValueError, 'interpolation tokens'):
            localization.load_catalog(root, 'fr')

    def test_extraction_protects_symbol_and_technical_literals(self):
        sources = localization._sources_in_html('''<p><span>↑</span><span>©</span><span>1.2.3</span>
            <span>Package v2</span><span>Locus</span><span>room-id_45</span><span>Words to translate</span><p>A legacy/simple flat ZIP preserves compatibility.</p><p>Download example-file.zip to begin.</p></p>''')
        self.assertEqual(sources, {'Words to translate', 'A legacy/simple flat ZIP preserves compatibility.', 'Download example-file.zip to begin.'})
