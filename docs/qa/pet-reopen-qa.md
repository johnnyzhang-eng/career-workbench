# 桌宠隐藏后恢复的隔离实机核验

日期：2026-09-25。使用独立分支、独立 App bundle ID `org.career-workbench.companion-menu-qa` 和本机虚构工作区 `private/menu-qa`（8843 端口）。没有触碰正在运行的 8794 小屋或私人求职数据。

## 观察与修订

原版 74×74 小屋中，用 CUA 点击原生「关闭小房间」后，窗口消失，但 `CompanionWindow` 进程仍在。此时执行 `open private/CareerWorkbenchCompanion.app`，进程 PID 保持不变，CUA 仍无法绑定窗口：通过 Launch Services 再次打开应用不能恢复已隐藏的面板。

加入 `applicationShouldHandleReopen` 后，在同一个隔离构建上重做：CUA 点击 × 隐藏；PID 71728 保持；执行 `open` 打开同一 App；PID 仍为 71728，CUA 重新看到原生窗口，随后 WKWebView 显示 `127.0.0.1:8843/compact`。点击网页「展开完整工作台」后，URL 变成 `/`，完整目标设置界面出现。这个验证覆盖了额外的 Launch Services 重开恢复入口和继续展开。

菜单栏 ⌂ 的「打开角落小窗」与新入口调用同一 `showCompanion` 方法，源代码中目标和动作已核对。但 CUA 在窗口隐藏后无法绑定这个菜单栏状态项，**本轮没有实际点击菜单栏恢复或菜单栏退出**。在展开的 QA 窗口上按 `⌘Q` 未使进程退出；它不是这里菜单项点击的替代验证。不要把本记录当成菜单栏闭环或退出后无残留进程的证明。菜单栏的这两步仍需实体鼠标验收。

新入口仅在已有进程被再次打开且没有可见窗口时触发；它不创建第二个服务、任务副本或新目标。窗口仍需本机 Python 服务先运行。CUA 的截图只留在工具会话里，仓库未包含电脑桌面截图。
