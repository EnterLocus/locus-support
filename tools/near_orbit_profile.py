"""Portable near-orbit v1/v2 contracts and the content-bound fallback proof.

v1 (`locus.view.near-orbit.v1`) is the bounded-region profile and stays exactly
as shipped. v2 (`locus.view.near-orbit.v2`, docs/package-spec-v2.md) is an
independent profile: a configurable body radius, rigid-or-drifting clouds and
an optional equirectangular tile grid instead of the v1 region patch. A v2
profile with tiles may add per-tile `surface` data (terrain slopes and water
cover, `locus.view.near-orbit.surface.v1`) on the same grid.
"""
import hashlib
import json
import math
from pathlib import PurePosixPath

CAPABILITY = 'locus.view.near-orbit.v1'
MINIMUM_APP = (1, 3, 0)
MATERIAL_REVISION = 4
STAR_CATALOG_MAX_BYTES = 1024 * 1024
PROOF_MAX_BYTES = 16 * 1024
TOTAL_TEXTURE_BYTES = 384 * 1024 * 1024
REGIONAL_TEXTURE_BYTES = 9 * 1024 * 1024
EXPERIMENTAL_CAPABILITY = 'locus.view.near-orbit.experimental.v0'
READER_STATUS = 'development-only-floor-pending'
RANGES = dict(latitudeDegrees=(-90,90),longitudeDegrees=(-180,180),altitudeKilometers=(200,1000),
              bearingDegrees=(-360,360),pitchFromNadirDegrees=(0,180),sunLatitudeDegrees=(-90,90),
              sunLongitudeDegrees=(-180,180),rotationPeriodSeconds=(3600,86400),
              cloudHeightKilometers=(1,20),atmosphereHeightKilometers=(20,100))
CAPABILITY_V2 = 'locus.view.near-orbit.v2'
MINIMUM_APP_V2 = (1, 3, 0)
MATERIAL_REVISION_V2 = 5
# A v2 profile with `surface` (per-tile terrain slopes and water cover) is
# baked with the atmosphere / sun glint / cloud-detail material (#1411).
# Revision 6 belongs to the `oceanGlint` experiment (reader c1be1275) still
# published on Dev (Low Orbit Earth 2.0.4, Earth from Space 1.1.4): the
# publisher keeps validating those packages exactly as that reader did, so
# surface profiles start at 7 and a profile cannot carry both blocks.
MATERIAL_REVISION_V2_OCEAN_GLINT = 6
MINIMUM_APP_OCEAN_GLINT = (1, 3, 2)
MATERIAL_REVISION_V2_SURFACE = 7
CAPABILITY_SURFACE = 'locus.view.near-orbit.surface.v1'
MINIMUM_APP_SURFACE = (1, 3, 2)
SURFACE_ENCODING = 'slope-east-north-water-v1'
TEXTURE_BYTES_V2 = 512 * 1024 * 1024
RANGES_V2 = dict(RANGES, bodyRadiusKilometers=(1000, 100000), cloudDriftRatio=(0.5, 2))
ASSETS_V2 = ['dayTexture', 'nightTexture', 'cloudTexture', 'fallbackPanorama', 'skyMask', 'galaxyTexture']
# Order of the source digests in the v2 proof token (fallbackPanorama is bound
# by `fallbackSHA256` instead; the tile manifest hash follows when tiles exist).
TOKEN_ASSETS_V2 = ['dayTexture', 'nightTexture', 'cloudTexture', 'skyMask', 'galaxyTexture', 'starCatalog']
TILE_KEYS = {'manifest', 'columns', 'rows', 'latitudeSouthDegrees', 'tileSize'}
TILE_MANIFEST_KEYS = {'formatVersion', 'columns', 'rows', 'tileSize', 'latitudeSouthDegrees', 'tiles'}
TILE_ENTRY_KEYS = {'row', 'column', 'path', 'sha256', 'byteCount'}
SURFACE_KEYS = {'manifest', 'tileSize'}
SURFACE_MANIFEST_KEYS = TILE_MANIFEST_KEYS | {'encoding'}
TILE_SIZE_RANGE = (16, 4096)
MAX_TILES = 1024
ASSETS = ['dayTexture','nightTexture','cloudTexture','regionTexture','regionMask','fallbackPanorama','skyMask','galaxyTexture']


