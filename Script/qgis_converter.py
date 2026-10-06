"""Read the bundled QGIS/GeoPackage AVISO projects without a QGIS installation."""
from __future__ import annotations

import collections
from contextlib import closing
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import struct
import xml.etree.ElementTree as ET
import zipfile

import aviso_converter as aviso


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def open_database(path):
    connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA query_only=ON')
    return connection


class WKB:
    def __init__(self, data):
        self.data, self.offset = memoryview(data), 0

    def take(self, fmt):
        size = struct.calcsize(fmt)
        if self.offset + size > len(self.data):
            raise ValueError('Truncated GeoPackage geometry')
        values = struct.unpack_from(fmt, self.data, self.offset)
        self.offset += size
        return values

    def geometry(self):
        flag, = self.take('B')
        if flag not in (0, 1):
            raise ValueError('Invalid WKB byte order')
        endian = '<' if flag else '>'
        raw, = self.take(endian + 'I')
        z, m, srid = bool(raw & 0x80000000), bool(raw & 0x40000000), bool(raw & 0x20000000)
        kind = raw & 0x1FFFFFFF
        if kind >= 1000:
            dimension, kind = divmod(kind, 1000)
            if dimension not in (1, 2, 3):
                raise ValueError('Unsupported WKB dimensionality')
            z, m = dimension in (1, 3), dimension in (2, 3)
        if m:
            raise ValueError('Measured coordinates cannot be exported as AVISO GeoJSON')
        if srid and self.take(endian + 'I')[0] != 4326:
            raise ValueError('Geometry must be saved in EPSG:4326')
        dimensions = 3 if z else 2

        def point():
            values = list(self.take(endian + 'd' * dimensions))
            if not all(math.isfinite(value) for value in values):
                raise ValueError('Empty or nonfinite coordinate')
            return values

        def count():
            value, = self.take(endian + 'I')
            if value > len(self.data) - self.offset:
                raise ValueError('Invalid geometry element count')
            return value

        if kind == 1:
            return dict(type='Point', coordinates=point())
        if kind == 2:
            points = [point() for _ in range(count())]
            if len(points) < 2:
                raise ValueError('A line needs at least two coordinates')
            return dict(type='LineString', coordinates=points)
        if kind == 3:
            rings = [[point() for _ in range(count())] for _ in range(count())]
            if not rings or any(len(ring) < 4 or ring[0] != ring[-1] for ring in rings):
                raise ValueError('A polygon needs closed rings')
            return dict(type='Polygon', coordinates=rings)
        multi = {4: ('MultiPoint', 'Point'), 5: ('MultiLineString', 'LineString'), 6: ('MultiPolygon', 'Polygon')}
        if kind not in multi:
            raise ValueError('Unsupported AVISO geometry type: ' + str(kind))
        name, child_type = multi[kind]
        children = [self.geometry() for _ in range(count())]
        if not children or any(child['type'] != child_type for child in children):
            raise ValueError('Invalid multipart geometry')
        return dict(type=name, coordinates=[child['coordinates'] for child in children])


def read_geometry(blob):
    if blob is None or len(blob) < 8 or blob[:2] != b'GP' or blob[2] != 0:
        raise ValueError('Invalid GeoPackage geometry header')
    flags = blob[3]
    if flags & 0xF0:
        raise ValueError('Empty or extended GeoPackage geometry is unsupported')
    envelope = (flags >> 1) & 7
    sizes = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}
    if envelope not in sizes:
        raise ValueError('Invalid GeoPackage envelope')
    if struct.unpack_from('<i' if flags & 1 else '>i', blob, 4)[0] != 4326:
        raise ValueError('Save the edited layer in EPSG:4326 before exporting')
    reader = WKB(blob[8 + sizes[envelope]:])
    geometry = reader.geometry()
    if reader.offset != len(reader.data):
        raise ValueError('Unexpected bytes after GeoPackage geometry')
    return geometry


