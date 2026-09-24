# 同场景运行对照（#20）

## 2026-09-24 用户评审后的纠偏

用户认为 A 的光影与真实感优于 B，C 表现一般。B 的旧称“改良”不是质量结论；当前改称“3D 试验”。D 复用了 C 的绘制代码并降低内部渲染分辨率，**不能作为真正像素美术路线的评估样本**，也不能用它否定像素路线。旧 PNG、视频、日志与运行代码保留，画面内旧标签属于历史记录。

新增角色、房间和 UI 实现已暂停，须先与用户讨论。见 [本轮研究](ROUND2_RESEARCH.md)：A/B 的光照、投影和几何差异是源码支持的机制线索，尚未通过单因素实验确认各因素贡献；许可候选均未下载或采用。原参考视频的屏幕提示词仍待主协调任务直接核验，本轮不把旧观看摘要或 ASR 当成新证据。

先打开 [index.html](index.html)：默认按逻辑尺寸并排看 A 原 3D 与 B 3D 试验；可切换 800×600、1280×720、昼夜、任务状态和交互短片，也可展开 C 等距 2D / D 降采样实验。原始图片和录屏都来自本机实际运行。

## 运行

需要 Godot 4.7。仓库根目录执行：

```sh
Godot --path prototype/godot res://comparison/main.tscn
```

macOS 官方应用的可执行文件为 `/Applications/Godot.app/Contents/MacOS/Godot`。默认打开 360×320 逻辑尺寸右上角小窗；Retina 2× 对应 720×640 原始像素。完整应用支持 1280×720，另有 800×600 对照。命令行可指定：

```sh
Godot --path prototype/godot res://comparison/main.tscn -- --route=2d --size=800x600 --phase=evening
```

`route` 为 `baseline / 3d / 2d / pixel`。四模式共用三项虚构任务与操作逻辑；切画风和尺寸保留本次运行状态，关闭后重置，不连接真实工作台。

- 电脑：当前任务的结果面板；日历：下一项任务。小窗两端是快捷按钮，完整应用按钮贴近物件。
- 开始 → 填一条虚构结果 → 保存；空结果不能完成。延期没有扣分、惩罚或虚构日期。
- 展开进入完整应用，收起成为 80×80 逻辑尺寸的小房子入口。点击恢复。
- 完整应用提供普通窗/置顶、半透按钮。快捷键：`M` 画风、`N` 昼夜、`H` 收起/恢复、`T` 置顶、`O` 半透、`F12` 导出当前应用截图。
- 透明是实验功能。跨应用穿透、全屏、Mission Control、双显示器行为没有验收通过；使用默认实色窗口无需依赖这些能力。

## 重建证据

不要并行启动多个采样进程。采集会开关真实应用窗口，不用于无人值守日常运行。

```sh
python3 prototype/comparison/run_evidence.py
python3 prototype/comparison/record_interactions.py
python3 prototype/comparison/run_evidence.py --performance
```

脚本接受 `--godot` 指定可执行文件；录屏另需 `ffmpeg`。矩阵为四模式 × 三尺寸 × 两时段，白天额外保存开始、完成、延期状态及操作日志。短片采样真实 viewport 帧后按 10 fps 编码，未加入虚构动作；不是用于分析精确时序的恒定时钟录屏。性能采样单独执行，每模式预热 30 秒，再采样 60 秒。

截图文件名使用**逻辑尺寸**，PNG 像素、显示缩放见同名 JSON；这台机器为 2×。普通渲染使用高分屏分辨率，像素研究内部使用逻辑场景尺寸的约 1/3，再最近邻放大，任务 UI 保持高分辨率。像素比例经过取整，非逐像素手工美术、非严格整数缩放。

`desktop-test.html` 是本地点击计数与斜纹背景控制样本，无网络请求。`--desktop-background-test` 只用于将窗口移到该背景上做隔离检查。正式入口仍为右上角。

## 评审文件

- [QA_RESULTS.md](QA_RESULTS.md)：实际结果、环境和限制。
- [QUALITY_GATE.md](QUALITY_GATE.md)：验收条件，未测不记通过。
- [VISUAL_REVIEW.md](VISUAL_REVIEW.md)：独立审图记录。
- [ASSET_LICENSES.md](ASSET_LICENSES.md)：原创源、引擎和字体边界。

本轮只提供美术路线选择证据，不决定首版画风，不实现正式 Goal/Plan/Replan 契约，也不比较模型能力。历史 3D 原型与截图保留在上一级目录。
