# 房间场景状态契约（本机目标工作台）

`GET /api/state` 的顶层 `scene` 是展示用读模型。每次读取都按目标时区的现实时间重算 `phase`，不写入任务事件。房间动作不等于任务完成、能力掌握或求职投递。

| 字段 | 含义 |
|---|---|
| `mode` | 当前可画出的动作：`idle`、`desk`、`study`、`interview`、`rest` |
| `phase` | 目标时区 06:00–17:59 为 `day`，其他时段为 `evening`；仅控制场景光照 |
| `activity_state` | `unknown`、`planned`、`declared_active`、`observed`、`self_selected` |
| `source` | `none`、`plan`、`daily_task`、`activity_observation`、`user_selected` |
| `suggested_mode` | 下一项已同步、尚未开始的任务对应场景；只用于“下一步”预告 |
| `task_id` / `task_title` | 对应当前行动或下一项计划；无任务时为 `null` |
| `as_of` | 生成场景状态的带时区时间戳 |
| `action` | `{state, task_id, at, can_resume}`，状态为 `none`、`active`、`paused`、`stopped`、`stale`；`can_resume` 控制“继续”按钮 |

目前后端只使用已同步的每日任务状态：`in_progress` 可让人物进入相应动作；`scheduled`/`deferred` 仍画 `idle`，仅设置 `suggested_mode`；已完成、取消、未同步的任务不驱动场景。`practice` → `study`，面试准备 → `interview`，其他行动 → `desk`。`rest` 只接受用户显式选择，不从空闲、晚间或任务标题推断。

用户可显式发起 `POST /api/actions/start|pause|resume|stop`，四个命令统一提交 `operation_id`、`goal_id`、`task_id`。行动事件只存于本机 `scene_actions.sqlite3`，不会调用每日任务的 `complete`，也不代表掌握、投递或考试结果。开始仅允许已同步、今日或待处理的非终态任务；暂停让人物待机，继续恢复动作，结束清除正在行动的表示。跨目标时区的午夜后，先前的 `active` 显示为 `stale` 并待机，只有本人明确“继续”才恢复。

适配器预留了明确授权、绑定本目标今日任务且十分钟内的活动线索接口。当前 `/api/state` 尚未连接活动收件箱；以后接入时，线索仅改变展示活动，不自动打勾。界面若展示 `planned`，应写“下一步建议”而非“正在做”。
