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

The 10,168 retained vSMR features are integrated into standard native files.
Runway reference lines have been removed from all datasets.
Existing GNG FIR directories were retained; added datasets use GNG/Additional.
KMZ files use normal KML geometry, styles, names and placemark IDs. Extra archive
assets are retained. LFXX and the separate LFMM coastline remain reference data.

GNG files use ordinary native regions, line segments and text rows:

```text
COLOR_RunwayConcrete
N049.00.00.0000 E002.30.00.0000
N049.00.01.0000 E002.30.00.0000
N049.00.01.0000 E002.30.01.0000
N049.00.00.0000 E002.30.00.0000
```

KML placemarks retain standard IDs for runtime customizations. GNG contains no
feature ID comments and needs no custom syntax. The converter matches GNG
coordinates and colors to KML placemarks, including multipart geometry and holes.
Shared line segments may belong to multiple KML features (such as arrow groups).

Fractional seconds keep the source precision. Polygon holes use zero-width
bridges in GNG and standard innerBoundaryIs rings in KML. KMZ preserves multipart
topology and placemark ordering. Labels use GNG text at the matching coordinate.
New or changed unmatched GNG geometry remains live with a generated ID; if an
edit changes its identity, review its feature overrides in Preserved. Keep GNG
and KMZ geometry synchronized when maintaining a layout.

All color values are standard #define entries in Colours.sct: LIGHT_*, DARK_*
and REAL_<ICAO>_*. GNG and KML style names use LIGHT_* entries; KML also embeds
its native color values for authoring applications. Preserved references the
palette names and stores vSMR groups, zoom levels and runway settings. Real palettes are not created for every airport.

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
