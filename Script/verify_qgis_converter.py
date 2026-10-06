"""Offline QGIS asset, round-trip and saved-edit regressions (standard library)."""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import struct
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

import aviso_converter as aviso
import qgis_converter as qgis


def input_hashes():
    paths = []
    for directory in ('GNG', 'KMZ', 'Settings', 'GeoJSON', 'QGIS'):
        paths.extend(path for path in (aviso.ROOT / directory).rglob('*') if path.is_file())
    paths.append(aviso.ROOT / 'Colours.sct')
    return {path: hashlib.sha256(path.read_bytes()).digest() for path in paths}


def wkb(geometry):
    """Independent encoder for comparing exported coordinates to source bytes."""
    kinds = {'Point': 1, 'LineString': 2, 'Polygon': 3, 'MultiPoint': 4,
             'MultiLineString': 5, 'MultiPolygon': 6}
    points = list(aviso.coordinates(geometry))
    dimensions = len(points[0])
    kind, coordinates = geometry['type'], geometry['coordinates']
    data = b'\x01' + struct.pack('<I', kinds[kind] + (1000 if dimensions == 3 else 0))
    point = lambda values: struct.pack('<' + 'd' * dimensions, *values)
    if kind == 'Point':
        return data + point(coordinates)
    if kind == 'LineString':
        return data + struct.pack('<I', len(coordinates)) + b''.join(point(p) for p in coordinates)
    if kind == 'Polygon':
        return data + struct.pack('<I', len(coordinates)) + b''.join(
            struct.pack('<I', len(ring)) + b''.join(point(p) for p in ring) for ring in coordinates)
    child_type = {'MultiPoint': 'Point', 'MultiLineString': 'LineString', 'MultiPolygon': 'Polygon'}[kind]
    return data + struct.pack('<I', len(coordinates)) + b''.join(
        wkb(dict(type=child_type, coordinates=part)) for part in coordinates)


def gpkg_geometry(geometry):
    return b'GP\x00\x01' + struct.pack('<i', 4326) + wkb(geometry)


def payload(blob):
    envelope_sizes = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}
    return blob[8 + envelope_sizes[(blob[3] >> 1) & 7]:]


def verify_assets():
    folder = aviso.ROOT / 'QGIS'
    airports = list((folder / 'Aeroports').glob('*.qgz'))
    assert len(airports) == 160
    for path in [folder / 'LFXX.qgz'] + airports:
        layers, _ = qgis.project_layers(path)
        assert len(layers) == 4
        for database, table, _, code in layers:
            assert database == (folder / 'AVISO.gpkg').resolve()
            assert table.startswith('geojson_')
            if path.parent.name == 'Aeroports':
                assert code == path.stem
    with closing(qgis.open_database(folder / 'AVISO.gpkg')) as connection:
        assert connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not list(connection.execute('PRAGMA foreign_key_check'))


def verify_roundtrip():
    folder = aviso.ROOT / 'QGIS'
    documents = qgis.collect(folder)
    assert len(documents) == 160
    features = {(code, feature['id']): feature for code, doc in documents.items() for feature in doc['features']}
    assert len(features) == 10760
    with closing(qgis.open_database(folder / 'AVISO.gpkg')) as connection:
        for table, geom_column in connection.execute('SELECT table_name,column_name FROM gpkg_geometry_columns'):
            for row in connection.execute('SELECT * FROM ' + qgis.quote(table)):
                feature = features[(row['airport'], row['source_id'])]
                assert feature['properties'] == json.loads(row['properties_json'])
                assert wkb(feature['geometry']) == payload(row[geom_column])
        for code, data in connection.execute('SELECT airport,document_json FROM geojson_documents'):
            original, actual = json.loads(data), documents[code]
            assert set(original['styles']) == set(actual['styles']), 'Unedited export created styles: ' + code
            for key, style in original['styles'].items():
                old = {k: v for k, v in style.items() if k != 'feature_count'}
                new = {k: v for k, v in actual['styles'][key].items() if k != 'feature_count'}
                assert old == new, (code, key)
            assert original['vsmr_groups'] == actual['vsmr_groups']
            assert original['metadata']['background_colors'] == actual['metadata']['background_colors']
            assert actual['metadata']['feature_count'] == len(actual['features'])
    direct = qgis.collect(folder / 'AVISO.gpkg')
    assert direct == documents
    airport = qgis.collect(folder / 'Aeroports' / 'LFPG.qgz')
    assert list(airport) == ['LFPG'] and airport['LFPG'] == documents['LFPG']
    return documents


