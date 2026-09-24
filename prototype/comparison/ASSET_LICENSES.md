# 美术对照素材来源与许可证

登记日期：2026-09-24。范围：Issue #20 同场景对照。以下登记本轮提交的原创源与使用边界；源文件、虚构fixture、应用自身截图和脱敏日志已进行人工检查，二进制发行另行检查。

## 原创内容

| 内容 | 来源/可编辑源 | 许可与分发说明 | 核验状态 |
| --- | --- | --- | --- |
| 原始学生与房间 | ../godot/main.gd；由 Godot 基础几何生成 | 仓库原创项目内容，沿用根目录 MIT LICENSE，保留版权与许可声明 | 已读取生成代码的资源引用；既有 QA 记录可追踪 |
| 书桌灯具 GLB | ../blender/build_lamp.py → ../godot/assets/desk_lamp.glb | 原创五部件程序建模，无外部贴图；输出沿用项目 MIT；生成脚本随仓保留 | 已读脚本：三个程序材质、法线重算、无骨骼 |
| 单桌面实验 GLB | [自制 Blender 脚本及可编辑母版](hero_desk_experiment/README.md) → [hero_desk_top.glb](../godot/comparison/assets/hero_desk_top.glb) | 2026-09-25 新增的原创单物件实验，沿用项目 MIT；不含外部模型/贴图，不代表已替换正式 A 基线 | Blender 5.1.2 重开确认 1 mesh、3 materials、2 modifiers；GLB 结构与 Godot 导入/昼夜截图见实验 manifest |
| 单角色实验站姿/电脑坐姿 GLB | [自制 Blender 脚本及可编辑母版](character_experiment/README.md) → `../godot/comparison/assets/adult_student_idle.glb`、`adult_student_typing.glb` | 2026-09-25 原创对照，沿用项目 MIT；仅 Blender 内置网格与程序材质，无外部模型、贴图或动作文件；**静态姿态、没有骨骼动画**，不替换正式 A | GLB 的 mesh/material/skin/animation 清单、Godot 导入、昼夜与两尺寸原大截图见 [manifest](character_experiment/manifest.json) |
| 改良 3D 学生、宿舍与道具 | [room_3d.gd](../godot/comparison/room_3d.gd)，继承 [main.gd](../godot/main.gd) | 仅原创程序几何/材质，沿用项目 MIT；无外部 base mesh、HDRI 或纹理 | 已核对脚本继承与本地资源引用；运行画面已抽样审阅，具体边界见 VISUAL_REVIEW.md |
| 等距 2D 学生、房间与动作 | [room_2d.gd](../godot/comparison/room_2d.gd) | 原创形状和颜色组合，沿用项目 MIT；不描摹游戏角色、素材包或视频帧 | 已核对程序多边形、线条和颜色绘制，无外部图片加载；运行画面已抽样审阅，具体边界见 VISUAL_REVIEW.md |
| 最近邻像素化 2D | [comparison.gd](../godot/comparison/comparison.gd) 的低分辨率 viewport，复用 room_2d.gd | 同源衍生输出，沿用项目 MIT；记录分辨率及缩放方法 | 已核对低分辨率 viewport 与实际运行输出；不代表手工像素美术 |
| UI、任务文本与截图 | [comparison.gd](../godot/comparison/comparison.gd)、[tasks.json](../godot/comparison/tasks.json) 和实际运行窗口 | 原创虚构内容；公开截图只含项目场景，不含其他应用、姓名或个人任务记录 | 已读三项虚构 fixture（核验/听力/复盘）；已检查应用自身截图，无桌面/其他应用截图；最终提交范围另经人工核对 |

项目许可证见 [LICENSE](../../LICENSE)。这里的“原创”表示本任务使用自写脚本与基础图形构造，不是对任何自动生成内容作超出证据的权利保证。所有新资产仍须由提交者检查来源与相似性；不用第三方素材库、收费 API 或购买素材。

## 工具和字体与资产分开登记

