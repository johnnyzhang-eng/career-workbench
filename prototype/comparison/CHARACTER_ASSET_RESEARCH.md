# 3D 主角与动作素材：来源核验及下一轮实验

核验日：2026-09-25。范围：公开的 Career Workbench 源码仓库、原版 A 房间、常驻 360×320 小窗。**本轮只核对页面和本仓源码，没有下载、购买、导入或提交第三方模型。** 页面列出的格式、三角面和动作不等于本项目已实测可用。

## 本场景真正需要什么

原版 A 在 `prototype/godot/main.gd` 用 Godot 球体、圆柱和盒子拼出约 2.2 世界单位高的学生：衣身、头、头发、左右腿与右臂均是独立节点。`prototype/godot/comparison/room_3d.gd` 的 A 模式保留透视 FOV 45° 和原光照，工作状态仅摆动右臂；没有人体骨骼、坐姿、键盘接点或读书动作。下一件资产应替换**角色一项**，保留 A 的镜头、房间、桌椅、光照、UI 和任务状态，避免把多种变化误记为角色提升。

候选入仓的硬门槛：①逐文件能追溯作者、页面、取得日期及许可，允许公开分发原始或修改后的网格、贴图、rig、动作；②成年大学生的日常衣着和比例，不借用未成年/奇幻/战斗身份；③正侧背视图与小窗原大轮廓可读；④ Blender 中可编辑网格与 rig，Godot 中可播放 idle、坐下、坐姿电脑、坐姿读书，手与键盘/书、髋与椅面不穿模；⑤单角色的文件大小、三角面、材质/纹理数和常驻性能可记录。只有静态 sitting **pose** 不能算 sitting **animation**，也不能等同 typing。

## 三条生产路径

