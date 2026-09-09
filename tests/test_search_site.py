"""Contracts for the search-enabled static publication."""
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET
ROOT = Path(__file__).resolve().parents[1]

class SearchSiteTests(unittest.TestCase):
    def test_all_public_pages_have_search_and_indexed_content(self):
        for loc in ET.parse(ROOT / 'sitemap.xml').iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
            path = ROOT / loc.text.removeprefix('https://enterlocus.com/') / 'index.html'
            with self.subTest(page=path):
                html = path.read_text()
                for text in ['data-pagefind-body', 'class="search-trigger"', 'src="/assets/search.js"', 'href="/assets/search.css"']:
                    self.assertIn(text, html)

    def test_each_faq_question_has_a_unique_deep_link(self):
        html = (ROOT / 'faq/index.html').read_text()
        questions = re.findall(r'<summary><h3 id="([^"]+)">', html)
        self.assertEqual(len(questions), html.count('<summary>'))
        self.assertEqual(len(questions), len(set(questions)))
        self.assertIn('lying-down', questions)
        for text in ['Locus 1.1.2 or later', 'Viewing position', '90°',
                     'Reset to upright', 'Real desk alignment is paused', 'current session']:
            self.assertIn(text, html)
