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
import sys
from urllib.request import Request, urlopen
import zipfile

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import external_assets

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'https://content.enterlocus.net/'
APP_LOOKUP = 'https://itunes.apple.com/lookup?id=6802168265&country=us'
MAX_ARCHIVE = 64 * 1024 * 1024
MAX_GALLERY_PHOTOS = 8
MAX_GALLERY_PHOTO_BYTES = 8 * 1024 * 1024
MAX_GALLERY_PHOTO_DIMENSION = 8192
MAX_GALLERY_PHOTO_PIXELS = 32 * 1024 * 1024
PHOTO_LABELS = {'front', 'left', 'right', 'alternate-seat'}
GALLERY_BASE = 'https://media.enterlocus.net/gallery/'
PHOTO_URL = re.compile(re.escape(GALLERY_BASE) + r'rendered-([a-f0-9]{64})\.(jpg|png)')
PREVIEW_RELEASES_FORMAT = 1


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


def validate_photo_registry(registry, asset_source=None, manifest=None):
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
                raise ValueError('Gallery photo URL must be its immutable SHA-256 path')
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
            filename = 'rendered-' + sha256 + '.' + match.group(2)
            try:
                if callable(asset_source):
                    data = asset_source(filename)
                elif asset_source is not None and (Path(asset_source) / filename).is_file():
                    data = (Path(asset_source) / filename).read_bytes()
                else:
                    assets = external_assets.load_manifest() if manifest is None else manifest
                    asset = external_assets.asset_for('assets/gallery/' + filename, assets)
                    if asset['url'] != GALLERY_BASE + filename:
                        raise ValueError('Gallery asset URL does not match its immutable path')
                    data = external_assets.hydrate(asset['path'], manifest=assets).read_bytes()
            except (OSError, ValueError) as exc:
                raise ValueError('Gallery photo asset is missing or invalid') from exc
            if len(data) > MAX_GALLERY_PHOTO_BYTES:
                raise ValueError('Gallery photo asset is missing or exceeds the size limit')
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


def validate_release_previews(release_previews):
    """Return exact owner-reviewed future revisions eligible for Gallery cards."""
    if not isinstance(release_previews, dict) or set(release_previews) != {'formatVersion', 'previews'}:
        raise ValueError('Invalid gallery preview release allowlist')
    if (release_previews['formatVersion'] != PREVIEW_RELEASES_FORMAT
            or not isinstance(release_previews['previews'], list)):
        raise ValueError('Unsupported gallery preview release allowlist')
    approved = {}
    for item in release_previews['previews']:
        if not isinstance(item, dict) or set(item) != {'id', 'contentVersion', 'appVersion'}:
            raise ValueError('Invalid gallery preview release')
        package_id = item['id']
        if not isinstance(package_id, str) or not re.fullmatch(r'space\.[a-z0-9-]+', package_id):
            raise ValueError('Invalid gallery preview release ID')
        version(item['contentVersion'])
        version(item['appVersion'])
        if package_id in approved:
            raise ValueError('Ambiguous gallery preview release')
        approved[package_id] = {'contentVersion': item['contentVersion'], 'appVersion': item['appVersion']}
    return approved


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


def select_release_previews(catalog, profile, release_previews):
    """Select exact future Room previews after validating their public contract."""
    approved = validate_release_previews(release_previews)
    selected = []
    for package_id, configured in approved.items():
        matches = [entry for entry in catalog['entries']
                   if (entry.get('packageID') == package_id
                       and entry.get('contentVersion') == configured['contentVersion'])]
        if len(matches) != 1:
            raise ValueError('Missing or ambiguous gallery preview release revision')
        entry = matches[0]
        preview = entry.get('preview')
        install = entry.get('install')
        if not isinstance(preview, dict) or not isinstance(install, dict):
            raise ValueError('Invalid gallery preview release metadata')
        try:
            preview_compatible = (
                entry['type'] == 'locus.room'
                and preview['contract'] == 'locus.preview.card.v1'
                and preview['visibility'] in ('generic', 'known-type')
                and compatible(preview['requires'], profile))
            install_valid = (install['access']['kind'], install['delivery']['kind']) in (
                ('free', 'public-https.v1'), ('supporter', 'grant.v2'))
            envelope_valid = install['artifact']['envelope'] == {'format': 'locusplace', 'version': 1}
            exact_release = install['requires']['minimumAppVersion'] == configured['appVersion']
        except (KeyError, TypeError, ValueError):
            raise ValueError('Invalid gallery preview release metadata')
        if not preview_compatible or not install_valid or not envelope_valid or not exact_release:
            raise ValueError('Gallery preview release is not compatible with its allowlist')
        selected.append((entry, configured['appVersion']))
    return selected


def image(ref, archive, images, prefix='thumbnails/'):
    path = safe_path(ref['path'], prefix)
    if (ref.get('mediaType') not in ('image/jpeg', 'image/png')
            or not 0 < ref['byteCount'] <= 2 * 1024 * 1024
            or archive.getinfo(path).file_size != ref['byteCount']):
        raise ValueError('Invalid public preview size or media type')
    suffix = '.png' if ref.get('mediaType') == 'image/png' else '.jpg'
    filename = 'library-' + ref['sha256'] + suffix
    images[filename] = checked(archive.read(path), ref)
    return {'url': GALLERY_BASE + filename, 'width': ref['width'], 'height': ref['height'],
            'sha256': ref['sha256']}


