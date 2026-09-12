# vSMR runtime customizations

Geometry and label text now live in GNG and KMZ, not here. There is no source
geometry backup, matching baseline, or numeric geometry-reference table.

- **Airports/<ICAO>/settings.json**: palettes, background, text zoom/size, groups,
  runway information and saved runway modes.
- **Airports/<ICAO>/features.json**: runtime overrides keyed by the native feature
  ID. A string value selects a style; an object sets style/group/property options.
- **common.json**: shared styles and settings, stored once.

## Editing

All palette color values are defined in **../Colours.sct** using standard
EuroScope decimal BGR values. These JSON files reference their names:
`DARK_<ROLE>`, `LIGHT_<ROLE>` and `REAL_<ICAO>_<ROLE>`. Airport-specific Light
variants include the ICAO. Change the definition to edit its referenced colors;
do not replace the name with a hex literal. The converter resolves names from
the selected source's Colours.sct and rejects missing definitions.

Edit a common entry to change all airports referencing it. An airport can override
individual fields without copying the shared definition:

```json
{
  "$ref": "style.line.runwayconcrete.555555",
  "paint": { "stroke": "TEXT_COLOR" }
}
```

Nested objects merge; lists replace the shared list. The actual reference names
are in the airport files. To remove inherited fields, replace the reference with
a complete inline object.

In settings.json:
- `metadata.background_colors`: background by palette.
- `styles.<id>.paint`: fill, stroke, text color, text size and zoomLevel.
- `paint.palette-overrides.light` / `.real`: alternate palette colors.
- `vsmr_groups`: group names, visibility, runway filters and accents.
- `metadata.runways` / `saved_active_runways`: runway information and selections.

In features.json, for example:

```json
"LFPG-example-id": {
  "style_id": "label.gates",
  "vsmr_group_ids": ["stands-and-gates"]
}
```

Native feature IDs come from standard `Placemark id="..."` attributes in KMZ.
GNG geometry is matched to these placemarks without custom comments. Preserve
KMZ IDs when editing existing objects; unmatched GNG objects get generated IDs.
A `null` property override omits that property. Optional
`metadata.exclude_features` is a list of native IDs to hide only in vSMR.

Edit geometry, label names and label positions in **both GNG and KMZ**. Do not
copy them back into Preserved. GNG is authoritative; matching KMZ data preserves
multipart topology, holes and placemark order. If the two geometries differ,
GNG takes priority and the regression check asks you to synchronize them.

Run `python Script/aviso_converter.py --local` after local edits. Double-click
conversion intentionally prefers the published GitHub pack.

Shared defaults are `BACKGROUND_COLOR`, `TEXT_COLOR` and `TEXT_HALO_COLOR`.
LFPG Real uses `REAL_LFPG_BACKGROUND_COLOR`; all other backgrounds share the
default. Equal color values share one definition across airports and palettes,
so changing that definition changes every reference to it. Sections and RGB
comments in Colours.sct make the decimal BGR values easier to edit.