| 项目 | 来源 | 使用边界 |
| --- | --- | --- |
| Godot 引擎 | [官方许可](https://godotengine.org/license/) | MIT 引擎许可不自动替本项目资产授权。分发含引擎的可执行包时保留引擎版权/许可及所含第三方组件声明；当前源项目不重新分发本机 Godot 应用。 |
| Blender 工具 | [官方许可](https://www.blender.org/about/license/)、[官方手册](https://docs.blender.org/manual/en/4.2/getting_started/about/license.html) | Blender 本体采用 GPL；官方说明输出作品不因工具自动成为 GPL。此任务仅本机生成 GLB，不分发 Blender 本体或第三方 add-on。 |
| 系统字体 | 运行机器已安装字体，经系统回退或 SystemFont 使用 | 只调用本机字体，不复制、打包或上传字体文件；不能称其 CC0/MIT。截图记录系统与实际字体配置；跨平台外观可能改变，需目标机器复测。 |
| Godot 默认/回退字体 | 本机 Godot 发行包及其第三方声明 | 默认引擎字体与操作系统字体不是同一来源；若实现未明确指定 SystemFont，应记录为引擎默认/系统回退待确认，不能捏造字体名。可执行导出前检查实际内嵌字体和引擎第三方声明。 |

官方许可页已于登记日期查阅；Blender 主站直连读取受限，许可说明以官方搜索结果及官方手册交叉核对。没有单独取得任何系统字体的再分发授权，故不分发字体文件。

## 参考范围

《模拟人生》的剖面房间、角色定制与生活互动，Spirit City: Lofi Sessions 的房间/专注工具构图，Virtual Cottage 的真实时钟氛围，仅是产品思想参考；不提取角色、家具、贴图、音频、UI 或游戏截图进入仓库。Windup 仅参考原创角色制作与质量检查流程；未授权移植任何角色或成品画风。参考视频只记录链接与时间码，不上传他人帧图。

Kenney、Poly Haven 曾在 #20 提案中作为可研究来源，本轮未采用，不能把站点常见 CC0 概括为已经核验某个资产。后续采用任何外部文件都需单独登记具体页面、作者、下载日期、原许可证、修改内容、署名和源文件再分发权限。

## 提交前清单

- 列明本轮实际新增资源文件与生成脚本路径，并删除仍未实现的条目或标明未采用。
- 查找所有 load/preload、字体路径、贴图路径和远程 URL；每个资源都能对应以上来源。
- 检查无 .ttf/.otf/.woff 等系统字体副本、下载素材、收费调用、私人 fixture 或跨应用截图。
- 若将来发布二进制，另验导出包内的引擎/字体/第三方 notices；源项目检查不代替发行包检查。

## 当前资源引用核对

`comparison.gd` 读取本地 `res://comparison/tasks.json` 并加载 `room_3d.gd` 或 `room_2d.gd`；`room_3d.gd` 继承 `res://main.gd`，原场景加载 `res://assets/desk_lamp.glb`。本轮三个脚本未发现远程 URL 或外部贴图/字体文件引用。代码只设置字体字号/颜色，未指定 SystemFont 或字体文件，因此当前实际字体记为 **Godot 默认/系统回退，实际字形来源待运行环境确认**。本记录针对读取时的源码；最终 diff 仍须重查新增引用。

## 高分屏截图与派生资源口径

窗口与截图采用逻辑尺寸和原生像素分别登记：本机 scale=2 时，逻辑 360×320 / 800×600 / 1280×720 对应原生 720×640 / 1600×1200 / 2560×1440。普通 2D/3D viewport 按显示倍率渲染，像素化路线保留低内部逻辑分辨率。该改动属于已有原创场景的渲染设置，没有引入第三方贴图或字体；字体字号依然按逻辑尺寸。旧同名截图会被重跑覆盖，许可证来源不变，但验收指纹和批次必须刷新；旧像素尺寸不得被当作实际逻辑窗口尺寸。
