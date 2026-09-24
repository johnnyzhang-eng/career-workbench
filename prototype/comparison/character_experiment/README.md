# R0/R1：原 A 房间的单角色实机对照

2026-09-25 制作。对照页：[index.html](index.html)。从原版 A 开始，R0 保留程序角色；R1 只替换角色，固定 A 的透视 FOV 45°、主光角 −55°/−32°、昼/夜光能量、桌椅、UI 和虚构任务。R1 idle 是**相同站位**的 Blender 角色，可比较造型；R1 started 另切到椅子上的**静态**电脑姿态，因此此状态同时改变人物位置与姿态，只验证可读行为，不可把差异归因于模型拓扑。

## 实物与许可

`build_character.py` 只用 Blender 内置网格从零制作站姿/坐姿两个原创版本，无第三方模型、纹理、字体和收费调用。`adult_student.blend` 保留各部件和鞋子倒角/法线 modifier，可编辑；导出时才把 modifier 烘焙进 GLB。角色有分层头发、帽衫/帽兜/下摆/口袋、牛仔裤、鞋和手臂。**它仍以独立几何部件构成，没有 armature、权重或动作曲线；不能称为完成的角色资产或动态打字动画。** 原创资产沿用仓库 MIT；其他既有资源登记见 [ASSET_LICENSES.md](../ASSET_LICENSES.md)。

源文件 `adult_student.blend` 约 159 KB；`adult_student_idle.glb` 约 207 KB、38 个 mesh；`adult_student_typing.glb` 约 215 KB、40 个 mesh；各含 8 个材质。准确字节、SHA、运行版本和参数见 [manifest.json](manifest.json)。GLB 中无 skins/animations；实际 Godot 4.7 Compatibility 导入并实例化成功。

## 重跑

在仓库根目录运行：

```sh
blender --background --python prototype/comparison/character_experiment/build_character.py
/Applications/Godot.app/Contents/MacOS/Godot --headless --editor --import --path prototype/godot
python3 prototype/comparison/run_character_experiment.py
```

第三条以真实 Godot 窗口采 R0/R1 × 360×320/1280×720 × day/evening 的 idle 与 started。每次 `--proof` 还产生 completed/deferred 图片以验证虚构任务交互，脚本核验后清除这两类副产物；index 只呈现 idle/started。每张 PNG 是 2× Retina 物理像素；网页的小窗显示宽 360 CSS 像素。日志将仓库绝对路径脱敏，manifest 保留源码 hash、GLB 结构、图片 hash 和每次运行的 `COMPARISON_PROOF_PASS baseline`。R0 的 360×320 白天 idle PNG 与先前桌面实验 D0 的同设置基线字节相同。

## 原大观察与限制

实际 Godot 投影 AABB（**逻辑像素**，来自运行时网格八角投影并除以 Retina scale=2；它包括被遮挡部分，并非仅可见像素）在 360×320 小窗：R0 idle **21.82×39.94**，R1 idle **18.70×39.29**，R1 started 静态坐姿 **23.47×29.08**。人物宽度甚至略缩小，帽兜、口袋、脸部等全窗细节在小窗几乎不可辨；**不能据此宣布质量门槛已跨过或 R1 胜出。**

全窗 R1 的更修长比例、头发和衣物层次可见，仍有由分立几何造成的拼接感。坐姿显示“到电脑前”，但手指级打字、手掌精准接触、髋部/椅面重量感和流畅过渡均未验收；切姿态是瞬时的。原版 R0 started 也没有坐姿，两个 started 图仅是行为可读性参考。小窗的角色只有约 19–22 逻辑像素宽，下一轮若想验证更精细的材质/五官，需**独立**做镜头构图或房间占比实验，不能与角色替换合并成一个改动。

任务的开始/记录结果仍是原本的虚构演示交互；动画/姿态从不写真实目标或完成事件。后续角色质量方向需要用户审图后选择，再做可换部件与骨骼权重；本轮不冻结美术路线。
