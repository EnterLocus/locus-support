"""Contracts for the public Place example downloads and their Gallery surfaces."""
import copy
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_site
import localization
import place_examples
import render_gallery

FIXTURE = ROOT / 'tests' / 'fixtures' / 'place-examples.json'
SHA256 = re.compile(r'[0-9a-f]{64}')


def fixture():
    return json.loads(FIXTURE.read_text())


def gallery():
    return json.loads((ROOT / 'data' / 'gallery.json').read_text())


def example(manifest, package_id):
    return next(item for item in manifest['examples'] if item['packageID'] == package_id)


class PublishedManifestTests(unittest.TestCase):
    """The committed manifest is public data for people and coding agents."""

    def setUp(self):
        self.manifest = json.loads((ROOT / 'data' / 'place-examples.json').read_text())

    def test_manifest_is_valid_and_published_at_a_stable_url(self):
        place_examples.validate(self.manifest)
        self.assertNotIn('data', build_site.EXCLUDED)
        self.assertEqual(place_examples.PUBLIC_URL, 'https://enterlocus.com/data/place-examples.json')

    def test_every_record_meets_the_data_contract(self):
        self.assertEqual(self.manifest['formatVersion'], 1)
        for license_id, url in self.manifest['licenses'].items():
            self.assertEqual(place_examples.LICENSES[license_id], url)
        for item in self.manifest['examples']:
            with self.subTest(example=item.get('packageID')):
                self.assertTrue({'packageID', 'kind', 'title', 'license', 'features',
                                 'package', 'source'} <= set(item))
                self.assertIn(item['kind'], {'room', 'view'})
                self.assertIn(item['license'], place_examples.LICENSES)
                self.assertTrue(set(item['features']) <= set(place_examples.FEATURES))
                files = [item['package']] + ([item['source']] if item['source'] else [])
                for record in files:
                    self.assertTrue(record['url'].startswith(
                        f'https://media.enterlocus.net/examples/{item["packageID"]}/'))
                    self.assertTrue(record['url'].endswith('/' + record['fileName']))
                    self.assertRegex(record['sha256'], SHA256)
                    self.assertGreater(record['byteCount'], 0)

    def test_gallery_examples_are_free_places(self):
        places = {place['id']: place for place in gallery()['places']}
        by_place, _extras = place_examples.match(gallery(), self.manifest)
        for place_id in by_place:
            with self.subTest(place=place_id):
                self.assertEqual(places[place_id]['access'], 'free')

    def test_notes_are_translated_in_every_catalog(self):
        notes = [item['notes'] for item in self.manifest['examples'] if item.get('notes')]
        for locale in localization.TRANSLATED_LOCALES:
            catalog = localization.load_catalog(ROOT, locale)
            for note in notes:
                with self.subTest(locale=locale, note=note):
                    self.assertTrue(localization.has_translation(note, catalog))


