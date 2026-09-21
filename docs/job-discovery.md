# 本地岗位候选工作台（Issue #9）

不同求职者各自在本地运行自己的岗位搜索 agent。agent 生成有原始来源的候选 JSON；工作台通过本地页面粘贴或当前用户私有目录中的文件导入，去重、展示和保存个人筛选。公开 Ashby board 是可选的补充来源。所有候选都待本人核查资格、开放状态和申请入口；工作台不运行 agent、不代投，也不把推荐理由当成资格结论。

## 从页面开始找岗位

在仓库根目录运行 `python3 -m workbench.web --workspace private/me`，打开终端显示的本地网址。第一次进入时，先由求职者本人填写[方向校准问卷](direction-calibration.md)：问卷把任务偏好与简历经历分开，保留多条方向假设；代理录入的草案在本人确认前不会进入找岗任务。确认后再填写并保存本人城市等筛选条件，复制页面生成的找岗任务给自己的本地 agent，将 agent 返回的纯 JSON 粘贴到页面导入。每次新搜索换一个 `batch_id`；重复粘贴旧批次不会重复记账。职位卡显示来源、发现时间、推荐理由、引用和未知项；本人在原站核验资格与是否开放。网页粘贴上限约 128 KB，更多候选可使用下述文件导入命令（上限 1 MiB）。没有本地 agent 时，可显式添加 Ashby board 读取公开岗位，但这只覆盖该 board。

## agent 的 JSON 契约与文件导入

请让 agent 将下面结构的 JSON 写入当前用户的 `private/alice/agent-batch.json`。例子全是虚构内容，真实求职资料只留在本人的 private workspace：

```json
{
  "schema_version": 1,
  "agent_id": "local_search_agent",
  "batch_id": "search_20260919_01",
  "generated_at": "2026-09-19T09:00:00+08:00",
  "candidates": [
    {
      "title": "虚构数据分析实习生",
      "job_url": "https://careers.example.com/jobs/data-intern",
      "apply_url": "https://careers.example.com/jobs/data-intern/apply",
      "location": "Shanghai",
      "department": "Data",
      "description": "2027 届与 SQL 要求，须以原站核查",
      "source": {
        "name": "虚构雇主招聘页",
        "url": "https://careers.example.com/jobs/data-intern",
        "observed_at": "2026-09-19T08:55:00+08:00"
      },
      "reason": "岗位描述提到 SQL，与本人选择的数据方向相近；资格尚未核验",
      "evidence_refs": [
        {"url": "https://careers.example.com/jobs/data-intern", "locator": "职位描述的要求段落"}
      ],
      "unknowns": ["届别资格", "岗位是否仍开放", "签约主体"]
    }
  ]
}
```

如果 agent 可以写本地文件，在仓库根目录也可用命令导入并启动本地网页：

```bash
python3 -m workbench.import_candidates --workspace private/alice --file private/alice/agent-batch.json
python3 -m workbench.web --workspace private/alice --port 8765
```

导入不需要网页运行；网页运行中再次导入后刷新页面即可看到候选。每批最多 100 条、文件最多 1 MiB，路径必须在指定 workspace 内。一个 agent 的同一批次重复导入会返回 `already_imported`；同批次 ID 对应不同内容会拒绝。不同 agent 给出同一规范化职位 URL 时列表只显示一个职位，但各自理由与证据分别保留。不同职位 URL 指向同一个现实岗位时，当前不会自动合并。粘贴导入与文件导入走相同校验和事务逻辑，错误会在页面说明，旧候选不会丢失。

所有 URL 只做严格的结构安全检查：HTTPS、公开 DNS 形式、具体路径、无凭据或片段。常见以查询参数指向职位的页面可保留 `gh_jid`、`job_id`、`posting_id`，其余查询参数（含个人跟踪参数）拒绝；例如 `https://careers.example.com/jobs?gh_jid=12345` 可导入。这个小型白名单仍不能覆盖所有招聘站链接格式。工作台不会替你访问或验证 agent 提供的 URL；链接是否真属雇主、职位是否在招、申请页是否可用仍需本人打开原站确认。不能安全去参时保留待人工核查，不编造新链接。证据引用只存 URL 与页面位置说明，不读取本地文件或复制整篇 JD。

## 可选：补充公开 Ashby board

例如增加一个有公开 API 的招聘 board：

```bash
python3 -m workbench.web --workspace private/alice --board Ashby --port 8765
```

在页面点击刷新 Ashby board；也可重复传入 `--board notion` 等名称。board 名来自 `https://jobs.ashbyhq.com/<board>` 的末段，程序只读取固定的 Ashby 公开 API 主机。若要在本地服务运行时周期刷新，增加 `--interval-minutes 30`（最短 15 分钟）；默认仅手动刷新。每个 board 有最小请求间隔、超时和失败退避，失败保留上次成功快照。关闭服务后不会继续刷新。无需 Ashby 时不要传 `--board`，页面仍能显示 agent 候选。

## 个人筛选与状态

每位求职者分别使用 `private/alice`、`private/bob` 等独立 workspace。`discovery.sqlite3` 保存本人的方向问卷、候选、来源报告、偏好、收藏和已查看状态；旧 CLI 的 `state.sqlite3` 仍由 `career.py init` 创建。导入或刷新不会改变申请状态机。

- 城市匹配来源位置字段；方向匹配职位、部门与团队；关键词和排除词匹配职位与纯文本描述。届别只按来源明确写出的文字匹配；未写出的保持“未知”，可选择保留。筛中不等于资格符合。
- agent 候选始终显示“待核查”，即使已经收藏或查看。Ashby 的“待核查”还可能表示它在最近一次成功同步中缺席；缺席不等于关闭。打开候选卡可查看各 agent 的理由、证据引用、未知项与来源时间。
- 职位详情与申请入口分别打开。agent 提供的申请入口标为待核验；缺失时先从职位原页核查。打开链接、收藏或标记已查看绝不会登记 submitted。
- 本人在原站实际申请后，仍按 `docs/workflow.md` 的旧 CLI 流程核验岗位、准备材料、确认并凭真实回执登记；学习进度不是投递前置条件。

## 来源范围与验证

Ashby 适配器依据 [官方 Public Job Postings API 文档](https://developers.ashbyhq.com/docs/public-job-posting-api) 的公开 GET、`jobUrl`、`applyUrl` 和 `isListed` 字段，不使用需凭证的写入接口。2026-09-18 16:48 UTC 的一次只读抽样：Ashby 自身 board 返回 73 条 listed 职位，标题中没有明确的 Intern 职位，位置字段没有 China/Shanghai，纯文本描述没有 `2027`。同日 `airwallex` board 有 577 条 listed，其中 20 条位置文字含 China/Shanghai/Beijing、2 条纯文本描述含 `2027`；这些计数未核对资格或开放状态，也不证明中国学生可投。样本会随时间变化。

本切片没有内置 agent、跨站全网搜索、申请表代填、自动上传、资格判定、模型收费调用或云端多用户账号。离线测试在 `tests/`；运行 `python3 -m unittest discover -s tests -v` 与 `python3 scripts/check_privacy.py`。浏览器和真实职位页仍需按具体用户任务验证，测试通过不等于真实申请成功。