def verify_binary_errors():
    assert qgis.color('#112233') == ('#112233', 1)
    assert qgis.color('17,34,51,255') == ('#112233', 1)
    point = dict(type='Point', coordinates=[2.5, 48.9, 17.25])
    assert qgis.read_geometry(gpkg_geometry(point)) == point
    big_endian = b'GP\x00\x00' + struct.pack('>i', 4326) + b'\x00' + struct.pack('>I3d', 1001, 2.5, 48.9, 17.25)
    assert qgis.read_geometry(big_endian) == point
    geometry = dict(type='MultiLineString', coordinates=[[[2, 48], [2.1, 48.2]], [[2.2, 48.3], [2.4, 48.5]]])
    assert qgis.read_geometry(gpkg_geometry(geometry)) == geometry
    invalid = [None, b'GP', gpkg_geometry(point)[:-1],
               b'GP\x00\x01' + struct.pack('<i', 3857) + wkb(point)]
    for blob in invalid:
        try:
            qgis.read_geometry(blob)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid/truncated/projected geometry accepted')


def verify_saved_edits(baseline):
    with tempfile.TemporaryDirectory(prefix='aviso-qgis-tests-') as temporary:
        scratch = Path(temporary)
        project_dir = scratch / 'Aeroports'
        project_dir.mkdir()
        database = scratch / 'AVISO.gpkg'
        with closing(sqlite3.connect(aviso.ROOT / 'QGIS' / 'AVISO.gpkg')) as original, closing(sqlite3.connect(database)) as edited:
            original.backup(edited)
        project = project_dir / 'LFPG.qgz'
        original_project = aviso.ROOT / 'QGIS' / 'Aeroports' / 'LFPG.qgz'
        project.write_bytes(original_project.read_bytes())
        changed_geometry = dict(type='Point', coordinates=[2.9, 49.1])
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.row_factory = sqlite3.Row
            # The fixture updates geometry without QGIS's spatial SQL extension.
            # Disable its R-tree triggers only in this disposable database.
            triggers = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name IN ('geojson_textes','geojson_surfaces')")]
            for trigger in triggers:
                connection.execute('DROP TRIGGER ' + qgis.quote(trigger))
            label = connection.execute("SELECT * FROM geojson_textes WHERE airport='LFPG' LIMIT 1").fetchone()
            connection.execute('UPDATE geojson_textes SET geom=?,text=?,name=? WHERE fid=?',
                               (gpkg_geometry(changed_geometry), 'EDITED LABEL', 'Edited name', label['fid']))
            surface = connection.execute("SELECT * FROM geojson_surfaces WHERE airport='LFPG' AND style_id='polygon.hardsurface4.969393' LIMIT 1").fetchone()
            connection.execute('UPDATE geojson_surfaces SET fill_color=? WHERE fid=?', ('17,34,51,255', surface['fid']))
        # Changing an individual project's canvas affects that airport only.
        with zipfile.ZipFile(project) as original:
            entries = [(info, original.read(info.filename)) for info in original.infolist()]
        with zipfile.ZipFile(project, 'w', compression=zipfile.ZIP_DEFLATED) as edited:
            for info, data in entries:
                if info.filename.endswith('.qgs'):
                    tree = ET.fromstring(data)
                    for part, value in [('Red', 18), ('Green', 52), ('Blue', 86)]:
                        tree.find(f"./properties/properties[@name='Gui']/properties[@name='CanvasColor{part}Part']").text = str(value)
                    data = ET.tostring(tree, encoding='utf-8', xml_declaration=True)
                edited.writestr(info, data)
        documents = qgis.collect(project)
        assert set(documents) == {'LFPG'}
        document = documents['LFPG']
        features = {feature['id']: feature for feature in document['features']}
        edited_label = features[label['source_id']]
        assert edited_label['geometry'] == changed_geometry
        assert edited_label['properties']['text-field'] == 'EDITED LABEL'
        assert edited_label['properties']['name'] == 'Edited name'
        assert document['bbox'][2] == 2.9
        assert document['metadata']['background_colors']['real'] == '#123456'
        assert document['metadata']['background_colors']['light'] == baseline['LFPG']['metadata']['background_colors']['light']
        original_style = baseline['LFPG']['styles'][surface['style_id']]
        new_style_id = features[surface['source_id']]['properties']['style_id']
        assert new_style_id != surface['style_id']
        assert {k: v for k, v in document['styles'][surface['style_id']].items() if k != 'feature_count'} == {
            k: v for k, v in original_style.items() if k != 'feature_count'}
        new_style = document['styles'][new_style_id]
        assert qgis.resolved_paint(new_style, 'real')['fill'] == '#112233'
        for palette in ('dark', 'light'):
            assert qgis.resolved_paint(new_style, palette) == qgis.resolved_paint(original_style, palette)
        for feature in document['features']:
            if feature['id'] != surface['source_id']:
                assert feature['properties']['style_id'] != new_style_id
        # QGIS duplicates copy source IDs. Both geometries must survive with
        # distinct output IDs, while a deleted geometry must remain deleted.
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.row_factory = sqlite3.Row
            current = connection.execute('SELECT * FROM geojson_textes WHERE fid=?', (label['fid'],)).fetchone()
            columns = [key for key in current.keys() if key != 'fid']
            connection.execute('INSERT INTO geojson_textes (' + ','.join(qgis.quote(key) for key in columns) + ') VALUES (' + ','.join('?' for _ in columns) + ')',
                               [current[key] for key in columns])
            deleted = connection.execute("SELECT fid,source_id FROM geojson_surfaces WHERE airport='LFPG' AND fid!=? LIMIT 1", (surface['fid'],)).fetchone()
            connection.execute('DELETE FROM geojson_surfaces WHERE fid=?', (deleted['fid'],))
        document = qgis.collect(project)['LFPG']
        ids = [feature['id'] for feature in document['features']]
        assert len(ids) == len(set(ids)) == len(baseline['LFPG']['features'])
        assert deleted['source_id'] not in ids
        copies = [feature for feature in document['features'] if feature['geometry'] == changed_geometry]
        assert len(copies) == 2 and copies[0]['id'] != copies[1]['id']
        output = scratch / 'GeoJSON'
        output.mkdir()
        sentinel = output / 'LFPO.geojson'
        sentinel.write_bytes(b'untouched other airport')
        result = subprocess.run([sys.executable, str(aviso.ROOT / 'Script' / 'aviso_converter.py'),
                                 '--qgis', str(project), '--output', str(output)], capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads((output / 'LFPG.geojson').read_text(encoding='utf-8')) == document
        assert sentinel.read_bytes() == b'untouched other airport'
        before = {path.name: path.read_bytes() for path in output.iterdir()}
        # Bad style references must not partially overwrite previous outputs.
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute("UPDATE geojson_textes SET style_id='missing.style' WHERE fid=?", (label['fid'],))
        try:
            qgis.run(project, output, log=lambda _: None)
        except ValueError as error:
            assert 'style_id' in str(error)
        else:
            raise AssertionError('Missing style accepted')
        assert before == {path.name: path.read_bytes() for path in output.iterdir()}
        for protected in ('GNG', 'KMZ', 'Settings', 'QGIS', 'Script'):
            try:
                qgis.run(project, aviso.ROOT / protected, log=lambda _: None)
            except ValueError as error:
                assert 'protected' in str(error)
            else:
                raise AssertionError('Protected output accepted')


def main():
    before = input_hashes()
    verify_assets()
    baseline = verify_roundtrip()
    verify_binary_errors()
    verify_saved_edits(baseline)
    assert before == input_hashes(), 'Verification modified repository sources or projects'
    print('PASS: 161 portable QGIS projects, 10760 exact round-trip features, edited geometry/text/colors,')
    print('      theme isolation, single-airport CLI export, read-only sources and invalid-input protection.')


if __name__ == '__main__':
    main()
