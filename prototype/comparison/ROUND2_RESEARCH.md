# 第二轮美术研究：光照机制、真实像素方法与候选来源

状态：2026-09-24，仅研究与待讨论方案；**暂停新实现，所有下述试验和素材采用均待用户讨论**。本轮未下载资产、购买素材或调用收费API。用户明确认为A的光影/真实感优于B、B仍粗糙；D只是降采样等距研究，不能代表像素路线。原视频真实画面、屏幕上的要求/提示词待主协调任务直接核验；本文件不使用ASR推断原视频要求。

## A/B复查：观察、源码与假设分开

本轮实际重看 `evidence/baseline-1280x720-day-idle.png` 与 `3d-1280x720-day-idle.png`（高分屏2560×1440），此前各轮PNG观察见 VISUAL_REVIEW.md。A图中人物、桌腿、书架的地面/墙面投影清楚；B图中光暗反差弱，家具接触关系更平，增加缝线、植物、表情细节并未自动形成更好质感。B标题中的“改良”是实验标签，不能作为质量结论。旧PNG经历覆写，不能拿当前源码数值冒充每一张历史图的原始配置。

已读 `../godot/main.gd` 与 `../godot/comparison/room_3d.gd` 的当前源码。以下是机制线索，不是已做控制实验的因果证明：

| 当前源码差异 | 可能影响（待验证） | 受控复查方案 |
| --- | --- | --- |
| apply_phase 白天A主光0.65/环境0.36，B主光0.42/环境0.65；B另有能量0.22、无阴影的fill | B更依赖均匀环境/补光，可能降低投影与接触反差 | 固定B模型/相机/材质，先只关fill，再单改环境强度，再单改主光；每次保存配置、昼夜图、CPU。不得一轮全改后宣布根因 |
| A原场景默认透视/FOV45；B设置正交，相机取景也变了 | 深度线索与角色占屏不同，会干扰“更真实”比较 | 同一几何/光照分别透视与正交，匹配人物逻辑像素高度、房间边界；镜头变化单独评价，不把正交本身定为错误 |
| B沿用Box/Sphere/Cylinder部件并叠加脸部、口袋等；多数基础材质默认roughness=1 | 轮廓拼装感、硬边、材料过于一致可能保留粗糙感 | 固定A式光照，先只替换一张桌子的倒角/法线，再只改木/布/陶瓷粗糙度；人物独立做三视图与肘腕动作，不靠道具数量掩盖 |
| 当前项目为Compatibility后端 | 灯/阴影的效果与支持项具有后端差异 | 固定Godot版本与后端；切换阴影后重新比亮度，不跨后端混报结果 |

