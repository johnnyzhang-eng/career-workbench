# 房间场景组件（可替换的视觉层）

`docs/goal-scene.js` 定义 `<goal-room-scene>`。它只画场景，不读取目标、判定任务完成、访问工具活动或写入工作台。`mode` 来自上层场景适配器：`idle | desk | study | interview | rest`；计划已安排但未开始时保持 `idle`。`phase=day|evening` 对应目标时区的现实时间；若不传，则组件按 `timezone` 读取当前时钟。角色姿态和光线只能作为当下状态的**视觉表达**，不能作为练习掌握或投递成功的证据。

## 两层美术素材

- `renderer="pixel"` 使用仓库内的原生 320×180 **正交 2D 像素画**背景，叠放 64×96 透明人物 sprite，并以 `image-rendering: pixelated` 缩放。背景和人物都是逐像素绘制的平面资产，未使用 3D 截图降采样或模糊滤镜。生成源码为 `scripts/build_goal_pixel_scene.py`，只依赖 Python 标准库；PNG 只含 IHDR、IDAT、IEND，无文本或 EXIF 元数据。这是原创像素草案，角色还不是用户本人。
- 默认 SVG 是 2.5D 插画**回退草案**，不称为像素成品。像素文件未配置、载入失败或 URL 未通过本机路径校验时，组件会回到此画面，并在无障碍说明中明确是草案。最终路线仍由用户看运行效果决定；可以更换整个 renderer/素材，而不改变目标与任务契约。

```html
<script nonce="由服务器提供" src="/goal-scene.js" defer></script>
<goal-room-scene
  renderer="pixel" mode="idle" phase="day" avatar="student"
  room-day-src="/scene-assets/room-day.png"
  room-evening-src="/scene-assets/room-evening.png"
  avatar-idle-src="/scene-assets/avatar-idle.png"
  avatar-desk-src="/scene-assets/avatar-desk.png"
  avatar-study-src="/scene-assets/avatar-study.png"
  avatar-interview-src="/scene-assets/avatar-interview.png"
  avatar-rest-src="/scene-assets/avatar-rest.png"
></goal-room-scene>
```

脚本启动时从其 `<script nonce>` 取 nonce，给 Shadow DOM 内 `<style>` 同 nonce；不需要放开 CSP 的 `'unsafe-inline'`。所有图片 URL 必须是同源 `/scene-assets/` 下的 PNG/WebP，拒绝远程地址、参数和 `..`。服务器还应对这 7 个固定文件建 allowlist，不提供任意文件服务。现有页面 CSP 的 `img-src 'self'` 足以显示这些本机图。

## 角色替换口

`avatar="student|indigo|amber|plum"` 是插画回退的配色预设。像素图可用 `avatar-src` 设定一张通用透明图，或用 `avatar-idle-src` 等按模式指定透明图；每个模式优先使用专用图。照片生成角色以后，先取得用户提供并认可的照片与输出，再把产物保存在本机允许的素材位置，并明确覆盖其使用范围。**本组件没有照片、上传逻辑或自动生成调用。** 新人物图应沿用 64×96 画布、透明底和脚底基线，或由上层调整容器中的角色锚点；不得悄悄把某个用户的照片或头像加入公开仓。

场景 DOM 不显示任务标题或私人文字，缩到约 320px 时人物、电脑、书本与休息椅仍有独立轮廓。动画只有轻微呼吸、眨眼和灯光；系统开启减少动态效果时关闭。屏幕阅读器获取当前 `mode` 和昼夜描述。

## 现阶段核验与限制

- `node --check docs/goal-scene.js`、`python3 -m py_compile scripts/build_goal_pixel_scene.py`；逐张核对 PNG 签名、尺寸及 chunk 清单；在原生 320×180 合成 day/idle、day/study、day/interview、evening/rest 画面作本地视觉检查。
- 第一轮素材见 Git 提交 `214c051`。第二轮只改了 `avatar-desk.png` 与 `avatar-interview.png`：电脑任务增加椅背、弯腿、伸手和键盘；面试增加正式上衣、耳麦及视频图标。背景和另外三态保持同一文件。`private/qa/scene-*-320.png` 是本机真实 320 CSS px 的五态截图，不随公开仓提交，可从两个提交复现素材对照。
- 第二轮 320px 截图里，书本、休息椅、电脑任务的坐姿和面试装束有不同轮廓；电脑人物与桌面仍像前景贴片，视频图标也很小。它们仅满足状态草案的可辨性，尚未达到用户参考视频的精修质量。下一轮需将人物坐姿、桌沿和屏幕按同一空间关系重绘，并与授权的高质量像素素材做同尺寸实机对照。
- 这些素材代表一个原创 2D 视觉方向，并不是对用户喜欢的完整游戏开发视频的最终美术对齐。最终角色风格、照片生成和桌面角落窗口的实际透明/置顶/鼠标穿透仍需后续设计与真实窗口验收。
