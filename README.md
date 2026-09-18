# Career Workbench

Career Workbench 正在构建一个面向求职学生的岗位目标驱动学习平台：找到并比较一个或多个目标方向，从真实岗位要求看见共通与专属的能力缺口，借助现成学习资源、短练习与复测积累证据，最后回到真实岗位入口和人工投递反馈。学习与投递可以并行，不需要等到“学完”才投。

这份目标产品仍处于[产品定义草案](docs/product/README.md)阶段；[边界图](docs/product/boundary-map-draft.html)和[架构基线](docs/product/architecture.md)区分了已有底座、设计建议和待确认事项。个性化补差计划支持用户自带模型，但模型只提出可复核的建议，不替代独立练习。本开发分支已有本地岗位候选网页和受控导入，仍待其他使用者试用；主线可运行的是本地命令行求职记录底座。缺口评估、模型接入、资源聚合、学习导航与证据验证尚未实现。真实个人记录保存在被 Git 忽略的 `private/`；公开仓库只放通用方法、代码、测试、空模板和虚构示例。

当前第一条开发切片是 [#9 持续发现岗位与原站投递入口](https://github.com/johnnyzhang-eng/career-workbench/issues/9)：每人用自己的本地 agent 按本人条件寻找候选岗位，通过受控数据契约把来源、原岗位链接和推荐依据交给本地工作台；工作台去重、展示待核验状态与原站投递入口。公开招聘接口可以作为补充来源。个人偏好与记录分别留在各自私有工作区；本人在原站申请。[#8 外部课程导航](https://github.com/johnnyzhang-eng/career-workbench/issues/8) 接在岗位入口后，不自建 SQL 课程或站内判题器。

## 试用本地岗位发现（#9 开发分支）

在仓库根目录运行：

```bash
python3 -m workbench.web --workspace private/me
```

打开命令行给出的 `http://127.0.0.1:8765/`。页面先填写自己的筛选条件，复制它生成的找岗任务给自己使用的本地 agent，再把 agent 返回的 JSON 粘贴导入。工作台显示来源、理由与未知项，允许打开原职位和待核验的申请入口。网页不运行 agent、不访问你的模型账号、不替你提交申请；每次新的 agent 结果可再次导入。输入 JSON 的格式和可选的 Ashby 补充来源见[岗位发现使用说明](docs/job-discovery.md)。不需要安装第三方 Python 包。

## 试用现有底座

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

已实现：本地状态机、缺项阻断、材料变更撤销确认、提交证据门槛、事件记录、复盘生成练习记录、待办、虚构端到端演示、隐私预检。

尚未实现：可解释的目标选择、真实岗位入口供给与核验、跨岗位能力缺口、学习资源聚合、在线练习判题与间隔复测、网站 UI。当前需手动提供岗位 URL，真正提交仍由本人完成。自动海投、自动联系、浏览器代填和绕过登录/验证码不在本产品范围内。

没有“拿 offer 保证”。用实际回执、面试反馈和独立练习结果验收，而不是用收藏数量验收。

[产品定义](docs/product/README.md) · [隐私与分享](docs/privacy.md) · [迭代清单](docs/backlog.md) · [开发约定](CONTRIBUTING.md) · [MIT 许可证](LICENSE)