def canvas_color(root):
    values = []
    for part in ('Red', 'Green', 'Blue'):
        node = root.find(f"./properties/properties[@name='Gui']/properties[@name='CanvasColor{part}Part']")
        if node is None:
            node = root.find('./properties/Gui/CanvasColor' + part + 'Part')
        if node is None:
            return None
        value = int(node.text)
        if not 0 <= value <= 255:
            raise ValueError('Invalid QGIS canvas color')
        values.append(value)
    return '#%02X%02X%02X' % tuple(values)


def project_layers(path):
    if path.suffix.lower() == '.qgz':
        with zipfile.ZipFile(path) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith('.qgs')]
            if len(names) != 1:
                raise ValueError('Expected one QGIS project in ' + str(path))
            root = ET.fromstring(archive.read(names[0]))
    else:
        root = ET.parse(path).getroot()
    layers = []
    for layer in root.findall('./projectlayers/maplayer'):
        if layer.get('type') != 'vector':
            continue
        uri = layer.findtext('datasource', '')
        components = uri.split('|')
        if not components[0].lower().endswith('.gpkg'):
            raise ValueError('QGIS AVISO export requires the bundled GeoPackage vector layers')
        database = Path(components[0])
        if not database.is_absolute():
            database = (path.parent / database).resolve()
        if not database.is_file():
            raise ValueError('Missing project GeoPackage: ' + str(database))
        options = dict(component.split('=', 1) for component in components[1:] if '=' in component)
        table = options.get('layername')
        if not table:
            raise ValueError('Missing GeoPackage layer name')
        subset = layer.findtext('subsetstring') or options.get('subset', '')
        airport = re.search(r'"?airport"?\s*=\s*\'([A-Z]{4})\'', subset)
        layers.append((database, table, subset, airport.group(1) if airport else None))
    if not layers:
        raise ValueError('No AVISO vector layers in the QGIS project')
    return layers, canvas_color(root)


def resolved_paint(style, palette):
    paint = copy.deepcopy(style['paint'])
    overrides = paint.pop('palette-overrides', {})
    paint.update(overrides.get(palette, {}))
    return paint


def color(value):
    value = value.strip()
    if re.fullmatch(r'#[0-9A-Fa-f]{6}', value):
        return value.upper(), 1
    parts = [int(part) for part in value.split(',')]
    if len(parts) != 4 or any(part < 0 or part > 255 for part in parts):
        raise ValueError('Expected a QGIS r,g,b,a or #RRGGBB color: ' + str(value))
    return '#%02X%02X%02X' % tuple(parts[:3]), parts[3] / 255


def row_paint(row, original, kind):
    paint = copy.deepcopy(original)
    channels = [('fill_color', 'fill', 'fill-opacity')] if kind in ('Polygon', 'MultiPolygon') else []
    if kind in ('LineString', 'MultiLineString', 'Polygon', 'MultiPolygon'):
        channels.append(('line_color', 'stroke', 'stroke-opacity'))
    if kind in ('Point', 'MultiPoint'):
        channels.extend([('text_color', 'text-color', 'text-opacity'), ('halo_color', 'text-halo-color', None)])
    for field, key, opacity_key in channels:
        if row[field] is None:
            continue
        hex_color, opacity = color(row[field])
        # Invisible default channels are implementation details, not new styles.
        if opacity == 0 and key not in original:
            continue
        old_color = original.get(key, '#000000')
        if hex_color.lower() != old_color.lower():
            paint[key] = hex_color
        if opacity_key and abs(opacity - original.get(opacity_key, 1)) > 1 / 510:
            paint[opacity_key] = opacity
    fields = [('line_width', 'stroke-width')] if kind in ('LineString', 'MultiLineString') or 'stroke' in paint else []
    if kind in ('Point', 'MultiPoint'):
        fields += [('text_font', 'text-font'), ('text_size', 'text-size'), ('halo_width', 'text-halo-width'),
                   ('text_anchor', 'text-anchor'), ('zoom_level', 'zoomLevel')]
    for field, key in fields:
        value = row[field]
        if value is not None and (key in original or value not in ('', 0)):
            defaults = {'stroke-width': 1, 'text-font': 'Arial', 'text-size': 12,
                        'text-halo-width': 1, 'text-anchor': 'center', 'zoomLevel': 0}
            if value != original.get(key, defaults.get(key)):
                paint[key] = value
    return paint


