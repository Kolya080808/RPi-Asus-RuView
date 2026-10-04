# Apartment map and device placement

Recorded on 2026-09-30. This document describes the supplied scan and the user's
placement annotations, not a new hardware inspection or sensing experiment.

## Source and generated artifacts

The user scanned the apartment in Polycam Space Mode and supplied
[`3dmodelhome.zip`](../3dmodelhome.zip), containing `30.09.2026.glb`.
The export contains 126 mesh objects, including walls, doors, windows, eight
floor regions, ceilings, furniture, and appliances.

- [Clear plan](../maps/home/floorplan.png) and [SVG](../maps/home/floorplan.svg).
- [Furniture reference plan](../maps/home/floorplan-furnished.png) and
  [SVG](../maps/home/floorplan-furnished.svg).
- [User placement annotation](../maps/home/floorplan-furnished-routers.png).
- [Map geometry and source hash](../maps/home/floorplan.json).
- [Device positions and provenance](../maps/home/devices.json).
- [Generation method and dependencies](../maps/home/README.md).
- [Reproducible generator](../scripts/build_floorplan.py).

`floorplan.json` owns map geometry. `devices.json` owns placement annotations;
regenerating the base plan does not overwrite those annotations. A future
consumer must load both and check the matching GLB hashes.

The panel uses the plot rectangle from the generated image rather than
stretching map bounds over the entire PNG. This keeps device markers aligned
with the map axes and is required for any phone or desktop client rendering
the image.

Hovering a device marker shows its model, region, height, and placement notes.
The information card is positioned relative to the browser viewport and
rendered above the map and other panels, so long placement text is not clipped
by the map container.

## Coordinate convention and accuracy

Plan x = GLB x; plan y = -GLB z; vertical height = GLB y. The plan retains
the source origin. North is unknown. The exported floor extent is approximately
9.35 by 9.70 m, a bounding rectangle rather than an apartment area measurement.
Scale follows the GLB meter convention and has not been physically verified.

R01 has a documented geometry correction in the generated `floorplan.json`:
the Polycam floor mesh contains a curved scan boundary, while the corresponding
room in the 3D model is treated as rectangular like the other rooms. The panel
renders the corrected rectangular footprint and retains the original GLB as the
source for future review; this is a map representation decision, not a claim
that the scan itself was edited.

R01–R08 identify exported floor regions. Their actual room names have not been
confirmed; automatic names such as Bedroom are not treated as ground truth.
The plan shows wall sections at GLB height 1 m, projected doors/windows, and
optional simplified furniture footprints. Scan artifacts, gaps, and curved
walls have been preserved. This is a reference plan, not a surveyed drawing.

Horizontal device coordinates were estimated from the centers of colored
markers on the unresized 2400 by 2400 image. Two decimal places are a storage
convention, not a claim of centimeter accuracy. Heights are user estimates of
placement above the floor, not measured antenna centers.

## Confirmed placement

| Device | Region | Marker | Plan x / y (m) | Height above floor | Placement |
|---|---|---|---|---|---|
| ASUS GT-AX11000 | R08 | Green | 3.10 / 0.10 | About 3 m | On top of a cabinet |
| ASUS RP-AX56 | R07 | Red, left | -1.28 / -3.67 | Floor level | Near a PC, using an extension power strip to accommodate a short cable |
| ASUS RP-AX58 | R02 | Red, bottom | -0.44 / -4.36 | Floor level | Near a PC, using an extension power strip to accommodate a short cable |
| TP-Link RE200 AC750 | R02 | Purple | 3.78 / -4.07 | About 1.40–1.50 m | Near the printer |

The user explicitly identified AX56 in R07 and AX58 in R02. The main router and
TP-Link model names come from the existing hardware inventory; the annotation
confirms their roles/brands and locations. TP-Link's stored height, 1.45 m, is
the midpoint of the reported range. ASUS repeater height 0 m means floor placement.
The router's approximate 3 m placement still needs reconciliation with local
scan height before using a physical 3D propagation model.

Network addresses and CSI capability observations remain in [HARDWARE.md](HARDWARE.md).
Placement on the map does not prove CSI capture from a repeater. TP-Link's IP
address is still unidentified. The monitored peer `A0:36:BC:9B:BF:89` has not
been conclusively assigned to one of the marked devices in this map workflow.
The Pi's exact position, antenna orientations, backhaul paths, wall materials,
and actual room names remain undocumented.

## Decisions from the discussion

1. Keep repository documentation, code comments, and interface text in English.
2. Set triangulation aside; it is not the current work item.
3. Use the map first as a tool for annotating real experiments. The user wants
   to draw routes and indicate where they stood, walked, or waved their arms.
4. Associate positions and activities with times in a specific capture session.
   A route drawing alone is insufficient to align movement with signal changes.
5. Build a small web panel and an API for the same maps, sessions, measurements,
   and annotations, accessible to the user, scripts, and the assistant.
6. Make the necessary collector/timing fixes part of that workflow. Map-based
   annotation takes priority over expanding sensing features.
7. Eventually estimate location without user map hints, comparing predictions
   against separately stored reference annotations. Room/zone recognition is
   the proposed first evaluation target; precise tracking is not established.

The local metadata-only web panel and shared HTTP API are now deployed on the
Raspberry Pi. They support map/device display, experiment points and routes,
read-only session history, and timed reference metadata. CSI capture from the
panel/API is deliberately disabled until retention, export, and cleanup are
defined. No synchronized route dataset or location model exists yet.

See [NEXT-STEPS.md](NEXT-STEPS.md) for the proposed implementation and experiment plan.
