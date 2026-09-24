# Visual prototype QA and art-direction handoff

Observed on macOS with Godot 4.7 and Blender 5.1.2 on 2026-09-24. This is a playable baseline for Issue #16, not final art or the persistent task system.

## What was checked

| Check | Observation |
|---|---|
| Blender prop | Reinstalled the missing official Blender app behind the stale Homebrew wrapper. `build_lamp.py` exported five meshes with three materials; transforms were applied, face normals recalculated, dimensions/materials asserted. No armature or skin weights are used for this rigid prop. |
| Godot import | Headless editor imported the GLB; runtime QA found the `Blender desk lamp` scene node. |
| Scene and character | Room, desk, student, monitor, calendar and lamp visible at 1280×720. Front/side/back checks found no missing mesh or obvious character penetration. The right arm animates in the started state. |
| Interactions | Mouse computer hotspot, task card, start, completion with typed conclusion plus HTTPS URL, and defer were clicked in the running window. Missing evidence blocks completion. Keyboard shortcuts and close were exercised. |
| Window sizes | 1280×720 and 800×600 were opened. At 800×600, the fixed 16:9 viewport letterboxes vertically; the task panel remains visible but text is small. |
| Captures | The PNG files in `evidence/` came from the Godot viewport using F12, so they contain only the fictional demo scene. |

## Visual defects to resolve before a final style decision

1. The student has a readable chibi outline but looks like assembled primitives. Hair, face, hands, clothing and pose lack character identity.
2. Flat materials and hard lighting make the wall, rug and lamp shade lose depth; the prop palette still needs art direction. The initial render was overexposed and was reduced, but the result remains basic.
3. The room has a large empty left side and few objects that tell a student-life story. The desk, calendar and books are only rough location markers.
4. The checklist is legible at full size but feels like a separate application panel over the room. At a smaller window, type becomes too small and the scene letterboxes.
5. Start only adds a bob and arm movement. The student does not approach, sit at, or look at the computer; completion and defer have text feedback but little in-world response.

## 2D or pixel alternative interface

Keep `fixture/snapshot.json` as this job-specific control sample, then adapt the renderer to the general Goal → Plan → Task → Result contract being designed in Issue #21. A 2D or pixel renderer could replace the room and mascot Node3D subtree with Node2D/Sprite2D/AnimatedSprite2D, retain named action hotspots, and reuse the checklist/detail with explicit command intents. The same student and room should be able to show study actions such as practice and review alongside recruiting actions. The renderer should receive task **view states** from the returned snapshot; domain validation, event IDs, real dates, plan versions and persistence remain with the logic track. This lets Issue #17 compare a 2D scene without rewriting task rules.

Windup is useful only as an example workflow for generating and checking original character assets. Its existing character art is not this product's visual target and is not included here. Any outside or existing asset needs a source and reuse-permission check before import.

## Remaining integration work

The preview loads one static fictional job task and keeps state only in memory. It does not send the future Issue #21 goal/task commands, persist events or plan versions, open an original job page, or label a real application submitted. Those are contract and Issue #17 integration items, not evidence of this prototype's completion.
