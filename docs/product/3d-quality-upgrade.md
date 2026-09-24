# 3D 房间品质升级：素材与制作流程实验

状态：2026-09-25。供 [#20](https://github.com/johnnyzhang-eng/career-workbench/issues/20) 与 [#34](https://github.com/johnnyzhang-eng/career-workbench/issues/34) 使用。**不决定首版采用 3D**，也不以模型参数档位替代原尺寸试玩。用户较认可原 A 的真实光影，因此保留 [PR #35](https://github.com/johnnyzhang-eng/career-workbench/pull/35) 的 A 场景为可重复基线。

## 现有实测指出的瓶颈

| 观察 | 可审证据 | 对制作顺序的影响 |
| --- | --- | --- |
| A 的房间光影得到用户更积极的反馈；先前所谓改良版显得粗糙 | 用户评语；[#35](https://github.com/johnnyzhang-eng/career-workbench/pull/35) 的 A/B 样本 | 保存 A 的镜头、主光和色调，改变角色/家具时单独留 A 对照 |
| 360×320 比较器中，房间画幅原为 344×141；L1 可扩至 344×222 | [#43](https://github.com/johnnyzhang-eng/career-workbench/pull/43) 的同帧 L0/L1 | 素材细节先按实际小窗检查；看不到的纹理和面数不优先 |
| R2→R3 坐姿触键的骨架/接触有改善，原尺寸手部变化仍很轻；站坐过渡不合格 | [#48](https://github.com/johnnyzhang-eng/career-workbench/pull/48) 的 36 帧/短录屏 | 下一轮重点是有轮廓差异的“电脑/读书/休息”姿态及接触，而非继续只加骨骼 |
| Godot 场景可以在 WKWebView 显示并单向读取任务状态；短时可见／隐藏采样已做，仍不能推断整天常驻成本 | [#44](https://github.com/johnnyzhang-eng/career-workbench/pull/44)、[#47](https://github.com/johnnyzhang-eng/career-workbench/pull/47)、[#54](https://github.com/johnnyzhang-eng/career-workbench/pull/54) | 画质升级须与原生小窗、遮挡、长时间闲置／唤醒一起验收 |
| 只把原 A 的浅色键盘换成可编辑 Blender 键盘，小窗昼夜各仅改变 55 个物理像素；展开态能辨认键帽 | [#53](https://github.com/johnnyzhang-eng/career-workbench/pull/53) 的 K0/K1 原尺寸与展开态同条件对照 | 小窗先改角色/任务姿态的轮廓和相机占比；键帽等微细节放到展开态优化 |
| 只替换原 A 的坐姿人物为更细致的 MPFB 模型，360×320 中人物投影从 R2 的 28.99×38.33 变成 R4 的 10.09×18.61 逻辑像素 | [#55](https://github.com/johnnyzhang-eng/career-workbench/pull/55) 的 Godot 实机控制图、18 例 manifest | 先统一房间尺度、镜头与角色在小窗的占比；模型细节不能独立解决可读性 |
| 把 CC0 1K 木桌单件换进原 A 小窗，修正旧桌腿重叠后，房间画幅白天变化 1,270/194,016 物理像素（0.6546%）；展开图能看到木纹 | [#56](https://github.com/johnnyzhang-eng/career-workbench/pull/56) 的 A/M2 同机昼夜截图、哈希与修正记录 | 高质量纹理在小窗里受场景占比限制；先定尺寸、构图与人物动作，材质再分配预算 |
| 固定桌面近镜头会裁切待开始的站立角色；随明确任务状态切换全景/近景可避免这个裁切，但真实比例坐姿在小窗又变小 | [#57](https://github.com/johnnyzhang-eng/career-workbench/pull/57) 的 R4/M3 待开始与进行中 16 张对照 | 同一个 UI 必须按任务状态编排镜头，并同时验完整站姿、坐姿、任务控件与切换动画 |

## 建议试验的生产流程

1. **场景先当模型草图。** 保留原 A 布光和相机，把现有程序几何视为占位。先挑键盘、椅子、书和一张书桌做材质/几何对照；逐件替换、同机同尺寸截昼夜图。桌面、椅面、手掌、脚底的接触应比远处装饰细节先通过。
2. **资产在 Blender 制作或修整，用 glTF 2.0/GLB 入 Godot。** Godot 4.7 [推荐 glTF 2.0](https://docs.godotengine.org/en/4.7/tutorials/assets_pipeline/importing_3d_scenes/available_formats.html)；它保留骨架、动画和 PBR 材质，OBJ 不能完整承载这些信息。源文件与导出文件分开管理，每个资产留尺寸、材质和来源记录。贴图、法线、粗糙度在 Godot 实际渲染中检查；Blender 程序材质可能不能原样转入。
3. **角色先有统一的可重定向骨架，再谈个人形象。** 当前 R3 只能证明一个原创学生的坐姿链路。Godot 4.7 的 [Humanoid BoneMap/SkeletonProfile](https://docs.godotengine.org/en/4.7/tutorials/assets_pipeline/retargeting_3d_skeletons.html) 可实验多个角色共用动作，但同名骨骼并不足够，骨骼休止姿态也须匹配。做一套待机、坐下、打字、起身、阅读、短休动作；每段在 360×320 和展开态看手/椅/书/地面接触及转场。
   [MakeHuman Community 的 MPFB 2.0.17](https://extensions.blender.org/add-ons/mpfb/) 已在 [R4 草稿实验 #55](https://github.com/johnnyzhang-eng/career-workbench/pull/55) 中用于参数化人体、骨骼、服装与静态坐姿。插件官方说明兼容 Blender 4.2+；本机 Blender 5.1.2 已生成并让 Godot 导入 GLB，但**动画导出与小窗品质仍未通过**。此轮保留原 A 灯光，并分别记录只换模型、调整镜头／桌椅接触、校正尺度、换衣服、恢复产品操作 UI 的条件；R2/R4 的身高、服装和动作并未严格统一，不能把不同条件的图直接当作画风胜负。插件 [GPL-3.0-or-later、内置资产 CC0、创作输出不由制作者主张权利](https://github.com/makehumancommunity/mpfb2/blob/master/LICENSE.md)；社区另下载的衣服、头发已在 #55 对具体单项核许可。
4. **环境素材优先检查 CC0 单件。** [Poly Haven](https://polyhaven.com/license) 的 HDRI、材质和模型标为 CC0，适合试一块木桌材质、墙面和柔和环境光；[Kenney](https://kenney.nl/support) 与 [Quaternius](https://quaternius.com/faq.html) 的资产也可作 CC0 候选，但它们的造型是否与 A 的真实感统一必须看实际截图。每件素材在取得时保存原页面、许可、作者/包名、版本与源文件哈希；不把整包堆入公开仓后再挑。
5. **有价格或限制的素材只作为备选来源。** [Fab 标准许可](https://www.fab.com/eula)允许在项目中使用、修改和与项目协作者分享，但限制把素材单独再次分发；公开 GitHub 仓库是否适合放原始资产须逐件核对。任何购买或按次生成调用先报具体费用并取得明确同意，当前试验只用原创或已核许可的免费素材。Mixamo 的[官方 FAQ](https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html)还注明中国地区代码的 Adobe ID 无法使用，所以不把它设为唯一动作来源。

### 已核来源、待实机判断的具体候选

| 候选 | 为什么看它 | 导入前的限制 |
| --- | --- | --- |
| [Poly Haven Fine Grained Wood](https://polyhaven.com/a/fine_grained_wood) | CC0 木纹与粗糙度可用于单件桌面材质对照 | 先选低分辨率贴图，在原大小窗看木纹是否真有增益；保留作者与资产页记录 |
| [Poly Haven Wood Floor](https://polyhaven.com/a/wood_floor) | CC0 室内地板材质，适合与 A 的光影做单因素对照 | 不能把整套高分辨率贴图直接塞进常驻 Web 场景；先测 1K 及图案重复 |
| [Poly Haven Desk Lamp Arm 01](https://polyhaven.com/a/desk_lamp_arm_01) | CC0 可动台灯，能检验真实感物件是否与原 A 房间协调 | 页面标 26K 三角面和多张材质图；先做简化/尺寸对照，不能当作当前默认素材 |
| [Poly Haven Decorative Book Set 01](https://polyhaven.com/a/decorative_book_set_01) | CC0 书本可为阅读场景提供视觉参考 | 页面说明整套为 113K 三角面且暂不提供 glTF；先做一册适配角色手部的原创书，不直接导入整套环境摆件 |

以上候选只验证来源与许可页，**尚未证明**在 Godot 小窗里好看或省资源；#56 采用的另一个木桌是已进入实机的单件对照。[Godot 4.7 的贴图限制说明](https://docs.godotengine.org/en/4.7/tutorials/3d/3d_rendering_limitations.html)支持在导入时设尺寸上限；后续家具与动作试验仍需分别记源贴图、导入后尺寸、Godot Web 包增量和常驻内存，而不是把素材站的最高分辨率视作质量目标。

## R4、M2、M3 实测后的制作顺序

[#55 的原大对照页](https://github.com/johnnyzhang-eng/career-workbench/blob/experiment/mpfb-character-r4/prototype/comparison/mpfb_character_experiment/index.html) 与 [manifest](https://github.com/johnnyzhang-eng/career-workbench/blob/experiment/mpfb-character-r4/prototype/comparison/mpfb_character_experiment/manifest.json) 覆盖原 A、R2、R4、昼夜、小窗和展开图。原 A 的椅子与键盘中心水平距离约 1.39 m，原椅面高约 0.84 m，真实比例的人体在这套场景里脚部悬空、手部距离失真。把人物放大 1.35 倍、下移 0.34 m、椅子和键盘分别调整后，R4 在房间优先小窗中的人物投影达到 79.76×121.24；**回到保留任务按钮的原小窗后又降至 52.23×77.00**。这些是诊断修正，不是新的正式场景尺度。大图里仍清楚看到椅子、桌面和墙是粗块几何。

因此下一轮先把家具与人体建到同一米制尺度，定三个接触检查点（髋／椅、手／任务道具、脚／地面），再在保留真实任务控件的 360×320 UI 中选镜头。轮廓和接触稳定后，先做坐下、输入、读书、起身的连续动作，再逐件精修椅子、桌面、书本的材质与道具细节。R4 GLB 当前是姿态烘焙的静态网格，没有 skin 或 animation；Blender 本地骨骼源不等于游戏里已有动作系统。

[#56 的木桌单件对照](https://github.com/johnnyzhang-eng/career-workbench/pull/56)证明来源清楚的 1K 资产能在原 A 显示、且展开态有木纹，但它为塞进原 A 的 3.55 m 桌子而非均匀拉伸，不能当作家具比例方案。初版按节点名只隐藏一条旧桌腿，复查后以网格几何断言隐藏全部四腿和桌面，重新捕获并修正上述数字。[#57 的组合样机](https://github.com/johnnyzhang-eng/career-workbench/pull/57)把桌面/椅面高度约校到 0.80/0.44 m，待开始看全景、明确开始后以 0.65 秒缓动看桌面，解决固定近镜头裁切待机角色；但[连续短片](https://github.com/johnnyzhang-eng/career-workbench/blob/experiment/scale-contact-m3/prototype/comparison/scale_contact_experiment/captures/m3-camera-transition.mp4)也显示人物仍瞬时从站立占位形象换成静态坐姿。桌子宽度仍沿用 3.55 m，占屏的人物在进行中从 R4 的 52.23×77.00 降到 M3 的 38.60×58.21，椅背仍遮挡躯干。它们是试验结果，不是新默认场景。

同一分支的 G2a 只把进行中相机转到侧面，人物投影升至 54.28×78.95 逻辑像素，[小窗实拍](https://github.com/johnnyzhang-eng/career-workbench/blob/experiment/scale-contact-m3/prototype/comparison/scale_contact_experiment/captures/G2a-side-360x320-day-started.png)也更能辨认手臂，但书桌/房间被大量裁切。这给出一个真实的构图权衡：下一轮不能只追人物占屏数字，需同屏保留角色活动、房间语义和可操作任务控件。

| 下一验收门 | 具体产物 | 通过证据 |
| --- | --- | --- |
| G1 统一尺度与接触 | 桌宽/高、椅座、键盘、显示器、人物身高共用米制基准；坐姿、站姿各有髋/手/脚接触参考 | 360×320 与展开态的昼夜截图，无悬脚、穿桌、手够不到键盘；不靠非均匀拉伸外部模型 |
| G2 镜头与工作台 | 待开始全景、电脑/读书/休息任务近景，保留可操作的 checklist、开始/记录结果/调整；镜头平滑过渡 | 同一虚构任务按明确状态切换的连续录屏，四个状态无裁切/遮挡主要控件 |
| G3 动作与角色 | 可编辑骨骼源、坐下/输入/读书/休息/起身动作，服装与不同身材共用接触锚点 | Godot 导入有真实 skin/animation；手、书、椅、地面的连续帧与转场验收，不以静态截图替代 |
| G4 材质与道具 | 逐件替换真实尺度椅子、桌面、书、灯；核每件来源、色调、纹理分辨率 | 原生小窗与展开态同机 A/B；可见收益、GLB/Web 包增量及主观审图记录 |
| G5 常驻资源 | 原生小窗可见/收起/后台/唤醒与事件桥长期采样 | 帧率、CPU/GPU、内存和电量在目标机器重测；#54 的短时 WebKit 样本只作起点 |

## 两个小而可比的下一轮样本

| 样本 | 只改变什么 | 必须同屏看见 | 停止条件 |
| --- | --- | --- | --- |
| G1a：统一尺度的桌椅/人体接触 | 保留原 A 光照，改一组米制桌椅与角色落点，先不换高分辨率材质 | 桌面、椅面、腕、髋和脚底在昼夜、小窗/展开态的一致接触 | 仅靠缩放挤进旧房间、人物又被椅背挡住或待机镜头裁切 |
| G3a：同一房间的连续阅读动作 | 沿用 G1a 尺度与角色，明确选择读书任务后坐下、拿书、阅读、合书 | 不看文字也能区分电脑与读书；计划未开始仍待机；暂停不继续表演 | 手穿书/桌、书和手错位、转场瞬移、原尺寸不可分辨 |

每组保留可打开的 Blender/GLB/Godot 来源、原大 PNG、连续短录屏和参数表。图像生成可用来制作概念稿或纹理方向，但生成图本身不是可复用的 3D 网格、骨架或动作；照片生成个人角色要另验本人照片的私有处理、删除与肖像相似度。通过 G1/G3 的 3D 样本最终与真正手绘像素 2D 在**同一任务事实、同一原生小窗**比较，由用户看运行效果决定首版路线。

执行跟踪：[同尺度可动角色与任务动作 #58](https://github.com/johnnyzhang-eng/career-workbench/issues/58)；[可控的照片生成个人形象 #59](https://github.com/johnnyzhang-eng/career-workbench/issues/59)。两项都用虚构或明确同意的测试素材，不把真人照片和衍生物提交到公开仓库。

## R4 角色实验的三项判据与结果

1. **先验测量方式。** #55 用原 A 与 R2 作控制，保持 360×320 逻辑尺寸和昼夜设置；截图是 2× Retina 物理像素，AABB 明确包含被遮挡网格。把仅替换模型、镜头与接触、房间画幅、服装、产品 UI 分开记录。#48 的 R3 连续动画尚未与 R4 同镜头并排，不能宣称 R4 动作更好。
2. **区分限制来源。** R2 的块状角色与 R4 的人体网格在原镜头里大小不同，不能直接把小窗差异归因于多边形或材质。换人体的第一步反而变小；放大画幅和校正家具接触后才看得出衣服与姿态。下一步用统一身高、相同动作时长/帧、同一镜头比较网格形变与动作可读性。
3. **先看产品尺寸再决定路线。** #55 的房间优先构图藏了任务控件；保留控件后人物再次变小。R4 尚未覆盖阅读／休息、连续过渡、照片定制或常驻负载验收，因此 3D/2D 路线仍由用户看真实运行效果后决定。小窗、展开态、隐藏恢复和资源预算都应入最终同场景门槛。
