# AVISO converter

Double-click **Convert AVISO.cmd** on Windows. Select local source (Enter/1) or
the original official GitHub source (2). Python 3.10+ is required.

For unattended conversion:

```powershell
python Script/aviso_converter.py --local
python Script/aviso_converter.py --github
python Script/aviso_converter.py --source "path/to/folder-or.zip"
```

No arguments means local source; it never contacts GitHub. Explicit GitHub
selection downloads vaccfr/France-Ground-Layouts master and reports network
errors without silently using another source. Local input accepts a checkout,
an extracted outer repository folder, or a ZIP with GNG/, KMZ/ and Colours.sct.
The root source is preferred, then equivalent inputs under Input/.

GeoJSON/ is generated output. All products are validated before writing files.
An explicit source selection overwrites the existing GeoJSON output; official
source may contain different airports and geometry from a customized checkout.
No reports, summaries or cached downloads are generated.

Data/ contains runtime styles, groups, zoom levels, runway settings and
per-feature overrides. Colours.sct contains original native COLOR_* definitions
plus AVISO palette entries. When external input lacks the AVISO palette entries,
local definitions supply them; definitions present in the selected source win.
Local geometry provenance is labeled local, and GitHub provenance names the
official repository.

## Geometry and identities

GNG uses standard regions, line segments and text rows without feature comments.
Matching KML placemarks supply stable identifiers and multipart/hole topology.
Unmatched GNG remains live with deterministic IDs. KMZ-only layouts without
placemark IDs receive deterministic IDs as well. New geometry does not
necessarily inherit the groups of a differently identified previous object.
Keep both native representations synchronized when editing a layout.

## Verification

```powershell
python Script/verify_converter.py
python Script/verify_upstream.py
```

The full regression check compares generated customized layouts with GeoJSON/.
The upstream check also works against unmodified official layouts, which need
not have matched GNG/KMZ geometry or committed GeoJSON snapshots.
