# R4：可编辑人体模型在原 A 房间里的实机实验

这轮只回答一个问题：使用成熟的人体基础网格、骨骼与服装，能否让「学生在电脑前」在实际 360×320 小窗中更可信？它是 Issue #20 的美术实验，不替换正式桌面工作台或任务流。对照图见 [index.html](index.html)，逐张参数与 SHA 见 [manifest.json](manifest.json)。

## 方法和素材

- 在 Blender 5.1.2 里使用官方 [MPFB 2.0.17 扩展](https://extensions.blender.org/add-ons/mpfb/)、[MakeHuman system assets](https://static.makehumancommunity.org/assets/assetpacks/makehuman_system_assets.html)、[poses01](https://static.makehumancommunity.org/assets/assetpacks/poses01.html)、[shirts01](https://static.makehumancommunity.org/assets/assetpacks/shirts01.html) 和 [pants01](https://static.makehumancommunity.org/assets/assetpacks/pants01.html)。插件本体 GPL-3.0-or-later；本次用到的角色基础资产与选定服装/姿态单项标记 CC0，工具输出许可边界以 [MPFB 项目许可说明](https://github.com/makehumancommunity/mpfb2/blob/master/LICENSE.md) 为准。原始 ZIP 和贴图只在本机 `private/`，不提交仓库。
- `build_character.py` 生成可在 Blender 编辑的人体、163 根骨骼、服装及坐姿；本地 `.blend` 保存在实验目录，不随 PR 分发，因为外部资产路径未打包。提交的 GLB 是**姿态烘焙的静态网格**，没有 skin/animation，约 6.8 MB；不能称为已经完成动作系统或照片定制。
- 选择了 `sweetan008_sitting-pose`，其包内 `.meta` 明写 `license CC0`。poses01 包的总览页与某些其他单项元数据并不完全一致，因此按**实际使用的单项**校验，不把整个包一概当作 CC0。日常服装选 `toigo_fisherman_sweater` 与 `cortu_cargo_pants`，两个包的 JSON 及各 `.mhclo` 均标记 CC0。正式发布前仍应复核最终分发包的具体素材清单。
- Blender GLB 导出曾将骨骼姿态重置成默认姿态。用帧 1 的 evaluated meshes 固化真实坐姿后，普通版和键盘 IK 版的 GLB SHA 才不同。此处只证明静态姿态出现在 Godot 画面，**没有**证明 glTF 动画管线正确。

本机下载件 SHA-256（重跑时核对版本）：MPFB ZIP `4f0a879d64a39bf646fbf5f53601ac678855da329d650617dca5737548239a87`；system assets ZIP `b542127a8e25547c7c29c19f2d1d2adb9a664c80396ecd694095dbc8028a0107`；shirts01 ZIP `a5a723b0e84a109bb190fcfeac7f1de4138d875da3e30fe5b3340eac9f38bcd3`；pants01 ZIP `e4e0ec60db34f279be291a83cfd7b342a7c5cf09bb7676682a5f39f4f6ac4ad9`。

## 控制与观察

固定虚构任务、原 A 房间及昼夜光参数，Godot 4.7 Compatibility 在原生 720×640 像素窗口渲染 360×320 逻辑尺寸。下表是**人物网格八角投影 AABB**，含被遮挡部分，不能当作可见像素面积。

| 条件 | 原程序骨骼人物 R2 | MPFB R4 | 含义 |
| --- | ---: | ---: | --- |
| 原镜头与原椅子 | 28.99×38.33 | 10.09×18.61 | 更细致的人体在原构图下反而太小 |
| 靠近桌面、降低椅背 | 74.06×88.85 | 24.03×44.81 | 只改镜头仍不够 |
| 房间优先画布、镜头靠近、椅子前移 | 108.46×130.88 | 44.51×69.32 | 场景占比影响动作可读性 |
| R4 再校正人物比例与高度 | — | 79.76×121.24 | 可见姿态改善，但原房间尺度未统一 |
| 同样 R4 放回保留任务操作的原小窗 | — | 52.23×77.00 | 工作台占屏后人物再次缩小，UI 与场景必须共同设计 |

原 A 的椅子中心与键盘中心水平距离约 1.39 m；椅面顶端约 0.84 m，而 MPFB 姿态的髋部约 0.84 m、脚约 0.32–0.42 m。人物与桌椅并未以同一真实尺度建造。因此最后一列的 1.35 倍人物、下移 0.34 m、椅子向桌移 0.55 m、键盘向人物移 0.15 m 都是**诊断性修正**，还不是精确人体工学配置。R2 原人物手臂和身体较夸张，原比例错误在画面里较不明显。

`--activity-focus-layout` 借用 #43 的 344×222 房间画布，会隐藏动作按钮；它只用来判断美术镜头，不是产品 UI。正式小窗还必须保留 #50 的任务入口与「开始/记录/调整」控件。夜景截图只验证相同模型在既有夜灯下的可辨性；尚未测能耗、连贯动画、椅面受力、手指接触、不同身材与服装适配。

`r4-product-casual` 额外保留原 360×320 小窗的任务状态和动作按钮。相同人物/镜头放进去后房间区域明显变短，所以扩大房间的美术图不能直接宣称解决了产品首屏；这个取舍需要在 UI 逻辑中继续设计。

## 重跑

先在独立 Blender 配置安装上述官方 MPFB ZIP，把 system assets、shirts01、pants01 的 `clothes/` 等目录展开到该配置的 MPFB user data；把 poses01 中选定 BVH 放到 `private/asset-packs/poses/sweetan008_sitting-pose/`。脚本按这些公开源文件重建，不依赖仓库外的个人照片或本机任务数据。

```sh
BLENDER_USER_CONFIG="$PWD/private/blender-config" BLENDER_USER_EXTENSIONS="$PWD/private/blender-extensions" /Applications/Blender.app/Contents/MacOS/Blender -b --python prototype/comparison/mpfb_character_experiment/build_character.py
BLENDER_USER_CONFIG="$PWD/private/blender-config" BLENDER_USER_EXTENSIONS="$PWD/private/blender-extensions" /Applications/Blender.app/Contents/MacOS/Blender -b --python prototype/comparison/mpfb_character_experiment/build_character.py -- --ik
BLENDER_USER_CONFIG="$PWD/private/blender-config" BLENDER_USER_EXTENSIONS="$PWD/private/blender-extensions" /Applications/Blender.app/Contents/MacOS/Blender -b --python prototype/comparison/mpfb_character_experiment/build_character.py -- --casual --ik
/Applications/Godot.app/Contents/MacOS/Godot --headless --editor --import --path prototype/godot
python3 prototype/comparison/mpfb_character_experiment/run_capture.py
```

## 下一轮具体提升

1. **统一场景尺度**：把桌面、椅座、键盘、地面和身材建在米制坐标系；用髋、足底、手腕三个接触点验证每种角色身材，不靠统一放大掩盖偏差。
2. **镜头和分层 UI 一起设计**：360×320 小窗优先让人物动作可辨，展开视图再展示五官/家具细节；动作控件始终能用。真实小窗中测一次投影尺寸与可见像素，不只看 AABB。
3. **做连续动作**：Blender 里制作坐下、读书、输入、起身的可复用动作，验证 Godot glTF 骨骼与重定向、手指和桌面的接触；任务状态只驱动视觉，不据动画推断任务完成。
4. **提高房间材质**：当前地面、桌子、椅子仍是大块程序几何，阴影边缘硬、脚部接触弱。逐件替换桌椅/灯/书本的高质量资产，在统一光照下重测小窗与展开视图；每件资产单独登记许可证。
5. **控制常驻成本**：#54 的短时 WKWebView 采样有环境噪声，不能推断整天电池消耗；需在目标机器比较可见、收起、后台和恢复场景。进入常驻入口前做预算门槛。

这个结果支持继续探索精修 3D，但不构成「3D 路线已经胜出」的决定。最终需和真正用心制作的纯 2D/像素路线在同一任务、同一小窗尺寸与同一资源预算下对照。
