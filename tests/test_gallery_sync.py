import copy
import importlib.util
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('sync_gallery', ROOT / 'tools/sync_gallery.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class GallerySyncTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads((ROOT / 'data/gallery-reader.json').read_text())
        self.snapshot = json.loads((ROOT / 'data/gallery.json').read_text())
        # Wire data at the external catalog boundary, not an internal service stub.
        self.entry = {
            'packageID': 'space.example', 'contentVersion': '1.0.0',
            'type': 'locus.room', 'availableFromAppVersion': '1.4.1',
            'preview': {'contract': 'locus.preview.card.v1', 'visibility': 'generic',
                        'requires': {'minimumAppVersion': '1.0.0', 'minimumOSVersion': '26.0.0',
                                     'capabilities': ['locus.preview.card.v1']}},
            'install': {'access': {'kind': 'supporter'}, 'delivery': {'kind': 'grant.v2'},
                        'artifact': {'envelope': {'format': 'locusplace', 'version': 1}},
                        'requires': {'minimumAppVersion': '1.0.0', 'minimumOSVersion': '26.0.0',
                                     'capabilities': ['locus.package.v2']}}}

    def select(self, entries, watermark='1.4.1'):
        return sync.select_entries({'entries': entries, 'releaseWatermarkAppVersion': watermark}, self.profile)

    def write_png(self, directory, width=3, height=2):
        def chunk(name, value):
            return struct.pack('>I', len(value)) + name + value + struct.pack('>I', zlib.crc32(name + value) & 0xffffffff)
        data = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
                + chunk(b'IDAT', zlib.compress(b''.join(b'\0' + b'\0\0\0' * width for _ in range(height))))
                + chunk(b'IEND', b''))
        sha256 = hashlib.sha256(data).hexdigest()
        path = Path(directory) / ('rendered-' + sha256 + '.png')
        path.write_bytes(data)
        return {'url': '/assets/gallery/' + path.name, 'width': width, 'height': height,
                'sha256': sha256, 'label': 'front', 'captureKind': 'visionos-simulator'}

    def registry(self, package_id, content_version, photo):
        return {'formatVersion': 1, 'packages': [{'id': package_id, 'contentVersion': content_version,
                                                   'photos': [photo]}]}

    def test_current_app_can_see_eligible_revision_above_old_watermark(self):
        newer = copy.deepcopy(self.entry)
        newer.update(contentVersion='1.0.1', availableFromAppVersion=self.profile['appVersion'])
        self.assertEqual(self.select([self.entry, newer]), [newer])

    def test_future_revision_does_not_replace_usable_revision(self):
        newer = copy.deepcopy(self.entry)
        newer.update(contentVersion='1.0.1', availableFromAppVersion='99.0.0')
        self.assertEqual(self.select([self.entry, newer]), [self.entry])

    def test_even_watermarked_revision_needs_current_install_compatibility(self):
        for field, value in [('minimumAppVersion', '99.0.0'), ('minimumOSVersion', '99.0.0'),
                             ('capabilities', ['locus.future.v1']), ('deviceCapabilities', ['future.device'])]:
            entry = copy.deepcopy(self.entry)
            entry['install']['requires'][field] = value
            with self.subTest(field=field):
                self.assertEqual(self.select([entry], '99.0.0'), [])

    def test_preview_requirements_and_unknown_access_fail_closed(self):
        entry = copy.deepcopy(self.entry)
        entry['preview']['requires']['capabilities'] = ['locus.preview.future.v1']
        self.assertEqual(self.select([entry]), [])
        entry = copy.deepcopy(self.entry)
        entry['install']['access']['kind'] = 'future'
        self.assertEqual(self.select([entry]), [])

    def test_promoted_update_app_revision_does_not_advertise_superseded_download(self):
        newer = copy.deepcopy(self.entry)
        newer.update(contentVersion='1.0.1', availableFromAppVersion='99.0.0')
        newer['install']['requires']['minimumAppVersion'] = '99.0.0'
        self.assertEqual(self.select([self.entry, newer], '99.0.0'), [])

    def test_versions_compare_numerically(self):
        newer = copy.deepcopy(self.entry)
        newer['contentVersion'] = '1.0.10'
        older = copy.deepcopy(self.entry)
        older['contentVersion'] = '1.0.9'
        self.assertEqual(self.select([newer, older]), [newer])

    def test_integrity_and_public_paths_reject_mutation(self):
        data = b'public preview'
        ref = {'byteCount': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        self.assertEqual(sync.checked(data, ref), data)
        with self.assertRaises(ValueError):
            sync.checked(data + b'changed', ref)
        for path in ['https://example.org/a', 'thumbnails/../private', '/thumbnails/a', 'thumbnails/a?token=x']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                sync.safe_path(path, 'thumbnails/')

    def test_committed_snapshot_contains_only_public_preview_fields(self):
        allowed = {'id', 'slug', 'type', 'title', 'description', 'image', 'access', 'animated',
                   'hasSound', 'builtIn', 'localizations', 'searchTerms', 'contentVersion', 'credits', 'photos',
                   'addedAt', 'updatedAt', 'previewRelease'}
        for place in self.snapshot['places']:
            self.assertLessEqual(set(place), allowed)
            self.assertIn(place['access'], ('free', 'supporter'))
            self.assertNotIn('install', place)
            self.assertNotIn('.locusplace', json.dumps(place))
        self.assertEqual({p['id'] for p in self.snapshot['places'] if p['builtIn']},
                         {p['id'] for p in self.profile['builtIns']})
        ids = {p['id'] for p in self.snapshot['places']}
        for series in self.snapshot['series']:
            self.assertLessEqual(set(series['members']), ids)
            self.assertGreaterEqual(len(series['members']), 2)

    def test_export_orders_new_and_substantially_updated_places_before_undated_builtins(self):
        data = b'public thumbnail'
        ref = {'path': 'thumbnails/example.jpg', 'byteCount': len(data),
               'sha256': hashlib.sha256(data).hexdigest(), 'width': 1024, 'height': 512,
               'mediaType': 'image/jpeg'}
        entries = []
        for name, added, updated in [
                ('old', '2026-09-01T00:00:00Z', '2026-09-01T00:00:00Z'),
                ('new', '2026-10-28T00:00:00Z', '2026-10-01T00:00:00Z'),
                ('revised', '2026-08-01T00:00:00Z', '2026-10-29T01:00:00+01:00')]:
            entry = copy.deepcopy(self.entry)
            entry.update(packageID='space.' + name, addedAt=added, updatedAt=updated)
            if name == 'old':
                entry['contentVersion'] = '99.0.0'  # Maintenance/version changes do not make content recent.
            entry['preview'].update(title=name, image=ref)
            entries.append(entry)
        catalog = {'environment': 'production', 'catalogProtocol': 3, 'snapshotID': 'example',
                   'publishedAt': '2026-10-29T00:00:00Z', 'expiresAt': '2026-11-29T00:00:00Z',
                   'releaseWatermarkAppVersion': '1.4.1', 'entries': entries}
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr(ref['path'], data)
        with zipfile.ZipFile(buffer) as archive:
            result = sync.export(catalog, catalog, archive, self.profile, {})
        self.assertEqual([p['id'] for p in result['places'][:3]],
                         ['space.revised', 'space.new', 'space.old'])
        self.assertTrue(all(p['builtIn'] for p in result['places'][3:]))

    def test_committed_snapshot_is_newest_first(self):
        dates = [max(p.get('addedAt', ''), p.get('updatedAt', '')) for p in self.snapshot['places']]
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_every_static_preview_exists_and_matches_its_published_hash(self):
        for place in self.snapshot['places']:
            image = place['image']
            self.assertTrue(image['url'].startswith('/assets/gallery/'))
            asset = ROOT / image['url'].lstrip('/')
            with self.subTest(place=place['id']):
                self.assertEqual(hashlib.sha256(asset.read_bytes()).hexdigest(), image['sha256'])

    def test_photo_registry_enriches_only_matching_selected_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            photo = self.write_png(directory)
            registry = sync.validate_photo_registry(self.registry('space.example', '1.0.0', photo), Path(directory))
        places = [
            {'id': 'space.example', 'contentVersion': '1.0.0'},
            {'id': 'space.example', 'contentVersion': '1.0.1'},
            {'id': 'space.other', 'contentVersion': '1.0.0'},
        ]
        sync.enrich_places_with_photos(places, registry)
        self.assertEqual(places[0]['photos'], [photo])
        self.assertNotIn('photos', places[1])
        self.assertNotIn('photos', places[2])

    def test_future_photo_registry_revision_does_not_export_on_older_place(self):
        with tempfile.TemporaryDirectory() as directory:
            photo = self.write_png(directory)
            registry = sync.validate_photo_registry(self.registry('space.example', '99.0.0', photo), Path(directory))
        places = [{'id': 'space.example', 'contentVersion': '1.0.0'}]
        sync.enrich_places_with_photos(places, registry)
        self.assertNotIn('photos', places[0])

    def test_photo_registry_enriches_builtin_only_at_its_profile_revision(self):
        builtin = copy.deepcopy(self.profile['builtIns'][0])
        profile = copy.deepcopy(self.profile)
        profile['builtIns'] = [builtin]
        catalog = {'environment': 'production', 'catalogProtocol': 3, 'snapshotID': 'example',
                   'publishedAt': '2026-10-29T00:00:00Z', 'expiresAt': '2026-11-29T00:00:00Z',
                   'releaseWatermarkAppVersion': '1.4.1', 'entries': []}
        with tempfile.TemporaryDirectory() as directory:
            photo = self.write_png(directory)
            registry = sync.validate_photo_registry(
                self.registry(builtin['id'], builtin['contentVersion'], photo), Path(directory))
        with zipfile.ZipFile(io.BytesIO(), 'w') as archive:
            result = sync.export(catalog, catalog, archive, profile, {}, registry)
        self.assertEqual(result['places'][0]['photos'], [photo])

    def test_photo_registry_rejects_path_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            photo = self.write_png(directory)
            photo['url'] = '/assets/gallery/rendered-' + '0' * 64 + '.png'
            with self.assertRaises(ValueError):
                sync.validate_photo_registry(self.registry('space.example', '1.0.0', photo), Path(directory))

    def test_series_covers_and_members_are_visible_same_kind(self):
        data = b'public thumbnail'
        ref = {'path': 'thumbnails/example.jpg', 'byteCount': len(data),
               'sha256': hashlib.sha256(data).hexdigest(), 'width': 1024, 'height': 512,
               'mediaType': 'image/jpeg'}
        room = copy.deepcopy(self.entry)
        room.update(packageID='space.room', addedAt='2026-10-01T00:00:00Z')
        room['preview'].update(title='room', image=ref)
        room_two = copy.deepcopy(room)
        room_two.update(packageID='space.room-two')
        view = copy.deepcopy(room)
        view.update(packageID='destination.view', type='locus.view')
        catalog = {'environment': 'production', 'catalogProtocol': 3, 'snapshotID': 'example',
                   'publishedAt': '2026-10-29T00:00:00Z', 'expiresAt': '2026-11-29T00:00:00Z',
                   'releaseWatermarkAppVersion': '1.4.1', 'entries': [room, room_two, view],
                   'extensions': {'locus.places.series.v1': {'series': [
                       {'id': 'mixed', 'title': 'Mixed', 'members': ['space.room', 'destination.view', 'space.room-two'],
                        'heroMember': 'destination.view', 'cover': ['destination.view', 'space.room-two']}]}}}
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr(ref['path'], data)
        with zipfile.ZipFile(buffer) as archive:
            result = sync.export(catalog, catalog, archive, self.profile, {})
        self.assertEqual(result['series'][0]['type'], 'room')
        self.assertEqual(result['series'][0]['members'], ['space.room', 'space.room-two'])
        self.assertNotIn('heroMember', result['series'][0])
        self.assertEqual(result['series'][0]['cover'], ['space.room-two'])

    def test_authorized_future_room_previews_export_without_artifacts(self):
        data = b'public thumbnail'
        ref = {'path': 'thumbnails/example.jpg', 'byteCount': len(data),
               'sha256': hashlib.sha256(data).hexdigest(), 'width': 1024, 'height': 512,
               'mediaType': 'image/jpeg'}
        entries = []
        for package_id in ('space.japanese-courtyard-mansion', 'space.pacific-palapa-house'):
            entry = copy.deepcopy(self.entry)
            entry.update(packageID=package_id, contentVersion='1.0.4',
                         availableFromAppVersion='1.4.4', addedAt='2026-10-30T00:00:00Z')
            entry['install']['requires']['minimumAppVersion'] = '1.4.4'
            entry['preview'].update(title=package_id, image=ref)
            entries.append(entry)
        catalog = {'environment': 'production', 'catalogProtocol': 3, 'snapshotID': 'example',
                   'publishedAt': '2026-10-29T00:00:00Z', 'expiresAt': '2026-11-29T00:00:00Z',
                   'releaseWatermarkAppVersion': '1.4.3', 'entries': entries}
        allowlist = {'formatVersion': 1, 'previews': [
            {'id': 'space.japanese-courtyard-mansion', 'contentVersion': '1.0.4', 'appVersion': '1.4.4'},
            {'id': 'space.pacific-palapa-house', 'contentVersion': '1.0.4', 'appVersion': '1.4.4'}]}
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr(ref['path'], data)
        with zipfile.ZipFile(buffer) as archive:
            result = sync.export(catalog, catalog, archive, self.profile, {}, release_previews=allowlist)
        preview_places = [place for place in result['places'] if place['id'] in {
            'space.japanese-courtyard-mansion', 'space.pacific-palapa-house'}]
        self.assertEqual({place['id'] for place in preview_places},
                         {'space.japanese-courtyard-mansion', 'space.pacific-palapa-house'})
        for place in preview_places:
            self.assertEqual(place['previewRelease'], '1.4.4')
            self.assertNotIn('install', place)
            self.assertNotIn('artifact', json.dumps(place))

    def test_nonapproved_future_entry_remains_hidden(self):
        future = copy.deepcopy(self.entry)
        future.update(packageID='space.not-approved', contentVersion='1.0.4', availableFromAppVersion='1.4.4')
        future['install']['requires']['minimumAppVersion'] = '1.4.4'
        allowlist = {'formatVersion': 1, 'previews': []}
        self.assertEqual(sync.select_release_previews({'entries': [future]}, self.profile, allowlist), [])

    def test_preview_release_requires_exact_configured_install_version_and_revision(self):
        entry = copy.deepcopy(self.entry)
        entry.update(packageID='space.japanese-courtyard-mansion', contentVersion='1.0.4')
        entry['install']['requires']['minimumAppVersion'] = '1.4.3'
        allowlist = {'formatVersion': 1, 'previews': [
            {'id': 'space.japanese-courtyard-mansion', 'contentVersion': '1.0.4', 'appVersion': '1.4.4'}]}
        with self.assertRaises(ValueError):
            sync.select_release_previews({'entries': [entry]}, self.profile, allowlist)
        entry['install']['requires']['minimumAppVersion'] = '1.4.4'
        allowlist['previews'][0]['contentVersion'] = '1.0.5'
        with self.assertRaises(ValueError):
            sync.select_release_previews({'entries': [entry]}, self.profile, allowlist)

    def test_malformed_or_ambiguous_preview_allowlist_fails_closed(self):
        with self.assertRaises(ValueError):
            sync.validate_release_previews({'formatVersion': 1, 'previews': [{}]})
        with self.assertRaises(ValueError):
            sync.validate_release_previews({'formatVersion': 1, 'previews': [
                {'id': 'space.example', 'contentVersion': '1.0.4', 'appVersion': '1.4.4'},
                {'id': 'space.example', 'contentVersion': '1.0.5', 'appVersion': '1.4.4'}]})

    def test_normal_selection_wins_over_authorized_preview(self):
        data = b'public thumbnail'
        ref = {'path': 'thumbnails/example.jpg', 'byteCount': len(data),
               'sha256': hashlib.sha256(data).hexdigest(), 'width': 1024, 'height': 512,
               'mediaType': 'image/jpeg'}
        profile = copy.deepcopy(self.profile)
        profile['appVersion'] = '1.4.4'
        entry = copy.deepcopy(self.entry)
        entry.update(packageID='space.japanese-courtyard-mansion', contentVersion='1.0.4',
                     availableFromAppVersion='1.4.4')
        entry['install']['requires']['minimumAppVersion'] = '1.4.4'
        entry['preview'].update(title='Maple Courtyard', image=ref)
        catalog = {'environment': 'production', 'catalogProtocol': 3, 'snapshotID': 'example',
                   'publishedAt': '2026-10-29T00:00:00Z', 'expiresAt': '2026-11-29T00:00:00Z',
                   'releaseWatermarkAppVersion': '1.4.3', 'entries': [entry]}
        allowlist = {'formatVersion': 1, 'previews': [
            {'id': 'space.japanese-courtyard-mansion', 'contentVersion': '1.0.4', 'appVersion': '1.4.4'}]}
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr(ref['path'], data)
        with zipfile.ZipFile(buffer) as archive:
            result = sync.export(catalog, catalog, archive, profile, {}, release_previews=allowlist)
        place = next(place for place in result['places'] if place['id'] == entry['packageID'])
        self.assertNotIn('previewRelease', place)


if __name__ == '__main__':
    unittest.main()
