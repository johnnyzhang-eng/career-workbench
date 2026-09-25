# 桌宠空闲图像

- 文件：`Resources/pet-room-idle.png`，1254×1254 RGBA PNG，约 1.4 MiB。入仓前移除了生成文件的附加 `caBX` 元数据块，只保留原始像素的 `IHDR`、`IDAT`、`IEND` 块；隐私脚本会核对 PNG 结构与 CRC。
- 来源：2026-09-25 使用 Codex 内建 ImageGen 生成。虚构学生、房间和物品；没有使用真人照片、参考游戏截图、第三方素材或可识别商标。
- 用途：仅作为原生 74×74 点收起态的静态预览。任务场景由工作台状态决定；此图不代表正在做事或任务已完成。
- 可替换性：`CompanionWindow.swift` 从 app bundle 按文件名加载；未来同名替换即可。保持透明外部、正方形画布、房屋与人物在 74 点窗口中仍可辨认，并在实际亮色/暗色桌面上检查轮廓和关闭按钮重叠。

生成提示词（原文）：

> Create one production-ready transparent PNG asset for a macOS desktop companion in a 74×74 point floating window. A tiny but refined cutaway study-room diorama: a warm small house with a clearly readable roof silhouette and two visible walls, one fictional university student with dark hair seated at a compact desk, warm desk-lamp glow, one book and a small plant. Single coherent miniature 3D / clay-render quality with tasteful real materials and soft lighting, not pixel art, not an app icon glyph. Composition must still read when reduced to 64×64 pixels: large simple silhouettes, house nearly fills square, student visibly distinct from desk, clear dark/light contrast. Straight-on three-quarter view; avoid deep perspective. Isolated object with genuinely transparent outside background, no rounded-square tile, no words, no labels, no logo, no border, no shadow outside its object footprint. Leave a tiny amount of transparent margin around the house for hover animation. One image only.

当前限制：它是一张静态图，无法表达读书、投递、面试准备等不同动作；人物也尚未支持照片生成的一致身份。多状态角色和高质量 3D 房间须按 Issue #20 的同尺寸实机门槛另行比较。
