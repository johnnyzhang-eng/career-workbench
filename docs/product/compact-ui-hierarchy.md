# 角落小窗首屏层级试验

关联：#20、#34；基于草稿 PR #45 的目标／清单状态。此目录的画面和任务均为虚构样本，当前 2D 房间只用于检验布局，未决定最终美术路线。

## 取舍

360×480 小窗先呈现房间、人物和一项当前行动。目标切换进入顶栏同一行；长目标名称在选择框里截短，完整选项和无障碍名称保留。小窗暂时不展示目标摘要、任务理由和证据表单；“全部任务／展开”进入原有完整工作台。房间图下注释保留活动线索与完成状态的边界，超出两行时只作视觉裁切，完整文本仍在 DOM/辅助功能树中。收起态仍是 74×74 房子入口。

## 实际验证

- 同一虚构 CET6 目标和 360×480 CSS 视口下，原版“开始行动”按钮顶部在 **744.9 px**，首屏外；新布局在 **385.7 px**，底部 **419.7 px**。房间、人物、任务标题、未开始状态和按钮同屏可见。对照见 [原版浏览器首屏](../../prototype/comparison/compact_ui_hierarchy/baseline-360x480-first-screen.png)与[本版浏览器首屏](../../prototype/comparison/compact_ui_hierarchy/improved-360x480-first-screen.png)。
- 从 PR #39 的原生 NSPanel/WKWebView 原型在私有测试目录编译一个指向独立 8813 端口的副本；窗口为 360×480 逻辑点，实机截图为 **720×960 像素**。见[未开始](../../prototype/comparison/compact_ui_hierarchy/native-360x480-retina-idle.png)、[行动中](../../prototype/comparison/compact_ui_hierarchy/native-360x480-retina-active.png)、[已暂停](../../prototype/comparison/compact_ui_hierarchy/native-360x480-retina-paused.png)。点击“开始行动”后房间切至学习动作、按钮变“暂停行动”；暂停后房间回到待机、按钮变“继续行动”。这只验证可见活动和入口，绝不等于任务完成。
- 原生目标选择框可切换 CET6／秋招，辅助功能树仍读到完整目标名称、房间状态、任务和操作；收起后原生 74×74 房子按钮可恢复小窗。浏览器在 1100×760 下完整工作台仍是左右两列，今日任务、复盘和计划均保留；见[展开页](../../prototype/comparison/compact_ui_hierarchy/expanded-1100x760.png)。

## 尚需处理

- PR #39 的原生房子按钮恢复时固定加载 `/compact`，未携带收起前的 `goal_id`；若之前切换到非最新目标，恢复后会回到最新目标。HTML 的收起链接已保留目标 ID，问题在原生 `reopenCompact()` 层。
- 目标标题特别长时选择框截短；需要通过展开选择框读取全名。无障碍文本仍完整。房间视觉质量、角色风格、长时间常驻的资源占用及跨应用遮挡不由此布局试验证明。
- 浏览器视口对照采用 360×480 CSS 像素；浏览器截图只覆盖其内容区。Retina 的 2 倍像素口径由上面的原生截图确认。
