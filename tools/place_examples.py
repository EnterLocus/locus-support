#!/usr/bin/env python3
"""Load, validate and match the public Place example downloads.

`data/place-examples.json` lists teaching examples: a final Place package and,
where one exists, a sanitized Blender source bundle. The site publishes the
file unchanged at https://enterlocus.com/data/place-examples.json for people
and coding agents, and the Gallery shows each example on its Place page.

Run without arguments to validate the manifest and print where each example
appears. `--verify` checks every download URL's HTTP status and byte count
without downloading the files; add `--hash` to download each file and compare
its SHA-256 as well.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / 'data' / 'place-examples.json'
GALLERY_PATH = ROOT / 'data' / 'gallery.json'
MEDIA_BASE = 'https://media.enterlocus.net/examples/'
PUBLIC_URL = 'https://enterlocus.com/data/place-examples.json'

# License identifiers the site can explain, with the anchor that explains them.
LICENSES = {
    'LicenseRef-EnterLocus-Example': 'https://enterlocus.com/asset-rights/#example-license',
    'CC-BY-4.0': 'https://enterlocus.com/asset-rights/#demo-room-notices',
}
LICENSE_PATHS = {
    'LicenseRef-EnterLocus-Example': '/asset-rights/#example-license',
    'CC-BY-4.0': '/asset-rights/#demo-room-notices',
}
# CC BY 4.0 belongs only to the three historical demo Rooms.
CC_BY_ROOMS = ('atrium-loft', 'courtyard-gallery', 'horizon-atelier')

FEATURES = (
    'video', 'room-animation', 'water', 'flowing-water', 'shore', 'midground',
    'day-night', 'procedural-sky', 'celestial', 'sound', 'music', 'light-layers',
    'baked-irradiance', 'interactive-states', 'generated-furniture', 'clouds',
    'particles', 'room-tv',
)
KINDS = {'room', 'view'}
EXAMPLE_KEYS = {'packageID', 'kind', 'title', 'license', 'features', 'package', 'source'}
OPTIONAL_EXAMPLE_KEYS = {'notes', 'upcoming'}
UPCOMING_KEYS = {'appVersion', 'package', 'source', 'features'}
PACKAGE_KEYS = {'contentVersion', 'minimumAppVersion', 'fileName', 'url', 'byteCount', 'sha256'}
SOURCE_KEYS = {'sourceVersion', 'blenderVersion', 'fileName', 'url', 'byteCount', 'sha256'}
_PACKAGE_ID = re.compile(r'[a-z0-9]+(?:[.-][a-z0-9]+)*')
_FILE_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]*')
_SHA256 = re.compile(r'[0-9a-f]{64}')
_VERSION = re.compile(r'\d+(?:\.\d+){1,3}')


def empty_manifest() -> dict:
    return {'formatVersion': 1, 'licenses': dict(LICENSES), 'examples': []}


def version(value: str) -> tuple[int, ...]:
    if not isinstance(value, str) or not _VERSION.fullmatch(value):
        raise ValueError(f'Invalid version {value!r}')
    parts = tuple(int(part) for part in value.split('.'))
    return parts + (0,) * (4 - len(parts))


def _file(record: object, keys: set[str], package_id: str, label: str, suffixes: tuple[str, ...]) -> dict:
    if not isinstance(record, dict) or set(record) != keys:
        raise ValueError(f'{package_id}: {label} must have exactly {sorted(keys)}')
    name = record['fileName']
    if not isinstance(name, str) or not _FILE_NAME.fullmatch(name) or not name.endswith(suffixes):
        raise ValueError(f'{package_id}: invalid {label} fileName {name!r}')
    expected = f'{MEDIA_BASE}{package_id}/{name}'
    if record['url'] != expected:
        raise ValueError(f'{package_id}: {label} url must be {expected}')
    count = record['byteCount']
    if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
        raise ValueError(f'{package_id}: {label} byteCount must be a positive integer')
    if not isinstance(record['sha256'], str) or not _SHA256.fullmatch(record['sha256']):
        raise ValueError(f'{package_id}: {label} sha256 must be 64 lowercase hex digits')
    return record


def validate(manifest: object) -> dict:
    """Return the manifest unchanged, or raise ValueError naming the first problem."""
    if not isinstance(manifest, dict) or set(manifest) != {'formatVersion', 'licenses', 'examples'}:
        raise ValueError('place-examples.json must have formatVersion, licenses and examples')
    if manifest['formatVersion'] != 1:
        raise ValueError('place-examples.json must use formatVersion 1')
    licenses = manifest['licenses']
    if not isinstance(licenses, dict) or any(LICENSES.get(key) != value for key, value in licenses.items()):
        raise ValueError(f'licenses must map known identifiers to their notices: {LICENSES}')
    if not isinstance(manifest['examples'], list):
        raise ValueError('examples must be a list')
    seen: set[str] = set()
    for example in manifest['examples']:
        if not isinstance(example, dict) or not EXAMPLE_KEYS <= set(example) <= EXAMPLE_KEYS | OPTIONAL_EXAMPLE_KEYS:
            raise ValueError(f'Each example must have {sorted(EXAMPLE_KEYS)} and optional notes')
        package_id = example['packageID']
        if not isinstance(package_id, str) or not _PACKAGE_ID.fullmatch(package_id):
            raise ValueError(f'Invalid packageID {package_id!r}')
        if package_id in seen:
            raise ValueError(f'Duplicate example {package_id}')
        seen.add(package_id)
        if example['kind'] not in KINDS:
            raise ValueError(f'{package_id}: kind must be room or view')
        prefix = {'space': 'room', 'destination': 'view'}.get(package_id.split('.', 1)[0])
        if prefix and prefix != example['kind']:
            raise ValueError(f'{package_id}: kind {example["kind"]!r} does not match its packageID')
        if not isinstance(example['title'], str) or not example['title'].strip():
            raise ValueError(f'{package_id}: title is required')
        license_id = example['license']
        if license_id not in licenses:
            raise ValueError(f'{package_id}: license {license_id!r} is not listed in licenses')
        if license_id == 'CC-BY-4.0' and not package_id.endswith(CC_BY_ROOMS):
            raise ValueError(f'{package_id}: CC-BY-4.0 is reserved for the three demo Rooms')
        package = _files(example, package_id, '')
        if 'upcoming' in example:
            _upcoming(example['upcoming'], example, package_id)
    return manifest


def _files(record: dict, package_id: str, label: str) -> dict:
    """Validate the features, package, source and notes shared by an example and its upcoming revision."""
    features = record['features']
    if (not isinstance(features, list) or len(set(features)) != len(features)
            or any(feature not in FEATURES for feature in features)):
        raise ValueError(f'{package_id}: {label}features must be unique ids from {FEATURES}')
    package = _file(record['package'], PACKAGE_KEYS, package_id, label + 'package', ('.locusplace', '.zip'))
    version(package['contentVersion'])
    version(package['minimumAppVersion'])
    if record['source'] is not None:
        source = _file(record['source'], SOURCE_KEYS, package_id, label + 'source', ('.zip',))
        version(source['sourceVersion'])
        version(source['blenderVersion'])
        if source['url'] == package['url']:
            raise ValueError(f'{package_id}: {label}source and package must be separate files')
    notes = record.get('notes')
    if notes is not None and (not isinstance(notes, str) or not notes.strip() or '\n' in notes):
        raise ValueError(f'{package_id}: {label}notes must be one non-empty line')
    return package


def _upcoming(upcoming: object, example: dict, package_id: str) -> None:
    """An upcoming revision needs a future App; it is shown before that App is public."""
    current = example['package']
    if not isinstance(upcoming, dict) or not UPCOMING_KEYS <= set(upcoming) <= UPCOMING_KEYS | {'notes'}:
        raise ValueError(f'{package_id}: upcoming must have {sorted(UPCOMING_KEYS)} and optional notes')
    package = _files(upcoming, package_id, 'upcoming ')
    app = version(upcoming['appVersion'])
    if app <= version(current['minimumAppVersion']):
        raise ValueError(f'{package_id}: upcoming appVersion must be newer than the current package minimumAppVersion')
    if version(package['minimumAppVersion']) > app:
        raise ValueError(f'{package_id}: upcoming package needs a newer App than its appVersion')
    if version(package['contentVersion']) <= version(current['contentVersion']):
        raise ValueError(f'{package_id}: upcoming package contentVersion must be newer than the current one')
    urls = [record['url'] for record in files(example)]
    if len(set(urls)) != len(urls):
        raise ValueError(f'{package_id}: upcoming files must differ from the current files')


def files(example: dict) -> list[dict]:
    """Every downloadable file of an example, including its upcoming revision."""
    records = [example['package'], example['source']]
    upcoming = example.get('upcoming')
    if upcoming:
        records += [upcoming['package'], upcoming['source']]
    return [record for record in records if record]


def all_notes(manifest: dict) -> list[str]:
    """Every English note the site shows, for translation checks."""
    result = []
    for example in manifest['examples']:
        for record in (example, example.get('upcoming') or {}):
            if record.get('notes'):
                result.append(record['notes'])
    return result


def load(path: Path = MANIFEST_PATH) -> dict:
    """Load the manifest; a missing file means no examples are published."""
    path = Path(path)
    if not path.is_file():
        return empty_manifest()
    return validate(json.loads(path.read_text(encoding='utf-8')))


def installable(example: dict, app_version: str) -> bool:
    return version(example['package']['minimumAppVersion']) <= version(app_version)


def match(gallery: dict, manifest: dict) -> tuple[dict[str, dict], list[dict]]:
    """Return examples by Gallery Place ID, plus installable examples outside the Gallery.

    A Place shows its example when the reviewed public App can install it and,
    for a Library Place, the example package is the Gallery's displayed
    revision or an older one; an example newer than the Gallery snapshot waits
    for the next refresh. A built-in Place ships inside the App, so its example
    is a separately imported package and only installability applies.
    """
    app_version = gallery.get('appVersion', '0.0')
    places = {place['id']: place for place in gallery.get('places', [])}
    by_place: dict[str, dict] = {}
    extras: list[dict] = []
    for example in manifest.get('examples', []):
        if not installable(example, app_version):
            continue
        place = places.get(example['packageID'])
        if place is None:
            extras.append(example)
        elif (place.get('builtIn')
              or version(example['package']['contentVersion']) <= version(place['contentVersion'])):
            by_place[place['id']] = example
    return by_place, extras


def _check_remote(record: dict, full: bool) -> str:
    request = Request(record['url'], method='GET' if full else 'HEAD',
                      headers={'User-Agent': 'Mozilla/5.0 LocusSiteExamples/1'})
    with urlopen(request, timeout=120) as response:
        length = response.headers.get('Content-Length')
        if not full:
            if response.status != 200 or length is None or int(length) != record['byteCount']:
                return f'byte count {length} != {record["byteCount"]}'
            return ''
        digest, total = hashlib.sha256(), 0
        while chunk := response.read(1 << 20):
            digest.update(chunk)
            total += len(chunk)
    if total != record['byteCount']:
        return f'byte count {total} != {record["byteCount"]}'
    if digest.hexdigest() != record['sha256']:
        return 'SHA-256 mismatch'
    return ''


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--manifest', type=Path, default=MANIFEST_PATH)
    parser.add_argument('--verify', action='store_true', help='check each URL and byte count over HTTPS')
    parser.add_argument('--hash', action='store_true', help='with --verify, download and compare SHA-256')
    args = parser.parse_args(argv)
    manifest = load(args.manifest)
    gallery = json.loads(GALLERY_PATH.read_text(encoding='utf-8'))
    by_place, extras = match(gallery, manifest)
    shown = {example['packageID'] for example in [*by_place.values(), *extras]}
    for example in manifest['examples']:
        where = ('Gallery place page' if example['packageID'] in by_place
                 else 'Gallery examples list' if example['packageID'] in shown else 'HIDDEN')
        upcoming = example.get('upcoming')
        later = (f' (+ {upcoming["package"]["contentVersion"]} for Locus {upcoming["appVersion"]})'
                 if upcoming else '')
        print(f'{example["packageID"]} {example["package"]["contentVersion"]}{later}: {where}')
    failures = 0
    if args.verify:
        for example in manifest['examples']:
            for record in files(example):
                problem = _check_remote(record, args.hash)
                print(f'{"FAIL" if problem else "ok"} {record["url"]} {problem}'.rstrip())
                failures += bool(problem)
    print(f'{len(manifest["examples"])} examples, {len(shown)} shown')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
