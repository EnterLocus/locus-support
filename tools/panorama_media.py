"""Authored panorama media v1, first supported by Locus 1.1.2.

Library capability registration is independent of reader availability. A Dev
catalog can preview these packages while older readers refuse installation.
"""
import math

CAPABILITY = 'locus.view.media.v1'
MINIMUM_APP = (1, 1, 2)


def validate_definition(value, require):
    require(isinstance(value, dict) and set(value) == {
        'version', 'sourcePanoramaSHA256', 'mask', 'sources', 'regions'}, 'invalid media fields')
    require(type(value['version']) is int and value['version'] == 1, 'unsupported media version')
    digest = value['sourcePanoramaSHA256']
    require(isinstance(digest, str) and len(digest) == 64 and all(c in '0123456789abcdef' for c in digest), 'invalid media panorama hash')
    require(isinstance(value['mask'], str) and bool(value['mask']), 'missing media mask')
    sources, regions = value['sources'], value['regions']
    require(isinstance(sources, list) and 1 <= len(sources) <= 4, 'media source limit')
    require(isinstance(regions, list) and 1 <= len(regions) <= 8, 'media region limit')
    ids, videos, paths, gain = set(), set(), [], 0
    def number(n): return type(n) in (float, int) and math.isfinite(n)
    def identifier(n): return isinstance(n, str) and 0 < len(n) <= 100 and all(c.isascii() and (c.isalnum() or c in '-_.') for c in n)
    for source in sources:
        require(isinstance(source, dict) and set(source) in ({'id','title','video','gain'}, {'id','title','audio','gain'}), 'invalid media source fields')
        require(identifier(source['id']) and source['id'] not in ids, 'duplicate/invalid media source id')
        ids.add(source['id'])
        require(isinstance(source['title'], str) and 0 < len(source['title']) <= 100, 'invalid media source title')
        require(number(source['gain']) and 0 <= source['gain'] <= 1, 'invalid media gain')
        gain += source['gain']
        kind = 'video' if 'video' in source else 'audio'
        if kind == 'video': videos.add(source['id'])
        require(isinstance(source[kind], str) and bool(source[kind]), 'invalid media asset')
        paths.append((kind, source[kind]))
    require(len(videos) <= 2 and gain <= 1, 'media video/gain budget')
    ids = set()
    for region in regions:
        require(isinstance(region, dict) and set(region) == {'id','source','bounds','mappingBounds','sourceRect'}, 'invalid media region fields')
        require(identifier(region['id']) and region['id'] not in ids, 'duplicate/invalid media region id')
        ids.add(region['id'])
        require(identifier(region['source']) and region['source'] in videos, 'media region requires a video source')
        for b in (region['bounds'], region['mappingBounds']):
            require(isinstance(b, list) and len(b) == 4 and all(number(n) for n in b), 'invalid media bounds')
            require(0 <= b[0] < 1 and b[0] < b[1] <= b[0]+1 and 0 <= b[2] < b[3] <= 1, 'invalid media bounds')
        b, m, r = region['bounds'], region['mappingBounds'], region['sourceRect']
        require(m[0] <= b[0] < b[1] <= m[1] and m[2] <= b[2] < b[3] <= m[3], 'media mapping must contain region')
        require(isinstance(r, list) and len(r) == 4 and all(number(n) for n in r), 'invalid source rectangle')
        require(r[0] >= 0 and r[1] >= 0 and r[2] > 0 and r[3] > 0 and r[0]+r[2] <= 1 and r[1]+r[3] <= 1, 'invalid source rectangle')
    def spans(b): return [(b[0], b[1])] if b[1] <= 1 else [(b[0], 1), (0, b[1]-1)]
    for i, region in enumerate(regions):
        a = region['bounds']
        for other in regions[i+1:]:
            b = other['bounds']
            overlap = max(a[2], b[2]) < min(a[3], b[3])-1e-10 and any(max(x[0],y[0]) < min(x[1],y[1])-1e-10 for x in spans(a) for y in spans(b))
            require(not overlap, 'overlapping media regions')
    return paths