class ValidationTests(unittest.TestCase):
    def assert_rejected(self, mutate, message):
        manifest = fixture()
        mutate(manifest)
        with self.assertRaisesRegex(ValueError, message):
            place_examples.validate(manifest)

    def test_fixture_is_valid(self):
        place_examples.validate(fixture())

    def test_rejects_wrong_host_scheme_or_path(self):
        for url in ['http://media.enterlocus.net/examples/space.hilltop-villa/space.hilltop-villa-1.0.14.locusplace',
                    'https://example.com/examples/space.hilltop-villa/space.hilltop-villa-1.0.14.locusplace',
                    'https://media.enterlocus.net/examples/space.other/space.hilltop-villa-1.0.14.locusplace']:
            with self.subTest(url=url):
                self.assert_rejected(lambda m: m['examples'][0]['package'].__setitem__('url', url), 'url must be')

    def test_rejects_bad_sha_size_and_versions(self):
        self.assert_rejected(lambda m: m['examples'][0]['package'].__setitem__('sha256', 'A' * 64), 'sha256')
        self.assert_rejected(lambda m: m['examples'][0]['source'].__setitem__('sha256', '…'), 'sha256')
        self.assert_rejected(lambda m: m['examples'][0]['package'].__setitem__('byteCount', 0), 'byteCount')
        self.assert_rejected(lambda m: m['examples'][0]['package'].__setitem__('contentVersion', 'v1'), 'version')

    def test_rejects_unknown_license_feature_and_fields(self):
        self.assert_rejected(lambda m: m['examples'][0].__setitem__('license', 'MIT'), 'license')
        self.assert_rejected(lambda m: m['licenses'].__setitem__('MIT', 'https://opensource.org/license/mit'),
                             'licenses')
        self.assert_rejected(lambda m: m['examples'][0]['features'].append('fog'), 'features')
        self.assert_rejected(lambda m: m['examples'][0]['features'].append('music'), 'features')
        self.assert_rejected(lambda m: m['examples'][0].__setitem__('thumbnail', 'x.jpg'), 'Each example')
        self.assert_rejected(lambda m: m['examples'][0]['source'].pop('blenderVersion'), 'source must have')

    def test_cc_by_is_reserved_for_the_demo_rooms(self):
        self.assert_rejected(lambda m: m['examples'][0].__setitem__('license', 'CC-BY-4.0'), 'demo Rooms')

    def test_rejects_kind_mismatch_and_duplicates(self):
        self.assert_rejected(lambda m: m['examples'][0].__setitem__('kind', 'view'), 'does not match')
        self.assert_rejected(lambda m: m['examples'].append(copy.deepcopy(m['examples'][0])), 'Duplicate')

    def test_missing_manifest_means_no_examples(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(place_examples.load(Path(directory) / 'absent.json')['examples'], [])


class MatchRuleTests(unittest.TestCase):
    def setUp(self):
        self.gallery = gallery()
        self.manifest = fixture()

    def test_shows_current_or_older_installable_revisions_only(self):
        places = {place['id']: place for place in self.gallery['places']}
        by_place, extras = place_examples.match(self.gallery, self.manifest)
        # Hilltop Villa's package is the Gallery revision; Lakeside Cabin's is older.
        self.assertEqual(by_place['space.hilltop-villa']['package']['contentVersion'],
                         places['space.hilltop-villa']['contentVersion'])
        self.assertLess(place_examples.version(by_place['space.lakeside-cabin']['package']['contentVersion']),
                        place_examples.version(places['space.lakeside-cabin']['contentVersion']))
        # Newer than the Gallery snapshot, or not installable by the public App: hidden.
        self.assertNotIn('space.sunlit-cafe', by_place)
        self.assertNotIn('space.cloudvault-retreat', by_place)
        self.assertEqual([item['packageID'] for item in extras], ['space.minimal-study'])

    def test_built_in_places_only_check_installability(self):
        # A built-in Place ships in the App; its example is a separate package.
        demo = example(self.manifest, 'space.atrium-loft')
        demo['package']['contentVersion'] = '9.9.9'
        by_place, _extras = place_examples.match(self.gallery, self.manifest)
        self.assertIn('space.atrium-loft', by_place)
        demo['package']['minimumAppVersion'] = '9.0'
        by_place, _extras = place_examples.match(self.gallery, self.manifest)
        self.assertNotIn('space.atrium-loft', by_place)

    def test_version_comparison_is_numeric(self):
        self.assertGreater(place_examples.version('1.10.3'), place_examples.version('1.9.9'))
        self.assertEqual(place_examples.version('1.4'), place_examples.version('1.4.0'))


class RenderingTests(unittest.TestCase):
    def setUp(self):
        self.gallery = gallery()
        self.manifest = fixture()
        self.places = {place['id']: place for place in self.gallery['places']}

    def test_detail_shows_package_and_source_with_a_different_revision(self):
        item = example(self.manifest, 'space.hilltop-villa')
        page = render_gallery.place_page(self.places['space.hilltop-villa'], self.gallery, 'en', item)
        self.assertIn(item['package']['url'], page)
        self.assertIn(item['source']['url'], page)
        self.assertIn('1.0.14 · ZIP file (.locusplace) · 117.8 MB · Locus 1.4.5 or later', page)
        self.assertIn('For version 1.0.17 · Blender 5.0.1 · 1.4 GB', page)
        self.assertIn('Light layers', page)
        self.assertIn('href="/asset-rights/#example-license">Locus Example License</a>', page)

    def test_detail_with_package_only_and_matching_source_revision(self):
        lakeside = render_gallery.place_page(self.places['space.lakeside-cabin'], self.gallery, 'en',
                                             example(self.manifest, 'space.lakeside-cabin'))
        self.assertIn('Place package', lakeside)
        self.assertNotIn('Blender source', lakeside)
        atrium = render_gallery.place_page(self.places['space.atrium-loft'], self.gallery, 'en',
                                           example(self.manifest, 'space.atrium-loft'))
        self.assertIn('>Blender 4.5.3 · 21.4 MB<', atrium)
        self.assertIn('href="/asset-rights/#demo-room-notices">Creative Commons CC BY 4.0</a>', atrium)

    def test_detail_copy_is_localized(self):
        item = example(self.manifest, 'space.hilltop-villa')
        for locale in render_gallery.LOCALES:
            with self.subTest(locale=locale):
                page = render_gallery.place_page(self.places['space.hilltop-villa'], self.gallery, locale, item)
                copy_ = render_gallery.EXAMPLE_COPY[locale]
                for key in ('files', 'package', 'zip', 'source', 'license'):
                    self.assertIn(copy_[key], page)
                self.assertIn(render_gallery.FEATURE_COPY[locale]['generated-furniture'], page)
                prefix = '' if locale == 'en' else f'/{locale}'
                self.assertIn(f'href="{prefix}/asset-rights/#example-license"', page)
        self.assertIn('117,8 Mo', render_gallery.place_page(self.places['space.hilltop-villa'], self.gallery, 'fr', item))

    def test_withheld_example_explains_and_links_related_place(self):
        self.assertEqual(set(render_gallery.WITHHELD_COPY), set(render_gallery.LOCALES))
        for locale in render_gallery.LOCALES:
            with self.subTest(locale=locale):
                self.assertIn('{link}', render_gallery.WITHHELD_COPY[locale])
                page = render_gallery.place_page(self.places['destination.lakeshore-water-lab'], self.gallery, locale)
                self.assertIn('data-gallery-example-withheld="destination.lakeshore-water-lab"', page)
                prefix = '' if locale == 'en' else f'/{locale}'
                self.assertIn(f'href="{prefix}/gallery/place/cloud-garden-isles/"', page)
                self.assertNotIn('media.enterlocus.net/examples/', page)
        other = render_gallery.place_page(self.places['destination.toposcope-sunset'], self.gallery, 'en')
        self.assertNotIn('data-gallery-example-withheld', other)

    def test_every_locale_has_every_example_string_and_feature(self):
        for locale in render_gallery.LOCALES:
            with self.subTest(locale=locale):
                self.assertEqual(set(render_gallery.EXAMPLE_COPY[locale]), set(render_gallery.EXAMPLE_COPY['en']))
                self.assertEqual(set(render_gallery.FEATURE_COPY[locale]), set(place_examples.FEATURES))
                self.assertIn('{version}', render_gallery.EXAMPLE_COPY[locale]['minimum'])

    def test_gallery_filter_marks_example_places_and_lists_the_rest(self):
        page = render_gallery.gallery_page(self.gallery, 'en', self.manifest)
        self.assertIn('data-gallery-filter="example"', page)
        self.assertEqual(page.count('data-example="true" data-search'), 4 + 1)  # Gallery cards + one extra
        self.assertIn('data-gallery-more-examples hidden', page)
        self.assertIn('Minimal Study', page)
        self.assertNotIn('space.sunlit-cafe-9.0.0', page)

    def test_without_examples_there_is_no_download_ui(self):
        for manifest in (None, place_examples.empty_manifest()):
            page = render_gallery.gallery_page(self.gallery, 'en', manifest)
            self.assertNotIn('data-gallery-filter="example"', page)
            self.assertNotIn('data-gallery-more-examples', page)
            self.assertNotIn('data-example="true"', page)
        detail = render_gallery.place_page(self.places['space.hilltop-villa'], self.gallery, 'en')
        self.assertNotIn('gallery-example', detail)

    def test_build_renders_examples_and_tolerates_an_absent_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root, output = Path(directory) / 'root', Path(directory) / 'out'
            (root / 'data').mkdir(parents=True)
            output.mkdir()
            shutil.copyfile(ROOT / 'data' / 'gallery.json', root / 'data' / 'gallery.json')
            shutil.copyfile(ROOT / 'sitemap.xml', output / 'sitemap.xml')
            render_gallery.build(root, output)
            self.assertNotIn('gallery-example', (output / 'gallery/place/hilltop-villa/index.html').read_text())
            shutil.copyfile(FIXTURE, root / 'data' / 'place-examples.json')
            render_gallery.build(root, output)
            detail = (output / 'ja/gallery/place/hilltop-villa/index.html').read_text()
            self.assertIn(render_gallery.EXAMPLE_COPY['ja']['source'], detail)
            self.assertIn('data-gallery-filter="example"', (output / 'gallery/index.html').read_text())


class GuideTests(unittest.TestCase):
    def test_tutorials_point_people_and_agents_to_the_examples(self):
        for page in ['build-a-room', 'make-a-room', 'build-a-view', 'make-a-view', 'create-your-own-place']:
            with self.subTest(page=page):
                text = (ROOT / page / 'index.html').read_text()
                self.assertIn('href="../gallery/?examples"', text)
                self.assertIn('href="../data/place-examples.json"', text)
        guide = (ROOT / 'reference' / 'locusplace-format.md').read_text()
        for term in ['https://enterlocus.com/data/place-examples.json', '../gallery/?examples', 'Blender file', 'sha256',
                     '../asset-rights/#example-license']:
            self.assertIn(term, guide)

    def test_skills_explain_manifest_features_fetching_and_license_limits(self):
        for skill in ['build-original-locus-room', 'build-a-view']:
            with self.subTest(skill=skill):
                text = (ROOT / '.agents' / 'skills' / skill / 'SKILL.md').read_text()
                for term in ['https://enterlocus.com/data/place-examples.json', 'features', 'sha256',
                             'validate_locusplace.py', 'LicenseRef-EnterLocus-Example', 'template',
                             'including commercially', 're-upload',
                             'https://enterlocus.com/asset-rights/#example-license']:
                    self.assertIn(term, text)

    def test_license_surfaces_agree(self):
        text = (ROOT / 'LICENSES' / 'LicenseRef-EnterLocus-Example.txt').read_text()
        self.assertTrue(text.startswith('Locus Example License (LicenseRef-EnterLocus-Example), version 1.1'))
        rights = (ROOT / 'asset-rights' / 'index.html').read_text()
        self.assertIn('id="example-license"', rights)
        self.assertIn('href="../LICENSES/LicenseRef-EnterLocus-Example.txt"', rights)
        self.assertNotIn('not licensed for redistribution, sublicensing, sale, or reuse elsewhere', rights)
        # Version 1.1 dropped the AI-training and outside-Locus bans; no surface may still state them.
        for path in ['asset-rights/index.html', 'LICENSE.md', 'README.md', 'reference/locusplace-format.md',
                     '.agents/skills/build-original-locus-room/SKILL.md', '.agents/skills/build-a-view/SKILL.md']:
            text = (ROOT / path).read_text()
            with self.subTest(path=path):
                self.assertNotRegex(text, r'(?i)train(?:ing)? (?:or fine-tune )?(?:an )?AI models?|outside Locus')
        self.assertIn('Use what you make anywhere, including commercially.', rights)
        self.assertIn('Re-upload the original example files.', rights)
        license_map = (ROOT / 'LICENSE.md').read_text()
        self.assertIn('## Locus Example License', license_map)
        self.assertIn('LICENSES/LicenseRef-EnterLocus-Example.txt', license_map)
        self.assertIn('Blender source', license_map)
        readme = (ROOT / 'README.md').read_text()
        self.assertNotIn('Place-package download links', readme)
        self.assertIn('## Place example downloads', readme)


if __name__ == '__main__':
    unittest.main()