| 路径 | 许可和可编辑性 | 本产品的实际门槛 | 建议用途 |
| --- | --- | --- | --- |
| 自制 Blender 母版 | 本仓独创网格/材质/rig/动作可随 MIT 仓库公开；制作脚本和 `.blend` 一起保留。 | 先画成年角色正侧背与房间比例图，做可换头发/肤色/上衣，建肩肘髋膝变形环、权重和四个动作；还要处理桌椅接触及小窗辨识。工作量最大，但身份和产品风格最可控。 | **主角的目标路线**；现有程序几何作为 A 控制，先做一套高完成度母版，不承诺凭模型选择就自动变精美。 |
| 可编辑开源人体底座 | [MakeHuman/MPFB 官方许可](https://static.makehumancommunity.org/about/license.html)将**核心资产**列为 CC0，工具代码另为 AGPL/GPL；[官方资产包表](https://static.makehumancommunity.org/assets/assetpacks/index.html)区分 CC0 的系统资产、Shirts 01/Pants 01/Shoes 01 和 sitting poses，以及 CC-BY 的其他衣物。仅选逐项 CC0 文件时，资产可入公开仓。 | 现实人体比例、皮肤贴图和高细节衣物可能与现有柔和 Q 版房间冲突；需统一样式、减面/贴图、重做材料与动作。单帧坐姿包不能替代键盘动作。社区下载资产必须逐件核许可，不能继承“MakeHuman 都是 CC0”的概括。 | 若用户选择更写实的主角，作为**形体/权重底座试验**；从 CC0 核心及明确列出的衣物开始。 |
| 现成带 rig/动作角色 | [Kay Lousberg Adventurers](https://www.kaylousberg.com/game-assets/characters-adventurers)作者官网明确 CC0、rig、基础动作、glTF/FBX 和 1024² 色板；但五名角色是地下城冒险者，不具成年学生衣着。[OpenGameArt 的 Wobble Blocks 角色底座](https://opengameart.org/content/ps2-styled-characters)作者页面列 CC0、rig 和可编辑纹理（约 704 KB ZIP），但 PS2 质感是独立视觉路线。[byzmod3d 角色合集](https://opengameart.org/content/3d-character-pack)列 CC0、rig/animated，3.1–29.2 MB 压缩包，具体角色、动作和每件来源未拆验。 | “有 rig/animated”不代表有 sit/typing/reading；现成风格可能破坏 A 的真实光影与成年学生身份。必须拆包看单件、license、Blender/Godot 导入和实际小窗，不能按站点预览直接替换。 | 可作**技术与质量参照**；目前没有一个已核实同时满足学生风格和四个动作的可直接入仓成品。 |

### 一个看似合适但不宜直接入公开仓的来源

[Quaternius Universal Base Characters 包页](https://quaternius.com/packs/universalbasecharacters.html)及其 [itch.io 页面](https://quaternius.itch.io/universal-base-characters)写 CC0：六种人体比例、20 种发型、humanoid rig、约 13k 三角面；免费 Standard ZIP 为 122 MB，含 glTF/FBX；作者可编辑 `.blend` Source ZIP 为 600 MB，页面显示至少 US$19.99。配套 [Universal Animation Library](https://quaternius.com/packs/universalanimationlibrary.html)写 CC0、120+ 动作且明确含 sitting，**未明确 typing/reading**。但作者官网 [2026-08-28 的 Quaternius Asset License (QAL)](https://quaternius.com/license.html)禁止把原样或修改后的资产作为素材文件再分发，且写了当前协议覆盖范围与旧许可版本边界。包页与总许可现时并存，不能只依一个页面给公开 GitHub 的 GLB/rig/动画判定可分发。若未来想采用，先取得该**具体下载版本**的许可文本或作者书面澄清并归档，再考虑本地试验；这不是断言以前以 CC0 取得的副本已失效。

[Adobe Mixamo 的 FAQ](https://community.adobe.com/questions-696/mixamo-faq-licensing-royalties-ownership-eula-and-tos-589400)允许把角色/动作放进游戏作品，但明确不允许把原始文件作为素材向非团队成员再分发；公开仓保留 FBX/GLB 会越过该边界。它可以作为个人设备上的动作技术参考，不能作为本项目**可复现的公开源码依赖**。本轮没有使用它。

## 可执行筛选表与受控验证

下一轮只选**一个**文件级许可明确的成人角色候选；先在仓外检查 ZIP 清单和每项许可证，不先复制到 `prototype/godot`。填写：作者原始链接、取得日期、ZIP/文件 SHA-256、具体子文件及各自许可、是否允许公开原/改模型与动作、源 `.blend` 可得性、顶点/三角面、骨骼/权重、材质/贴图、已有动作精确名称、文件大小、成人衣着与可换部件。权属或年龄气质不清楚即暂不引入。

试验 `R0/R1`：R0 保留原 A 角色；R1 在原角色位置**仅替换一个角色**，用同一脚本加载 GLB，固定相机 FOV 45°、灯光、环境、桌椅和 UI。先采 idle 的 day/evening × 360×320/1280×720；若角色通过静态审图，再采 sit、typing、reading 每个动作的起/中/末帧以及短录屏。记录角色投影像素宽高、椅面/脚底/手掌接点与穿模、骨骼映射、纹理失真、包体/常驻资源。Godot 的[骨骼重定向文档](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/retargeting_3d_skeletons.html)说明共享动作要核对 bone rest、bone map 和位移轨道，不能假定 humanoid 命名相同就能直接播放。

验收时先在**360×320 逻辑原大**盲看“人是在电脑前、读书还是休息”，再看全窗表情/材料和四个动作的接点。任务状态依然来自显式开始/暂停/结束和证据，动画不写任务完成事件。若没有候选同时满足许可、成年学生外观和动作，就推进原创角色 brief 与骨骼母版，不为了填实验位把不合适资产放进产品。

## 本轮判断边界

P1：已对照作者官网/发布者页面与仓内代码；仅页面资料，未下载逐件解包或在 Godot 实测。P2：QAL 与包页 CC0 的冲突是**再分发授权不明**，不是模型导入故障或 CC0 通常不可再分发；MakeHuman 则是核心/社区资产许可分层。P3：现成 rig 可能更快，但用户更重视 A 的角色与房间整体质感；需允许合法候选在真实小窗试验里胜过自制，也不能按作者宣称的 rig/三角面直接评为产品可用。
