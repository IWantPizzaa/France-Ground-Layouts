# France Ground Layouts — vSMR fork

This fork integrates the vSMR additions into native GNG and KMZ source files and
includes a converter for 196 AVISO datasets. Their geometry, text, palettes,
groups and runway settings preserve the original vSMR data, with runway reference
lines removed. Empty datasets have been removed.

**Double-click `Script/Convert AVISO.cmd` on Windows.** The converter reads this
fork's GitHub source first, falls back to local source when unavailable, and
writes the GeoJSON files into `AVISO/`. It asks no questions and generates no
report or summary files. Python 3.10+ is required; there are no extra packages.

- `GNG/`: native regions, lines and labels without feature ID comments.
- `KMZ/`: matching KML placemarks, including polygon holes and multipart geometry.
- `Colours.sct`: the Light palette, including shared custom color definitions.
- `Preserved/`: only vSMR palettes, groups, zoom/runway settings and feature overrides.
- `Script/`: converter, double-click launcher and regression checks.
- `AVISO/`: generated shared-geometry GeoJSON files.

See [converter instructions](Script/README.md) and
[customization instructions](Preserved/README.md). For source edits, run
`python Script/aviso_converter.py --local`, then `python Script/verify_converter.py`
before committing the updated native files and AVISO output.

The original [vaccfr/France-Ground-Layouts](https://github.com/vaccfr/France-Ground-Layouts)
documentation and GPL-3.0 license follow below. Additional datasets are under
`GNG/Additional/`; established airport directories retain their original FIR grouping.

---

<p align="center"><img src="https://i.imgur.com/n17WHdO.png" width="auto"></p>

<p align="center"><br>Official repository for the ground layouts of the French Sector File<br>
<a href="https://www.vatsim.fr/fr" target="_blank">https://vatsim.fr/fr</a> <i>(Version française)</i><br>
<a href="https://www.vatsim.fr/gb" target="_blank">https://vatsim.fr/gb</a> <i>(English version)</i>
</p>

---

## French vACC AVISO Map  

A map displaying the available, work-in-progress and planned airports is available [here](https://www.google.com/maps/d/viewer?mid=1BH-EmsmISqlP5sPrPS61wtXdW6Of-q0y&usp=sharing)  

# Design standard  

## General guidelines  

- As few points as possible should be used to maintain EuroScope's performance while ensuring a sufficient level of accuracy (smooth curves, etc.).
- Only “drivable” areas should be drawn. Consequently, shoulders will not be drawn as aprons, taxiways, or runways.
- To optimize the number of polygons, overlapping polygons should be preferred.
- The associated freetext (taxiways, VFR points and gates) should be updated consequently

## Colors  

- **Runways** must be defined as separate polygons, color **LIGHT_RUNWAY_CONCRETE**
- **Grass runways** must be defined as separate polygons, color **LIGHT_RUNWAY_GRASS**
- **Taxiways** must be defined as separate polygons, with the color **LIGHT_HARD_SURFACE2**
- **Grass taxiways** must be defined as separate polygons, with the color **LIGHT_GRASS_SURFACE2**
- **Aprons** must be defined as separate polygons, with the color **LIGHT_HARD_SURFACE3**
- **Grass areas** must be defined as separate polygons, color **LIGHT_GRAS_SURFACE**
- **Buildings** must be defined as separate polygons, color **LIGHT_BUILDING**
- **CAT I holding points** must be defined as separate polygons, color **LIGHT_STOPBAR**
- **CAT III holding points** must be defined as separate polygons, color **LIGHT_TAXIWAY_ORANGE**
- **Unusable paved areas** must be defined as separate polygons, color **LIGHT_HARD_SURFACE4**
- **Gate centerlines** must be defined as separate lines (under the [GEO] section), using the color **LIGHT_TAXIWAY**
- **Intermediate holding points** must be defined as dashed lines, using the color **LIGHT_TAXIWAY_ORANGE**
  
If you have any questions or issues regarding the creation or updating of an AVISO, please visit the French vACC Discord server.

Palette values are centralized in `Colours.sct` under `DARK_*`, `LIGHT_*`,
and `REAL_<ICAO>_*` names. Preserved files reference these definitions.
