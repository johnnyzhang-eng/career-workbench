# 数据契约 v0.1（供协作评审，尚未实现）

这些名称和字段是模块间的**设计契约**，不是当前 `career.py` 的 JSON 格式，也不是数据库迁移已完成。实现前可在关联 Issue 中调整，但不得默默改变字段含义。对外公开的只有虚构 fixture；真实记录按[隐私边界](../privacy.md)留在本人工作区。

## 通用约定

- 每个实体有稳定 `id`、`schema_version`、`created_at`；时间统一带时区。更新保留原事件，不悄悄覆盖首次作答或投递历史。
- `unknown` 是有效状态，不等于 `false`、`fail`、空字符串或“模型没提到”。模型输出和第三方字段默认 `proposed`，学生确认后才是 `confirmed`。
- 来源引用用 `source_ref` 指向岗位/作答/资源的具体片段或字段；没有可检查来源就不能产生硬性资格结论。链接可能含个人追踪参数，只在私有记录保存；公开 fixture 用 `example.com`。
- 原始证据与派生判断分开：模型版本、提示版本或规则变化可重算建议，但不能重写学生当时的作答、求助程度和人工投递回执。

## 核心实体

| 实体 | 最小字段 | 不变量 |
|---|---|---|
| `JobSnapshot` | `id`, `source_kind`, `source_url`, `job_url`, `apply_url?`, `company`, `title`, `location?`, `employment_type?`, `captured_at`, `verified_at?`, `review_state` | 原始职位页与投递页分开；来源/核验时间缺失则不得显示“已核验可投” |
| `JobRequirement` | `id`, `job_id`, `text`, `category`, `requiredness`, `source_ref`, `review_state` | 每条要求来自具体 JD；学历/届别不由技能匹配推断 |
| `TargetDirection` | `id`, `name`, `job_ids`, `user_priority`, `updated_at` | 可并存、可调整；方向名不是录用概率 |
| `EvidenceItem` | `id`, `skill_id`, `kind`, `artifact_ref?`, `assistance`, `observed_at`, `review_state` | 项目经历、AI 辅助作答、独立作答、间隔复测级别不同；个人内容私有 |
| `GapProposal` | `id`, `target_ids`, `requirement_ids`, `evidence_ids`, `skill_id`, `judgement`, `rationale`, `source_refs`, `model_run_id?`, `review_state` | 只能提出 `needs_practice` / `evidence_present` / `unknown` 等候选判断；不能直接写“已掌握” |
| `PracticeUnit` | `id`, `skill_ids`, `requirement_ids`, `prerequisites`, `prompt`, `grader_kind`, `hint_levels`, `resource_ids`, `retest_unit_id?` | 题目原创、版本固定；复测用不同题面/数据但同能力目标 |
| `Attempt` | `id`, `unit_id`, `started_at`, `submitted_at?`, `answer_ref`, `assistance`, `grader_result?`, `independent_claim`, `is_retest` | 首次尝试不可覆盖；得到提示/AI 答案的同题不计独立通过 |
| `ResourceLink` | `id`, `title`, `url`, `source`, `skill_ids`, `prerequisites`, `access_terms`, `checked_at` | 只存合法引用和元数据，不复制第三方付费内容 |
| `ApplicationEvent` | `id`, `job_id`, `kind`, `at`, `evidence_ref?`, `human_confirmed` | `submitted` 必须有本人确认的真实回执；练习未完成不阻断投递 |

`source_ref` 应足以让使用者回看其**本人有权限阅读**的原文，而不是仅有模型生成的解释。公开演示不能包含真实 JD 全文、简历片段或面试转写。`model_run_id` 用于追查提议来自哪一次授权调用；不保留不必要的原始提示或响应全文。

## 模块端口（请求 → 响应）

| 端口 | 请求 | 响应 / 出错语义 |
|---|---|---|
| `JobSource.read` | 用户提供的具体 URL 或经许可的企业站点标识 | `JobSnapshot` 草稿 + 可引用 JD 片段；失败返回 `needs_user_text` / `needs_login` / `unavailable`，不返回“closed” |
| `JobReview.confirm` | 草稿、学生逐项确认/修正 | 已确认字段与未知项；缺来源的硬门槛仍为 unknown |
| `ModelPort.proposeGaps` | 经用户预览并授权的最少必要 `JobRequirement[]`、`EvidenceItem[]` | `GapProposal[]` 草稿 + 来源引用 + 模型运行元数据；拒绝/失败不写能力结论 |
| `Planner.nextAction` | 目标方向、已确认缺口、练习与资源目录 | 小任务及理由；岗位可投路径并行保留 |
| `Practice.submit` | `PracticeUnit`、作答和求助信息 | 不可变 `Attempt` + 可解释判题结果；模型评语不覆盖可运行测试 |
| `Evidence.recompute` | 新 `Attempt` / 面试反馈 | 各目标方向的证据摘要，保留未知与反证 |
| `Application.record` | 本人确认与回执位置 | 新 `ApplicationEvent`；无回执的 submitted 请求被拒绝 |

端口没有指定框架或远端服务。Alpha 先以同一进程的纯函数/对象实现，只有 `JobSource` 和 `ModelPort` 可跨外部网络边界；浏览器 UI 不直接持有模型密钥。

## 两个必须先通过的虚构用例

1. 两个虚构实习岗都要求基础 SQL，其中一个额外要求流处理。虚构学生只有 AI 辅助完成 SQL 项目的经历。系统可提出“SQL 基础待独立验证”的共通缺口，流处理是方向专属未知；不能把项目经历变成独立掌握，也不能因为没学流处理阻断另一个岗位的人工投递。
2. 同一学生第一次在提示后答对 `SELECT`/`FROM` 题。`Attempt.assistance` 记录提示，不能改写为独立通过；新题独立答对并在间隔后复测，证据才可上调。若模型离线，原作答和岗位仍可查看，缺口草稿标未分析。

这两个用例必须在测试中断言行为，而不只是断言 JSON 能通过解析。
