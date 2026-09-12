# AVISO runtime settings

- Airports/<ICAO>/settings.json: styles, groups, backgrounds, zoom levels and runway settings.
- Airports/<ICAO>/features.json: overrides keyed by native/matched feature IDs.
- common.json: reusable runtime settings referenced with {"$ref": "name"}.

Colors are named definitions in ../Colours.sct. BACKGROUND_COLOR is the shared
default; LFPG Real uses REAL_LFPG_BACKGROUND_COLOR. TEXT_COLOR and TEXT_HALO_COLOR
are used only for text. Other roles retain their own color references, even
when their initial RGB values match. Original COLOR_* names remain compatible
with upstream native layouts. DARK_*, LIGHT_* and REAL_<ICAO>_* describe AVISO
palette roles. Undefined references are errors.

$ref objects recursively merge local overrides over common settings. Lists
replace inherited lists. Feature overrides can be style ID strings or objects
with style_id, vsmr_group_ids and other runtime properties. A null property
omits that property. metadata.exclude_features hides specified feature IDs.

Geometry and labels belong in GNG/KMZ, not in Data. Matching placemark IDs
preserve overrides; unmatched source edits may generate new IDs that need new
overrides. Official GitHub layouts may differ from the customized local ones.
