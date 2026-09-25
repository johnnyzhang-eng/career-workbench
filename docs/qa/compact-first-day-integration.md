# 首日任务与角落小窗：草稿集成验收

状态：2026-09-25，使用虚构 CET6 与秋招资料；本分支以 [PR #52](https://github.com/johnnyzhang-eng/career-workbench/pull/52) 为底，并把 [PR #49](https://github.com/johnnyzhang-eng/career-workbench/pull/49) 的原生窗口文件接入同一个源码树。网页版首日行为仍由 #52 及其依赖提供；本次合流重点复核原生小窗的首屏和可见关闭入口。

## 本机可复核路径

本分支以 `private/integration-qa` 内的虚构工作区启动 `scripts/serve_goal_companion.py`，临时端口 8796；复制样本只在被 Git 忽略的 `private/` 下，不进入 PR。

1. 真实浏览器打开 `/compact`，首屏显示“虚构 CET6 七日练习”、夜晚房间、今日任务、`09月25日` 和“开始行动”；点击开始后，房间转为学习、任务卡转为“行动中”、按钮转为“暂停行动”。
2. 点击暂停，房间回待机，任务卡显示“已暂停”和“继续行动”；展开链接仍带同一个 `goal_id`，完整工作台显示同一任务及继续、结束、记录依据入口。
3. 恢复后在完整工作台填三项**虚构**材料/基线/观察位置，保存完成依据；房间返回待机并明确说实际结果仍需本人确认。回 `/compact` 后，任务卡显示“已记录完成”，另有“1 项实际结果待确认”和进入确认的链接。此时页面没有声称 CET6 通过。
4. 用本分支 `prototype/macos/build.sh` 构建真实 macOS `NSPanel` / `WKWebView`，加载同一个本机服务。#50 的固定样本截图见 [首屏布局证据](../product/compact-ui-hierarchy.md)；下方记录接入原生关闭栏后的复核。

测试：`python3 -m unittest discover -s tests` 为 96 项通过；`docs/goal-companion.html` 的内联 JS 经 `node --check`；`git diff --check` 通过。以上是本机集成观察，不是发布版或所有状态/屏幕的视觉验收。#49 的独立双目标收起恢复验证见其 README；秋招完整日循环与网页新建目标保留选择的独立浏览器证据见 [秋招 QA](autumn-recruiting-local-e2e.md)。

## 原生合流复核：虚构秋招首日

在本分支新建被 Git 忽略的 `private/integration-qa` 工作区，启动 `python3 scripts/serve_goal_companion.py --workspace private/integration-qa --port 8836`，用本机 API 建立并明确接受、同步虚构 CET6 与秋招七日计划。两个目标各有一项今天的任务。执行 `prototype/macos/build.sh`，然后用 `private/CareerWorkbenchCompanion.app/Contents/MacOS/CompanionWindow --url 'http://127.0.0.1:8836/compact?goal_id=G-RCAAAAAAAAAAAAAAAAAAAAAA'` 打开虚构秋招目标。

- 实机可访问性树显示选中「虚构秋招首日测试」、今日「确定岗位筛选条件」、主按钮「开始行动」及原生「关闭小房间」按钮。
- 360×480 的 Retina 截图中，上方 28px 原生关闭栏、房间、当前行动和「开始行动」按钮同时可见；没有滚动才看到主按钮。时钟显示现实日期 `09月25日`，任务排在本地 `20:00`。
- 点击可见关闭按钮后，CUA 对窗口的后续读取超时，不能把这个超时单独当成「窗口已隐藏」的证明；本次只记录按钮可见与点击动作。**菜单栏恢复、退出应用和图标态关闭的实体点击仍未在此合流分支验证**。本次测试进程已经结束，没有留下常驻小窗。
- 本分支的 96 项单元测试、Swift 构建、`plutil -lint`、`git diff --check` 和隐私扫描通过。隐私扫描现在仅允许这六张已审阅的虚构对照 PNG，并按 PNG 块与 CRC 检查它们；没有放宽为整个 `prototype/` 目录。

同一个 8836 服务上，还按真实 HTTP 命令复核虚构秋招任务：开始 → 暂停 → 继续时 Daily 仍为 `scheduled`；完整视图和角落视图均返回同一服务页面；提交虚构 `result_ref` 后 Daily 为 `completed`、房间回 `idle`、实际结果先保持 `awaiting_user_confirmation`；本人另填 12 分钟和「未核对岗位，未申请」后才变成 `recorded`。相同完成命令重放没有增加结果。停止并重启服务后，秋招完成与确认结果均恢复，另一虚构 CET6 目标仍无结果。此项是 HTTP 与持久化检查；浏览器逐屏操作证据仍以 [秋招 QA](autumn-recruiting-local-e2e.md) 为准。

## 当前分界

- 此集成仍用原创 2D 像素房间草案。3D 的 [只读 Godot 状态桥](https://github.com/johnnyzhang-eng/career-workbench/pull/47)尚未替换这个房间，也没有在此窗口测常驻资源。
- 本轮只验证单个当天任务在角落小窗首屏可见；多任务排序、超长目标名、全屏应用遮挡、跨日后原生窗口回显尚需逐项验。
- 任务完成依据、本人确认的实际结果、外部考试/投递结果仍是不同事实；场景只读。照片输入尚未生成个人角色。
