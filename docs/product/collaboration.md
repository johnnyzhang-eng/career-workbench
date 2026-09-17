# 多人协作契约

目标是让贡献者能并行开发而不各自发明用户、岗位或“已掌握”的定义。产品判断以[简报](brief.md)和[架构基线](architecture.md)为准；模块字段以[数据契约](contracts.md)为当前评审对象。它们仍是设计，不代表功能已上线。

## 任务分界与依赖

| 工作流 | 所属 Issue | 可以并行做 | 接口交点 |
|---|---|---|---|
| 用户任务验证 | [#1](https://github.com/johnnyzhang-eng/career-workbench/issues/1) | 虚构试用脚本、经同意的观察方案 | 反馈给其他任务的验收标准；不公开真人材料 |
| 岗位入口与目标 | [#5](https://github.com/johnnyzhang-eng/career-workbench/issues/5) | 链接/JD 导入、来源适配、原站入口、目标比较 | 输出 `JobSnapshot`、`JobRequirement`、`TargetDirection` |
| 证据与缺口 | [#3](https://github.com/johnnyzhang-eng/career-workbench/issues/3) | 证据分级、模型端口、来源校验、差距草稿 | 输入岗位要求，输出 `GapProposal`；不得覆盖真实证据 |
| 练习与资源 | [#2](https://github.com/johnnyzhang-eng/career-workbench/issues/2) | 资源元数据、章节匹配、学习进度 | 输入已确认技能，输出推荐与 `LearningEvent` |
| 架构与协作基线 | [#6](https://github.com/johnnyzhang-eng/career-workbench/issues/6) | 维护边界、契约和协作规则 | 跨模块字段或隐私规则改变时先在此讨论 |

建议的合并顺序：先确定用例和契约，再做岗位要求到外部章节的资源导航切片，最后接入模型草稿和跨方向证据回流；独立的资源元数据或 UI 草图可并行。任务认领在 Issue 指派或留言，不能仅在聊天中口头声称。每个 PR 关联一个主 Issue；跨接口改动先在关联 Issue 说明影响，再由受影响模块的贡献者 review。没有受影响者的确认，不把字段改名当作“内部重构”。

## PR 完成定义

- 明确用户场景、输入与来源、产物、非目标，以及“已有/拟建/待验证”的状态。
- 对外可见的断言有虚构端到端用例；保留失败、未知、求助与人工复核路径。
- 运行相应单元/契约测试、演示和隐私扫描；PR 的离线 CI 会跑现有测试与扫描，但不能只报告“命令没崩”。
- 人工检查待推文件、diff、提交作者与链接参数；不得提交真实简历、录音、面试原话、回执、凭证或供应商密钥。
- 若改契约、状态机或用户可见行为，同步更新文档和迁移说明。Review 后再合并，不以 PR 已打开代替验收。

现有命令行底座的回归命令见根目录 README；新增模块必须增加自己的虚构测试。岗位数据接口、模型服务和资源网站不能成为 CI 的唯一真相源：离线 fixture 验结构，人工或受控集成验实时性。任何收费或对外投递动作均不属于自动测试。

## 决策与冲突

对架构有分歧时，先在 Issue 写明候选方案、当前证据、会影响的契约和最小验证任务；不要在不同分支里偷偷形成两个版本。新证据推翻旧结论时，改最初的决策记录和仍开放的任务卡。来源合法性、私人资料外发、模型调用费用或托管用户数据涉及新责任时，单独提出并取得明确授权。

## 标签与生命周期

参考 Windup 的提案、规格和用户文档状态，按本项目的责任边界使用：

| 维度 | 标签 | 使用条件 |
|---|---|---|
| 提案 | proposal | 产品或架构方案待讨论 |
| 决策 | Proposal-Accepted / Proposal-Denied / Proposal-NoPlan | 互斥；接受必须有明确决定，不能因 PR 已开就自动接受 |
| 规格 | FullSpec / MiniSpec | 二选一；跨模块完整规格或小改动规格，不表示功能已完成 |
| 优先级 | P0 / P1 / P2 | 最多一个；当前阻塞 / 本阶段下一优先 / 后续 |
| 用户文档 | Need-Document / Documented | 仅用于已实现功能的用户文档，不能给设计草稿贴 Documented |
| 材料与拆解 | document / sub-task | 架构材料 / 父提案的独立可验收切片 |
| 领域 | area:architecture / area:jobs / area:evidence / area:learning / area:validation | 可多选，表示受影响领域，不表示负责人 |

提案讨论后记录决策，明确规格与验收，再认领开发；实现 PR 关联主 Issue，验收与评审完成后合并。Assignee 表示负责人，Open/Closed 与 PR Review 表示工作状态；不重复创建一套状态标签。阶段范围明确后再挂 Milestone，阶段验收后才发 Release，不以标签齐全代替开发结果。

本仓保留版本化产品文档，Issue 记录范围、决定及文档/提交链接；不自动采用其他仓库“设计 PR 不合并”或特定机器人的要求。修订设计时同时更新仍开放的任务卡和首片验收，避免两套范围流通。
