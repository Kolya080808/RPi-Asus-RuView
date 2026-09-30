# Home plan for device placement

Generated from `3dmodelhome.zip`, member `30.09.2026.glb`.

- `floorplan.png`: clear plan for drawing device markers and routes.
- `floorplan-furnished.png`: the same plan with furniture footprints for orientation.
- `.svg` versions: scalable copies for vector editors.
- `floorplan.json`: source hash, coordinate convention, floor triangles, and region IDs.
- `devices.json`: approximate device positions from the user's colored markers in
  `floorplan-furnished-routers.png`. Red identifies ASUS repeaters, green the main
  router, and purple the TP-Link repeater. The user confirmed AX56 in R07 and AX58 in R02. Reported heights are
  approximately 3 m for the router, floor level for both ASUS repeaters, and
  1.40-1.50 m for TP-Link near the printer. These are placement estimates,
  not measured antenna heights. Device annotations are stored separately so regenerating
  the base plan does not erase them; `floorplan.json` contains no device placements.

Open either PNG in an image editor and save an annotated copy. Label the main
router `ASUS`, the repeaters `AX58` and `AX56`, and any other devices by model.
Include each device's approximate height above the floor. Leave the original
plan intact so annotations can be compared against its coordinate frame.

R01–R08 are identifiers for the eight floor regions in the export, not verified
room names. Furniture and door/window classifications come from the model.
Furniture is shown as a projected convex footprint and may be simplified.
Dark outlines are horizontal wall sections at GLB height 1 m; amber dashed
lines mark exported doors and blue lines mark exported windows. Door swing
directions are not inferred. Ceilings are omitted.

The plan uses x = GLB x and y = -GLB z, with GLB y as height. Units follow the
model's meter convention and have not been checked against a physical length.
Compass north is unknown. Unusual walls, gaps, and misplaced furniture are
preserved from the scan rather than silently corrected. Confirm these features
before using the geometry as a constraint in sensing experiments.

To regenerate from the repository root:

```sh
python scripts/build_floorplan.py
```

Requires NumPy, SciPy, and Matplotlib. This runs locally without device access.
