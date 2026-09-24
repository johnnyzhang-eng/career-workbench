# 首日任务与角落小窗：草稿集成验收

状态：2026-09-25，仅使用虚构 CET6 资料；本分支为合流草案，基于 [PR #46](https://github.com/johnnyzhang-eng/career-workbench/pull/46)，叠加 [PR #50](https://github.com/johnnyzhang-eng/career-workbench/pull/50) 的小窗首屏和 [PR #51](https://github.com/johnnyzhang-eng/career-workbench/pull/51) 的目标选择修复。原生外壳使用独立的 [PR #49](https://github.com/johnnyzhang-eng/career-workbench/pull/49) 构建产物读取同一临时服务；它的 Swift 修改不在本分支。

## 本机可复核路径

本分支以 `private/integration-qa` 内的虚构工作区启动 `scripts/serve_goal_companion.py`，临时端口 8796；复制样本只在被 Git 忽略的 `private/` 下，不进入 PR。

1. 真实浏览器打开 `/compact`，首屏显示“虚构 CET6 七日练习”、夜晚房间、今日任务、`09月25日` 和“开始行动”；点击开始后，房间转为学习、任务卡转为“行动中”、按钮转为“暂停行动”。
2. 点击暂停，房间回待机，任务卡显示“已暂停”和“继续行动”；展开链接仍带同一个 `goal_id`，完整工作台显示同一任务及继续、结束、记录依据入口。
3. 恢复后在完整工作台填三项**虚构**材料/基线/观察位置，保存完成依据；房间返回待机并明确说实际结果仍需本人确认。回 `/compact` 后，任务卡显示“已记录完成”，另有“1 项实际结果待确认”和进入确认的链接。此时页面没有声称 CET6 通过。
4. 用 #49 的真实 macOS `NSPanel` / `WKWebView` 加载同一个 8796 集成服务。360×480 小窗的 720×960 Retina 画面中，房间、人物、任务、状态和主按钮同时在首屏，未滚动；此次观察为暂停态。#50 的固定样本截图另见 [首屏布局证据](../product/compact-ui-hierarchy.md)。

测试：`python3 -m unittest discover -s tests` 为 96 项通过；`docs/goal-companion.html` 的内联 JS 经 `node --check`；`git diff --check` 通过。以上是本机集成观察，不是发布版或所有状态/屏幕的视觉验收。原生窗口未在此次集成重新测试多目标收起恢复；#49 的独立双目标实机验证见其 README。秋招完整日循环与网页新建目标保留选择的独立浏览器证据见 [秋招 QA](autumn-recruiting-local-e2e.md)。

## 当前分界

- 此集成仍用原创 2D 像素房间草案。3D 的 [只读 Godot 状态桥](https://github.com/johnnyzhang-eng/career-workbench/pull/47)尚未替换这个房间，也没有在此窗口测常驻资源。
- 本轮只验证单个当天任务在角落小窗首屏可见；多任务排序、超长目标名、全屏应用遮挡、跨日后原生窗口回显尚需逐项验。
- 任务完成依据、本人确认的实际结果、外部考试/投递结果仍是不同事实；场景只读。照片输入尚未生成个人角色。
