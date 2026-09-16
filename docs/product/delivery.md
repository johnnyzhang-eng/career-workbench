# 从产品发现到可用工作台

公开仓库已经提供可运行的本地命令行原型与产品草案；这不等于学习闭环已完成。遵循[开发约定](../../CONTRIBUTING.md)与[隐私边界](../privacy.md)。

## 四个阶段及放行条件

| 阶段 | 主要产物 | 放行条件 |
|---|---|---|
| 发现 | 用户需求、匿名访谈摘要、岗位样本、竞品能力边界、风险清单 | 能指出首个用户实际卡住的任务；把观察和假设分开；用户认可 MVP 边界 |
| Alpha | 真实岗位→SQL 入门单元→独立复测→记录证据的纵向样板 | 首位用户能独立完成新题并找回原岗位；失败与求助记录不被覆盖；无未经授权的云端上传 |
| Beta | 至少另一位学生独立安装并完成不同岗位/技能包的流程 | 安装、任务理解、隐私和数据迁移经真实使用验收；修复可重复阻塞 |
| 扩展 | Python、算法和其他技能包，职位发现与网页体验 | 每项能力有真实用户验收、可追溯来源、独立练习与隐私检查；不按功能数量放行 |

这不是发布日期承诺。过不了放行条件就继续研究或修复，不用增加功能清单掩盖未验证的核心行为。GOV.UK 的[alpha 研究指南](https://www.gov.uk/service-manual/user-research/user-research-in-alpha)强调用真实用户测试端到端原型，而不是只验证界面偏好。

## GitHub 工作法

每个问题先建 Issue，写清用户、场景、输入来源、产物、非目标、验收与隐私风险；实现 PR 只解决一个可验证问题并关联 Issue。GitHub [Issues/PR 关联机制](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues)用于保留需求到代码的线索；需要看板时再用[Projects](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects)，不要用看板状态冒充真实用户验收。

第一批公开任务宜围绕：① 通用学习包数据契约及样例；② 零基础 SQL 纵向课程与独立判题；③ 岗位要求、技能证据与任务映射；④ 隐私安全的面试反馈录入；⑤ 外部用户可用性测试。每个 Issue 都要有虚构端到端用例，不能把一位用户的私密录音或简历作为 CI fixture。

## 决策记录格式

重大产品取舍在 Issue/文档中留下：决定、候选方案、证据与局限、用户影响、复测触发条件。尤其是“是否 fork/贡献 PathFinder”“是否自动抓取岗位”“是否使用外部 AI 服务”，均未在此文档里默认决定。Google PAIR 的[可解释性与信任指南](https://pair.withgoogle.com/chapter/explainability-trust)提醒 AI 产品应让用户理解能力边界并纠正系统；这里用来源、未知状态和人工确认落实这一点。
