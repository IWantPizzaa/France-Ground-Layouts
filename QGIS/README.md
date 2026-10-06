# QGIS AVISO projects

Open **LFXX.qgz** for all 160 airports, or **Aeroports/ICAO.qgz** for one airport.
Keep these projects together with **AVISO.gpkg**: all data paths are relative.
The projects were saved with QGIS 4.2.3.

Geometry, text, groups and styles come directly from the final vSMR GeoJSON.
The selected palette is Real for LFBO, LFLL, LFML, LFMN, LFPG, LFPO and LFSB;
other airports use Light. Airport projects have their own palette background.
LFMM Region Coastline is excluded.

The large background polygons have been removed from LFMT, LFTW, LFMA, LFMC,
LFKS, LFLU, LFMH, LFLP, LFST, LFPM, LFOQ and LFOT. This data set therefore
contains 10,760 features. Labels, single lines, multipart lines and polygons
are separate editable layers; their original geometry types are preserved.

## Edit and export

1. Open the complete project or an airport project in QGIS.
2. Edit the geometries and save layer edits. The underlying coordinates must
   remain **EPSG:4326**; the project's display CRS can stay EPSG:3857.
3. For a label, edit `text`; `name` can be edited independently. For an object,
   edit `fill_color` or `line_color` in `r,g,b,a` or `#RRGGBB` format, plus `line_width` as needed.
   Text fields include `text_color`, `text_font`, `text_size`, `halo_color` and
   `halo_width`. Data-defined colors take precedence over the QGIS layer symbol's
   default color; change these attributes to export a color edit.
4. Save the project, then double-click **Script/Convert AVISO.cmd** and select
   **3 — QGIS projects → AVISO GeoJSON**. Enter exports LFXX; supplying an airport
   project exports that airport only.

The export writes `GeoJSON/`. Python 3.10+ is sufficient; the reverse converter
does not require QGIS's Python bindings or external packages. It reads the saved
project and GeoPackage, not the state of an unsaved QGIS window.

Original AVISO palettes, styles, runtime settings and groups are retained.
A color edit creates a style variant for the edited objects in the selected
palette; it does not change other airports, objects or themes. Changing an
airport project's canvas background updates that airport's selected background.
Geometry deletions are reflected in the exported GeoJSON, including the 12
removed rectangles. Duplicated features receive distinct IDs; a new feature
must have a known `airport` and `style_id`. Leave `source_id` empty for automatic
ID generation. Only the airports in the selected project are written, and
unrelated GeoJSON files are left intact.

`properties_json` and `feature_extra_json` retain original feature information.
The nonspatial `geojson_documents` GeoPackage table retains the full original
metadata, palette and group definitions. These preserved fields are managed by
the converter; use the editable attributes above for changes.

The existing Local/GitHub options still convert GNG into GeoJSON. Running those
options replaces generated GeoJSON with their selected GNG source; QGIS edits
remain in AVISO.gpkg and can be exported again with option 3. Exporting QGIS does
not modify GNG, KMZ, Settings or the saved QGIS projects.
