# Career Workbench

面向求职学生的开源工作台：从目标岗位出发，把能力缺口、学习练习、人工投递与复盘连成有证据的闭环。

**主线版本是本地命令行 MVP；本草稿分支增加本机目标执行工作台和 macOS 角落小窗样机。** Python 3.10+、标准库、无模型调用、无需账号。真实个人记录保存在被 Git 忽略的 `private/`。仓库只放通用方法、代码、测试、空模板和虚构示例。工作台不会自动海投；更完整的产品范围见[产品定义](docs/product/README.md)。

## 试用目标执行工作台（草稿分支）

先在本机私有工作区启动服务，打开打印出的地址。页面可从秋招或 CET6 虚构目标开始，查看有来源的七日提案，明确接受并写入今日清单，然后开始行动、记录依据和本人确认实际结果。

```bash
python3 scripts/serve_goal_companion.py --workspace private/goal-companion --port 8794
```

macOS 角落小窗需在另一个终端构建并打开。无边框窗口有可见 ×；菜单栏 ⌂ 提供重新打开和退出入口。原生窗口目前不会代管 Python 服务。

```bash
prototype/macos/build.sh
open private/CareerWorkbenchCompanion.app
```

现实目标、时间和外部来源仍需本人核对。房间动作、工具活动和每日任务完成不代表岗位已投递或考试通过。虚构复核路径见[首日集成记录](docs/qa/compact-first-day-integration.md)与[桌宠首日合流](docs/qa/pet-first-day-integration.md)，原生窗口边界见[小窗说明](prototype/macos/README.md)。

## 先看图，再跑通

打开 [完整流程图](docs/workflow.html)，再读 [阶段与验收](docs/workflow.md)。

```bash
python3 career.py demo
python3 career.py --workspace private/demo today
python3 -m unittest discover -s tests -v
python3 scripts/check_privacy.py
```

`demo` 用虚构公司走完收集 → 核验 → 材料 → 人工确认 → 记录提交 → 面试 → 复盘 → 练习。它不会访问网站、发消息或投递简历；重复执行不会覆盖已有演示数据。

## 开始自己的求职

```bash
python3 career.py init
python3 career.py --help
python3 career.py add private/opportunity.json
python3 career.py assess JOB-001 private/assessment.json
python3 career.py prepare JOB-001 private/materials.json
python3 career.py approve JOB-001 --confirm
# 本人完成实际投递后，才登记有回执的状态
python3 career.py record JOB-001 submitted --evidence '本人核验的投递回执位置'
python3 career.py today
```

参考 `templates/` 填写自己的 JSON，放在 `private/` 内；不要往共享模板填真人数据。材料包里的路径以当前工作目录为基准，必须指向当前 workspace 内的文件。

继续流程：

```bash
python3 career.py record JOB-001 interview --evidence '面试邀请位置'
python3 career.py review JOB-001 private/review.json
python3 career.py practice 1 --evidence '自己写的代码与测试位置' --independent
```

`practice` 只记录本人声明的独立练习证据，不自动判定掌握。延迟复测另建任务。

## 协作方式

- 主负责人处理目标、取舍、事实冲突和验收；执行者按小任务提交产物与证据。
- 每项开发用需求 → Issue/任务卡 → 实现 → 测试 → review → 更新文档的流程。
- 同学独立填写画像和运行 `private/`，不照搬他人的岗位优先级或能力结论。
- 模型与工具自行选择；本项目不绑定供应商，不自动启动付费调用或子 agent。
- 修改通用方法可以走 PR；个人求职记录不放 Issue、PR、截图或 Actions 日志。

## 当前边界

已实现：本地状态机、缺项阻断、材料变更撤销确认、提交证据门槛、事件记录、复盘生成练习、待办、虚构端到端演示、隐私预检。

尚未实现：官网抓取适配器、浏览器代填、登录/验证码、自动联系、跨设备同步、自动简历生成、自动评分。网页目标执行界面和原生小窗仍是草稿样机；查岗和真正提交仍由人或获授权的工具完成。

没有“拿 offer 保证”。用实际回执、面试反馈和独立练习结果验收，而不是用收藏数量验收。

[产品定义](docs/product/README.md) · [隐私与分享](docs/privacy.md) · [迭代清单](docs/backlog.md) · [开发约定](CONTRIBUTING.md) · [MIT 许可证](LICENSE)

每日任务内核的说明见[任务与七天虚构用例](docs/daily-tasks.md)。目标工作台与原生小窗已经在此草稿分支接入同一本机服务；3D 场景、长期常驻资源和真人验收仍另行进行。
