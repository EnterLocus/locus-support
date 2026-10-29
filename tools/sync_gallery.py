"""Export public preview metadata from Production; never fetch Place packages.

Reader profiles come from a reviewed, immutable App Store release. A newer App
Store version does not silently expand the known reader's capabilities.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'https://content.enterlocus.net/'
APP_LOOKUP = 'https://itunes.apple.com/lookup?id=6802168265&country=us'
MAX_ARCHIVE = 64 * 1024 * 1024
MAX_GALLERY_PHOTOS = 8
MAX_GALLERY_PHOTO_BYTES = 8 * 1024 * 1024
MAX_GALLERY_PHOTO_DIMENSION = 8192
MAX_GALLERY_PHOTO_PIXELS = 32 * 1024 * 1024
PHOTO_LABELS = {'front', 'left', 'right', 'alternate-seat'}
PHOTO_URL = re.compile(r'/assets/gallery/rendered-([a-f0-9]{64})\.(jpg|png)')


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+\.\d+(?:\.\d+)?', value):
        raise ValueError('Invalid version')
    parts = tuple(int(x) for x in value.split('.'))
    return parts + (0,) * (3 - len(parts))


def fetch(url, limit=MAX_ARCHIVE):
    request = Request(url, headers={'User-Agent': 'Mozilla/5.0 LocusGallery/1',
                                    'Cache-Control': 'no-cache'})
    with urlopen(request, timeout=45) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Response exceeds limit')
    return data


def safe_path(value, prefix):
    if not isinstance(value, str):
        raise ValueError('Unexpected public object path')
    path = PurePosixPath(value)
    if (not value.startswith(prefix)
            or path.is_absolute() or '..' in path.parts or '\\' in value
            or '?' in value or '#' in value):
        raise ValueError('Unexpected public object path')
    return value


def checked(data, ref):
    if len(data) != ref['byteCount'] or hashlib.sha256(data).hexdigest() != ref['sha256']:
        raise ValueError('Public object integrity mismatch')
    return data


def image_dimensions(data, suffix):
    """Return dimensions for a small, local PNG or JPEG without third-party code."""
    if suffix == 'png':
        if (len(data) < 24 or data[:8] != b'\x89PNG\r\n\x1a\n'
                or data[8:12] != b'\x00\x00\x00\r' or data[12:16] != b'IHDR'):
            raise ValueError('Invalid PNG gallery photo')
        width = int.from_bytes(data[16:20], 'big')
        height = int.from_bytes(data[20:24], 'big')
    elif suffix == 'jpg':
        if len(data) < 4 or data[:2] != b'\xff\xd8':
            raise ValueError('Invalid JPEG gallery photo')
        position = 2
        width = height = None
        sof = set(range(0xc0, 0xc4)) | set(range(0xc5, 0xc8)) | set(range(0xc9, 0xcc)) | set(range(0xcd, 0xd0))
        while position < len(data):
            while position < len(data) and data[position] == 0xff:
                position += 1
            if position >= len(data):
                break
            marker = data[position]
            position += 1
            if marker in (0x00, 0xd8, 0xd9):
                continue
            if position + 2 > len(data):
                break
            length = int.from_bytes(data[position:position + 2], 'big')
            if length < 2 or position + length > len(data):
                break
            if marker in sof:
                if length < 8:
                    break
                height = int.from_bytes(data[position + 3:position + 5], 'big')
                width = int.from_bytes(data[position + 5:position + 7], 'big')
                break
            position += length
        if width is None or height is None:
            raise ValueError('JPEG gallery photo is missing dimensions')
    else:
        raise ValueError('Unsupported gallery photo type')
    if not width or not height:
        raise ValueError('Invalid gallery photo dimensions')
    return width, height


def validate_photo_registry(registry, gallery_directory):
    """Validate public capture metadata and return only fields safe to export."""
    if not isinstance(registry, dict) or set(registry) != {'formatVersion', 'packages'}:
        raise ValueError('Invalid gallery photo registry')
    if registry['formatVersion'] != 1 or not isinstance(registry['packages'], list):
        raise ValueError('Unsupported gallery photo registry')
    if len(registry['packages']) > 250:
        raise ValueError('Too many gallery photo packages')
    validated = {}
    for package in registry['packages']:
        if not isinstance(package, dict) or set(package) != {'id', 'contentVersion', 'photos'}:
            raise ValueError('Invalid gallery photo package')
        package_id = package['id']
        content_version = package['contentVersion']
        if (not isinstance(package_id, str)
                or not re.fullmatch(r'(?:destination|space)\.[a-z0-9-]+', package_id)):
            raise ValueError('Invalid gallery photo package ID')
        version(content_version)
        photos = package['photos']
        if not isinstance(photos, list) or not 0 < len(photos) <= MAX_GALLERY_PHOTOS:
            raise ValueError('Invalid gallery photo count')
        key = (package_id, content_version)
        if key in validated:
            raise ValueError('Duplicate gallery photo package revision')
        public_photos = []
        seen = set()
        for photo in photos:
            if not isinstance(photo, dict) or set(photo) - {'url', 'width', 'height', 'sha256', 'label', 'captureKind'}:
                raise ValueError('Invalid gallery photo fields')
            if set(photo) - {'label'} != {'url', 'width', 'height', 'sha256', 'captureKind'}:
                raise ValueError('Gallery photo fields are incomplete')
            url, sha256 = photo['url'], photo['sha256']
            match = PHOTO_URL.fullmatch(url) if isinstance(url, str) else None
            if (not match or not isinstance(sha256, str)
                    or not re.fullmatch(r'[a-f0-9]{64}', sha256)
                    or match.group(1) != sha256):
                raise ValueError('Gallery photo URL must be its local SHA-256 path')
            if not all(isinstance(photo[name], int) and not isinstance(photo[name], bool)
                       for name in ('width', 'height')):
                raise ValueError('Invalid gallery photo dimensions')
            if (not 0 < photo['width'] <= MAX_GALLERY_PHOTO_DIMENSION
                    or not 0 < photo['height'] <= MAX_GALLERY_PHOTO_DIMENSION
                    or photo['width'] * photo['height'] > MAX_GALLERY_PHOTO_PIXELS):
                raise ValueError('Gallery photo dimensions exceed limits')
            if photo['captureKind'] != 'visionos-simulator':
                raise ValueError('Unsupported gallery photo capture kind')
            if 'label' in photo and photo['label'] not in PHOTO_LABELS:
                raise ValueError('Unsupported gallery photo label')
            asset = gallery_directory / ('rendered-' + sha256 + '.' + match.group(2))
            if not asset.is_file() or asset.stat().st_size > MAX_GALLERY_PHOTO_BYTES:
                raise ValueError('Gallery photo asset is missing or exceeds the size limit')
            data = asset.read_bytes()
            if hashlib.sha256(data).hexdigest() != sha256:
                raise ValueError('Gallery photo asset hash mismatch')
            if image_dimensions(data, match.group(2)) != (photo['width'], photo['height']):
                raise ValueError('Gallery photo asset dimensions mismatch')
            if url in seen:
                raise ValueError('Duplicate gallery photo')
            seen.add(url)
            public = {name: photo[name] for name in ('url', 'width', 'height', 'sha256', 'captureKind')}
            if 'label' in photo:
                public['label'] = photo['label']
            public_photos.append(public)
        validated[key] = public_photos
    return validated


def enrich_places_with_photos(places, photo_registry):
    """Add captures only to the exact public revision selected for export."""
    for place in places:
        photos = photo_registry.get((place['id'], place['contentVersion']))
        if photos:
            place['photos'] = copy.deepcopy(photos)


def compatible(requirements, profile):
    return (version(requirements['minimumAppVersion']) <= version(profile['appVersion'])
            and version(requirements['minimumOSVersion']) <= version(profile['minimumOSVersion'])
            and set(requirements['capabilities']) <= set(profile['capabilities'])
            and not requirements.get('deviceCapabilities'))


def select_entries(catalog, profile):
    """Select the App's newest visible revision, then omit unusable previews.

    Gallery showcases usable content, so it excludes even watermarked
    preview-only/Update App entries. This is stricter than the App's card list.
    """
    selected = {}
    watermark = version(catalog['releaseWatermarkAppVersion'])
    current = version(profile['appVersion'])
    for entry in catalog['entries']:
        preview, install = entry['preview'], entry['install']
        known = entry['type'] in ('locus.view', 'locus.room')
        if (preview['contract'] != 'locus.preview.card.v1'
                or preview['visibility'] not in ('generic', 'known-type')
                or (not known and preview['visibility'] != 'generic')
                or not compatible(preview['requires'], profile)):
            continue
        access, delivery = install['access']['kind'], install['delivery']['kind']
        usable = (known and compatible(install['requires'], profile)
                  and (access, delivery) in (('free', 'public-https.v1'), ('supporter', 'grant.v2'))
                  and install['artifact']['envelope'] == {'format': 'locusplace', 'version': 1})
        audience = version(entry['availableFromAppVersion'])
        if audience > watermark and not (audience <= current and usable):
            continue
        pid = entry['packageID']
        if pid not in selected or version(entry['contentVersion']) > version(selected[pid][0]['contentVersion']):
            selected[pid] = (entry, usable)
    return [selected[key][0] for key in sorted(selected) if selected[key][1]]


def image(ref, archive, images, prefix='thumbnails/'):
    path = safe_path(ref['path'], prefix)
    if (ref.get('mediaType') not in ('image/jpeg', 'image/png')
            or not 0 < ref['byteCount'] <= 2 * 1024 * 1024
            or archive.getinfo(path).file_size != ref['byteCount']):
        raise ValueError('Invalid public preview size or media type')
    suffix = '.png' if ref.get('mediaType') == 'image/png' else '.jpg'
    filename = 'library-' + ref['sha256'] + suffix
    images[filename] = checked(archive.read(path), ref)
    return {'url': '/assets/gallery/' + filename, 'width': ref['width'], 'height': ref['height'],
            'sha256': ref['sha256']}


def recent_date(place):
    dates = []
    for field in ('addedAt', 'updatedAt'):
        if place.get(field):
            value = datetime.fromisoformat(place[field].replace('Z', '+00:00'))
            if value.tzinfo is None:
                raise ValueError('Gallery dates must include a timezone')
            dates.append(value)
    return max(dates, default=datetime.min.replace(tzinfo=timezone.utc))


def export(catalog, descriptor, archive, profile, images, photo_registry=None):
    if (catalog['environment'] != 'production' or catalog['catalogProtocol'] != 3
            or any(catalog[k] != descriptor[k] for k in ('environment', 'snapshotID', 'publishedAt', 'expiresAt'))):
        raise ValueError('Production descriptor/catalog identity mismatch')
    places = copy.deepcopy(profile['builtIns'])
    animated = set(profile['animatedViewCapabilities'])
    for entry in select_entries(catalog, profile):
        preview = entry['preview']
        pid = entry['packageID']
        if not re.fullmatch(r'(?:destination|space)\.[a-z0-9-]+', pid):
            raise ValueError('Unexpected Place ID')
        locales = {tag: {'title': value.get('title', preview['title']),
                         'description': value.get('caption', preview.get('caption', '')),
                         'searchTerms': value.get('searchTerms', entry.get('searchTerms', []))}
                   for tag, value in preview.get('localizations', {}).items()}
        places.append({'id': pid, 'slug': pid.split('.', 1)[1],
                       'type': 'view' if entry['type'] == 'locus.view' else 'room',
                       'title': preview['title'], 'description': preview.get('caption', ''),
                       'image': image(preview['image'], archive, images),
                       'access': entry['install']['access']['kind'],
                       'animated': entry['type'] == 'locus.view' and entry.get('hasAnimatedView',
                           bool(animated.intersection(entry['install']['requires']['capabilities']))),
                       'hasSound': entry.get('hasBackgroundSound', False), 'builtIn': False,
                       'credits': {key: value for key, value in entry.get('about', {}).items()
                                   if key in ('creator', 'credit', 'licenseName', 'licenseURL',
                                              'sourceURL', 'modification', 'aiGenerated', 'aiProvider')},
                       'contentVersion': entry['contentVersion'],
                       **{key: entry[key] for key in ('addedAt', 'updatedAt') if key in entry},
                       'searchTerms': entry.get('searchTerms', []), 'localizations': locales})
    # Match Library Recent: content chronology, not export/build time or version.
    # Stable ties retain source order; undated built-ins follow dated content.
    places.sort(key=recent_date, reverse=True)
    enrich_places_with_photos(places, photo_registry or {})
    ids = {p['id'] for p in places}
    if len(ids) != len(places) or len({p['slug'] for p in places}) != len(places):
        raise ValueError('Duplicate Place identity or slug')
    series = []
    for item in catalog.get('extensions', {}).get('locus.places.series.v1', {}).get('series', []):
        by_id = {place['id']: place for place in places}
        members = []
        for package_id in item['members']:
            if package_id in by_id and package_id not in members:
                members.append(package_id)
        if members:
            kind = by_id[members[0]]['type']
            members = [pid for pid in members if by_id[pid]['type'] == kind]
        if len(members) < 2:
            continue
        value = {key: copy.deepcopy(item[key]) for key in ('id', 'title', 'description', 'localizations') if key in item}
        value['members'] = members
        value['type'] = kind
        # Banners are catalog-contained artwork, not independently hosted objects.
        # The renderer uses the selected hero member's already-public thumbnail.
        hero = item.get('heroMember')
        if hero in members:
            value['heroMember'] = hero
        cover = item.get('cover', [])
        if isinstance(cover, str):
            cover = [cover]
        if isinstance(cover, list):
            visible_cover = [member for member in cover if member in members]
            if visible_cover:
                value['cover'] = visible_cover
        series.append(value)
    return {'formatVersion': 1, 'appVersion': profile['appVersion'],
            'catalogGeneration': catalog['snapshotID'], 'places': places, 'series': series}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check if the committed snapshot is current')
    args = parser.parse_args()
    profile = json.loads((ROOT / 'data/gallery-reader.json').read_text())
    photo_registry = validate_photo_registry(
        json.loads((ROOT / 'data/gallery-photos.json').read_text()), ROOT / 'assets/gallery')
    result = json.loads(fetch(APP_LOOKUP, 2 * 1024 * 1024))['results']
    shipped = next(x['version'] for x in result if x.get('trackId') == 6802168265)
    if version(profile['appVersion']) > version(shipped):
        raise ValueError('Gallery profile is newer than the publicly available App')
    descriptor = json.loads(fetch(ORIGIN + 'catalog/v3/current.json', 1024 * 1024))
    if descriptor['environment'] != 'production' or descriptor['catalogProtocol'] != 3:
        raise ValueError('Expected Production v3 descriptor')
    if datetime.fromisoformat(descriptor['expiresAt'].replace('Z', '+00:00')) <= datetime.now(timezone.utc):
        raise ValueError('Production catalog is expired; retain the committed snapshot')
    ref = descriptor['archive']
    blob = checked(fetch(ORIGIN + safe_path(ref['path'], 'catalog/v3/snapshots/')), ref)
    images = {}
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        info = archive.getinfo('catalog.json')
        if info.file_size > 8 * 1024 * 1024:
            raise ValueError('Catalog JSON exceeds limit')
        value = export(json.loads(archive.read(info)), descriptor, archive, profile, images, photo_registry)
    output = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    target = ROOT / 'data/gallery.json'
    if args.check:
        if not target.exists() or target.read_text() != output:
            raise SystemExit('Gallery snapshot needs refresh: run python3 tools/sync_gallery.py')
        for name, data in images.items():
            local = ROOT / 'assets/gallery' / name
            if not local.exists() or local.read_bytes() != data:
                raise SystemExit('Gallery preview needs refresh: ' + name)
    else:
        directory = ROOT / 'assets/gallery'
        directory.mkdir(parents=True, exist_ok=True)
        for name, data in images.items():
            (directory / name).write_bytes(data)
        for previous in directory.glob('library-*'):
            if re.fullmatch(r'library-[a-f0-9]{64}\.(jpg|png)', previous.name) and previous.name not in images:
                previous.unlink()
        target.write_text(output)
    print('Gallery: {} Places, {} Series; reviewed reader {}, public App {}'.format(
        len(value['places']), len(value['series']), profile['appVersion'], shipped))


if __name__ == '__main__':
    main()
