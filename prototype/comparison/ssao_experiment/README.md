# 原版 3D 的 Godot 4.7 SSAO 单因素对照

日期：2026-09-25。此实验为 Issue #20 的独立证据，不改正式场景和产品任务状态。S0 与 S1 均从原 A 的透视镜头、主光、环境光、房间、角色和任务 UI 起步；唯一差异是 `Environment.ssao_enabled` 由 `false` 变为 `true`，半径和强度保留 Godot 默认值。仍使用本机 Godot 4.7 的 **GL Compatibility**；没有切到 Forward+ 或打开其它后期效果。

运行 `python3 prototype/comparison/run_ssao_experiment.py`，初次在新 worktree 运行前先执行 `/Applications/Godot.app/Contents/MacOS/Godot --headless --editor --import --path prototype/godot`。八次真实窗口采集覆盖 S0/S1 × 360×320/1280×720 × 日/夜，渲染器与物理像素口径在日志和 [manifest.json](manifest.json)。小窗逻辑 360×320 的 PNG 物理尺寸为 720×640（Retina 2×）；请在 [对照页](index.html)按 **360×320 CSS 像素、浏览器 100%** 观看，不要放大后判读小窗。

## 观察

本次按 UI 中的场景矩形计算 RGB 差分，阈值为任一色道相差至少 3/255：小窗白天 S0/S1 有 950/194,016 像素达到阈值（0.490%），夜晚 1,077/194,016（0.555%）；全窗白天 0.621%，夜晚 0.733%。日志中的 `SSAO_ENABLED` 与 `SSAO_VARIANT` 核对了实际开关，Godot 退出码、脚本错误和图片存在性同时检查，不能仅凭 PNG 文件产生就记为成功。上述百分比**不是视觉质量分数**，只是同机同版本同场景的差异大小；不同帧时间和阴影抖动仍可能贡献一部分像素差。

控制样本校准：S0 的 `360×320` 白天 PNG 与前一轮桌面实验 D0 的同条件 A 基线 SHA-256 完全一致；差异计算仅裁取 UI 中的场景矩形，不计顶部时钟或下方文字。

我在原大小窗观看，椅子、人物与地面接触没有可稳定辨出的改善；现有角色像素占比小，场景的投影和轮廓问题没有因默认 SSAO 开关解决。这只约束“默认参数、此镜头和此场景”的实测，不能推出 SSAO 对精修角色、其它镜头或 Forward+ 都没有价值。无长时 GPU/电池消耗测量，因此不建议现在将开关并入产品默认值。下一轮优先验证角色本身与紧凑构图，保留 SSAO 开关作为后期单独复测项。

Godot 官方 [4.7 渲染器表](https://docs.godotengine.org/en/4.7/tutorials/rendering/renderers.html)与[环境后期文档](https://docs.godotengine.org/en/4.7/tutorials/3d/environment_and_post_processing.html)指出，4.6 起 Compatibility 有简化 SSAO，只有半径和强度可调；此实现与 Forward+ 的效果不同。此前版本文档若说 Compatibility 没有 SSAO，不适用于本机 4.7。官方也说明 SSAO 主要作用于环境光与屏幕内几何，因此不能把它当作几何、阴影贴图或动作制作的替代。
