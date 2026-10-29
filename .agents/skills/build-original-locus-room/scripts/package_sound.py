"""Independent Package v2 View/Room background sounds, continuous effects
and Room music (docs/package-spec-v2.md "View and Room sounds")."""
import math

MINIMUM_APP = (1, 1, 4)
# A Room `role: "music"` source is readable from Locus 1.4.1 on, which also
# requires `locus.room.audio.music.v1` in Library declarations.
MUSIC_MINIMUM_APP = (1, 4, 1)
MUSIC_CAPABILITY = 'locus.room.audio.music.v1'
ROLES = ('background', 'effect', 'music')


def has_music(value):
    return isinstance(value, dict) and any(
        isinstance(s, dict) and s.get('role') == 'music' for s in value.get('sources') or [])


def minimum_app(value):
    return MUSIC_MINIMUM_APP if has_music(value) else MINIMUM_APP


def has_background_sound(value):
    """Discovery mark: Room music counts as background sound; effects never do."""
    return isinstance(value, dict) and any(
        isinstance(s, dict) and s.get('role') in ('background', 'music') for s in value.get('sources') or [])


def capabilities(value, owner):
    result = [f'locus.{owner}.audio.v1']
    if value['version'] == 2:
        result.append(f'locus.{owner}.audio.v2')
        if any(s['placement']['type'] != 'ambient' for s in value['sources']):
            result.append(f'locus.{owner}.audio.spatial.v1')
        if any(s['playback']['type'] == 'random' for s in value['sources']):
            result.append(f'locus.{owner}.audio.random.v1')
        if owner == 'room' and has_music(value):
            result.append(MUSIC_CAPABILITY)
    return result


def source_paths(source):
    return source.get('clips', [source.get('path')])


def validate_definition(value, require, owner=None):
    require(isinstance(value, dict) and set(value) == {'version', 'backgroundPriority', 'sources'}, 'invalid sound fields')
    require(type(value['version']) is int and value['version'] in (1, 2), 'unsupported sound version')
    require(type(value['backgroundPriority']) is int and 0 <= value['backgroundPriority'] <= 100, 'invalid background priority')
    require(isinstance(value['sources'], list) and 1 <= len(value['sources']) <= 8, 'sound source limit')
    ids, paths, gain, music = set(), [], 0, False
    for source in value['sources']:
        fields = {'id', 'title', 'path', 'role', 'gain'} if value['version'] == 1 else {'id', 'title', 'role', 'gain', 'clips', 'placement', 'playback'}
        require(isinstance(source, dict) and set(source) == fields, 'invalid sound source fields')
        sid = source['id']
        require(isinstance(sid, str) and 0 < len(sid) <= 100 and all(c.isascii() and (c.isalnum() or c in '-_.') for c in sid) and sid not in ids, 'invalid sound source id')
        ids.add(sid)
        require(isinstance(source['title'], str) and 0 < len(source['title']) <= 100, 'invalid sound title')
        require(source['role'] in ROLES, 'invalid sound role')
        if source['role'] == 'music':
            # One looping, unpositioned track per Room; Views have no music.
            require(owner != 'view', 'music is Room-only')
            require(value['version'] == 2, 'music requires sound version 2')
            require(isinstance(source.get('placement'), dict) and source['placement'].get('type') == 'ambient', 'music requires ambient placement')
            require(isinstance(source.get('playback'), dict) and source['playback'].get('type') == 'loop', 'music requires loop playback')
            require(not music, 'at most one music source')
            music = True
        g = source['gain']
        require(type(g) in (int, float) and math.isfinite(g) and 0 <= g <= 1, 'invalid sound gain')
        gain += g
        tracks = source_paths(source)
        require(isinstance(tracks, list) and 1 <= len(tracks) <= 8, 'invalid sound clips')
        for p in tracks:
            require(isinstance(p, str) and '\\' not in p and all(x not in ('', '.', '..') for x in p.split('/')) and p.rsplit('.', 1)[-1].lower() in ('m4a', 'mp3', 'wav'), 'invalid sound path')
            paths.append(p)
        require(len(set(tracks)) == len(tracks), 'duplicate sound clip')
        if value['version'] == 2:
            validate_v2(source, require, owner)
    require(gain <= 1, 'sound gain budget')
    return paths