def _safe_path(path, suffixes):
    return (isinstance(path, str) and bool(path) and len(path) <= 512 and '\\' not in path
            and not any(ord(c) < 32 for c in path) and not PurePosixPath(path).is_absolute()
            and not any(part in ('', '.', '..') for part in path.split('/'))
            and path.lower().endswith(suffixes))


def _is_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def tile_step(columns):
    """Tile edge in degrees: `360 / columns`, which must tile the circle exactly."""
    step = 360 / columns
    if step * columns != 360:
        raise ValueError('invalid tiles.columns')
    return step


def validate_tiles(tiles):
    if not isinstance(tiles, dict) or set(tiles) != TILE_KEYS:
        raise ValueError('invalid tiles fields')
    if not _safe_path(tiles['manifest'], ('.json',)):
        raise ValueError('invalid asset path tiles.manifest')
    columns, rows, size = tiles['columns'], tiles['rows'], tiles['tileSize']
    if type(columns) is not int or not 1 <= columns <= 360:
        raise ValueError('invalid tiles.columns')
    step = tile_step(columns)
    if type(rows) is not int or not 1 <= rows <= 180 or rows * columns > MAX_TILES:
        raise ValueError('invalid tiles.rows')
    if type(size) is not int or not TILE_SIZE_RANGE[0] <= size <= TILE_SIZE_RANGE[1]:
        raise ValueError('invalid tiles.tileSize')
    south = tiles['latitudeSouthDegrees']
    if not _is_number(south) or not -90 <= south < 90:
        raise ValueError('invalid tiles.latitudeSouthDegrees')
    if south + rows * step > 90:
        raise ValueError('tile rows exceed the north pole')
    return tiles


def validate_surface(surface, tiles):
    """The optional v2 `surface` block: `{manifest, tileSize}` on the `tiles` grid."""
    if not isinstance(surface, dict) or set(surface) != SURFACE_KEYS:
        raise ValueError('invalid surface fields')
    if not _safe_path(surface['manifest'], ('.json',)) or surface['manifest'] == tiles['manifest']:
        raise ValueError('invalid asset path surface.manifest')
    size = surface['tileSize']
    if type(size) is not int or not TILE_SIZE_RANGE[0] <= size <= TILE_SIZE_RANGE[1]:
        raise ValueError('invalid surface.tileSize')
    return surface


def validate_v2(profile):
    keys = set(RANGES_V2) | set(ASSETS_V2) | {'version', 'starCatalog'}
    if not isinstance(profile, dict) or not keys <= set(profile) <= keys | {'tiles', 'surface', 'oceanGlint'}:
        raise ValueError('invalid near-orbit fields')
    if 'surface' in profile and 'oceanGlint' in profile:
        # Different materials (revision 7 vs the Dev-only revision 6).
        raise ValueError('surface cannot coexist with oceanGlint')
    for key, (low, high) in RANGES_V2.items():
        n = profile[key]
        if type(n) not in (int, float) or not math.isfinite(n) or not low <= n <= high:
            raise ValueError('invalid ' + key)
    for key in ASSETS_V2:
        if not _safe_path(profile[key], ('.jpg', '.png')):
            raise ValueError('invalid asset path ' + key)
    if not _safe_path(profile['starCatalog'], ('.json',)):
        raise ValueError('invalid asset path starCatalog')
    if 'oceanGlint' in profile:
        from ocean_glint import validate as validate_glint
        validate_glint(profile['oceanGlint'])
    if 'tiles' in profile:
        validate_tiles(profile['tiles'])
    if 'surface' in profile:
        if 'tiles' not in profile:
            raise ValueError('surface requires tiles')
        validate_surface(profile['surface'], profile['tiles'])
    return profile


