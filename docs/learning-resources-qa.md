# Issue #8 虚构本机端到端验收

2026-09-25，分支 `feat/learning-resource-journey`。所有岗位、JD、练习笔记均为虚构文本，保存在被 Git 忽略的 `private/learning-demo-final/`。没有真实岗位回执、外站学习账号、申请资料或个人笔记。

## 实际操作

使用 `scripts/demo_learning_resources.py` 建两虚构岗位和五条技能映射，启动 `scripts/serve_learning_companion.py --workspace private/learning-demo-final --port 8822`，在本机 Chromium 通过 Playwright 操作页面。

| 检查点 | 实际观察 |
|---|---|
| 首屏 | 虚构分析岗显示 SQL、Python 两条要求及来源片段；SQL 出现 PostgreSQL 具体教程与 SQLite 替代，Python 出现第 4 章与第 3 章。 |
| 未知与无匹配 | 虚构工程岗的流处理映射待核验；在页面手工新增一条已确认的虚构流处理要求后显示 `无匹配章节`，没有生成链接。 |
| 选择和打开 | 在页面新增已确认的虚构 SQL 片段，选择 PostgreSQL；点击专用打开按钮后浏览器导航到 `https://www.postgresql.org/docs/current/tutorial-select.html`。源站返回内容不属于本机应用验收。 |
| 返回与进度 | 返回 `/?job_id=FICTIONAL-DATA` 后记录进行中，填虚构本机笔记说明，自报完成；刷新后仍显示“证据未核验，技能仍待验证”。 |
| 申请边界 | `career.py` 岗位保持 `discovered`；本机申请事件表无 `submitted`。页面没有把学习自报变成投递或掌握。 |

初次浏览器运行发现 `/?job_id=...` 刷新会返回 404，已修复根页面的查询参数路由后复测。上述外站导航是另一次针对性浏览器操作验证；最初的长脚本在导航尚未完成时读到本机 URL，因此不把那次读数计为外站已到达。

测试：最终执行 `python3 -m unittest discover -s tests`，104 项通过；`python3 scripts/check_privacy.py` 扫描 94 个候选文件，0 项标记。测试含两岗位同技能、岗位与章节来源修订、前置与替代、未知/no_match、事件顺序/重复、证据待核验、选择/拒绝、访问待重验、HTTP Host/Origin/CSRF、固定路由及模拟本地存储异常 503。模拟 503 只验证错误显示协议，不声称真实磁盘故障曾发生。

尚未验收：真人岗位的来源核对、外站课程内容完成、独立技能评测、投递回执；这些均不能由本轮虚构测试推出。
