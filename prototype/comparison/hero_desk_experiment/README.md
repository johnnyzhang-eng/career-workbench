# 原版 A：单桌面 Blender 网格实证

2026-09-25，Godot 4.7 stable / GL Compatibility，Blender 5.1.2。[本地审图页](index.html)并排展示 D0 原版方盒桌面与 D1 自制 Blender 桌面；逻辑 360×320、1280×720，day/evening。**只替换 `Desk top` 一件物体**；保留原版 A 的 FOV 45°、主光/环境光、四条桌腿、椅子、角色、道具、UI、任务和 idle 状态。不叠加前面光照/相机的实验值。

## 来源、可编辑文件与资产体积

| 文件 | 内容和使用 |
| --- | --- |
| [build_asset.py](build_asset.py) | 本仓自写 Blender Python，创建一件 3.55×1.35×0.17 的桌面；顶部/侧面/倒角三材质；0.04 单位、3 段非破坏性倒角和 Weighted Normals。没有外部 base mesh、贴图、字体或付费 API。 |
| [hero_desk_top.blend](hero_desk_top.blend) | **可编辑母版**，保存时仍保有 BEVEL 和 WEIGHTED_NORMAL 两个 modifier，1 个网格对象、3 个材料；97,943 字节。 |
| [hero_desk_top.glb](../../godot/comparison/assets/hero_desk_top.glb) | 导出件，16,524 字节，glTF 2.0；Godot 导入用。GLB 原始 JSON 审计为 1 mesh、3 materials、3 primitives；倒角材质对应 360 个 POSITION 顶点，含 NORMAL。 |
| [manifest.json](manifest.json) | 原版源文件、可编辑母版、构建脚本、GLB、8 张截图的 hash 与采集参数。 |

以上作品和脚本为本仓自制实验资产，沿用项目 MIT；不含第三方素材。Blender 软件许可证不改变本资产的许可证。若以后替换为外部模型，需另登记每个文件的来源/许可证。Godot `.glb.import` 保存导入参数；缓存 `.godot/` 不作为交付资产。

制作时发现两处导出测量链问题并已修正：第一份 GLB 虽在 `.blend` 保有倒角 modifier，导出后只有平盒顶点；现先保存可编辑 `.blend`，再**仅在内存的导出副本**应用倒角/法线，GLB 审计到 3 材质和细分边缘。初次材质也因将 sRGB 十六进制直接写入场景线性 shader 而偏亮；构建脚本现先转场景线性值。最终证据只用修正后的资产。

## 运行与画面检查

`run_hero_desk_experiment.py` 锁定 `main.gd`、`room_3d.gd`、`comparison.gd`、`project.godot` 的 SHA-256，与三轮 A 基线相同。D0 的小窗昼夜 PNG 与先前 A0 **逐字节相同**；全窗昼夜只在实时系统时钟文字处各差 273 原生像素（x=87–102、y=130–151）。D0/D1 × 两尺寸 × 昼夜共 8 次真实 Godot 窗口采集成功、正常退出，日志无 `SCRIPT ERROR` 或 `ERROR:`；D1 运行日志确认只导入 1 个 MeshInstance3D，AABB 尺寸约 (3.55, 0.17, 1.35)，中心放在原桌面位置 (−0.65, 1.16, −1.55)。逻辑 360×320 → 720×640 PNG；逻辑 1280×720 → 2560×1440 PNG，本机 scale=2。

直接看 D0/D1 同状态原图：全窗的桌面前缘从硬直角变为可见的浅色圆边，顶部与侧边有不同色调；键盘、电脑、灯仍在原位置。小窗原大只看到很少桌沿像素变化，人物行为与房间整体识别没有因此改变。像素差异集中在桌面及其近邻投影区域：360×320 的差异边界约为原生像素 x=330–432、y=205–260；1280×720 为 x=837–1237、y=631–847。静帧**不证明整体质量升级**，也不等于角色/动作、性能或互动验收。

## 重建与重跑

从仓库根目录依次执行：

```sh
blender --background --python prototype/comparison/hero_desk_experiment/build_asset.py
/Applications/Godot.app/Contents/MacOS/Godot --headless --editor --import --path prototype/godot
python3 prototype/comparison/run_hero_desk_experiment.py
```

Blender 重建时可能产生本地 `.blend1` 备份，不属于交付物。采集会依次打开八次真实 Godot 窗口并覆盖本目录同名截图；不要与其他采集脚本并行。截图只含本仓虚构任务 UI，不含私人桌面。原始 `.blend` 文件已用 Blender 重新打开确认 1 mesh/3 materials/2 modifiers；GLB 的结构与法线由脚本审计，Godot 的尺寸和可见性由真实运行图及日志检查。
