# 3D 房间品质升级：素材与制作流程实验

状态：2026-09-25。供 [#20](https://github.com/johnnyzhang-eng/career-workbench/issues/20) 与 [#34](https://github.com/johnnyzhang-eng/career-workbench/issues/34) 使用。**不决定首版采用 3D**，也不以模型参数档位替代原尺寸试玩。用户较认可原 A 的真实光影，因此保留 [PR #35](https://github.com/johnnyzhang-eng/career-workbench/pull/35) 的 A 场景为可重复基线。

## 现有实测指出的瓶颈

| 观察 | 可审证据 | 对制作顺序的影响 |
| --- | --- | --- |
| A 的房间光影得到用户更积极的反馈；先前所谓改良版显得粗糙 | 用户评语；[#35](https://github.com/johnnyzhang-eng/career-workbench/pull/35) 的 A/B 样本 | 保存 A 的镜头、主光和色调，改变角色/家具时单独留 A 对照 |
| 360×320 比较器中，房间画幅原为 344×141；L1 可扩至 344×222 | [#43](https://github.com/johnnyzhang-eng/career-workbench/pull/43) 的同帧 L0/L1 | 素材细节先按实际小窗检查；看不到的纹理和面数不优先 |
| R2→R3 坐姿触键的骨架/接触有改善，原尺寸手部变化仍很轻；站坐过渡不合格 | [#48](https://github.com/johnnyzhang-eng/career-workbench/pull/48) 的 36 帧/短录屏 | 下一轮重点是有轮廓差异的“电脑/读书/休息”姿态及接触，而非继续只加骨骼 |
| Godot 场景可以在 WKWebView 显示并单向读取任务状态，但常驻资源尚未量完 | [#44](https://github.com/johnnyzhang-eng/career-workbench/pull/44)、[#47](https://github.com/johnnyzhang-eng/career-workbench/pull/47) | 画质升级须与隐藏/闲置时渲染成本一起验收 |

## 建议试验的生产流程

1. **场景先当模型草图。** 保留原 A 布光和相机，把现有程序几何视为占位。先挑键盘、椅子、书和一张书桌做材质/几何对照；逐件替换、同机同尺寸截昼夜图。桌面、椅面、手掌、脚底的接触应比远处装饰细节先通过。
2. **资产在 Blender 制作或修整，用 glTF 2.0/GLB 入 Godot。** Godot 4.7 [推荐 glTF 2.0](https://docs.godotengine.org/en/4.7/tutorials/assets_pipeline/importing_3d_scenes/available_formats.html)；它保留骨架、动画和 PBR 材质，OBJ 不能完整承载这些信息。源文件与导出文件分开管理，每个资产留尺寸、材质和来源记录。贴图、法线、粗糙度在 Godot 实际渲染中检查；Blender 程序材质可能不能原样转入。
3. **角色先有统一的可重定向骨架，再谈个人形象。** 当前 R3 只能证明一个原创学生的坐姿链路。Godot 4.7 的 [Humanoid BoneMap/SkeletonProfile](https://docs.godotengine.org/en/4.7/tutorials/assets_pipeline/retargeting_3d_skeletons.html) 可实验多个角色共用动作，但同名骨骼并不足够，骨骼休止姿态也须匹配。做一套待机、坐下、打字、起身、阅读、短休动作；每段在 360×320 和展开态看手/椅/书/地面接触及转场。
4. **环境素材优先检查 CC0 单件。** [Poly Haven](https://polyhaven.com/license) 的 HDRI、材质和模型标为 CC0，适合试一块木桌材质、墙面和柔和环境光；[Kenney](https://kenney.nl/support) 与 [Quaternius](https://quaternius.com/faq.html) 的资产也可作 CC0 候选，但它们的造型是否与 A 的真实感统一必须看实际截图。每件素材在取得时保存原页面、许可、作者/包名、版本与源文件哈希；不把整包堆入公开仓后再挑。
5. **有价格或限制的素材只作为备选来源。** [Fab 标准许可](https://www.fab.com/eula)允许在项目中使用、修改和与项目协作者分享，但限制把素材单独再次分发；公开 GitHub 仓库是否适合放原始资产须逐件核对。任何购买或按次生成调用先报具体费用并取得明确同意，当前试验只用原创或已核许可的免费素材。Mixamo 的[官方 FAQ](https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html)还注明中国地区代码的 Adobe ID 无法使用，所以不把它设为唯一动作来源。

### 已核来源、待实机判断的具体候选

| 候选 | 为什么看它 | 导入前的限制 |
| --- | --- | --- |
| [Poly Haven Fine Grained Wood](https://polyhaven.com/a/fine_grained_wood) | CC0 木纹与粗糙度可用于单件桌面材质对照 | 先选低分辨率贴图，在原大小窗看木纹是否真有增益；保留作者与资产页记录 |
| [Poly Haven Wood Floor](https://polyhaven.com/a/wood_floor) | CC0 室内地板材质，适合与 A 的光影做单因素对照 | 不能把整套高分辨率贴图直接塞进常驻 Web 场景；先测 1K 及图案重复 |
| [Poly Haven Desk Lamp Arm 01](https://polyhaven.com/a/desk_lamp_arm_01) | CC0 可动台灯，能检验真实感物件是否与原 A 房间协调 | 页面标 26K 三角面和多张材质图；先做简化/尺寸对照，不能当作当前默认素材 |
| [Poly Haven Decorative Book Set 01](https://polyhaven.com/a/decorative_book_set_01) | CC0 书本可为阅读场景提供视觉参考 | 页面说明整套为 113K 三角面且暂不提供 glTF；先做一册适配角色手部的原创书，不直接导入整套环境摆件 |

以上只验证来源与许可页，**尚未证明**在 Godot 小窗里好看或省资源。[Godot 4.7 的贴图限制说明](https://docs.godotengine.org/en/4.7/tutorials/3d/3d_rendering_limitations.html)支持在导入时设尺寸上限；M1/M2 需分别记源贴图、导入后尺寸、Godot Web 包增量和常驻内存，而不是把素材站的最高分辨率视作质量目标。

## 两个小而可比的下一轮样本

| 样本 | 只改变什么 | 必须同屏看见 | 停止条件 |
| --- | --- | --- | --- |
| M1：原 A + 一组真实感桌椅/书材质 | 保持灯光、相机、角色动作、窗口不变；替换与任务接触的 2–3 件物件 | 房间整体风格、手与键盘、臀与椅、书的识别度，昼夜各一张 | 素材风格割裂、许可不清、原尺寸看不出收益 |
| M2：原 A + 阅读动作 | 同一角色/家具/灯光/镜头，切换电脑与读书动作；动作必须由明确任务状态触发 | 不看文字也能区分电脑与读书；计划未开始仍待机；暂停不继续表演 | 手穿书/桌、书和手错位、转场瞬移、原尺寸不可分辨 |

每组保留可打开的 Blender/GLB/Godot 来源、原大 PNG、连续短录屏和参数表。图像生成可用来制作概念稿或纹理方向，但生成图本身不是可复用的 3D 网格、骨架或动作；照片生成个人角色要另验本人照片的私有处理、删除与肖像相似度。M1/M2 与真正手绘像素 2D 最终在**同一任务事实、同一原生小窗**比较，由用户看运行效果决定首版路线。