def has_surface(profile):
    return isinstance(profile, dict) and profile.get('version') == 2 and 'surface' in profile


def material_revision(profile):
    """Native material revision a fallback proof must carry: 4 for v1, 5
    for v2, 6 for v2 with `oceanGlint`, 7 for v2 with `surface`."""
    if profile.get('version') != 2:
        return MATERIAL_REVISION
    if 'surface' in profile:
        return MATERIAL_REVISION_V2_SURFACE
    return MATERIAL_REVISION_V2_OCEAN_GLINT if 'oceanGlint' in profile else MATERIAL_REVISION_V2


def capabilities(profile):
    """Catalog capabilities a formal profile requires. `oceanGlint` adds
    `locus.view.ocean-glint.v1`, which the publisher derives for nearOrbit and
    celestial alike."""
    if profile.get('version') != 2:
        return [CAPABILITY]
    return [CAPABILITY_V2] + ([CAPABILITY_SURFACE] if 'surface' in profile else [])


def minimum_app(profile):
    if profile.get('version') != 2:
        return MINIMUM_APP
    if 'surface' in profile:
        return MINIMUM_APP_SURFACE
    return MINIMUM_APP_OCEAN_GLINT if 'oceanGlint' in profile else MINIMUM_APP_V2


def validate(profile):
    """Validate a formal profile: version 1 (unchanged) or version 2."""
    version = profile.get('version') if isinstance(profile, dict) else None
    if type(version) is int and version == 2:
        return validate_v2(profile)
    return validate_v1(profile)


def validate_v1(profile):
    if not isinstance(profile,dict) or set(profile) != set(RANGES)|set(ASSETS)|{'version','regionBounds','starCatalog'}:
        raise ValueError('invalid near-orbit fields')
    if type(profile['version']) is not int or profile['version'] != 1:
        raise ValueError('unsupported near-orbit version')
    for key,(low,high) in RANGES.items():
        n=profile[key]
        if type(n) not in (int,float) or not math.isfinite(n) or not low<=n<=high:
            raise ValueError('invalid '+key)
    for key in ASSETS:
        path=profile[key]
        if (not isinstance(path,str) or not path or len(path)>512 or '\\' in path
                or any(ord(c)<32 for c in path) or PurePosixPath(path).is_absolute()
                or any(part in ('', '.', '..') for part in path.split('/'))
                or not path.lower().endswith(('.jpg','.png'))):
            raise ValueError('invalid asset path '+key)
    path = profile['starCatalog']
    if (not isinstance(path,str) or not path or len(path)>512 or '\\' in path
            or any(ord(c)<32 for c in path) or PurePosixPath(path).is_absolute()
            or any(part in ('', '.', '..') for part in path.split('/'))
            or not path.lower().endswith('.json')):
        raise ValueError('invalid asset path starCatalog')
    bounds=profile['regionBounds']
    if not isinstance(bounds,list) or len(bounds)!=4 or any(type(n) not in (int,float) or not math.isfinite(n) for n in bounds):
        raise ValueError('invalid region bounds')
    west,south,east,north=bounds
    if not -180<=west<east<=180 or not -90<=south<north<=90 or east-west>10 or north-south>10:
        raise ValueError('invalid bounded region extent')
    return profile


def validate_experimental(profile):
    """Research-only adapter; public package validation never calls this."""
    if (not isinstance(profile, dict) or profile.get('capability') != EXPERIMENTAL_CAPABILITY
            or profile.get('readerStatus') != READER_STATUS):
        raise ValueError('development-only profile required')
    portable = {key: value for key, value in profile.items() if key not in ('capability', 'readerStatus')}
    validate(dict(portable, version=1, starCatalog='experimental-unused.json'))
    if 'version' in portable or 'starCatalog' in portable:
        raise ValueError('invalid experimental fields')
    return profile


def proof_path(profile):
    return str(PurePosixPath(profile['fallbackPanorama']).with_suffix('.proof.json'))


