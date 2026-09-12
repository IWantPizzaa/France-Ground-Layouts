"""Native GNG region bridges and KML topology equivalence."""

import collections
import copy
import hashlib
import json


def match_native_records(code, published, authoring):
    """Match ordinary GNG primitives to KML topology without GNG ID comments.

    Consume matching polygon components and line segments separately: native
    GNG has neither multipart objects nor identifiers. Unmatched GNG data stays
    live and receives a deterministic ID; unmatched KML never restores deleted
    GNG geometry.
    """
    def key(value):
        return json.dumps(value, separators=(',', ':'))

    polygons, labels, segments = collections.defaultdict(list), collections.defaultdict(list), collections.defaultdict(list)
    for item in published:
        geom = item['geometry']
        if item['kind'] == 'label':
            labels[key(geom['coordinates'])].append(item)
        elif item['kind'] == 'polygon':
            polygons[(item['color'], key(geom['coordinates'][0]))].append(item)
        else:
            lines = geom['coordinates'] if geom['type'] == 'MultiLineString' else [geom['coordinates']]
            for line in lines:
                for a, b in zip(line, line[1:]):
                    if a != b:
                        segments[(item['color'], tuple(sorted((tuple(a), tuple(b)))))].append(item)

    result = []
    used_segments = set()
    for authored in authoring:
        geom, kind, color = authored['geometry'], authored['kind'], authored['color']
        if kind == 'label':
            bucket = labels.get(key(geom['coordinates']), [])
            if not bucket:
                continue
            # Prefer the matching text when labels share a coordinate.
            index = next((i for i, r in enumerate(bucket) if r['name'] == authored['name']), 0)
            source = bucket.pop(index)
        elif kind == 'polygon':
            parts = geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]
            needed = collections.Counter((color, key(bridge_rings(part))) for part in parts)
            if any(len(polygons[k]) < count for k, count in needed.items()):
                continue
            for k, count in needed.items():
                for _ in range(count):
                    source = polygons[k].pop(0)
        else:
            lines = geom['coordinates'] if geom['type'] == 'MultiLineString' else [geom['coordinates']]
            needed = {(color, tuple(sorted((tuple(a), tuple(b))))) for line in lines for a, b in zip(line, line[1:]) if a != b}
            if not needed or any(not segments[k] for k in needed):
                continue
            for k in sorted(needed):
                source = segments[k][0]
                used_segments.add(k)
        item = copy.deepcopy(source)
        item['geometry'] = copy.deepcopy(geom)
        if kind != 'label':
            item['name'] = authored['name']
        item['source_id'] = authored.get('source_id') or code + '-' + hashlib.sha256(key(authored).encode()).hexdigest()[:20]
        result.append(item)

    remaining = [item for bucket in polygons.values() for item in bucket]
    remaining.extend(item for bucket in labels.values() for item in bucket)
    leftover_lines = collections.defaultdict(list)
    prototypes = {}
    for (color, segment), bucket in segments.items():
        if (color, segment) in used_segments:
            continue
        for item in bucket:
            group = (item['file'], color)
            prototypes[group] = item
            leftover_lines[group].append([list(p) for p in segment])
    for group, lines in leftover_lines.items():
        item = copy.deepcopy(prototypes[group])
        item['geometry'] = dict(type='MultiLineString', coordinates=lines)
        remaining.append(item)
    used = {item['source_id'] for item in result}
    for original in remaining:
        item = copy.deepcopy(original)
        base = code + '-' + hashlib.sha256(key(item).encode()).hexdigest()[:20]
        identifier, number = base, 1
        while identifier in used:
            number += 1
            identifier = base + '-' + str(number)
        item['source_id'] = identifier
        used.add(identifier)
        result.append(item)
    return result


def signed_area(ring):
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:]))


def bridge_rings(rings):
    """Represent polygon holes as a normal region with zero-width bridges."""
    outer = [p[:] for p in rings[0]]
    if outer[-1] != outer[0]:
        outer.append(outer[0][:])
    result = outer[:]
    for inner in rings[1:]:
        hole = [p[:] for p in inner]
        if hole[-1] != hole[0]:
            hole.append(hole[0][:])
        if signed_area(outer) * signed_area(hole) > 0:
            hole.reverse()
        result.extend(hole + [outer[0][:]])
    return result


def native_equivalent(gng, kml):
    """Use KMZ's multipart/hole topology only when GNG draws the same geometry."""
    if gng['type'] == 'Point' or kml['type'] == 'Point':
        return gng == kml
    if gng['type'] in ('Polygon', 'MultiPolygon') and kml['type'] in ('Polygon', 'MultiPolygon'):
        source = gng['coordinates'] if gng['type'] == 'MultiPolygon' else [gng['coordinates']]
        authoring = kml['coordinates'] if kml['type'] == 'MultiPolygon' else [kml['coordinates']]
        return [polygon[0] for polygon in source] == [bridge_rings(polygon) for polygon in authoring]
    if gng['type'] in ('LineString', 'MultiLineString') and kml['type'] in ('LineString', 'MultiLineString'):
        def segments(geometry):
            lines = geometry['coordinates'] if geometry['type'] == 'MultiLineString' else [geometry['coordinates']]
            return {tuple(sorted((tuple(a), tuple(b)))) for line in lines for a, b in zip(line, line[1:]) if a != b}
        return segments(gng) == segments(kml)
    return False