def validate_v2(source, require, owner):
    def number(v, low, high):
        return type(v) in (float, int) and math.isfinite(v) and low <= v <= high
    def pair(v, low, high):
        return isinstance(v, list) and len(v) == 2 and all(number(x, low, high) for x in v) and v[0] <= v[1]
    p, play = source['placement'], source['playback']
    require(isinstance(p, dict) and p.get('type') in ('ambient', 'point', 'points', 'region'), 'invalid sound placement')
    kind = p['type']
    if kind == 'ambient':
        require(set(p) == {'type'}, 'ambient has no position')
    else:
        require(p.get('frame') in ('view', 'room') and (owner is None or p['frame'] == owner), 'invalid sound frame')
        require(number(p.get('rolloff', 1), 0, 4), 'invalid sound rolloff')
        required = {'type', 'frame'} | ({'point'} if kind == 'point' else {'points'} if kind == 'points' else {'azimuthCenterDegrees', 'azimuthSpanDegrees', 'elevationRangeDegrees', 'distanceRangeMeters'})
        require(required <= set(p) <= required | {'rolloff'}, 'invalid placement fields')
        if kind == 'region':
            require(p['frame'] == 'view', 'region requires view frame')
            require(number(p['azimuthCenterDegrees'], -180, 180) and number(p['azimuthSpanDegrees'], 0, 360), 'invalid sound azimuth')
            require(pair(p['elevationRangeDegrees'], -90, 90) and pair(p['distanceRangeMeters'], .1, 100), 'invalid sound region range')
        else:
            points = [p['point']] if kind == 'point' else p['points']
            require(isinstance(points, list) and (kind != 'points' or 2 <= len(points) <= 16), 'invalid sound point count')
            require(all(point != earlier for i, point in enumerate(points) for earlier in points[:i]), 'duplicate sound point')
            for point in points:
                require(isinstance(point, dict), 'invalid sound point')
                if p['frame'] == 'room':
                    require(set(point) == {'positionMeters'} and isinstance(point['positionMeters'], list) and len(point['positionMeters']) == 3 and all(number(x, -100, 100) for x in point['positionMeters']), 'invalid room sound position')
                else:
                    require(set(point) == {'azimuthDegrees', 'elevationDegrees', 'distanceMeters'}, 'invalid view sound position')
                    require(number(point['azimuthDegrees'], -180, 180) and number(point['elevationDegrees'], -90, 90) and number(point['distanceMeters'], .1, 100), 'invalid view sound coordinates')
    require(isinstance(play, dict) and play.get('type') in ('loop', 'random'), 'invalid sound playback')
    if play['type'] == 'loop':
        require({'type'} <= set(play) <= {'type', 'fadeInSeconds', 'fadeOutSeconds'} and len(source['clips']) == 1 and kind in ('ambient', 'point'), 'invalid looping source')
        require(all(number(play.get(k, 0), 0, 5) for k in ('fadeInSeconds', 'fadeOutSeconds')), 'invalid sound fade')
    else:
        require({'type', 'intervalSeconds', 'maxConcurrent'} <= set(play) <= {'type', 'intervalSeconds', 'maxConcurrent', 'avoidImmediateRepeat'}, 'invalid random playback fields')
        require(pair(play['intervalSeconds'], .25, 600) and type(play['maxConcurrent']) is int and play['maxConcurrent'] == 1, 'invalid random interval/concurrency')
        require(type(play.get('avoidImmediateRepeat', False)) is bool, 'invalid random repeat policy')
