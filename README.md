# Career Workbench

**新产品方向提案（2026-09-24）：**在现有求职记录底座上，探索与现实时间同步的目标执行伴随系统：设置目标、拆分每日行动、记录结果并调整计划。秋招求职与技能学习是首批领域，CET6 用于检验通用目标流程；见[定位与体验门槛](docs/product/product-direction-gate.md)、[秋招用例计划](docs/product/daily-workbench-plan.md)和 [Issue #12](https://github.com/johnnyzhang-eng/career-workbench/issues/12)。这些新功能尚未实现，不改变下方现有命令的行为。

面向求职学生的开源工作台：从目标岗位出发，把能力缺口、学习练习、人工投递与复盘连成有证据的闭环。

**当前版本是本地命令行 MVP，不是网站，也不是自动海投机器人。** Python 3.10+、标准库、无模型调用、无需账号。真实个人记录保存在被 Git 忽略的 `private/`。仓库只放通用方法、代码、测试、空模板和虚构示例。规划中的岗位驱动学习、零基础课程与网页工作台见[产品定义](docs/product/README.md)，不能当作现有功能。

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

尚未实现：官网抓取适配器、浏览器代填、登录/验证码、自动联系、网站 UI、跨设备同步、自动简历生成、自动评分。查岗和真正提交仍由人或获授权的工具完成。

没有“拿 offer 保证”。用实际回执、面试反馈和独立练习结果验收，而不是用收藏数量验收。

[产品定义](docs/product/README.md) · [隐私与分享](docs/privacy.md) · [迭代清单](docs/backlog.md) · [开发约定](CONTRIBUTING.md) · [MIT 许可证](LICENSE)
