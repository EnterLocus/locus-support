#!/usr/bin/env python3
"""Verify and hydrate externally stored public assets.

The tracked manifest is the source of truth for every binary deliberately kept
out of Git.  Hydrated copies always live in an ignored cache; this tool never
recreates an asset at its historical repository path.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tempfile
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / 'data' / 'external-assets.json'
DEFAULT_CACHE = ROOT / '.scratch' / 'external-assets'
REQUIRED_FIELDS = {'path', 'url', 'byteCount', 'sha256'}


def _safe_path(value):
    if not isinstance(value, str):
        raise ValueError('Invalid external asset path')
    path = PurePosixPath(value)
    if (path.is_absolute() or '..' in path.parts
            or '\\' in value or not value or value.endswith('/')):
        raise ValueError('Invalid external asset path')
    return value


def load_manifest(path=MANIFEST_PATH):
    """Load and validate the deliberately small external-asset registry."""
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(value, dict) or set(value) != {'formatVersion', 'assets'}:
        raise ValueError('Invalid external asset manifest')
    if value['formatVersion'] != 1 or not isinstance(value['assets'], list):
        raise ValueError('Unsupported external asset manifest')
    paths = set()
    urls = set()
    result = {}
    for asset in value['assets']:
        if not isinstance(asset, dict) or set(asset) != REQUIRED_FIELDS:
            raise ValueError('Invalid external asset record')
        asset = dict(asset)
        asset['path'] = _safe_path(asset['path'])
        if (not isinstance(asset['url'], str) or not asset['url'].startswith('https://')
                or '?' in asset['url'] or '#' in asset['url']):
            raise ValueError('Invalid external asset URL')
        if (not isinstance(asset['byteCount'], int) or isinstance(asset['byteCount'], bool)
                or asset['byteCount'] <= 0):
            raise ValueError('Invalid external asset byte count')
        if not isinstance(asset['sha256'], str) or len(asset['sha256']) != 64:
            raise ValueError('Invalid external asset SHA-256')
        try:
            int(asset['sha256'], 16)
        except ValueError as exc:
            raise ValueError('Invalid external asset SHA-256') from exc
        if asset['path'] in paths or asset['url'] in urls:
            raise ValueError('Duplicate external asset path or URL')
        paths.add(asset['path'])
        urls.add(asset['url'])
        result[asset['path']] = asset
    return result


def validate_bytes(data, asset):
    """Fail closed if downloaded bytes differ from the committed record."""
    if len(data) != asset['byteCount']:
        raise ValueError('External asset byte count mismatch: ' + asset['path'])
    if hashlib.sha256(data).hexdigest() != asset['sha256']:
        raise ValueError('External asset SHA-256 mismatch: ' + asset['path'])
    return data


def download(asset):
    request = Request(asset['url'], headers={'User-Agent': 'Mozilla/5.0 LocusSiteAssets/1',
                                             'Cache-Control': 'no-cache'})
    with urlopen(request, timeout=60) as response:
        data = response.read(asset['byteCount'] + 1)
    if len(data) > asset['byteCount']:
        raise ValueError('External asset exceeds declared byte count: ' + asset['path'])
    return validate_bytes(data, asset)


def asset_for(path, manifest=None):
    manifest = load_manifest() if manifest is None else manifest
    try:
        return manifest[path]
    except KeyError as exc:
        raise ValueError('External asset is not declared: ' + path) from exc


def hydrate(path, cache_dir=DEFAULT_CACHE, manifest=None, downloader=download, use_cache=True):
    """Return a verified cache copy for one manifest path.

    ``downloader`` makes the integrity boundary independently testable without
    replacing the production HTTP implementation.
    """
    asset = asset_for(path, manifest)
    cache_dir = Path(cache_dir)
    filename = asset['sha256'] + '-' + Path(asset['path']).name
    target = cache_dir / filename
    if use_cache and target.is_file():
        try:
            validate_bytes(target.read_bytes(), asset)
            return target
        except ValueError:
            target.unlink()
    cache_dir.mkdir(parents=True, exist_ok=True)
    data = downloader(asset)
    validate_bytes(data, asset)
    with tempfile.NamedTemporaryFile(dir=cache_dir, prefix='.download-', delete=False) as stream:
        stream.write(data)
        temporary = Path(stream.name)
    try:
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=MANIFEST_PATH)
    parser.add_argument('--cache-dir', type=Path, default=DEFAULT_CACHE)
    parser.add_argument('--hydrate', action='append', metavar='PATH',
                        help='Hydrate only this declared asset; may be repeated')
    parser.add_argument('--verify', action='store_true', help='Download and verify every declared asset')
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    paths = args.hydrate or (list(manifest) if args.verify else [])
    if not paths:
        parser.error('choose --verify or at least one --hydrate PATH')
    for path in paths:
        target = hydrate(path, args.cache_dir, manifest, use_cache=not args.verify)
        print('{} -> {}'.format(path, target))


if __name__ == '__main__':
    main()