def canonical_profile_bytes(profile):
    """Match the typed Swift JSONEncoder's sorted, compact UTF-8 output.

    Profile numbers are bounded doubles: whole doubles lose the trailing .0,
    and negative zero retains its sign. Other doubles use shortest round-trip
    formatting, including the zero-padded exponent shared by Swift/Python.
    """
    def encode(value):
        if isinstance(value, dict):
            return '{' + ','.join(encode(key) + ':' + encode(value[key]) for key in sorted(value)) + '}'
        if isinstance(value, list):
            return '[' + ','.join(encode(item) for item in value) + ']'
        if type(value) is float:
            if value == 0:
                return '-0' if math.copysign(1, value) < 0 else '0'
            return str(int(value)) if value.is_integer() else repr(value)
        return json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    return encode(profile).encode('utf-8')


def profile_token(profile, read_asset):
    validate(profile)
    digest = hashlib.sha256(canonical_profile_bytes(profile))
    if profile['version'] == 2:
        digest.update(b'near-orbit-material-%d' % material_revision(profile))
        paths = [profile[field] for field in TOKEN_ASSETS_V2]
        if 'tiles' in profile:
            paths.append(profile['tiles']['manifest'])
        if 'surface' in profile:
            paths.append(profile['surface']['manifest'])
        if 'oceanGlint' in profile:
            paths.append(profile['oceanGlint']['mask'])
        for path in paths:
            digest.update(hashlib.sha256(read_asset(path)).hexdigest().encode('ascii'))
        return digest.hexdigest()
    digest.update(b'near-orbit-material-4')
    for field in ASSETS:
        if field != 'fallbackPanorama':
            digest.update(hashlib.sha256(read_asset(profile[field])).hexdigest().encode('ascii'))
    digest.update(hashlib.sha256(read_asset(profile['starCatalog'])).hexdigest().encode('ascii'))
    return digest.hexdigest()


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key in tile manifest')
        result[key] = value
    return result


def tile_bounds_v2(profile, row, column):
    """`(west, south, east, north)` in degrees of one v2 tile.

    Column `c` covers longitude `-180 + c*D ... -180 + (c+1)*D`; row `r`
    covers latitude `south + (rows-1-r)*D ... south + (rows-r)*D` with
    `D = 360 / columns`, so row 0 is the northernmost row.
    """
    tiles = validate(profile)['tiles']
    columns, rows = tiles['columns'], tiles['rows']
    if type(row) is not int or type(column) is not int or not (0 <= row < rows and 0 <= column < columns):
        raise ValueError('tile outside grid')
    step = tile_step(columns)
    south = tiles['latitudeSouthDegrees']
    return (-180 + column * step, south + (rows - 1 - row) * step,
            -180 + (column + 1) * step, south + (rows - row) * step)


