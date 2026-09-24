# 原版 A · 键盘接触细节 M1

2026-09-25，Godot 4.7 stable / GL Compatibility，Blender 5.1.2。[原尺寸并排审图页](index.html)包含 K0 原版 A 与 K1 自制键盘，逻辑 360×320／1280×720，day/evening。**只替换 `Keyboard` 场景节点**；A 的镜头 FOV 45°、主光与环境光、桌面、椅子、人物、任务 UI、idle 状态均不改。它独立于 #35 的 D1 桌面、#43 构图和 #48 角色实验，不叠加这些修改。

## 制作及来源

| 文件 | 用途 |
| --- | --- |
| [build_asset.py](build_asset.py) | 本仓编写的 Blender 构建脚本；深色圆边壳体、低矮键床、四排独立键帽、宽空格键，四种材质。sRGB 颜色转 Blender 线性值。 |
| [keyboard_contact.blend](keyboard_contact.blend) | 可编辑母版，45 个独立网格，保留非破坏性圆边和加权法线；保存后仅在内存中的导出副本应用 modifier 并按材质合并。 |
| [keyboard_contact.glb](../../godot/comparison/assets/keyboard_contact.glb) | Godot 导入件：4 个网格／4 个材质／4 个 primitive、9,720 个导出 POSITION 顶点、344,836 字节。 |
| [manifest.json](manifest.json) | 资产与固定场景 SHA-256、八次窗口采集的参数、尺寸和输出 hash。 |

这是本仓自制模型与脚本，沿用仓库 MIT；无外部 mesh、贴图、字体或按次计费调用。`.blend` 文件保留真实编辑能力；GLB 的导出结构由采集脚本解析检查。Godot `.import` 记录导入参数，`.godot/` 缓存不交付。

## 画面观察与边界

八次 Godot 实窗采集均正常退出；日志无 `SCRIPT ERROR` 或 `ERROR:`；K1 日志确认导入 4 个 MeshInstance3D。逻辑 360×320 保存 720×640 Retina PNG；逻辑 1280×720 保存 2560×1440 PNG。K0／K1 同状态的小窗物理像素差异：白天 55 像素，夜晚 55 像素；边界分别为 x=353–384、y=214–231，以及 x=353–366、y=214–220。全窗白天 719 像素，夜晚 720 像素；均集中在键盘及其近邻投影。计数基于 RGB 像素任一通道不同，不能当作质量评分。

全窗原图可见键帽和更有层次的壳体；小窗在原尺寸下，这些结构基本无法被独立识别。该实验表明**仅加密键盘几何不足以解决本次小窗的动作与任务辨识度**，不判断 3D 画风整体优劣，也不替代人物接触动作、构图、持续运行性能和多目标真实 UI 验收。资产体积与顶点数是导出件事实，不是 GPU 性能测量。

## 复跑

在仓库根目录运行：

```sh
blender --background --python prototype/comparison/keyboard_contact_experiment/build_asset.py
/Applications/Godot.app/Contents/MacOS/Godot --headless --editor --import --path prototype/godot
python3 prototype/comparison/run_keyboard_contact_experiment.py
```

Blender 重建可能产生本地 `.blend1` 备份，不作为交付。采集会依次打开 8 个真实 Godot 窗口并覆盖本目录同名证据文件；不要与别的画面采集脚本并行。截图只包含仓库虚构任务，不含私人桌面或照片。
