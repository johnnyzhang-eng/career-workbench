# 数据契约 v0.2（供协作评审，尚未实现）

当前契约服务“岗位要求 → 合适的外部课程章节 → 学习记录”的首片。它不是现有 career.py 的存储格式，也不表示迁移已完成。来源与证据保留未知，课程内容在外站提供。

## 通用约定

实体具有稳定 id、schema_version、created_at；时间带时区。内容修订产生明确版本，旧来源引用仍可定位。事件只追加，重复事件 ID 幂等；事件和投影同事务。

人工录入/模型候选默认 proposed，确认后才为 confirmed；未确认、未核验和无匹配不能伪装成符合。学习进度与能力判断分开，自报完成不自动变为独立证据。公开 fixture 使用虚构岗位和 example.com 链接。

## 首片实体

| 实体 | 最小字段 | 不变量 |
|---|---|---|
| SourceRef | entity_id, revision, locator | 指向本人有权限查看的具体片段或字段；修订不重写历史引用 |
| JobSnapshot | id, revision, source_url, job_url, apply_url?, title, captured_at, verified_at?, review_state | 具体岗位页与投递页分开；核验状态不能由 HTTP 成功推出 |
| JobRequirement | id, job_id, text, category, requiredness, source_ref, review_state | 资格与技能分类；没有出处不产生硬资格结论 |
| TargetDirection | id, name, job_ids, user_priority | 可多个方向并存，不生成录用概率 |
| SkillDefinition | id, revision, name, definition | 同一能力有统一含义，基础 SQL 不代表全部 SQL |
| RequirementSkillLink | id, requirement_id, skill_id, source_refs, review_state | 人工确认或待确认；共通技能跨岗位共用 |
| ResourceLink | id, provider, title, chapter, url, language, format, prerequisites, level, learning_objectives, access_terms, checked_at?, verification_state | 只存元数据和具体章节入口；不复制课程/题库正文，不以可访问证明教学效果 |
| ResourceSkillLink | id, resource_id, skill_id, source_refs, review_state | 关联要有章节目标依据；不能因标题含 SQL 就覆盖所有 SQL 技能 |
| ResourceRecommendation | id, requirement_ids, resource_id, rationale, unmet_prerequisites, alternative_resource_ids, origin | 理由可解释；origin 区分规则/人工/模型；无合适项返回 no_match |
| LearningActivity | id, resource_id, skill_ids, created_at | 可在投递前开始；同一活动可关联多个岗位共通技能 |
| LearningEvent | id, activity_id, kind, at, evidence_ref? | kind 为 opened/in_progress/completed_self_reported；不能直接更新能力为已掌握 |
| EvidenceItem | id, skill_id, kind, artifact_ref?, assistance, observed_at, review_state | 首片外部学习记录只作未验证自述；artifact_ref 不赋予读取任意本地文件权限 |
| ApplicationEvent | id, job_id, kind, at, evidence_ref?, human_confirmed | 原 CLI 状态机继续生效；学习不阻断投递，submitted 需要本人确认的真实回执 |

verification_state 区分 unchecked、page_checked、needs_review；检查异常保留原因与旧检查记录，不能把瞬断判为永久失效。opened 只证明点击；completed_self_reported 只证明用户声明，evidence_status 保持 unverified。

## 端口

| 端口 | 输入 → 输出 | 边界 |
|---|---|---|
| JobReview.confirm | 岗位要求与来源 → 已确认字段/未知项 | 首片人工核对，缺出处的硬门槛仍 unknown |
| ResourceCatalog.match | 已确认技能、前置与语言偏好 → 推荐、替代或 no_match/needs_review | 确定性筛选，规则与模型来源分开；不编造链接 |
| Learning.record | 活动、进度与可选证据引用 → 追加事件与待验证摘要 | 事务保存、幂等；不自动读取外站账号/进度 |
| Evidence.summarize | 已有证据与关联技能 → 各方向证据摘要 | 学习进度不等于能力升级；保留未知和反证 |
| Application.record | 本人确认与回执位置 → 旧状态机记录 | 不绕过确认、材料版本与回执门槛 |
| JobSource.read / ModelPort.proposeGaps | 外部岗位 / 授权最小上下文 → 来源草稿 / GapProposal | 首片未配置；明确 not_configured，不伪造成功 |

UI 调用用例服务，服务依赖契约与存储端口，不依赖 HTTP。首片没有外部服务调用；打开课程或招聘网站由用户浏览器完成，不能把这类导航混同后端读取。

## 后续能力验证（不进入首片）

GapProposal 仍只能表达有来源的 needs_practice/evidence_present/unknown 候选，不能直接标掌握。接入模型时记录授权和运行版本，校验引用与权限。

PracticeUnit/Attempt/RetestPlan 不作为当前开发依赖。确需能力验证时，再明确外部证据导入或独立验证方式、题目版本/内容标识、前序尝试、帮助事件、间隔策略、判题结果及其信任边界。不能仅凭 independent_claim 或 is_retest 布尔值提升证据；也不预设工作台必须自建课程或判题器。

## 首片虚构用例

两个岗位共享 SQL 入门要求，其中一个另需流处理。学生查看有出处的映射，按语言与前置选择具体外部章节；SQL 记录跨两个方向可见，流处理保持未知。打开链接、自报完成、填写证据引用后，进度分别保存，能力仍待验证。

模型未配置、没有合适资源、链接核验异常、未知资格、重复请求和存储错误均须保留诚实状态。即使未开始学习，原岗位入口仍可打开。