[Godot灯光文档](https://docs.godotengine.org/en/stable/tutorials/3d/lights_and_shadows.html)说明环境、灯节点、阴影各自作用，并特别提示Compatibility中启用阴影可能改变光照外观；因此“开阴影与关阴影同energy”也不能直接当同曝光比较。先用灰球、立方体和地面接触样本验证工具链，再改产品场景。此处仅提出实验，尚未执行。

## 官方工作流与可讨论的小样

| 目标 | 官方来源与具体操作提案 | 限制 |
| --- | --- | --- |
| 桌沿/柜角产生稳定高光 | [Blender Bevel Modifier](https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/bevel.html?highlight=select+edge)：对一件家具应用缩放后加小倒角，检查segments、重叠、法线，再导出对照 | 不把“更多面”当更好；小窗看不见的倒角无需扩量。主站正文直取受限，已通过官方搜索结果核对其segments/normal说明，实际操作须与本机版本再核对 |
| PBR材质表达 | [Godot StandardMaterial/ORM](https://docs.godotengine.org/en/stable/tutorials/3d/standard_material_3d.html)、[Khronos glTF2规范](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html)：一组木材/布/陶瓷测试物，分别设roughness；仅金属物用metallic；核对normal与ORM通道 | 纹理不代替几何轮廓；不要把室外旧木板直接铺满温暖室内。Blender节点不能假定全部无损导出，必须在Godot复查 |
| 真正像素路线 | [Godot多分辨率官方文档](https://docs.godotengine.org/en/stable/tutorials/rendering/multiple_resolutions.html)：先确定角色像素画布、调色板和逐帧轮廓，再nearest＋整数倍缩放；UI独立高分辨率层 | 官方建议integer避免像素不均。把现有矢量等距图缩小不是逐像素设计；D保留为渲染处理样本，不进入“像素路线已验证”证据 |

可讨论的像素小样：先画一个原创24×32或32×48角色母版，保留橙衣/深发/绿背包，以2×逻辑显示形成48×64或64×96角色；房间用16×16基础瓦片设计，限定一套调色板，分别手工修正idle、投入、完成三个关键姿态。房间与人物使用相同像素网格，不允许人物半像素移动导致闪动；全窗选择整数倍率或留边，不把像素层拉伸填满任意面板。以上画布与倍率是待讨论参数，未实现、未验收。

## 逐资产许可候选（全部未采用）

以下是2026-09-24实际打开的资产页/官方仓，不以站点印象代替具体许可。CC0允许复制、修改和再分发且通常无强制署名；仍建议保留作者/URL/下载日期及原许可文件。CC0不提供商标、隐私或他人权利担保，网站页面/标志不随资产自动授权；[CC0原文说明](https://creativecommons.org/publicdomain/zero/1.0/)。

| 候选与实际URL | 实际许可/署名 | 可用处与再分发边界 |
| --- | --- | --- |
| [Godot Lights and Shadows demo](https://github.com/godotengine/godot-demo-projects/tree/master/3d/lights_and_shadows) | 仓库[MIT许可](https://github.com/godotengine/godot-demo-projects/blob/master/LICENSE.md)，Godot Engine contributors / Juan Linietsky, Ariel Manzur | 学习灯光开关/阴影测试场景；复制代码保留版权与许可。已读该目录README和仓库LICENSE，未逐个下载资源检查；未来复制其中纹理/模型还须查看该文件附属license/credits，不能用根MIT覆盖例外 |
| [Godot Material Testers demo](https://github.com/godotengine/godot-demo-projects/tree/master/3d/material_testers) | 同上根MIT；目录存在由GitHub API核实，README已读取 | 用于材质对照方法，不是宿舍成品资产包；复制范围逐文件记录，附属资源许可同样另验 |
| [Kenney Furniture Kit](https://kenney.nl/assets/furniture-kit) | 具体资产页明确CC0；作者Kenney，建议署名“Kenney / Furniture Kit” | 140件3D家具候选，适合桌椅尺度、构图试验；可改/再分发资产，但不保证已有所需倒角/PBR质量，须下载后核对格式、网格和包内许可。免费单包可用，不购买All-in-1 |
| [Kenney Tiny Town](https://kenney.nl/assets/tiny-town) | 具体资产页明确CC0、16×16像素瓦片；建议署名“Kenney / Tiny Town” | 用于像素网格、瓦片边界、调色板与整数显示试验，可改/再分发；它是城镇/overworld包，不是宿舍人物成品，不应强行移植成视觉目标 |
| [Poly Haven Modern Buildings 2](https://polyhaven.com/a/modern_buildings_2) | 具体资产页CC0，作者Alexander Scholten | 高反差自然光HDRI可作照明方向控制样本；不是宿舍背景。只考虑低分辨率照明测试，勿先下载21K。资产可再分发，站点logo/页面截图另属其范围；建议署名作者和资产名 |
| [Poly Haven Wood Floor Deck](https://polyhaven.com/a/wood_floor_deck) | 具体资产页CC0，作者Dimitrios Savva；含Diffuse、AO/Rough/Metal、GL/DX normal等 | 用于PBR通道/尺度验证，可修改再分发；风化室外木板可能不适合学生卧室，仅作为测试候选。Godot使用时验证normal约定与UV尺度，不把DX/GL法线混用 |

Poly Haven具体页均直接显示作者与CC0，并核对其[官方许可范围](https://polyhaven.com/license)。本研究未采用上述任何文件，因此不向现有ASSET_LICENSES清单添加“已采用”记录。若讨论后决定试用，先取最小必要文件、保存哈希/原LICENSE/来源，再在隔离小样中测；新增可分发代码/素材以具体包内容为最终依据。

## 小窗质量门槛提案（待讨论）

1. **测量条件**：逻辑360×320，Retina2×原生720×640；同时保存scale、原生尺寸、窗口位置和原始PNG。实际屏幕360逻辑尺寸看效果，原生PNG放大只能诊断细节。候选人物占屏高度先匹配，排除镜头倍率混淆。
2. **轮廓**：原尺寸可区分头/手/脚和橙衣/绿包；投入、短完成反馈、静止三种轮廓可辨。试用者不靠状态文案指出动作；不达标先调构图/姿态，不立即加贴图或改模型。
3. **光照/材料**：脚底与桌腿接地、家具不漂浮；白天有可辨方向光与接触暗部，夜晚脸部可读；墙/木/布不全部表现为相同亮度和平面色。维持用户认可的A光影作为视觉参照，不把B当默认质量升级。
4. **像素**：角色以原始像素母版验收，检查色块、单像素杂点、轮廓和关键帧；最近邻且整数倍率，无大小不均的像素格/细线；录屏动作无亚像素抖动。D旧图不能满足这一制作证据门槛。
5. **温和反馈**：完成动作结束后同一completed任务保持至少3秒，证实自然回静止；延期无扣分/受伤/羞辱。idle连续观察60秒无抢焦点/闪烁。
6. **资源与许可证**：同机同后端同帧率上限取启动、idle/active CPU/RSS；渲染截图不算性能采样；记录每个外部文件的具体许可、署名和再分发要求。
7. **交付分级**：每个方案只给一个角色/一件家具或一间最小房间、昼夜、小窗/全窗及同任务动作；先评审再扩大资产。结果可为继续验证，不能仅凭一次“更漂亮”宣布路线或模型胜负。

## 待用户讨论的选项

- **3D灯光优先复查**：保留A的空间感，先单因素确认B变平原因，再讨论少量倒角/PBR与人物轮廓修整。成本是受控试验与建模检查时间，当前不启动。
- **原创像素母版试验**：新做原生像素角色/房间小样，按整数缩放验收；Tiny Town仅辅助验证显示方法，不能替代原创宿舍设定。当前不启动。
- **保留等距2D作为第三对照**：先匹配角色占屏比和动作，再比较光影/成本；不将D降采样继续称作完整像素候选。

本文件提供可执行调查方案与许可线索，尚无新方案的运行证据。关于原视频要求，应等主代理的真实帧/屏幕文字复核后再合并决策。
