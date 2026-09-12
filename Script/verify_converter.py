"""Offline conversion and native-format regression checks (standard library only)."""
import copy
import io
import json
import re
from pathlib import Path
import tempfile
from unittest.mock import patch
import zipfile

import aviso_converter as c
from native_geometry import match_native_records


def main():
    root = c.ROOT
    source = c.load_source(root)
    c.require_native_ids(source)
    for path in (root / 'Data').rglob('*.json'):
        assert not re.search(r'"#[0-9A-Fa-f]{6}"', path.read_text(encoding='utf-8')), 'Palette literals belong in Colours.sct'
    changed_colors = dict(source['colors'], BACKGROUND_COLOR='#123456')
    changed_settings = c.load_preserved(changed_colors)
    assert changed_settings['recipes']['LFPG']['document']['metadata']['background_colors']['dark'] == '#123456'
    assert changed_settings['recipes']['LFPG']['document']['metadata']['background_colors']['real'] == '#6F6F6F'
    for code, recipe in changed_settings['recipes'].items():
        for mode, color in recipe['document']['metadata']['background_colors'].items():
            if (code, mode) != ('LFPG', 'real'):
                assert color == '#123456', (code, mode)
    text_settings = c.load_preserved(dict(source['colors'], TEXT_COLOR='#123456'))
    for recipe in text_settings['recipes'].values():
        for style in recipe['document']['styles'].values():
            if 'text-color' in style['paint']:
                assert style['paint']['text-color'] == '#123456'
    missing_colors = dict(source['colors'])
    del missing_colors['BACKGROUND_COLOR']
    try:
        c.load_preserved(missing_colors)
        raise AssertionError('Undefined palette color accepted')
    except ValueError as error:
        assert 'Undefined palette color' in str(error)
    try:
        c.read_colors(b'#define DARK_TEST 0\n#define DARK_TEST 1\n')
        raise AssertionError('Duplicate palette definition accepted')
    except ValueError as error:
        assert 'Duplicate color' in str(error)
    expected_files = {p.name: p.read_bytes() for p in (root / 'GeoJSON').glob('*.geojson')}
    assert expected_files, 'Generate GeoJSON before running the checks'
    for name, data in expected_files.items():
        doc = json.loads(data)
        allowed = {'ground-layout-east', 'ground-layout-west'} if name == 'LFPG.geojson' else set()
        assert {g['id'] for g in doc.get('vsmr_groups', [])} == allowed
        for feature in doc['features']:
            assert set(feature['properties'].get('vsmr_group_ids', [])) <= allowed
    with tempfile.TemporaryDirectory(prefix='vsmr-aviso-tests-') as scratch:
        scratch = Path(scratch)
        c.run(root, scratch / 'GeoJSON')
        actual_files = {p.name:p.read_bytes() for p in (scratch / 'GeoJSON').iterdir()}
        assert actual_files == expected_files, 'Committed GeoJSON is not current: regenerate from local source'
        # Both native representations must agree, including holes and multipart lines.
        native_gng = {r['source_id']: r for records in source['airports'].values() for r in records}
        native_kmz = {}
        for path in (root / 'GNG').rglob('*.txt'):
            assert b'; Feature:' not in path.read_bytes(), 'GNG must use ordinary native syntax'
        for path in (root / 'KMZ').glob('*.kmz'):
            for item in c.parse_kmz(path.relative_to(root).as_posix(), path.read_bytes()):
                if 'source_id' in item:
                    assert item['source_id'] not in native_kmz, 'Duplicate KMZ feature ID'
                    native_kmz[item['source_id']] = item
        assert native_gng.keys() == native_kmz.keys(), 'GNG/KMZ feature IDs differ'
        for fid, published in native_gng.items():
            authoring = native_kmz[fid]
            assert published['geometry'] == authoring['geometry'], fid
            if published['kind'] == 'label':
                assert published['name'] == authoring['name'], fid
            else:
                assert source['colors'][published['color']].upper() == authoring['kml_color'].upper(), fid

        # Exercise the raw GNG-to-KML matching, not just already matched records.
        raw = c.parse_gng('GNG/LFFF/TEST/TEST Gates.txt',
                          b'N049.00.00.000 E002.00.00.000 renamed\n')
        authored = dict(raw[0], source_id='TEST-gate', name='old')
        matched = match_native_records('TEST', raw, [authored])
        assert matched[0]['source_id'] == 'TEST-gate'
        assert matched[0]['name'] == 'renamed'
        assert match_native_records('TEST', [], [authored]) == []
        moved = copy.deepcopy(raw)
        moved[0]['geometry']['coordinates'][0] += 0.001
        updated = match_native_records('TEST', moved, [authored])
        assert len(updated) == 1 and updated[0]['geometry'] == moved[0]['geometry']
        assert updated == match_native_records('TEST', moved, [authored])

        # Only the three native source entries are needed; no old geometry snapshot.
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name in ('GNG', 'KMZ', 'Colours.sct'):
                path = root / name
                for file in sorted(path.rglob('*')) if path.is_dir() else [path]:
                    if file.is_file():
                        archive.writestr('France-Ground-Layouts-master/' + file.relative_to(root).as_posix(), file.read_bytes())
        buffer.seek(0)
        assert c.load_source(buffer) == source
        with patch.object(c, 'github_source', side_effect=AssertionError('Local conversion contacted GitHub')):
            assert c.choose_source() == source
        with patch.object(c, 'github_source', return_value=source), patch.object(c, 'local_source', side_effect=AssertionError('GitHub selection used local input')):
            assert c.choose_source('github') == source
        with patch.object(c, 'github_source', side_effect=OSError('simulated offline')):
            try:
                c.choose_source('github')
                raise AssertionError('Explicit GitHub failure silently changed source')
            except OSError:
                pass

        # Source text/coordinates remain live. Added labels inherit the same settings.
        saved = c.load_preserved()
        original = source['airports']['LFPG']
        edited = copy.deepcopy(original)
        gate = next(r for r in edited if r['kind']=='label' and r['name']=='I04')
        gate['name'] = 'RENAMED'
        gate['geometry']['coordinates'][0] += 0.0001
        new_gate = copy.deepcopy(gate)
        new_gate.update(source_id='LFPG-regression-new', name='NEW-GATE')
        edited.append(new_gate)
        deleted = next(r['source_id'] for r in edited if r['kind']=='label' and r['name']=='I05')
        edited = [r for r in edited if r['source_id'] != deleted]
        doc = c.convert_airport('LFPG', saved['recipes']['LFPG'], edited, source['colors'])
        result = {f['id']:f for f in doc['features']}
        assert deleted not in result
        assert result[gate['source_id']]['properties']['text-field']=='RENAMED'
        assert result[gate['source_id']]['geometry']==gate['geometry']
        assert result['LFPG-regression-new']['properties']['style_id']==result[gate['source_id']]['properties']['style_id']
        assert result['LFPG-regression-new']['properties']['vsmr_group_ids']==result[gate['source_id']]['properties']['vsmr_group_ids']

        # Runtime customizations still apply independently of native geometry.
        recipe = copy.deepcopy(saved['recipes']['LFPG'])
        recipe['document']['metadata']['background_colors']['dark'] = '#123456'
        recipe['document']['styles']['label.gates']['paint']['zoomLevel'] = 11
        custom = c.convert_airport('LFPG', recipe, original, source['colors'])
        assert custom['metadata']['background_colors']['dark']=='#123456'
        assert custom['styles']['label.gates']['paint']['zoomLevel']==11
        assert [f['geometry'] for f in custom['features']]==[r['geometry'] for r in original]

        broken = scratch / 'broken.zip'
        broken.write_bytes(b'not a zip')
        try:
            c.run(broken, scratch / 'GeoJSON')
            raise AssertionError('Malformed ZIP accepted')
        except zipfile.BadZipFile:
            pass
        assert {p.name:p.read_bytes() for p in (scratch / 'GeoJSON').iterdir()} == actual_files
        assert not list(scratch.rglob('Conversion report.json'))
        assert not list(scratch.rglob('Conversion summary.txt'))
    print(f'PASS: {len(expected_files)} GeoJSON files; {len(native_gng)} native features; exact GNG/KMZ agreement; source edits; palettes/groups; explicit local/GitHub selection.')


if __name__ == '__main__':
    main()
