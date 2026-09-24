# M3：桌椅人物高度与明确任务镜头的组合诊断

本实验衔接 [R4 人物草稿 #55](https://github.com/johnnyzhang-eng/career-workbench/pull/55) 与 [M2 木桌草稿 #56](https://github.com/johnnyzhang-eng/career-workbench/pull/56)，展示为什么单独提高人物网格或桌面纹理仍不足以形成精美可用的 3D 小窗。它只使用**虚构任务**，不是首版美术路线决定。看 [同尺寸对照](index.html) 与 [逐张参数/SHA](manifest.json)。

## 固定内容与变化

两组都保留 A 房间昼夜光照、任务清单、明确点击开始/记录结果的 UI、同一 MPFB 日常服装静态坐姿和同一 Godot/2× Retina 捕获链。R4 控制组沿用 #55 的 1.35 倍人物、向前椅子、低椅背和固定桌面近镜头；M3 复用 #56 经单项许可核查的 [Poly Haven Wooden Table 02](https://polyhaven.com/a/wooden_table_02) GLB（SHA-256 在 manifest 中），并把桌面高度校到约 0.80 m、椅面顶端约 0.44 m、键盘与角色坐姿一起下移约 0.40 m。椅子/人物前移 0.55 m，键盘向人移动 0.15 m；角色保持原始 1.0 倍，而不是再放大。旧桌面与四条桌腿用几何尺寸识别并断言全部隐藏，避开 Godot 自动重命名同名节点的问题。这是**多项同时调整的组合样机**，不能用 R4/M3 两张图推断某一单项带来的因果效果。

M3 相机只随**明确任务状态**切换：待开始/已完成显示房间全景，点击开始后用 0.65 秒缓动拉到书桌近景。它不会读取窗口活动来猜任务，更不会据角色动作自动标记完成。原 A 站立吉祥物仍是占位，开始时会立即换成 MPFB 静态坐姿；人物换装/动作没有过渡，两者造型和比例也不统一。[镜头过渡短片](captures/m3-camera-transition.mp4)把这个跳变保留下来，不能把单张最终截图当作完整效果。

## 实机观察

R4 固定近镜头在「待开始」时会把站立吉祥物严重裁切；M3 的状态镜头恢复了能看到整个房间和人物的待开始画面。开始后 M3 的人物与桌面高差较合理，但产品小窗里人体仍很小，椅背遮住部分躯干；比起 R4 的放大人物，M3 不能被称为视觉质量胜出。扩大到工作台后能清楚看见木纹，也更清楚地看见未完成的桌椅/墙体形状。每个投影 AABB 都包含遮挡与裁切，数值只用于分析构图，不能当作可见像素或画质评分。

| 360×320 产品小窗白天 | 待开始人物 AABB | 进行中人物 AABB | 观察 |
| --- | ---: | ---: | --- |
| R4 固定近镜头 | 132.25×247.67，顶部 y=−1.17 | 52.23×77.00 | 待开始站立角色超出 141 高的场景画布；进行中人物更大 |
| M3 状态镜头 | 18.70×39.29，顶部 y=58.82 | 38.60×58.21 | 待开始人物完整但很小；开始后切近桌面，仍有椅背遮挡 |

这个样本仍把真实约 1.13 m 宽的木桌**非均匀拉宽到原 A 的 3.55 m 占位**，所以只有高度关系更接近人体尺寸，家具的整体比例依然失真；脚底/椅面/指尖也没有严格接触测试。用于正式首版前，必须统一桌子宽度、房间平面、人物身高和完整角色动作，重新构图，然后实测常驻 Web/原生窗口的资源预算。

## 重跑与许可

本分支直接使用 #56 相同 SHA 的 `polyhaven_wooden_table_02_1k.glb`，其 1K glTF 下载、校验与 Blender 打包脚本在 [#56 的木桌实验](https://github.com/johnnyzhang-eng/career-workbench/tree/experiment/desk-asset-m2/prototype/comparison/desk_asset_experiment)。Poly Haven 页面与[许可页](https://polyhaven.com/license)将该单件标为 CC0；MPFB 基础人体、服装、动作单项许可证和本地源流程见 #55。这个组合草稿不引入照片、第三方游戏截图或收费调用。

```sh
python3 prototype/comparison/scale_contact_experiment/run_capture.py
python3 prototype/comparison/scale_contact_experiment/make_transition_film.py
```

脚本先让 Godot 4.7 导入 GLB，再以真实窗口采 R4/M3 × 360×320/1280×720 × 白天/夜晚的待开始与进行中共 16 张图，同时在虚构数据上跑 `--proof`。PNG 元数据清理后存档，manifest 给出 SHA、渲染物理像素、人物投影 AABB 和构建源码指纹。
短片脚本再次跑 Godot 的 `--film --proof`，将待开始与开始后连续 26 帧编码成 14 fps 的 MP4，`camera_film.json` 记录成品与源码 SHA；需要本机有 ffmpeg/ffprobe。
