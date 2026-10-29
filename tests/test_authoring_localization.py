"""Localized authoring prose must leave executable examples and identifiers intact."""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_site
import localization

# Field names in prose, filenames, command flags and capability identifiers.
PROTECTED = re.compile(r'(?<![\w])(?:[a-z]+(?:[A-Z][A-Za-z0-9]*)+|locus\.[a-z0-9.-]+|--[a-z][a-z0-9-]+|[A-Za-z0-9_./-]+\.(?:json|py|zip|locusplace|usdz|jpg|png|ktx|mp4|m4a|md))(?![\w])')


class CodeParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ('pre', 'code'):
            self.depth += 1

    def handle_endtag(self, tag):
        if tag in ('pre', 'code'):
            self.depth -= 1

    def handle_data(self, text):
        if self.depth:
            self.parts.append(text)


def code_text(document):
    parser = CodeParser()
    parser.feed(document)
    return parser.parts


class AuthoringLocalizationTests(unittest.TestCase):
    def test_complete_guide_has_translated_prose_and_preserves_inline_identifiers(self):
        source = (ROOT / 'reference/locusplace-format/index.html').read_text()
        keys = localization._sources_in_html(source)
        for locale in localization.TRANSLATED_LOCALES:
            catalog = localization.load_catalog(ROOT, locale)
            for key in keys:
                with self.subTest(locale=locale, source=key):
                    self.assertTrue(localization.has_translation(key, catalog), 'missing authoring prose')
                    self.assertEqual(Counter(PROTECTED.findall(key)),
                                     Counter(PROTECTED.findall(catalog[key])),
                                     'field names, filenames, flags and capability IDs must remain exact')

    def test_touched_field_paragraphs_translate_connecting_prose(self):
        # These fragments sit between code spans in the expanded water reference.
        fragments = (') and', '), and', ', and it also\nrequires', ', radius is',
                     ', speed is', '; its centre is\nwithin', 'defaults to')
        for locale in localization.TRANSLATED_LOCALES:
            catalog = localization.load_catalog(ROOT, locale)
            for fragment in fragments:
                with self.subTest(locale=locale, fragment=fragment):
                    self.assertTrue(localization.has_translation(fragment, catalog))

    def test_every_locale_keeps_reference_code_and_json_byte_for_byte(self):
        for relative in (Path('reference/locus-asset-format/index.html'),
                         Path('reference/locusplace-format/index.html')):
            source = (ROOT / relative).read_text()
            expected = code_text(source)
            self.assertTrue(expected)
            for locale in localization.TRANSLATED_LOCALES:
                with self.subTest(locale=locale, page=str(relative)):
                    translated = build_site._translate_document(source, relative, locale,
                                             localization.load_catalog(ROOT, locale))
                    self.assertEqual(code_text(translated), expected)
                    self.assertIn('"formatVersion"', ''.join(code_text(translated)))


if __name__ == '__main__':
    unittest.main()
