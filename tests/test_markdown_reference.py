"""Contracts for staging the Markdown-owned public format reference."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / 'tools' / 'render_markdown_page.mjs'
SOURCE = ROOT / 'reference' / 'locus-asset-format.md'


class MarkdownReferenceTests(unittest.TestCase):
    def test_public_html_uses_the_readable_reference_route(self):
        excluded = {'.site', 'node_modules', '.scratch', 'test-results', 'playwright-report'}
        pages = [path for path in ROOT.rglob('*.html')
                 if not any(part in excluded for part in path.relative_to(ROOT).parts)]
        self.assertTrue(pages)
        for page in pages:
            with self.subTest(page=page.relative_to(ROOT)):
                if page == ROOT / 'reference/locus-asset-format/index.html':
                    self.assertIn('href="../locus-asset-format.md" download', page.read_text(encoding='utf-8'))
                    continue
                self.assertNotIn('reference/locus-asset-format.md', page.read_text(encoding='utf-8'))

    @unittest.skipUnless(shutil.which('node') and (ROOT / 'node_modules' / 'markdown-it').is_dir(),
                         'requires npm ci before running the Markdown renderer')
    def test_renderer_preserves_expected_anchors_and_resolves_source_links(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'reference' / 'locus-asset-format' / 'index.html'
            subprocess.run([
                'node', str(RENDERER), str(SOURCE), str(output),
                'reference', 'reference/locus-asset-format',
            ], check=True)
            rendered = output.read_text(encoding='utf-8')

        self.assertEqual(rendered, (ROOT / 'reference/locus-asset-format/index.html').read_text(encoding='utf-8'))
        self.assertIn('id="one-pure-data-capability-contract"', rendered)
        self.assertIn('id="room-lighting-formatversion-2"', rendered)
        self.assertIn('href="../../schemas/view-celestial-v1.schema.json"', rendered)
        self.assertIn('href="../locus-asset-format.md" download', rendered)
        self.assertIn('class="reference-table-scroll"', rendered)
