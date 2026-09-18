# 岗位目标驱动的学习平台：产品发现（草案）

本目录描述下一阶段产品方向，**不是已上线功能清单**。目标是帮助学生选择一个或多个岗位方向、找到真实岗位入口、识别共通与专属缺口，并通过练习和复测积累证据。当前仓库只有本地命令行投递记录底座；上述网页体验仍待开发和用户验收。

先读：

1. [产品简报](brief.md)：用户、问题、边界与成功标准。
2. [证据与研究计划](evidence.md)：哪些已经观察到，哪些仍是假设。
3. [MVP 规格](mvp.md)：岗位发现首片、外部学习后续切片与验收场景。
4. [交付方式](delivery.md)：阶段门槛、Issue / PR 和隐私检查。
5. [架构图](architecture-map.html)、[架构基线](architecture.md)、[数据契约](contracts.md)、[协作契约](collaboration.md)：供不同贡献者按边界开发和验收。

先看[产品边界草图](boundary-map-draft.html)：区分工作台、学生本人、招聘网站和现成学习资源，并标明现有底座与待验证设计。[架构图](architecture-map.html)反映 2026-09-17 的资源导航优先方案，其“第一切片”标注已被 2026-09-19 的优先级决定替换，以本页和 [MVP 规格](mvp.md)为准。此前的[产品总览](workbench-overview.html)和[SQL 第一课](sql-first-lesson.html)保留为历史探索图，不作为当前开发规格。

第一切片 [#9](https://github.com/johnnyzhang-eng/career-workbench/issues/9) 从**持续发现具体岗位**出发：公开来源可刷新、不同用户可独立筛选、原站详情和投递入口可打开。本人在原站投递，点击不等于提交。第二切片 [#8](https://github.com/johnnyzhang-eng/career-workbench/issues/8) 才把岗位要求接到现成课程具体章节与本地学习记录；进度和能力证据分开，自报完成仍待验证。SQL 是首批资源样本，不自建课程、判题或复测引擎。

仓库级 [`career-gap-coach` skill](../../.agents/skills/career-gap-coach/SKILL.md)用于人工试验“JD → 证据 → 下一题”的分析方式，不是每位学生必须使用 Codex，也不是产品已经接好用户自带模型。

这份文档只用匿名化观察和虚构例子。真实简历、面试录音、逐字稿、岗位申请及学习作答留在使用者本地 `private/`，不进入 Issue、PR 或演示数据。
