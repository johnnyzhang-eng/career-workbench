# Scene-only Godot A: read-only state bridge

This is an isolated follow-up to the [Godot WebKit feasibility probe](../README.md) in draft PR #44. It keeps the existing **A · original 3D** room at **360 × 320 CSS points**, removes all Godot checklist/buttons, and consumes only the workbench's scene read model. The workbench remains the sole owner of goals, task actions, evidence, and completion.

## Boundary and behavior

```
existing local workbench GET /api/state
  -> scene {phase, mode, activity_state}
  -> same-origin host.html (enum validation, change detection)
  -> Godot JavaScriptBridge careerRoomSetScene(JSON string)
  -> original A room light/character state + temporary visual cues
```

The local proxy and host forward **only** `phase: day|evening`, `mode: idle|desk|study|interview|rest`, and `activity_state: unknown|planned|declared_active|observed|self_selected`. IDs, titles, evidence, and completion never cross this bridge. `planned` and `unknown` do not depict work; `declared_active` and `observed` show the selected activity. `self_selected` can show the mode cue without an in-progress character state. A connected tool event may supply `observed` through the existing workbench read model, but this scene does not infer completion from it. The mode props in this probe are simple reversible state markers, **not an art-direction proposal**.

`host.html` currently polls every two seconds. The `demo=sequence` fixture progresses by API request count in one probe process; it is deterministic evidence for a changing read model, not a production scheduler. The phase comes from `/api/state`; the scene does not read the system clock itself.

## Reproduce locally

Requires Godot 4.7 and the official `web_nothreads_release.zip` template. PR #44's [template fetch instructions](../README.md) download only the 10.24 MB entry from the official 4.7 release archive; copy or point `--template` to that local ZIP. No downloaded binary is committed here.

```bash
python3 prototype/comparison/web_embed_feasibility/scene_state_bridge/build_scene_only.py \
  --template /absolute/path/to/web_nothreads_release.zip
python3 prototype/comparison/web_embed_feasibility/scene_state_bridge/serve_scene_bridge.py --port 8822
# Open http://127.0.0.1:8822/?demo=sequence in a browser.
```

For the existing local workbench read model, run this server instead:

```bash
python3 prototype/comparison/web_embed_feasibility/scene_state_bridge/serve_scene_bridge.py \
  --port 8823 --upstream http://127.0.0.1:8794/api/state
# Open http://127.0.0.1:8823/ . This proxy uses GET only.
```

Optional standalone native WKWebView probe:

```bash
swiftc -framework AppKit -framework WebKit \
  prototype/comparison/web_embed_feasibility/scene_state_bridge/WKSceneBridgeProbe.swift \
  -o /tmp/wk_scene_bridge_probe
/tmp/wk_scene_bridge_probe 'http://127.0.0.1:8822/?demo=sequence' \
  /tmp/wk_scene_bridge_capture
```

The native probe opens a separate 360 × 320 window and exits after 18 seconds. Build files under `_build/` and local templates are ignored. It does not use or alter the existing companion window on port 8794.

## Actual run, 2026-09-25

- Godot 4.7 scene-only export succeeded. `index.wasm` was **39,509,339 bytes**, `index.pck` **524,220 bytes**. The Web export was served locally; the generated files are ignored, not part of this PR.
- The macOS WKWebView probe reported iframe bounds **360 × 320 CSS**, canvas backing width **720** on a 2× display, `careerRoomSetScene` as a function, and no logged JavaScript errors. Its [sequence log](evidence/wk-sequence.log) recorded `appliedCount` **1 → 2 → 3**, with `evening/idle/planned` at sample 4, `day/study/declared_active` at sample 8, and `evening/idle/planned` at sample 14. Native snapshots: [before](evidence/wk-sequence-early.png), [active study](evidence/wk-sequence-middle.png), [after](evidence/wk-sequence-late.png). The later image returns byte-for-byte to the first after PNG metadata stripping.
- A separate `evening/study/planned` fixture was applied in WKWebView ([log](evidence/wk-planned-study.log), [snapshot](evidence/wk-planned-study-late.png)). Its snapshot has the same image bytes as the `evening/idle/planned` control: the planned study mode alone did **not** show an active book cue.
- A separate local server did a **read-only GET** of the running workbench at `127.0.0.1:8794/api/state`; its client-facing response contained only the three scene fields. The [WK log](evidence/wk-live.log) shows `evening/idle/planned` applied in the 360 × 320 window. This is a live read-model integration probe, not a write or a complete goal workflow.

The base room and character are the existing procedural A assets. This subdirectory adds no third-party art, licensed asset, font, private photo, personal task data, or external service call. Screenshots are from fictional fixture states and have ancillary PNG metadata removed.

## Integration still needed

The actual native companion's HTML has **not** been edited. It needs a deliberate scene slot beside its existing checklist and task controls, and a single owner for polling `/api/state`; this probe uses its own host page to avoid touching in-flight UI changes. Before selecting a production route, test the integrated small/expanded window, long-running CPU/GPU use, hidden/background pause behavior, accessibility fallback, and export packaging. The official [Godot JavaScriptBridge documentation](https://docs.godotengine.org/en/4.7/classes/class_javascriptbridge.html) describes the Web callback API; the [Web export guide](https://docs.godotengine.org/en/4.7/tutorials/export/exporting_for_web.html) notes background-tab processing limits. This probe does not claim reliable offscreen animation or final art quality.
