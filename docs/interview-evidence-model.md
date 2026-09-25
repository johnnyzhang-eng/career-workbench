# 面试观察与练习线索：本机事件模型

对应 [Issue #68](https://github.com/johnnyzhang-eng/career-workbench/issues/68)，关联岗位技能证据 #3 与每日结果复盘 #32。本切片只提供 Python 服务层；不改目标页面、旧申请状态机或简历材料。

## 区分三个层次

1. **观察**：本人填写面试官的问题或反馈、自己记得的作答/卡点，标明是原话、转述还是不确定，附本机文件或 HTTPS 来源。`observation_confidence` 是回忆把握，不是能力评分；`status=user_checked` 只表示本人核对过来源，不代表外部确认。
2. **推断**：可选的 `inference` 单独保存，带 `inference_confidence`，明确标为 `user_hypothesis`。例如“可能要补 SQL 空值逻辑”，不能转换成“面试官认定 SQL 不行”。
3. **行动**：`linked_skill_target` 使用稳定的技能 ID 字符串，可选 `linked_goal_id` 关联已有目标；`next_practice_step` 由人填写具体练习。记录始终输出 `mastery_status=not_assessed` 和 `resume_claim_status=not_created`。只有后续独立练习、测验与人工核对才能建立能力证据；本模块没有这个判定器，也不会替调用者检查目标是否存在。

## 存储与更正

`InterviewEvidenceStore(workspace)` 只接受明确位于 `private/` 下的本机工作区，独立创建 `interview_evidence.sqlite3`（目录权限 0700、数据库 0600）。不联网、不读取证据文件内容、不把观察送到模型。文件证据必须已存在且解析后仍在当前工作区内，数据库路径拒绝符号链接；存储相对路径与文件大小，不保存绝对用户名路径。URL 仅作本地引用，要求无凭证、查询参数或片段的 HTTPS 地址，程序不会验证外站内容。

`interview_events` 是追加式表：创建为版本 1，更正时必须提交完整替换快照、`expected_version` 和更正原因；新事件引用前一事件 ID，旧版本始终可读。`interview_operations` 按 operation_id 和请求摘要去重；同一 ID 的重复提交不插入第二事件，异内容复用会报错。SQLite `BEGIN IMMEDIATE` 将并发的更正版本检查与写入放在同一事务中。更正只更新本模块的当前视图，绝不改 `career.py` 的已投、面试或复盘事件。

## 可供接线的 API

```python
from workbench.interview_evidence import InterviewEvidenceStore

with InterviewEvidenceStore("private/my-workspace") as store:
    note = {
        "interview_date": "2026-09-24",
        "company": "虚构甲公司", "role": "虚构分析实习",
        "input_kind": "question", "interviewer_input": "请解释 SQL 如何筛选数据？",
        "input_fidelity": "paraphrase",
        "self_observed_answer_or_problem": "本人记得说了 WHERE，没解释空值。",
        "evidence_source": {"kind": "local_path", "value": "fictional-note.txt"},
        "observation_confidence": "medium", "status": "unverified",
        "inference": "可能需要练习三值逻辑", "inference_confidence": "low",
        "linked_skill_target": "sql-foundations", "linked_goal_id": "GOAL-FAKE",
        "next_practice_step": "独立写三条 NULL 条件查询并解释结果。",
    }
    created = store.add({"operation_id": "fictional-note-1", "note": note})
    corrected_note = {**note, "interviewer_input": "后来核对：问的是 LEFT JOIN 与 NULL。"}
    corrected = store.correct({"operation_id": "fictional-correction-1",
        "record_id": created["record_id"], "expected_version": created["version"],
        "reason": "核对原笔记后更正提问", "note": corrected_note})
    latest = store.get(created["record_id"], include_history=True)
    matching = store.list(company="虚构甲公司", role="虚构分析实习", goal_id="GOAL-FAKE")
```

运行示例前，需在对应工作区创建 `fictional-note.txt`；`correct` 的 `note` 必须是与 `add` 相同结构的完整字典。测试中的 `mock-note.txt` 是虚构本机文件。建议 UI 先展示“观察/推断”并排字段，再将用户确认过的 `next_practice_step` 映射到每日任务；接线前应保留这两个来源标签，不把假设自动升格为事实。

## 范围和验收

本轮无网页入口、自动录音/转写、面试官身份核验、外站账号同步、简历句子生成或能力认证。测试以虚构资料覆盖创建、更正、旧版追溯、幂等、来源路径/URL、重启持久化与旧申请事件不变；真正面试资料只应进入本人 `private/`，不进入 Issue、PR、测试或截图。
