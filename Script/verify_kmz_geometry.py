"""Round-trip native KMZ geometry to temporary GNG; compare with current GNG.

Polygon starting vertices, winding and line direction/packaging do not change
geometry. All coordinate values, native color tokens and multiplicities must
match exactly. Text stays exclusively in GNG; KMZ files are never read by the
production GeoJSON converter.
"""
from __future__ import annotations

import collections
from decimal import Decimal, localcontext
from pathlib import Path
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile

import aviso_converter as c

NS = 'http://www.opengis.net/kml/2.2'


def tag(name):
    return '{' + NS + '}' + name


def points(element):
    if element is None or not element.text:
        raise ValueError('Missing KML coordinates')
    result = []
    for item in element.text.split():
        values = item.split(',')
        if len(values) not in (2, 3):
            raise ValueError('Invalid KML coordinate: ' + item)
        result.append([float(values[0]), float(values[1])])
    return result


def read_kmz(path):
    records = []
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError(str(path) + ': corrupt archive')
        for name in archive.namelist():
            if not name.lower().endswith('.kml'):
                continue
            root = ET.fromstring(archive.read(name))
            ids = {element.attrib['id'] for element in root.iter() if 'id' in element.attrib}
            for reference in root.iter(tag('styleUrl')):
                if reference.text and reference.text.startswith('#') and reference.text[1:] not in ids:
                    raise ValueError(str(path) + ': missing style ' + reference.text)
            if list(root.iter(tag('Point'))):
                raise ValueError(str(path) + ': text/point annotation remains')
            for style in root.iter(tag('Style')):
                if style.findtext(tag('LabelStyle') + '/' + tag('scale')) != '0':
                    raise ValueError(str(path) + ': labels are not disabled')
            for placemark in root.iter(tag('Placemark')):
                color = placemark.findtext(tag('name'), '')
                for polygon in placemark.iter(tag('Polygon')):
                    if polygon.find(tag('innerBoundaryIs')) is not None:
                        raise ValueError(str(path) + ': polygon holes cannot be represented by native GNG')
                    ring = points(polygon.find(tag('outerBoundaryIs') + '/' + tag('LinearRing') + '/' + tag('coordinates')))
                    records.append(dict(kind='polygon', color=color, geometry=dict(type='Polygon', coordinates=[ring])))
                for line in placemark.iter(tag('LineString')):
                    records.append(dict(kind='line', color=color, geometry=dict(type='LineString', coordinates=points(line.find(tag('coordinates'))))))
    return records


def ring_key(ring):
    ring = tuple(map(tuple, ring))
    if ring and ring[-1] == ring[0]:
        ring = ring[:-1]
    if not ring:
        raise ValueError('Empty polygon')
    # Starting vertex and winding do not affect the native filled surface.
    return min(sequence[index:] + sequence[:index]
               for sequence in (ring, ring[::-1])
               for index, point in enumerate(sequence) if point == min(ring))


def inventory(records):
    result = collections.Counter()
    for record in records:
        kind, color, geometry = record['kind'], record['color'], record['geometry']
        if kind == 'label':
            continue
        if kind == 'polygon':
            result[('polygon', color, ring_key(geometry['coordinates'][0]))] += 1
        else:
            paths = [geometry['coordinates']] if geometry['type'] == 'LineString' else geometry['coordinates']
            for path in paths:
                for start, end in zip(path, path[1:]):
                    if start != end:
                        result[('segment', color, tuple(sorted((tuple(start), tuple(end)))))] += 1
    return result


def dms(value, latitude):
    # Sufficient decimal precision to preserve the parsed binary float exactly.
    with localcontext() as context:
        context.prec = 60
        seconds = abs(Decimal(str(value))) * 3600
        degree = int(seconds // 3600)
        seconds -= degree * 3600
        minute = int(seconds // 60)
        seconds -= minute * 60
        hemisphere = ('N' if value >= 0 else 'S') if latitude else ('E' if value >= 0 else 'W')
        return f'{hemisphere}{degree:03d}.{minute:02d}.{seconds:028.25f}'


def row(point):
    return dms(point[1], True) + ' ' + dms(point[0], False)


def export_gng(records):
    rows = []
    for record in records:
        color, geometry = record['color'], record['geometry']
        if not re.fullmatch(c.COLOR_TOKEN + r'|\d+', color):
            raise ValueError('Not a native GNG color token: ' + color)
        if record['kind'] == 'polygon':
            rows.append(color)
            rows.extend(row(point) for point in geometry['coordinates'][0])
            rows.append('')
        else:
            for start, end in zip(geometry['coordinates'], geometry['coordinates'][1:]):
                if start != end:
                    rows.append(row(start) + ' ' + row(end) + ' ' + color)
    return ('\n'.join(rows) + '\n').encode('utf-8')


def export_groups(records):
    """Keep repeated native segments in separate files, as GNG requires."""
    groups = []
    seen = []
    for record in records:
        geometry = record['geometry']
        keys = set()
        if record['kind'] == 'line':
            keys = {(record['color'], tuple(start), tuple(end))
                    for start, end in zip(geometry['coordinates'], geometry['coordinates'][1:]) if start != end}
        index = next((index for index, existing in enumerate(seen) if not keys & existing), len(groups))
        if index == len(groups):
            groups.append([])
            seen.append(set())
        groups[index].append(record)
        seen[index].update(keys)
    return groups


def main():
    airports = archives = annotations_only = 0
    with tempfile.TemporaryDirectory(prefix='kmz-gng-roundtrip-') as directory:
        for path in sorted((c.ROOT / 'KMZ').glob('*.kmz')):
            records = read_kmz(path)
            archives += 1
            code = path.name[:4]
            files = sorted((c.ROOT / 'GNG').glob('*/' + code + '/*.txt'))
            if not files:
                # Regional coastline and reference template have no airport GNG.
                assert path.name in ('LFMM Region Coastline.kmz', 'LFXX reference.kmz'), path.name
                continue
            native = [record for file in files for record in c.parse_gng(file.relative_to(c.ROOT).as_posix(), file.read_bytes())]
            expected, actual = inventory(native), inventory(records)
            assert actual == expected, f'{path.name}: {sum((expected-actual).values())} missing / {sum((actual-expected).values())} extra geometry items'
            converted = []
            for index, group in enumerate(export_groups(records)):
                generated = Path(directory) / (path.stem + f'-{index}.txt')
                generated.write_bytes(export_gng(group))
                converted.extend(c.parse_gng(generated.name, generated.read_bytes()))
            assert inventory(converted) == expected, path.name + ': KMZ -> GNG round trip changed coordinates, colors or multiplicities'
            assert all(record['kind'] != 'label' for record in converted)
            airports += 1
            annotations_only += not bool(expected)
    print(f'PASS: {archives} text-free KMZ; {airports} airport archives match current GNG exactly; KMZ -> GNG round trip verified; {annotations_only} have text-only GNG. Coastline/reference checked separately.')


if __name__ == '__main__':
    main()
