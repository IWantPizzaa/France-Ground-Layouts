# AVISO runtime settings

- Airports/<ICAO>/settings.json: styles, groups, backgrounds, zoom levels and runway settings.
- Airports/<ICAO>/features.json: optional toggle-group assignments keyed by native/matched feature IDs.
- common.json: reusable runtime settings referenced with {"$ref": "name"}.

Colors are named definitions in ../Colours.sct. BACKGROUND_COLOR is the shared
default; LFPG Real uses REAL_LFPG_BACKGROUND_COLOR. TEXT_COLOR and TEXT_HALO_COLOR
are used only for text. Other roles retain their own color references, even
when their initial RGB values match. Original COLOR_* names remain compatible
with upstream native layouts. DARK_*, LIGHT_* and REAL_<ICAO>_* describe AVISO
palette roles. Undefined references are errors.

$ref objects recursively merge local overrides over common settings. Lists
replace inherited lists.

features.json is optional and contains only group assignments:

```json
{
  "line.ground_layout_arrows.east.green": {
    "vsmr_group_ids": ["ground-layout-east"]
  }
}
```

Only LFPG currently needs this file, for six East/West arrow features. Other
features need no entries. Styles are inferred from native color names, geometry
kind and label file categories. Geometry roles follow the selected style;
no per-feature style or rendering overrides are stored or accepted.

Geometry and labels belong in GNG/KMZ, not in Data. Keep IDs stable only for
features explicitly assigned to toggle groups. Ordinary feature IDs are an
output detail, not a mapping that needs manual maintenance. Official GitHub
layouts may differ from the customized local ones.