def feature_from_row(row, geometry, document):
    code = row['airport']
    props = json.loads(row['properties_json'] or '{}')
    fields = ('name', 'layer', 'category', 'object_type', 'style_id', 'source_group', 'geometry_role')
    for key in fields:
        value = row[key]
        if key in props or value not in (None, ''):
            if value is None:
                props.pop(key, None)
            else:
                props[key] = value
    props['airport'] = code
    if row['vsmr_group_ids'] is not None:
        groups = json.loads(row['vsmr_group_ids'])
        if not isinstance(groups, list) or not all(isinstance(group, str) for group in groups):
            raise ValueError(code + ': vsmr_group_ids must be a JSON list of group IDs')
        props['vsmr_group_ids'] = groups
    if 'text-field' in props or props.get('geometry_role') == 'text_label':
        props['text-field'] = row['text'] if row['text'] is not None else props.get('name', '')
    style_id = props.get('style_id')
    if style_id not in document['styles']:
        raise ValueError(code + ': choose an existing style_id for each new feature')
    palette = row['palette']
    if palette not in document['metadata']['color_palettes']:
        raise ValueError(code + ': unknown selected palette')
    original_style = document['styles'][style_id]
    original_paint = resolved_paint(original_style, palette)
    edited_paint = row_paint(row, original_paint, geometry['type'])
    if edited_paint != original_paint:
        # A per-feature edit creates a style variant rather than repainting
        # every other feature, airport or theme using the original style.
        changes = {key: value for key, value in edited_paint.items() if value != original_paint.get(key)}
        variant_id = style_id + '.qgis.' + hashlib.sha256(aviso.packed([palette, changes])).hexdigest()[:12]
        if variant_id not in document['styles']:
            variant = copy.deepcopy(original_style)
            variant['paint'].setdefault('palette-overrides', {}).setdefault(palette, {}).update(changes)
            document['styles'][variant_id] = variant
        props['style_id'] = variant_id
    extra = json.loads(row['feature_extra_json'] or '{}')
    feature_id = row['source_id'] or extra.get('id')
    if not feature_id:
        feature_id = code + '-qgis-' + hashlib.sha256(aviso.packed([props, geometry])).hexdigest()[:20]
    return dict(extra, type='Feature', id=str(feature_id), properties=props, geometry=geometry)


