# Godot A in a 360 × 320 WebKit window: feasibility evidence

This is an isolated export of the existing **A · 原 3D** comparison scene from PR #35. It does not change the original Godot scene, the native companion, task data, or the art-direction decision. All six images are actual `WKWebView.takeSnapshot` results from a 360 × 320 point macOS window on a 2× display; they are 720 × 640 PNGs.

## Result and controls

| Run | Web export / copied scene change | Actual WKWebView observation |
| --- | --- | --- |
| P0 | Canvas resize `Project`; original `screen_get_scale()` and `window_set_size(logical × scale)` | WebGL2 starts, but the UI occupies part of the canvas with a large black band; CJK characters are missing. [Capture](evidence/P0-project-policy-native-scale.png) |
| P1 | P0 plus Web `display_scale = 1` | Content moves to the upper half; black lower half. This single change does not fix sizing. [Capture](evidence/P1-project-policy-web-scale.png) |
| P2 | P1 plus skip Web `window_set_size`; canvas resize `None` | Content is smaller and offset; black area remains. [Capture](evidence/P2-none-policy.png) |
| P3 | P2 with canvas resize `Adaptive` | Original A fills the 360 × 320 canvas, but Chinese labels render as missing-glyph boxes. [Capture](evidence/P3-adaptive-no-font.png) |
| P4 | P3 plus local Noto Sans SC subset as the Godot theme font | Full-frame A and readable fictional task labels. [Capture](evidence/P4-adaptive-noto-font.png) |
| P5 | P4 plus an AppKit `NSEvent` down/up sent directly to this probe's WKWebView at the Start button | Task changes from `○ / 待开始` to `● / 进行中`, Start becomes disabled, and the footer says the character started the task. [Capture](evidence/P5-native-pointer-start.png) |

The `P0 → P3` evidence points to a **Web sizing path conflict**, not a broken model: the desktop comparison multiplies a logical window size by display scale, while the browser's 360 × 320 CSS canvas already has a 720 × 640 backing buffer on this Retina screen. The exact Godot/WebKit internals need a production integration test; the observed fix is a Web-only export configuration, not a change to desktop A.

The same export was opened in the Codex in-app browser. Its first `Project`-policy build rendered with the same crop and missing glyphs. After P4, a reload showed full-frame A and readable Chinese. Pressing `n` while the canvas was focused changed day to evening lighting. Browser pointer targeting was not available through that browser control surface; P5 is the standalone native WebKit pointer proof. The WK probe logs `navigation_finished`, `webgl2=true`, canvas backing `720×640`, a removed Godot loading overlay, the title `目标书桌 · A · 原 3D`, and no JavaScript error messages in its sampled run.

## Size and source

- Installed editor: Godot `4.7.stable.official.5b4e0cb0f`; local export-template directory was initially empty.
- Official [4.7 release asset](https://github.com/godotengine/godot-builds/releases/tag/4.7-stable) `Godot_v4.7-stable_export_templates.tpz`: 1,279,207,690 bytes. The archive supports HTTP byte ranges, so `remote_template_probe.py` read its ZIP directory and fetched only `templates/web_nothreads_release.zip`: 10,243,416 bytes saved / 10,223,004 bytes transferred. The archive itself is not in this repo.
- P4 export: `index.wasm` 39,509,339 bytes and `index.pck` 560,992 bytes; no-font P3 pack was 519,640 bytes. These are uncompressed local files. No CPU, GPU, idle, or long-running memory comparison has been made.
- Font test: `fetch_noto_subset.py` asked the Google Fonts CSS API for 246 unique printable characters in this **fictional comparison UI** and fetched a 55,080-byte Noto Sans SC TTF subset. The source [Noto CJK Sans](https://github.com/notofonts/noto-cjk/tree/main/Sans) is under [SIL OFL 1.1](https://github.com/notofonts/noto-cjk/blob/main/Sans/LICENSE). The downloaded subset remains local and ignored by Git. It covers this fixture's text only; production must cover real user text with an appropriate licensed font strategy.

## Reproduce locally

```sh
python3 prototype/comparison/web_embed_feasibility/remote_template_probe.py \
  'https://github.com/godotengine/godot-builds/releases/download/4.7-stable/Godot_v4.7-stable_export_templates.tpz' \
  1279207690 \
  --extract templates/web_nothreads_release.zip \
  --out prototype/comparison/web_embed_feasibility/_local_templates
python3 prototype/comparison/web_embed_feasibility/fetch_noto_subset.py
python3 prototype/comparison/web_embed_feasibility/build_web_probe.py \
  --font prototype/comparison/web_embed_feasibility/_local_templates/NotoSansSC-fictional-subset.ttf
python3 -m http.server 8811 --bind 127.0.0.1 \
  --directory prototype/comparison/web_embed_feasibility/_build/web
```

In another terminal on macOS:

```sh
swiftc -framework AppKit -framework WebKit \
  prototype/comparison/web_embed_feasibility/WKWebViewProbe.swift \
  -o prototype/comparison/web_embed_feasibility/_build/wk_probe
prototype/comparison/web_embed_feasibility/_build/wk_probe \
  http://127.0.0.1:8811/ \
  prototype/comparison/web_embed_feasibility/_build/wk_snapshot.png \
  --click-start
```

The build script copies `prototype/godot/` into ignored `_build/project` and changes only that copy: comparison main scene, baseline route, 360 × 320 viewport, Web display scale, Web window-size call, and optional theme font. It exports with `html/canvas_resize_policy=2` (Adaptive). The copied source and generated export are local test artifacts; this PR commits only scripts, notes, and small screenshots.

## Integration boundary

P4/P5 prove **the existing full comparison UI** can render and receive input inside a standalone macOS WKWebView. The actual companion at `127.0.0.1:8794` was not modified or embedded by this probe. Directly placing this export alongside the HTML workbench would duplicate checklist and task buttons. A production integration should export a **scene-only** Godot canvas, then pass the same goal/task state into it from the existing local workbench. Task selection and completion must continue to be owned by the workbench, with Godot limited to visual state and explicit hotspots. Godot's [JavaScriptBridge](https://docs.godotengine.org/en/4.7/classes/class_javascriptbridge.html) supports a Web-side event bridge, but that bridge has not yet been implemented or measured here.

The [Godot 4.7 Web export guide](https://docs.godotengine.org/en/4.7/tutorials/export/exporting_for_web.html) specifies WebGL2/Compatibility rendering, single-threaded default Web exports, and active-tab background pausing. The observed standalone WKWebView startup and click do not establish that a hidden/minimized companion will keep animating or meet an idle-resource target. That requires a separate native-window integration run.
