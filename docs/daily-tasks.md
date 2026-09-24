# 每日任务内核（Issue #15 草稿）

这是本地、标准库实现的任务事件层。`career.py` 继续独占真实岗位状态转换；每日任务只读取它的岗位和事件，不能自动申请、发信、确认能力或修改岗位状态。全部个人数据写在被 Git 忽略的 `private/<workspace>/daily.sqlite3`，与旧 `state.sqlite3` 同目录。

## 七天虚构用例

运行 `python3 scripts/demo_daily.py`。脚本在一次性临时目录创建两条虚构岗位，不访问网站、不发送申请、不留个人数据。其日期从运行当天开始，由注入时钟逐日推进；生产快照使用系统时钟，现实一天就是系统时间的一天。

| 天 | 输入与任务动作 | 应看到的结果 |
|---|---|---|
| 1 | 安排 A 岗核验、B 岗核验和一场宣讲 | 今日只显示已到日期的任务；B 岗截止未知 |
| 2 | A 岗在旧工作流记核验结论；宣讲留参加笔记 | 两任务完成，A 岗建议准备材料；未投递 |
| 3 | B 岗届别保留 unknown；安排 A 岗材料 | B 岗核验任务完成但岗位仍 hold，未知截止无倒计时 |
| 4 | A 岗材料准备并由本人确认 | 材料与确认各有旧工作流事件；岗位仍 approved |
| 5 | 打开 A 岗原站，尝试打勾；之后模拟有回执的提交 | 仅打开链接时拒绝完成；旧状态机登记虚构回执后任务完成 |
| 6 | 收到虚构面试邀请，准备笔记；B 岗补查受阻 | A 岗面试准备完成；B 岗保留阻塞原因 |
| 7 | 应用休眠后再打开 | B 岗原任务日期、未知截止和阻塞原因仍可见；无自动拒绝 |

## 快照与命令

`DailyStore.snapshot(timezone_name)` 保留 [共享契约](https://github.com/johnnyzhang-eng/career-workbench/pull/14) 的 v0 字段。`tasks` 包含今天已安排、已到日期的未完任务、当天完成/取消的任务，以及从旧岗位状态计算的 `suggested` 项。建议是只读提案，用户需以 `schedule` 命令安排；旧 `Workflow.today()` 的摘要没有被覆盖。UI 和桌面小窗应调用同一存储接口，不自行推断“已投递”。

为显示跨日与延期历史，快照增加三个**待 #17 对齐的可选字段**：`origin_scheduled_at`（最初安排时间）、`carryover_reason`（跨日时原任务未完或最近延期/阻塞原因）、`due_verified_at`（截止核验时间）。`scheduled_at` 始终是当前安排时间。`due_at` 可以是来源未核实的线索，此时 `due_verified=false` 且 `due_verified_at=null`，UI 不应计算精确倒计时。固定虚构快照在 `templates/daily_snapshot.json`；该文件不是个人记录。

命令为 `schedule/start/complete/defer/block/cancel`。调用 `DailyStore.command(command, event_id, task_id, payload, at)`；稳定事件 ID 重试幂等，复用 ID 但改内容会报错。所有时间是带时区的 ISO 8601，缺省 `at` 取注入时钟；任务事件不允许倒填到前一事件之前或提前超过五分钟。`defer/block/cancel` 必须有原因；延期需要新的未来 `scheduled_at`。终态只读。`claim_reminders()` 针对当前安排时间给出一次提醒，领取记录在 SQLite 中，重启或换时区不会重复领取；它不会用未知截止时间创建倒计时。

`complete` 根据任务类型检查依据。`verify_job/prepare_materials/approve_materials/apply_job/practice` 接收 `{"evidence":{"job_event_seq":整数}}`，核对同一个私有工作区内旧状态机的相应事件和岗位 ID。`apply_job` 必须指向 `submitted` 事件；仅有已确认材料、打开原站或任务打勾均不满足。旧状态机仍负责材料版本、本人确认与回执门槛。`practice` 只证明记录了本人独立练习的自述与作品位置，**不证明掌握**。`attend_event/prepare_interview/follow_up/custom` 分别要求参加记录及时间、笔记位置、跟进依据或产物位置。这些是本地记录完整性检查，不会替用户验证外部事实真实性。

## CLI 示例

先运行 `python3 career.py --workspace private/demo init`。在 `private/demo/task-command.json` 中写入下面的虚构安排命令，再运行 `python3 daily.py --workspace private/demo schedule private/demo/task-command.json`：

```json
{
  "event_id": "DEMO-EVENT-001",
  "task_id": "DEMO-TASK-001",
  "payload": {
    "task": {
      "id": "DEMO-TASK-001",
      "title": "核验虚构岗位的届别要求",
      "kind": "verify_job",
      "source_kind": "job",
      "source_id": "DEMO-JOB-001",
      "reason": "资格尚未核实",
      "scheduled_at": "2026-09-24T14:00:00+08:00",
      "due_at": null,
      "due_verified": false
    }
  }
}
```

查看当前时区的今日快照：`python3 daily.py --workspace private/demo snapshot --timezone Asia/Shanghai`。`python3 daily.py --workspace private/demo reminders` 领取当前到点提醒；它会改变领取记录，适合由客户端的提醒服务调用。其他命令同样读取 private/ 下的 JSON envelope，字段为 `event_id`、`task_id`、`payload` 和可选 `at`。公开仓库不要提交真实任务、简历或回执。

本切片没有 UI、系统通知投递器、自动职位刷新或真实用户验收；#17 负责把场景接到命令和快照，后续阶段再做完整应用与桌面小窗。