def collect(source):
    source = Path(source).resolve()
    if source.is_dir():
        source = source / 'LFXX.qgz'
    if source.suffix.lower() == '.gpkg':
        with closing(open_database(source)) as connection:
            layers = [(source, row['table_name'], '', None) for row in connection.execute('SELECT table_name FROM gpkg_geometry_columns')]
        canvas = None
    elif source.suffix.lower() in ('.qgs', '.qgz'):
        layers, canvas = project_layers(source)
    else:
        raise ValueError('Select LFXX.qgz, an airport .qgz/.qgs, or AVISO.gpkg')
    documents, templates, selected, seen, features, backgrounds = {}, {}, set(), {}, collections.defaultdict(list), {}
    for path, table, subset, airport in layers:
        with closing(open_database(path)) as connection:
            try:
                for row in connection.execute('SELECT airport,document_json FROM geojson_documents'):
                    document = json.loads(row['document_json'])
                    code = row['airport']
                    if code in templates and templates[code] != document:
                        raise ValueError('Conflicting original AVISO settings for ' + code)
                    templates[code] = document
                    if code not in documents:
                        documents[code] = copy.deepcopy(document)
                info = connection.execute('SELECT column_name,srs_id FROM gpkg_geometry_columns WHERE table_name=?', (table,)).fetchone()
            except sqlite3.Error as error:
                raise ValueError('GeoPackage must originate from the AVISO QGIS exporter') from error
            if info is None or info['srs_id'] != 4326:
                raise ValueError(table + ': the AVISO geometry layer must use EPSG:4326')
            selected.update([airport] if airport else documents)
            query = 'SELECT * FROM ' + quote(table) + (' WHERE (' + subset + ')' if subset else '')
            for row in connection.execute(query):
                code = row['airport']
                if code not in documents:
                    raise ValueError('Set airport to a known ICAO before exporting a new feature')
                geometry = read_geometry(row[info['column_name']])
                feature = feature_from_row(row, geometry, documents[code])
                feature_id = feature['id']
                # QGIS's duplicate-feature action copies attributes, including
                # IDs. Keep both geometries and assign the duplicate a new ID.
                if (code, feature_id) in seen:
                    digest = hashlib.sha256(aviso.packed([feature, len(features[code])])).hexdigest()[:20]
                    feature['id'] = code + '-qgis-' + digest
                seen[(code, feature['id'])] = feature
                features[code].append(feature)
                palette, background = row['palette'], row['background_color']
                if background is not None:
                    if not re.fullmatch(r'#[0-9A-Fa-f]{6}', background):
                        raise ValueError(code + ': background_color must be an RGB hex color')
                    key = (code, palette)
                    if key in backgrounds and backgrounds[key] != background:
                        raise ValueError(code + ': set background_color consistently for the selected palette')
                    backgrounds[key] = background
    if not documents or not selected or selected - documents.keys():
        raise ValueError('No matching airport settings in the QGIS project')
    products = {}
    for code in sorted(selected):
        document = documents[code]
        document['features'] = features[code]
        for (airport, palette), background in backgrounds.items():
            if airport == code:
                document['metadata']['background_colors'][palette] = background
        if len(selected) == 1 and canvas:
            palettes = {key[1] for key in backgrounds if key[0] == code}
            if len(palettes) == 1:
                document['metadata']['background_colors'][next(iter(palettes))] = canvas
        group_ids = {group['id'] for group in document.get('vsmr_groups', [])}
        for feature in document['features']:
            if set(feature['properties'].get('vsmr_group_ids', [])) - group_ids:
                raise ValueError(code + ': unknown AVISO group ID')
        document['bbox'] = []
        aviso.update_counts(document)
        aviso.validate(code, document)
        products[code] = document
    return products


def run(source=None, output=None, log=print):
    source = Path(source) if source else aviso.ROOT / 'QGIS' / 'LFXX.qgz'
    output = Path(output) if output else aviso.ROOT / 'GeoJSON'
    for name in ('GNG', 'KMZ', 'Settings', 'QGIS', 'Script'):
        protected, destination = (aviso.ROOT / name).resolve(), output.resolve()
        if destination == protected or protected in destination.parents or destination in protected.parents:
            raise ValueError('Output overlaps protected source/project directory: ' + str(output))
    log('\n  QGIS -> AVISO GEOJSON\n  Reading: ' + str(source))
    products = collect(source)
    serialized = {code: aviso.serialize_document(document) for code, document in products.items()}
    # All airports are validated before any output file is changed. An airport
    # project updates that airport only, never deleting unrelated GeoJSON files.
    output.mkdir(parents=True, exist_ok=True)
    for code, data in serialized.items():
        path = output / (code + '.geojson')
        temporary = path.with_suffix('.geojson.tmp')
        temporary.write_bytes(data)
        temporary.replace(path)
    count = sum(len(document['features']) for document in products.values())
    log(f'  DONE | {len(products)} airports | {count} features\n  Output: {output}')
    return dict(airport_count=len(products), feature_count=count)
