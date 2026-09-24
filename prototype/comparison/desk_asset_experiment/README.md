# M2：原 A 房间的真实木桌单件对照

这轮以原 A 房间为控制，只将桌面与四条桌腿换成 [Poly Haven Wooden Table 02](https://polyhaven.com/a/wooden_table_02) 的 1K glTF/材质，并保持人物、任务文本、相机、灯光、昼夜、其他道具和窗口尺寸相同。原大截图见 [对照页](index.html)，逐张 SHA、输入素材与现场记录见 [manifest.json](manifest.json)。这是 Issue #20 的**素材效果实验**，不替换正式场景。

## 来源、许可与构建

素材作者为 Serhii Khromov，资产页标注 CC0、约 1.1 m 宽、196 triangles；[Poly Haven 许可页](https://polyhaven.com/license)确认其站内模型可按 CC0 使用和再分发。`fetch_source.py` 只拉这一件官方 1K glTF、diffuse/normal/ARM 三张 JPG 与 BIN，按官方 API 的 MD5 校验，另记 SHA-256；源文件存在忽略的 `private/`。`build_asset.py` 在 Blender 5.1.2 将其打成带三张 1K 图片的单个 GLB，不重新绘制原作者纹理。本地 `.blend` 也留在 `private/`；仓库只提交生成脚本、GLB、Godot 实验脚本、截图与来源记录。

原 A 桌子宽约 3.55 m、桌面高约 1.25 m，外部模型只有约 1.13 m 宽、0.80 m 高。为了只看替换素材在**相同构图占比**的效果，M2 把模型非均匀放大到原桌子的宽、高、深；这会拉伸桌腿与木纹，不能当作真实人体尺度或生产最终设计。人体、桌椅、键盘仍必须整体重标定，见 [3D 品质计划](https://github.com/johnnyzhang-eng/career-workbench/blob/docs/daily-workbench-plan/docs/product/3d-quality-upgrade.md)。

## 实机证据和边界

脚本使用 Godot 4.7 Compatibility，在同一虚构任务下对 A/M2 逐一截取 360×320 与 1280×720 的昼夜、未开始与进行中画面。截图为 2× Retina 物理像素，且 `--proof` 完成一条虚构任务状态循环。`manifest.json` 的变化像素只计算**未开始时房间画布**，排除时钟文字，却仍包含由模型几何带来的阴影与抗锯齿差异；它不是画质分数。原大审图须同时看小窗和展开图，而不能只看变化像素比例。

| 画面 | 房间区域物理像素 | A→M2 变化像素 | 占房间区域 |
| --- | ---: | ---: | ---: |
| 360×320 白天 | 194,016 | 1,270 | 0.6546% |
| 360×320 夜晚 | 194,016 | 1,269 | 0.6541% |
| 1280×720 白天 | 2,028,400 | 17,981 | 0.8865% |
| 1280×720 夜晚 | 2,028,400 | 17,954 | 0.8851% |

计数仪器的同一张小窗图片自比结果为 0；M2 运行日志明确载入了外部 GLB。差异集中在桌面与相关阴影，从原大展开图能看到木纹，但小窗里桌子仍只占一角。像素占比不能代替视觉好坏，尤其用户可能注意到少量高对比的变化。

初版统计少隐藏了三条原桌腿：Godot 自动给重复的「Desk leg」节点改名，只按名称匹配漏掉了三条。修订版按原网格尺寸和位置定位四条腿，并断言桌面＋桌腿恰好隐藏 5 个部件；上表、截图与 manifest 均是修订后重跑值。旧数据 1,091／1,090 与 15,227／15,209 物理像素不再用作素材效果结论。

当前小窗里原 A 的整个房间本来就较小；木纹在展开态比小窗更容易辨认。更真实的资产如果只让屏幕上极少像素变化、还引入不合比例的桌腿，就不应单凭「来源更高级」进入正式版。此实验未测 Web 包下载、长时间常驻内存与电池、动态碰撞或多身材坐姿，也没有决定 2D/3D 路线。

## 重跑

```sh
python3 prototype/comparison/desk_asset_experiment/fetch_source.py
/Applications/Blender.app/Contents/MacOS/Blender -b --python prototype/comparison/desk_asset_experiment/build_asset.py
python3 prototype/comparison/desk_asset_experiment/run_capture.py
```

`run_capture.py` 会先导入 GLB，再以正常 Godot 窗口采图；本机需要 `ffmpeg` 将 PNG 解码以计房间区域的差异像素。这个测量依赖是实验工具，不进入应用运行时。

## 下一步

先在统一米制坐标下重新布局桌、椅、键盘与人物，再比较这类 1K 资产的纹理/边缘效果；若仍希望木纹可在小窗识别，应优先调整镜头、房间在 UI 中的面积、光照与对比，而非直接换 4K 贴图。展开态可以保留更细材质，但资源开销需与 #54 的常驻试验一起评估。
