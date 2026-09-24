# 360 × 320 room runtime budget probe

This is a resource **measurement**, not an art decision or an integrated product benchmark. It tests the scene-only Godot A Web export from draft PR #47 in a fresh 360 × 320 point macOS WKWebView. The fixture is the fictional `evening/idle/planned` state; it reads no personal goal or activity data. A second run loads the existing 2D pixel room component from branch `fix/native-goal-selection` at `6051450`, in the **same probe WKWebView and window size**. The 2D run is a renderer-only control, not the full native companion with its checklist and server.

## Reproduce

Use the PR #47 [scene export steps](../scene_state_bridge/README.md) first. Its ignored local `_build/web/godot` files are required; the official Godot 4.7 Web template is not committed. With this branch checked out, run:

```bash
python3 prototype/comparison/web_embed_feasibility/scene_state_bridge/serve_scene_bridge.py --port 8833
python3 prototype/comparison/web_embed_feasibility/scene_runtime_budget/sample_runtime.py
```

For the optional 2D renderer control, check out the `fix/native-goal-selection` worktree at `6051450` and run:

```bash
python3 prototype/comparison/web_embed_feasibility/scene_runtime_budget/serve_pixel_control.py \
  --source-root /absolute/path/to/career-workbench-native-goal-selection --port 8834
python3 prototype/comparison/web_embed_feasibility/scene_runtime_budget/sample_runtime.py \
  --kind pixel --url http://127.0.0.1:8834/ \
  --out prototype/comparison/web_embed_feasibility/scene_runtime_budget/evidence/pixel_control
python3 -m unittest prototype/comparison/web_embed_feasibility/scene_runtime_budget/test_sample_runtime.py
```

The sampler compiles only its isolated `WKRoomBudgetProbe.swift` into ignored `_runtime/`. It orders the window visible for 30 seconds after scene readiness, hides it with `NSWindow.orderOut` for 25 seconds, restores it for 20 seconds, and exits. It captures the first frame and a frame five seconds after restoration. Hiding does not close the WKWebView or the process. `window.isVisible` is logged, but actual foreground occlusion by other apps is **not** measured. The Godot host uses `/api/state` polling every two seconds, so the measured 3D budget includes this small local HTTP activity. The pixel control does not poll a server after asset load.

To reproduce the separate state-change-on-restore check, start the same scene server on port 8835 with `--fixture-file` pointing to this probe's ignored `_runtime/switch_fixture.json`, then run:

```bash
python3 prototype/comparison/web_embed_feasibility/scene_state_bridge/serve_scene_bridge.py \
  --port 8835 --fixture-file /absolute/path/to/scene_runtime_budget/_runtime/switch_fixture.json
python3 prototype/comparison/web_embed_feasibility/scene_runtime_budget/sample_runtime.py \
  --url http://127.0.0.1:8835/ --switch-fixture-on-hidden \
  --out prototype/comparison/web_embed_feasibility/scene_runtime_budget/evidence/state_change_after_hide
```

The sampler creates that fixture before opening WKWebView and changes it from fictional `evening/idle/planned` to fictional `day/study/declared_active` after the window is hidden. This behavioral run is separate from the stable-state resource rows. [Input SHA-256 hashes](evidence/inputs.json) pin the Godot export and the 2D renderer/assets used by these runs.

## Instrument check and accounting

