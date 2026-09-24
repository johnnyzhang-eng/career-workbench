# R3：椅面接点与小窗动作质量实验

本页为原 A 3D 房间里的第三轮角色实验，来自同仓 R1 的可编辑 Blender 母版。对照页面见 [R3 原尺寸审图](R3-index.html)，数据见 [R3 manifest](R3/manifest.json) 和 [小窗动作差分](R3/motion_measure.json)。**R3 是待评估原型，不是最终人物。**原 A 的房间、镜头 FOV 45°、光照、任务 UI 和虚构任务均不改；只替换电脑前人物。R2 控制图继续保留。

## 本轮实际修改

- R2 的裤子髋球体中心 Y=0.78、半径 0.17，椅面顶 Y=0.84，几何底端约 Y=0.61，穿入椅面约 0.23。R3 抬高髋与躯干 0.23，并重建两段大腿、两段上袖，静态髋球体底端约 Y=0.84。这是设计坐姿的几何接点校正，不代表布料模拟或逐帧无穿透。
- R3 在肘部加同材质桥接球遮住原分件缝隙。网格依然采用单骨刚性权重，球体与袖子并非连续平滑变形；全窗仍能辨出球形肩肘。
- 骨架由 8 根增至 12 根（加左右大腿、胫骨）。有 `ReachToType` 0.6 秒和 `TypingLoop` 1.2 秒两段动画。R3 在工作状态切入时已经坐在椅上，先伸手到键盘，再循环打字。**未实现站立走到椅子并坐下。**
- 试过把起始髋骨抬 0.26 再落座，[实机图](rejected-r3-hover-start-1280x720-day.png)显示鞋底悬空，所以否决该动作，不把它剪成“站坐过渡”。真正站坐需要站姿同骨架、膝踝约束与足底接地检查。

## 实机验证与局限

Godot 4.7.stable Compatibility 导入同仓原创 GLB 后记录 1 skin、12 joints、2 actions。真实窗口在 360×320 和 1280×720 各采白天/夜晚、9 个关键帧，共 36 张 PNG；360×320 白天另采 91 帧、3.03 秒 H.264 视频。Retina PNG/视频物理像素为 2 倍，审小窗时应以 360 CSS 像素观看。所有图是 Godot 窗口捕获，不是 Blender 渲染。

键盘水平投影 X ∈ [−1.295, −0.345]、Z ∈ [−1.43, −1.15]。R3 两个交替峰值的腕骨世界坐标 X ∈ [−1.282, −0.441]、Z ∈ [−1.247, −1.235]，均在投影内；**仅校验腕骨，不宣称指尖精准接触或无模型穿透**。曾试更大的手臂幅度，腕骨 X=−1.419 越界，因此收回。

在 360×320 原 A 构图中，R3 的人仍只有约 30 逻辑像素高。固定角色局部 65×70 物理像素、左右打字峰值 RGB 差分阈值 >16：R2 194 像素，R3 199 像素。这个差异很小，原大视频里可看出坐在电脑前，**不能据此说手部动作已经一眼可辨**。把角色放到小窗更大空间的构图实验应单独评估，不能把构图收益归到骨骼改进。

此资产和动作由本仓 Blender 脚本原创构建；`.blend` 可编辑，GLB 可重导入；未下载模型、动作、贴图或调用付费生成。沿用本仓 MIT，登记于 [ASSET_LICENSES](../ASSET_LICENSES.md)。不改正式产品人物，也不写入真实任务状态。

## 复现

在仓库根目录：

```sh
blender --background --python prototype/comparison/rigged_character_experiment/build_rigged_character_r3.py
/Applications/Godot.app/Contents/MacOS/Godot --headless --editor --import --path prototype/godot
python3 prototype/comparison/rigged_character_experiment/run_capture_r3.py
python3 prototype/comparison/rigged_character_experiment/measure_motion_r3.py
```

后两步需要桌面图形环境和 `ffmpeg`。捕获脚本核对骨架、动画、Godot 日志、像素尺寸和 SHA；它不能代替人工审图、动作接触测试或美术质量验收。