def stage_missing_images(images, manifest, asset_output, root=ROOT):
    """Stage unknown immutable thumbnails and a candidate manifest outside Git.

    This deliberately has no access to gallery.json: publishing metadata is a
    second operation after upload and HTTPS readback of the candidate manifest.
    """
    directory = Path(asset_output).resolve()
    scratch = (Path(root) / '.scratch').resolve()
    if directory != scratch and scratch not in directory.parents:
        raise ValueError('--asset-output must be inside the ignored .scratch directory')
    missing = []
    for name, data in images.items():
        path = 'assets/gallery/' + name
        if path in manifest:
            continue
        missing.append((path, name, data))
    if not missing:
        return None
    directory.mkdir(parents=True, exist_ok=True)
    candidate = list(manifest.values())
    for path, name, data in missing:
        destination = directory / name
        if destination.exists() and destination.read_bytes() != data:
            raise ValueError('Refusing to overwrite different immutable gallery bytes: ' + str(destination))
        destination.write_bytes(data)
        candidate.append({'path': path, 'url': GALLERY_BASE + name,
                          'byteCount': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    candidate_path = directory / 'external-assets.json'
    candidate_path.write_text(json.dumps({'formatVersion': 1, 'assets': candidate}, indent=2) + '\n')
    return candidate_path


def recent_date(place):
    dates = []
    for field in ('addedAt', 'updatedAt'):
        if place.get(field):
            value = datetime.fromisoformat(place[field].replace('Z', '+00:00'))
            if value.tzinfo is None:
                raise ValueError('Gallery dates must include a timezone')
            dates.append(value)
    return max(dates, default=datetime.min.replace(tzinfo=timezone.utc))


def export(catalog, descriptor, archive, profile, images, photo_registry=None, release_previews=None):
    if (catalog['environment'] != 'production' or catalog['catalogProtocol'] != 3
            or any(catalog[k] != descriptor[k] for k in ('environment', 'snapshotID', 'publishedAt', 'expiresAt'))):
        raise ValueError('Production descriptor/catalog identity mismatch')
    places = copy.deepcopy(profile['builtIns'])
    animated = set(profile['animatedViewCapabilities'])
    normal_entries = select_entries(catalog, profile)
    selected = [(entry, None) for entry in normal_entries]
    if release_previews is not None:
        normal_ids = {entry['packageID'] for entry in normal_entries}
        selected.extend((entry, app_version) for entry, app_version in
                        select_release_previews(catalog, profile, release_previews)
                        if entry['packageID'] not in normal_ids)
    for entry, preview_release in selected:
        preview = entry['preview']
        pid = entry['packageID']
        if not re.fullmatch(r'(?:destination|space)\.[a-z0-9-]+', pid):
            raise ValueError('Unexpected Place ID')
        locales = {tag: {'title': value.get('title', preview['title']),
                         'description': value.get('caption', preview.get('caption', '')),
                         'searchTerms': value.get('searchTerms', entry.get('searchTerms', []))}
                   for tag, value in preview.get('localizations', {}).items()}
        place = {'id': pid, 'slug': pid.split('.', 1)[1],
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
                       'searchTerms': entry.get('searchTerms', []), 'localizations': locales}
        if preview_release is not None:
            place['previewRelease'] = preview_release
        places.append(place)
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
    parser.add_argument('--asset-output', type=Path,
                        help='Ignored directory for new immutable catalog thumbnails; never use assets/gallery')
    args = parser.parse_args()
    profile = json.loads((ROOT / 'data/gallery-reader.json').read_text())
    release_previews = json.loads((ROOT / 'data/gallery-preview-releases.json').read_text())
    manifest = external_assets.load_manifest()

    def remote_gallery_asset(filename):
        path = 'assets/gallery/' + filename
        asset = external_assets.asset_for(path, manifest)
        if asset['url'] != GALLERY_BASE + filename:
            raise ValueError('Gallery asset URL does not match its immutable path')
        return external_assets.download(asset)

    photo_registry = validate_photo_registry(
        json.loads((ROOT / 'data/gallery-photos.json').read_text()), remote_gallery_asset)
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
        value = export(json.loads(archive.read(info)), descriptor, archive, profile, images, photo_registry,
                       release_previews)
    output = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    target = ROOT / 'data/gallery.json'
    unpublished = [name for name in images if 'assets/gallery/' + name not in manifest]
    for name, data in images.items():
        path = 'assets/gallery/' + name
        if path in manifest:
            if remote_gallery_asset(name) != data:
                raise SystemExit('Gallery preview HTTPS bytes differ from the verified catalog: ' + name)
    if unpublished:
        if args.asset_output is None:
            raise SystemExit('New gallery preview requires --asset-output before metadata can be published: '
                             + ', '.join(unpublished))
        candidate = stage_missing_images(images, manifest, args.asset_output)
        print('Gallery assets staged at {}. Upload them, run "python3 tools/external_assets.py '
              '--manifest {} --verify", install that verified manifest, then rerun sync_gallery.'
              .format(Path(args.asset_output).resolve(), candidate))
        return
    if args.check:
        if not target.exists() or target.read_text() != output:
            raise SystemExit('Gallery snapshot needs refresh: run python3 tools/sync_gallery.py')
    else:
        target.write_text(output)
    print('Gallery: {} Places, {} Series; reviewed reader {}, public App {}'.format(
        len(value['places']), len(value['series']), profile['appVersion'], shipped))


if __name__ == '__main__':
    main()