- Before each run, `/usr/bin/yes` is a known CPU-positive control; the sampler requires its accumulated `ps time` to advance by over 0.5 CPU seconds during 1.5 wall seconds. A prior trial incorrectly treated macOS `ps %CPU` as instantaneous. `man ps` says `%CPU` is a decaying average over up to a minute, so [that trial](evidence/pilot_ps_average/summary.json) is retained only as an instrument audit and **its phase CPU values are invalid**.
- Every second, raw [sample records](evidence/samples.jsonl) collect accumulated CPU time, `ps %CPU` diagnostic, and RSS KiB for the host PID and all WebKit XPC processes. CPU percentages in the result table are **differences of accumulated CPU seconds divided by wall seconds**, expressed as percentage of one logical core. Phase windows exclude startup and the first five seconds after hiding/restoring. `ps %CPU` is never used for the phase result.
- WebKit XPC processes have PPID 1 here. A newly seen process therefore cannot be proved to belong to this WKWebView from `ps` parentage. The reported **launch cohort** is limited to WebKit PIDs first seen within five seconds of probe launch; PIDs first seen later are excluded. [The second pilot](evidence/pilot_all_new_webkit/summary.json) recorded another native WebKit app starting roughly 42 seconds later, which would have contaminated a naive “all new WebKit” sum. The clean probe also checks whether its cohort is still present two seconds after the host exits. This strengthens attribution but is still temporal evidence, not a private WebKit ownership API.
- RSS sums are process resident mappings and can double-count shared pages. They are **not** unique memory footprint. A `0.00%` CPU result means no 0.01-second increment of accumulated CPU time was observed across the approximately 15–20-second phase, not literally zero instructions. These tests do not measure GPU energy, battery drain, a full-day background session, app packaging, or the complete companion UI.
- Snapshot PNGs were stripped of all ancillary chunks including EXIF before publication, without recompressing their IDAT image bytes. Each screenshot contains only fictional scene art.

## Actual run on 2026-09-25

Machine: Apple Silicon arm64, macOS 26.6.2, 10 logical CPUs. Godot scene and 2D control each occupy 360 × 320 points and produce 720 × 640 pixel WKWebView snapshots on the 2× display. Details, host/WebKit candidate PIDs, exact phase durations and raw samples are in each `summary.json` / `samples.jsonl` / `events.jsonl` set. The state and images are fictional. An absolute CPU budget has **not** been agreed; the rows below are observations under this machine and these probes.

| Probe | Ordered-visible idle: host + launch-cohort CPU (% one core) | Hidden CPU | Restored CPU | Ordered-visible host RSS / WebKit RSS sum (KiB) | Restoration |
|---|---:|---:|---:|---:|---|
| Godot A room, first clean probe | 1.34 + 54.13 | 0.05 + 10.28 | 1.78 + 16.95 | 64,128 / 102,752 | [initial](evidence/visible-initial.png) and [restored](evidence/restored.png) PNG hashes equal |
| Godot A room, repeat | 1.09 + 100.97 | 0.00 + 9.46 | 1.77 + 0.00 | 59,904 / 387,856 | [initial](evidence/godot_repeat/visible-initial.png) and [restored](evidence/godot_repeat/restored.png) PNG hashes equal |
| Existing 2D pixel room renderer control | 0.05 + 0.00 | 0.00 + 0.00 | 0.00 + 0.00 | 74,640 / 67,216 | [initial](evidence/pixel_control/visible-initial.png) and [restored](evidence/pixel_control/restored.png) PNG hashes equal |

Both stable-state Godot runs completed, created one GPU, one Networking and one WebContent launch-cohort process within 0.6 seconds, and that cohort was gone two seconds after probe exit. The restored JavaScript read returned `hidden:false`, a 720-pixel canvas and the same `evening/idle/planned` state without error. The snapshots prove the previous room frame was displayed again. A separate [state-change run](evidence/state_change_after_hide/summary.json) switched the fictional fixture during the hidden phase; on restoration, its [event log](evidence/state_change_after_hide/events.jsonl) read back `appliedCount:2`, `day/study/declared_active`, and the [restored screenshot](evidence/state_change_after_hide/restored.png) visibly differed from the [initial idle screenshot](evidence/state_change_after_hide/visible-initial.png). This demonstrates new state was applied by the time the window was visible again; it does not isolate whether polling happened while hidden or after restoration. The fresh repeat launch also loaded successfully, but it is not an app restart test with a preserved user workspace.

The 3D WebContent CPU and RSS differ substantially between these short runs, particularly after restoration. This probe suggests a dedicated frame-cap or redraw-on-state-change experiment is worth measuring, but does not establish a steady long-term rate or a pass/fail threshold. The 2D control has different scene content and no read-model polling, so its numbers only bound the renderer comparison in this isolated host. Both routes still need an integrated native-window run with the real checklist, app switching, and longer-duration idle sampling before a production art/runtime decision.
