# AVISO converter

Double-click **Convert AVISO.cmd**. It downloads the native source from
[IWantPizzaa/France-Ground-Layouts](https://github.com/IWantPizzaa/France-Ground-Layouts)
(master), converts it immediately and writes **AVISO/** beside this folder.
The terminal stays open when finished. No prompts, reports, summaries or download
cache files are generated. Python 3.10+ and Windows PowerShell are required.

If GitHub is unavailable or its pack lacks the fork's native feature IDs, local
sources are tried automatically:

1. GNG/, KMZ/ and Colours.sct in this checkout.
2. Those three entries inside Input/.
3. An extracted repository directory inside Input/.
4. A repository ZIP inside Input/, newest first.

Only GNG, KMZ and Colours.sct are source inputs. The converter never executes
anything from a downloaded ZIP. Palettes and runtime settings come from Preserved.

## Maintaining native layouts

All 10,578 original vSMR features were integrated into standard native files.
Existing GNG FIR directories were retained; added datasets use GNG/Additional.
KMZ files use normal KML geometry, styles, names and placemark IDs. Extra archive
assets are retained. LFXX and the separate LFMM coastline remain reference data.

A native GNG feature starts with an ordinary comment:

```text
; Feature: LFPG-example-id
COLOR_RunwayConcrete
N049.00.00.0000 E002.30.00.0000
N049.00.01.0000 E002.30.00.0000
N049.00.01.0000 E002.30.01.0000
N049.00.00.0000 E002.30.00.0000
```

The same feature is a normal KML placemark with `id="LFPG-example-id"`.
Keep these IDs stable and unique. Comments remain comments to native GNG consumers;
no proprietary geometry syntax or KML ExtendedData is used.

Regions, line segments and coordinate/text rows retain their original syntax.
Fractional seconds keep the source precision. Polygon holes use zero-width
bridges in GNG and standard innerBoundaryIs rings in KML. MultiPolygon components
share the same feature comment; KMZ uses MultiGeometry. GNG and KMZ must describe
the same geometry; KMZ preserves topology and original placemark ordering.
Labels use the GNG text row, so editing GNG text updates the next conversion.

Light colors are standard COLOR_* definitions in Colours.sct and KML styles.
Dark/Real palette variants, vSMR groups, zoom levels and runway settings remain
in Preserved. Real palettes are not created for every airport.

## Local changes and checks

Normal double-click conversion deliberately prefers the published GitHub pack.
To preview uncommitted source changes instead:

```powershell
python Script/aviso_converter.py --local
python Script/verify_converter.py
```

An explicit ZIP or directory can also be converted with
`python Script/aviso_converter.py --source "path"`.

The checks run offline. They verify:
- Generated output matches the committed AVISO files.
- Every GNG feature has matching KMZ geometry, color and label text.
- Polygon holes and multipart lines remain equivalent.
- Added, renamed and moved labels follow source data.
- Runtime palettes/groups remain independent of geometry.
- GitHub-first selection, local fallback and invalid-input isolation.

Commit source edits and their regenerated AVISO files together. CI runs the same
checks on pushes and pull requests. AVISO is a generated output folder; store
manual appearance changes in Preserved.

See [the customization guide](../Preserved/README.md) for runtime editing.
