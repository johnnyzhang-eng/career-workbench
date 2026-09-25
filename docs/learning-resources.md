# 岗位要求到外部章节：首个纵向切片

对应 [Issue #8](https://github.com/johnnyzhang-eng/career-workbench/issues/8)。这是独立的本机学习页面，读取同一工作区 `career.py` 已保存的岗位快照；学习可在投递前开始。它不更改岗位状态，也不复用旧 `practice` 为能力认证。

## 运行

```bash
python3 scripts/demo_learning_resources.py --workspace private/learning-demo
python3 scripts/serve_learning_companion.py --workspace private/learning-demo --port 8795
```

打开终端打印的 `http://127.0.0.1:8795/`。演示含**两家完全虚构公司**和虚构 JD 片段；两岗位均要求 SQL，另一岗位另有待核验的流处理要求。演示链接 `example.com` 不是真实岗位或投递入口。实际使用时，先用 `career.py --workspace private/<你的工作区> add private/<你的岗位 JSON>` 保存岗位，再将上述服务指向同一工作区，手工录入本人核对的 JD 片段。不要把真实片段、证据或数据库提交到仓库。

## 页面做什么

1. 选择岗位，查看原岗位入口；手工粘贴 JD 的具体技能片段、来源 URL，并注明“本人确认”或“待核验”。映射固定在保存时的岗位身份版本和片段摘要，来源变动后显示待重验，不自动漂移。
2. 依据稳定技能定义与静态资源元数据给出具体章节。页面显示提供方、语言、形式、难度、前置、访问条件、核验状态、匹配理由和替代章；无映射返回 `no_match`，未确认/前置/语言/访问条件不满足返回 `needs_review`。首版没有 AI，页面显示“无模型自动判断”。
3. 本人可选择或拒绝推荐。章节选择与学习事件还绑定章节内容修订；目录同 ID 更新时，旧事件留作历史，当前章节需要重认。专用“打开原站并记已打开”按钮先在本地记录 `opened` 再导航；普通资源链接不改变状态。返回后可记录 `in_progress` 和带本地证据引用的 `completed_self_reported`，刷新/重启后仍在。重复操作不会重复插入同状态事件。
4. 所有学习事件的证据状态保持 `unverified`，技能状态保持 `needs_validation`。这里没有独立练习、阅卷或复测，因此不能显示“已掌握”。课程打开、自报、笔记和学习完成都不触发岗位投递。

资源目录目前手工维护于 `workbench/learning_resources.py`：

| 技能 | 具体章节 | 状态 |
|---|---|---|
| SQL 基础查询 | [PostgreSQL 2.5 Querying a Table](https://www.postgresql.org/docs/current/tutorial-select.html)；替代 [SQLite SELECT reference](https://www.sqlite.org/lang_select.html) | 提供方页面于 2026-09-25 核对 |
| Python 控制流 | [Python Tutorial 4](https://docs.python.org/3/tutorial/controlflow.html)；前置替代 [Tutorial 3](https://docs.python.org/3/tutorial/introduction.html) | 提供方页面于 2026-09-25 核对 |
| 算法入门 | [MIT OCW 6.006 Lecture 1](https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-fall-2011/resources/lecture-1-algorithmic-thinking-peak-finding/)；替代 [Khan Academy 入门视频](https://www.khanacademy.org/computing/computer-science/algorithms/intro-to-algorithms/v/what-are-algorithms) | MIT 课程要求 Python/离散数学；Khan 页面访问待本人重验 |
| 流处理 | 尚无已核对的适配章节 | `no_match` 或待确认 |

只保存元数据和用户本机行为，不下载/复制课程，不登录或读取外站学习账号。页面只监听 loopback；写请求检查 Host、Origin、CSRF 和 JSON。`private/` 不通过静态文件服务开放。

## 本轮边界

需求与技能的确认仍由人做，系统不能证明粘贴的片段来自该 URL。只有上述有限的英语资源目录；中文偏好会提示待核验，不虚构中文替代。外站页面会变化，页面核对日期不是永久可访问保证。用户报告访问问题只标记“访问待重验”，不会宣称资源失效。新的技能或课程目前需维护目录代码；站内推荐编辑器、课程搜索/抓取、测评和能力验证尚未实现。

浏览器验收与可复现证据见 [虚构端到端记录](learning-resources-qa.md)。
