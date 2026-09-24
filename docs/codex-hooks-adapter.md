# Codex Hooks 本地活动线索适配器（#28）

这是一条**用户主动连接后才启用**的本机入口。Codex 的 [Hooks 官方文档](https://learn.chatgpt.com/docs/hooks)（2026-09-24 查阅）支持 `UserPromptSubmit`、`Stop`、`Interrupt` 与部分 `PostToolUse` 本地事件；它们分别记录“提交提示的线索”“回合准备结束的线索”“中断线索”“支持的工具返回线索”。都不等于任务完成、投递成功或考试成绩。`PostToolUse` 不覆盖 hosted 工具，部分特殊工具路径也可能不触发。`SessionEnd` 不是切走聊天时立即触发，因此未用作任务结束信号。

## 数据最小化

脚本只读取 Hook JSON 的 `hook_event_name`、`session_id`、`turn_id`、`tool_use_id`、`tool_name`，并取当前本机时间。会话／回合／事件 ID 在写入前哈希；原始 ID 与 `prompt`、`tool_input`、`tool_response`、`transcript_path`、`cwd`、模型名均不落库、不进入日志。工具名只允许短标识符，无法接受路径。观察记录仍受 #23 的暂停、断开、查看、删除和默认 30 天保留策略约束。

## 本机手动接入

1. 由工作台的可信界面明确启用一个连接：`ActivityInbox(workspace).connect("codex-hooks", "codex.hooks", ["turn_prompted", "turn_stop_observed", "turn_interrupted", "tool_used"])`。连接控制方法不能暴露给 Hook 进程；目前此代码仅完成本地验证边界，尚未有正式 UI 授权面板或跨进程身份认证。
2. 在用户自己审查后，将下方配置合入自己的 `~/.codex/hooks.json`，把绝对脚本路径与私有 workspace 路径替换成实际位置。Codex 会对非托管 Hook 定义显示信任审查；修改后需重新审查。[官方说明](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks)
3. 通过 `list_connections()`、`list_observations("codex-hooks")` 核查是否收到线索；可随时 `pause`、`disconnect` 或 `forget_connection`。不要把真实 `activity.sqlite3` 提交到仓库。

```json
{
  "hooks": {
    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "python3 /ABS/REPO/scripts/codex_hook_activity.py --workspace /ABS/PRIVATE/WORKSPACE --connection codex-hooks", "timeout": 3}]}],
    "Stop": [{"hooks": [{"type": "command", "command": "python3 /ABS/REPO/scripts/codex_hook_activity.py --workspace /ABS/PRIVATE/WORKSPACE --connection codex-hooks", "timeout": 3}]}],
    "Interrupt": [{"hooks": [{"type": "command", "command": "python3 /ABS/REPO/scripts/codex_hook_activity.py --workspace /ABS/PRIVATE/WORKSPACE --connection codex-hooks", "timeout": 3}]}],
    "PostToolUse": [{"hooks": [{"type": "command", "command": "python3 /ABS/REPO/scripts/codex_hook_activity.py --workspace /ABS/PRIVATE/WORKSPACE --connection codex-hooks", "timeout": 3}]}]
  }
}
```

Hook 命令在收件箱未授权或暂停时返回空 JSON，避免干扰 Codex 工作；它不会绕过 Workbench 的连接状态。脚本和测试均使用虚构数据，**本机桌面应用触发与信任流程尚未端到端实测**。官方 [App Server](https://learn.chatgpt.com/docs/app-server)事件流适用于自行运行的客户端，不能据此声称可以订阅现有桌面应用的全部任务事件。正式产品需要连接管理 UI、进程隔离或本机授权通道，以及用户触发后的覆盖范围健康检查。
