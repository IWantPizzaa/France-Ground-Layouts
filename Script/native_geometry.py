"""Native GNG region bridges and KML topology equivalence."""


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
