# Autumn Desk: original 3D scene prototype

This is the visual track for [Issue #16](https://github.com/johnnyzhang-eng/career-workbench/issues/16). It is an original dorm desk and stylized student made from editable Godot primitives, plus a Blender-generated desk lamp. The task comes from `godot/fixture/snapshot.json`, which follows the proposed snapshot v0 in PR #14. All content is fictional.

## Run and interact

Godot 4.7 is required. Open `prototype/godot/project.godot` in Godot and press **F5**, or run:

```bash
/Applications/Godot.app/Contents/MacOS/Godot --path prototype/godot
```

- Click the computer, calendar, or task card to open the task. Enter also opens it; Escape closes it.
- Start makes the student move while checking the source. Complete requires a typed conclusion and an HTTPS source URL. Defer gives a visible deferred state without inventing a deadline.
- F12 saves a clean viewport PNG to `prototype/evidence/`. This screenshot contains only fictional scene content.
- Keys 1, 2 and 3 show the room, student side, and student back for visual inspection.
- Reloading starts again from the fixture. Preview transitions live in memory; Issue #17 will connect the real event commands and persistence. The prototype never records a real submission.

The clock reads the local system time. When the fixture date differs from the computer's date, the heading changes to **Fixture day** rather than presenting the old task as today's real task.

## Asset source and QA

`godot/main.gd` generates the room, furniture, student and their materials. The student uses separate rigid meshes; the right arm is animated as a Node3D pivot. There is no armature, skin deformation or vertex weighting in this slice. `blender/build_lamp.py` creates the editable Blender desk lamp, applies transforms, checks every mesh has a material and valid dimensions, recalculates face normals, then exports `godot/assets/desk_lamp.glb`. If the GLB has not been generated yet, the room shows a Godot primitive lamp in the same position.

```bash
blender --background --python prototype/blender/build_lamp.py
/Applications/Godot.app/Contents/MacOS/Godot --headless --path prototype/godot --editor --quit
/Applications/Godot.app/Contents/MacOS/Godot --headless --path prototype/godot --script res://qa.gd
```

The Godot QA script checks fixture loading, both hotspot collision bodies, start, completion evidence gate, completed state protection, and defer. Inspect the room at 1280×720 and 800×600; at the smaller window the fixed 16:9 viewport letterboxes vertically. No third-party art or personal applicant data is included.

## Integration boundary

The scene's `in_progress`, `completed` and `deferred` flags are temporary visual feedback. They are not the Issue #15 domain states or commands. The logic track will own the authoritative snapshot, event ID, validation and persistence. To integrate, replace these local handlers with calls to that command interface and refresh the scene from its returned snapshot; do not infer application submission from task completion.
