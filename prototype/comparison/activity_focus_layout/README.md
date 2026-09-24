# 原 3D 小窗空间分配试验

状态：2026-09-25，Issue #20 的独立布局试验；不是美术定稿，也没有接入真实工作台。查看 [并排原尺寸对照](index.html)。本轮没有改 3D 模型、光照、相机或材质，也没有引入外部资产。

## 问题与唯一改动

在原 A 对照器中，360×320 逻辑窗口的房间纹理面积为 344×141；顶部导航、状态文字、结果和延期按钮占去大部分高度。人物即使有更多模型细节，也只占很少像素。用户希望默认小窗先看到“房子＋人”，展开才出现完整 workbench。

L0 是原 A 布局。L1 把同一房间纹理改为 344×222，保留顶部展开/收起与昼夜对照，底部保留一行任务标题；任务开始、结果与延期按钮只在展开窗中。**这改变的是布局信息分配**，没有声称两版功能等价。它验证场景面积对可读性的贡献及 UI 取舍，并非宣称 L1 已可作为产品默认小窗。

## 实际运行与复核

`run_activity_focus_layout.py` 依次运行 L0/L1、360×320/1280×720、白天/夜晚，先采 idle，再通过脚本把同一虚构任务设为 started 采图，共 16 张真实窗口截图；八次进程均退出 0 且日志无 `SCRIPT ERROR`/`ERROR:`。全窗时钟文字由两版共同固定为实验用 `12:00`，避免跨分钟让截图产生无关差异；不改变昼夜灯光。正式游戏仍使用真实时钟。本机 Godot 4.7.stable.official / GL Compatibility、Retina scale=2；小窗 PNG 720×640 原生像素，对照页用 CSS 显示为 360×320 逻辑尺寸。逐轮参数和 SHA-256 见 `manifest.json`，原始 `.log`/`.json` 在 L0、L1 目录。

L0 的白天、夜晚小窗 idle PNG 与现有原 A `comparison/evidence/baseline-360x320-*-idle.png` **逐字节相同**；L0 与 L1 的白天、夜晚全窗 idle PNG 也**逐字节相同**。这验证了脚本在非小窗状态下没有悄悄改动 3D 画面。

按 360×320 原大看，L1 的房间和人物明显更大，电脑、桌、书架与地面边界仍完整；昼夜投影保留。它更符合“先看到房子＋人”的入口，但当前角色的 started 动作仍是站在桌前摆臂，没有明确坐下与键盘接触；L1 不能靠变大解决动作真实性。L1 还隐藏了直接开始、记录结果、延期按钮，只有顶部「展开」可进入操作；需要在 [PR #38](https://github.com/johnnyzhang-eng/career-workbench/pull/38) 的实际任务界面里验证这个层级是否顺手。顶部热点仍是原对照器的演示按钮，不是最终产品导航。

## 与 R2 骨骼角色组合复查

在 [PR #35](https://github.com/johnnyzhang-eng/career-workbench/pull/35) 加入原创 R2 骨骼角色后，另以 `run_rigged_focus_layout.py` 固定 R2 的 `TypingLoop` 0.45 秒关键帧，再跑 L0/L1 × 昼夜四次真实 Godot 窗口采集，均无脚本错误且日志确认 8 骨/两段动画导入；原始图、日志和参数见 `rigged/`。这一组**只比较同一角色同一姿势在两种小窗布局中的可读性**，不把 R2 与原 A 角色当单因素布局对照。

R2＋L1 原大能更清楚辨出角色坐在桌前、双手朝向键盘，房间仍完整；具体哪只手敲键、指尖与键盘的接触在这个尺寸仍难确认。R2 本身记录的髋部椅面穿插、袖口接缝和不完整站坐过渡仍存在。另用 `run_rigged_focus_video.py` 从同一真实 Godot 小窗连续采 60 帧并编码为 2.5 秒视频，见 `rigged/L1/sit-and-type-focus-360x320-day.mp4`。原大观看时手部位移很弱，仍看不清敲键节奏；这条录屏是待改进证据，不是动作验收通过。

## 重跑

```sh
/Applications/Godot.app/Contents/MacOS/Godot --headless --editor --import --path prototype/godot
python3 prototype/comparison/run_activity_focus_layout.py
python3 prototype/comparison/run_rigged_focus_layout.py
python3 prototype/comparison/run_rigged_focus_video.py
```

这轮只证明真实窗口画幅变化与可观察的画面差异；没有测启动耗时、长期 CPU/RSS、跨应用点击、原生桌面嵌入，也没有和 2D 像素样本在同一产品小窗里进行最终偏好比较。下一步应把连续坐姿打字动作与 L0/L1 分别结合，并用同一任务状态在实际原生角落窗口中评审。
