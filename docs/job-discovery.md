# 本地岗位发现：试用指南（Issue #9）

这个切片读取你启用的公开 Ashby 招聘 board，保留上次成功读取的职位，并给出招聘方的职位详情与申请页面。它目前只覆盖这些 board；筛选结果不代表岗位仍开放、资格符合或已经投递。职位申请仍由本人在原站完成。

## 启动

在仓库根目录运行：

```bash
python3 -m workbench.web --workspace private/alice --board Ashby --port 8765
```

打开终端显示的 `http://127.0.0.1:8765/`，点击“刷新这家公司的岗位”。可以重复传入 `--board`，例如再加入 `--board notion` 或 `--board airwallex`。board 名取自 `https://jobs.ashbyhq.com/<board>` 的末段，只允许字母、数字、下划线和连字符；程序只请求固定的 Ashby 公开 API 主机。一个来源暂不支持时不会假装已有覆盖。

运行期间需要本地周期刷新，可加 `--interval-minutes 30`（最短 15 分钟）。默认只手动刷新。每个 board 的请求至少间隔 60 秒；失败会逐步延长重试间隔。关闭本地程序后不再刷新；重开后已保存的职位仍在。首次打开空列表时需要先刷新。

不同求职者应分别使用 `private/alice`、`private/bob` 等独立 workspace。筛选偏好、收藏、已查看状态与 `discovery.sqlite3` 都留在各自本地目录；旧 CLI 的 `state.sqlite3` 仍由 `career.py init` 创建。不要把真实个人资料放进共享示例或 Issue。

## 如何读列表

- “新发现”表示本次成功同步才首次看到；“已查看”来自本人在本地点击标记；“待核查”表示上次成功快照有、最近一次成功同步未出现。它**不等于已关闭**。
- 城市匹配来源位置字段，方向匹配职位/部门/团队，关键词及排除词匹配职位与纯文本描述。届别只按来源明确写出的文字匹配；未写出的保持“未知”，可勾选保留。任何匹配都不等于资格核验。
- “打开原站职位详情”与“去原站申请”是不同链接。若来源没有安全的独立申请入口，页面提示先从详情页核查。打开链接、标记已查看或收藏不会登记 submitted。
- 真正申请以后，仍按 `docs/workflow.md` 的现有 CLI 流程核验岗位、准备材料、本人确认，并用真实回执登记状态。发现页面不会绕过这些门槛。

## 来源、核查与限制

适配器依据 [Ashby Public Job Postings API 官方文档](https://developers.ashbyhq.com/docs/public-job-posting-api) 的公开 GET、`jobUrl`、`applyUrl`、`isListed` 和原始字段实现；不使用需要凭证的 `jobPosting.list` 或申请提交接口。读取失败、重定向、响应太大或字段异常都保留最后成功快照；本地不会把 404、空响应或缺席职位直接判为“招满”。只保存纯文本描述和必要字段，不渲染来源 HTML。

2026-09-18 16:48 UTC 的一次只读抽样：Ashby 自身 board 返回 73 条 `isListed=true` 职位，73 条都有职位和申请 URL；标题中没有明确的 Intern 职位，位置字段没有 China/Shanghai，纯文本描述没有 `2027`。同日另查 `airwallex` board：577 条 listed，其中 20 条位置文字含 China/Shanghai/Beijing、2 条纯文本描述含 `2027`；这些计数没有核对资格或开放状态，也不能推断中国学生可投。样本随招聘方更新会变；接口能读取与岗位适合某个学生是两件事。当前没有跨招聘站全网覆盖、自动发现所有 board、资格判定或自动投递。

虚构流程与安全验证在 `tests/test_job_discovery.py`；运行 `python3 -m unittest discover -s tests -v` 和 `python3 scripts/check_privacy.py`。测试仅证明本地行为，不代表真实职位申请成功。