def tile_for(profile, latitude, longitude):
    """`(row, column)` of the tile containing a point, or None outside the band.

    Longitude wraps; the north edge belongs to row 0 and +180 to the last
    column. Interior edges belong to the tile to the east / north of them.
    """
    tiles = validate(profile)['tiles']
    columns, rows = tiles['columns'], tiles['rows']
    if not _is_number(latitude) or not _is_number(longitude):
        raise ValueError('invalid coordinate')
    step = tile_step(columns)
    south = tiles['latitudeSouthDegrees']
    north = south + rows * step
    if not south <= latitude <= north:
        return None
    wrapped = (longitude + 180) % 360
    if longitude == 180:
        wrapped = 359.999999999
    column = min(columns - 1, int(wrapped // step))
    row = min(rows - 1, max(0, int((north - latitude) // step)))
    return row, column


def _load_manifest(manifest_bytes, kind):
    try:
        return json.loads(manifest_bytes.decode('utf-8'), object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('invalid %s manifest JSON' % kind) from error


def _validate_grid_manifest(manifest, tiles, tile_size, kind, suffixes, reserved_paths, read_asset):
    """Shared tile/surface manifest rules on the profile's `tiles` grid."""
    for key in ('columns', 'rows'):
        if type(manifest[key]) is not int or manifest[key] != tiles[key]:
            raise ValueError('%s manifest %s does not match the profile' % (kind, key))
    if type(manifest['tileSize']) is not int or manifest['tileSize'] != tile_size:
        raise ValueError('%s manifest tileSize does not match the profile' % kind)
    south = manifest['latitudeSouthDegrees']
    if not _is_number(south) or south != tiles['latitudeSouthDegrees']:
        raise ValueError('%s manifest latitudeSouthDegrees does not match the profile' % kind)
    entries = manifest['tiles']
    columns, rows = tiles['columns'], tiles['rows']
    if not isinstance(entries, list):
        raise ValueError('invalid %s manifest tiles' % kind)
    seen, paths, order = set(), set(), []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != TILE_ENTRY_KEYS:
            raise ValueError('invalid %s entry fields' % kind)
        row, column = entry['row'], entry['column']
        if type(row) is not int or type(column) is not int or not (0 <= row < rows and 0 <= column < columns):
            raise ValueError('%s entry outside the grid' % kind)
        if (row, column) in seen:
            raise ValueError('duplicate %s r%dc%d' % (kind, row, column))
        seen.add((row, column))
        order.append((row, column))
        path = entry['path']
        if not _safe_path(path, suffixes):
            raise ValueError('invalid %s path r%dc%d' % (kind, row, column))
        if path in paths or path in reserved_paths:
            raise ValueError('duplicate %s path %s' % (kind, path))
        paths.add(path)
        digest = entry['sha256']
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('invalid %s sha256 r%dc%d' % (kind, row, column))
        if type(entry['byteCount']) is not int or entry['byteCount'] <= 0:
            raise ValueError('invalid %s byteCount r%dc%d' % (kind, row, column))
    if len(seen) != rows * columns:
        missing = sorted(set((r, c) for r in range(rows) for c in range(columns)) - seen)
        raise ValueError('missing %s r%dc%d' % ((kind,) + missing[0]))
    if order != sorted(order):
        raise ValueError('%s manifest entries must be sorted by row then column' % kind)
    for entry in entries:
        data = read_asset(entry['path'])
        if len(data) != entry['byteCount']:
            raise ValueError('%s byteCount mismatch %s' % (kind, entry['path']))
        if hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('%s sha256 mismatch %s' % (kind, entry['path']))
    return manifest


def validate_tile_manifest(profile, manifest_bytes, read_asset):
    """Check the packaged tile manifest against the profile and tile bytes.

    Shape, exact coverage of `rows x columns` (each pair once, sorted by row
    then column), agreement with the profile's `tiles` block, and every
    tile's `byteCount`/`sha256` against the bytes `read_asset(path)` returns.
    Returns the parsed manifest. Image dimensions and the sidecar entries are
    archive-context checks left to `validate_locusplace.py`.
    """
    validate(profile)
    tiles = profile.get('tiles')
    if profile['version'] != 2 or tiles is None:
        raise ValueError('profile declares no tiles')
    manifest = _load_manifest(manifest_bytes, 'tile')
    if not isinstance(manifest, dict) or set(manifest) != TILE_MANIFEST_KEYS:
        raise ValueError('invalid tile manifest fields')
    if type(manifest['formatVersion']) is not int or manifest['formatVersion'] != 1:
        raise ValueError('unsupported tile manifest formatVersion')
    reserved = {tiles['manifest']} | ({profile['surface']['manifest']} if 'surface' in profile else set())
    return _validate_grid_manifest(manifest, tiles, tiles['tileSize'], 'tile', ('.jpg', '.png'),
                                   reserved, read_asset)


def validate_surface_manifest(profile, manifest_bytes, read_asset, day_tile_paths):
    """Check the packaged surface manifest (`surface.manifest`).

    The same grid rules as the tile manifest, against `surface.tileSize`,
    plus `encoding`; surface tiles are lossless `.png` only and their paths
    are distinct from both manifests and from every day tile path
    (`day_tile_paths`, from the validated tile manifest). Pixel format and
    dimensions are archive-context checks left to `validate_locusplace.py`.
    """
    validate(profile)
    surface = profile.get('surface')
    if profile['version'] != 2 or surface is None:
        raise ValueError('profile declares no surface')
    tiles = profile['tiles']
    manifest = _load_manifest(manifest_bytes, 'surface')
    if not isinstance(manifest, dict) or set(manifest) != SURFACE_MANIFEST_KEYS:
        raise ValueError('invalid surface manifest fields')
    if type(manifest['formatVersion']) is not int or manifest['formatVersion'] != 1:
        raise ValueError('unsupported surface manifest formatVersion')
    if manifest['encoding'] != SURFACE_ENCODING:
        raise ValueError('unsupported surface manifest encoding')
    reserved = {tiles['manifest'], surface['manifest']} | set(day_tile_paths)
    return _validate_grid_manifest(manifest, tiles, surface['tileSize'], 'surface', ('.png',),
                                   reserved, read_asset)


def validate_star_catalog(value, require):
    from procedural_sky import validate_star_catalog as validate_catalog
    validate_catalog(value, require, real_sky_present=False)
    require(value['frame'] == 'horizontal', 'nearOrbit star catalog must use horizontal View directions')


def mip_bytes(width, height, channels):
    total = width * height * channels
    while width > 1 or height > 1:
        width, height = max(1, width//2), max(1, height//2)
        total += width * height * channels
    return total


def validate_texture_budget(images, require):
    """Match NearOrbitLOD admission, including its fixed 256/512/1024 pool."""
    pool = mip_bytes(256, 256, 4) + mip_bytes(512, 512, 4)
    total, regional = pool, pool
    for field in ASSETS:
        width, height, opaque_gray = images[field]
        channels = 1 if field in ('cloudTexture', 'regionMask') and opaque_gray else 4
        size = mip_bytes(width, height, channels)
        total += size
        if field in ('regionTexture', 'regionMask'):
            regional += size
    require(total <= TOTAL_TEXTURE_BYTES and regional <= REGIONAL_TEXTURE_BYTES,
            'nearOrbit textures exceed 384 MiB total or 9 MiB regional budget')
    return total, regional


def validate_texture_budget_v2(images, sidecar_bytes, require):
    """v2 admission: the globals (day, night, cloud, fallback, sky mask, galaxy).

    `images` maps each field to `(width, height, opaque_gray)`. A global with a
    `gpuTextures` sidecar is resident as that ASTC payload (`sidecar_bytes`
    maps field to KTX byte count); the others count as full RGBA8 mip chains
    (one channel for an opaque-grayscale cloud map). There is no regional
    budget: tiles are streamed and bounded by the renderer's hysteresis
    (expected at most ~20 resident), not by admission.
    """
    total = 0
    for field in list(ASSETS_V2) + (["oceanGlint.mask"] if "oceanGlint.mask" in images else []):
        width, height, opaque_gray = images[field]
        if field in sidecar_bytes:
            total += sidecar_bytes[field]
        else:
            total += mip_bytes(width, height, 1 if field in ('cloudTexture', 'oceanGlint.mask') and opaque_gray else 4)
    require(total <= TEXTURE_BYTES_V2, 'nearOrbit global textures exceed 512 MiB')
    return total


def validate_proof(profile, proof, read_asset):
    revision = material_revision(profile)
    if not isinstance(proof, dict) or type(proof.get('materialRevision')) is not int or proof['materialRevision'] != revision:
        raise ValueError('near-orbit fallback requires materialRevision %d proof' % revision)
    if proof.get('profileToken') != profile_token(profile, read_asset):
        raise ValueError('near-orbit fallback profileToken mismatch')
    if proof.get('fallbackSHA256') != hashlib.sha256(read_asset(profile['fallbackPanorama'])).hexdigest():
        raise ValueError('near-orbit fallback SHA-256 mismatch')
    return proof
