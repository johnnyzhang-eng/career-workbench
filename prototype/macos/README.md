# macOS 角落窗口实验

状态：2026-09-25 可编译、可在本机实机显示的实验；不是安装包或完成的桌面应用。它把现有本机目标工作台放进一个 `WKWebView`/`NSPanel`。任务状态仍由 Python loopback 服务和本地 SQLite 保存，窗口层没有自己的任务副本。

## 运行

在仓库根目录开两个终端：

```sh
python3 scripts/serve_goal_companion.py --workspace private/goal-companion --port 8794
prototype/macos/build.sh
open private/CareerWorkbenchCompanion.app
```

构建产物只在被 Git 忽略的 `private/` 下。默认从 `http://127.0.0.1:8794/collapsed` 启动，显示 74×74 点的小屋与虚构学生；也可直接运行 `private/CareerWorkbenchCompanion.app/Contents/MacOS/CompanionWindow --url http://127.0.0.1:PORT/compact`。URL 校验仅接受带端口的 `127.0.0.1` HTTP 和 `/`、`/compact`、`/collapsed` 三个入口；WebView 拒绝跳出这个源。尚未让窗口自行启动或管理 Python 服务，必须先启动服务。

Web 页的「收起／展开工作台／角落小窗」改变路由；原生窗口跟随路由切成 74×74 桌宠、360×480 角落面板或最大 1100×760 工作台。桌宠态用可替换的透明房间画面，里面有人在书桌前；它是静态空闲预览，不从图像推断任务完成。点击一次进入角落面板，窗口尺寸变化后内容淡入；指针靠近时仅做一次轻微放大，没有循环动画。系统启用「减少动态效果」时跳过这些过渡。初始桌宠态延迟加载 WebView，直到点击展开。角落面板闲置六秒且指针在窗外时透明度降到 0.82。无边框窗口左上角（桌宠态右上角）有可见的关闭按钮，关闭后从菜单栏 ⌂ 的「打开角落小窗」恢复；菜单栏「退出应用」才会终止窗口进程。窗口保持浮在普通窗口之上，跟随所有 Spaces；菜单栏还可切换整个窗口的鼠标穿透。穿透开启后需用菜单栏恢复点击，不能点窗口本身恢复。

对已隐藏的小屋再次执行 `open private/CareerWorkbenchCompanion.app` 也会恢复角落面板，且复用原有窗口进程。这个入口适合菜单栏状态项一时找不到时使用；退出仍需从菜单栏选择「退出应用」。

桌宠素材在 `Resources/pet-room-idle.png`，其生成说明和替换门槛见 [ART_ASSET.md](ART_ASSET.md)。这张图只用于初始空闲态。未来换成 2D 像素或精修 3D 时，只要保持透明方形画布与小尺寸可辨性，窗口逻辑无需改动。

这些选择是可替换的交互实验。Apple 的 [NSWindow](https://developer.apple.com/documentation/appkit/nswindow) 提供窗口透明度和鼠标穿透，[NSWindow CollectionBehavior](https://developer.apple.com/documentation/appkit/nswindow/collectionbehavior-swift.struct) 控制 Spaces/全屏行为，[WKWebView](https://developer.apple.com/documentation/webkit/wkwebview) 负责本机页面；这些 API 的存在不代表跨应用体验已验收。

## 已复核和待验边界

- `swiftc` 编译与 `plutil -lint` 成功。本机用实际 WKWebView 验到 360×480 角落画面显示夜间像素房间、74×74 图标显示，并从原生图标返回角落画面。
- 桌宠化追加复核（2026-09-25）：CUA 实机看到了 74×74 小屋里的人物，原生可访问性树有「展开今日房间」与「关闭小房间」两个明确按钮；点击小屋后首次延迟加载 WKWebView，并显示虚构 CET6 的 360×480 今日房间和任务，再点网页「收起」回到桌宠。首次 `getAXState` 仍可能落在页面载入途中，随后二次观察确认载入完成。关闭按钮点击后窗口隐藏、进程仍在；由于隐藏后 CUA 无法重新绑定窗口，菜单栏恢复没有在这一轮完成实体点击复核。
- 资源采样：初始桌宠启动后约 8 秒，`CompanionWindow` 进程 RSS 为 67,136 KiB、采样瞬间 CPU 为 0.0%；这不包含可独立运行的 WebKit 子进程，不能作为完整常驻成本。透明 PNG 原文件为 1.5 MiB；展开/收起及指针过渡由事件触发，没有新增常驻动画定时器。仍需长时间、双屏和全屏采样。
- 关闭入口复核：新编译的窗口在无边框小窗中通过可访问性树暴露「关闭小房间」按钮，实机截图可见左上角 ×；点击后原生窗口被隐藏，窗口进程保留供菜单栏恢复。当前未单独复测菜单栏重新打开和图标态关闭按钮的实体点击。
- 多目标恢复复核：旧版从 `/collapsed?goal_id=...` 点原生 74×74 图标时固定重载 `/compact`，服务端会默认选最新目标。在独立虚构双目标工作区中，从较早的 CET6 目标收起并恢复，旧行为会切到新目标；现仅把当前 URL 的 `goal_id` 带入原生恢复链接。修订版实机 WKWebView 的收起→原生图标恢复后，URL 和可访问标题仍指向较早的 CET6 目标。菜单栏“打开角落小窗”走同一恢复函数，但未单独做鼠标点击复测。
- 目前只验证了单屏上的展示和展开/收起。普通应用、浏览器、全屏应用、Mission Control、双屏、开机启动和长时间资源占用还没有系统测试。
- 跨应用首击复核（2026-09-25）：从 Finder 切回本窗口，在真实 WKWebView 上用 CUA 坐标单击「展开工作台」。临时 AppKit `sendEvent` 记录显示，目标点击命中 `ActiveWebView`，其 `acceptsFirstMouse(for:)` 返回 `true`，WebKit 在同一次点击后发出导航请求；未加激活修复时也如此。即时无变化的可访问性树不能证明首击被吞：一次反向导航的请求发出到页面加载完成约 29 秒，期间仍显示旧页。CUA 的一次点击还可能产生一个窗外鼠标事件，故其事件数不能直接当作实体鼠标点击数。试验过在 `sendEvent` 中对非 key 窗口先调用 `NSApp.activate()` / `makeKeyAndOrderFront`；它没有形成稳定优于原行为的证据，已撤回，没有改默认窗口行为。[AppKit 对 `acceptsFirstMouse` 的定义](https://developer.apple.com/documentation/appkit/nsview/acceptsfirstmouse%28for%3A%29)、[命中视图](https://developer.apple.com/documentation/appkit/nsview/hittest%28_%3A%29)与[窗口事件派发](https://developer.apple.com/documentation/appkit/nswindow/sendevent%28_%3A%29)是这次定位依据。
- CUA 拒绝控制 Codex 应用，因此上述受控实机测试是 Finder ↔ 本窗口，尚不能声称 Codex ↔ 本窗口的实体首击已经通过。需在本机 Codex 和浏览器前台，用实体鼠标分别试一次「展开工作台」与「角落小窗」，并等页面加载结束后再判断是否需要第二次点击。原生图标按钮此前已能一次展开；这不代表 Web 链接或所有应用层级都完成验收。不能把「浮窗可以显示」当成「不会挡操作」。
- Codex 宠物本机窗口同样因 CUA 对 `com.openai.codex` 的访问限制无法实看。交互参考仅来自 [官方 Pets 文档](https://learn.chatgpt.com/docs/pets)：桌面浮宠可置于其他应用窗口前、调整尺寸、拖动、隐藏，且尊重系统减少动态效果。这里没有声称本样机已达到 Codex 的拖动或输入穿透体验；当前 74×74 点的透明窗口仍会在其矩形范围接收点击。
- 导航延迟复核：旧 8794 服务上，实测 WebKit 从导航开始到提交约 29.016 秒、提交到完成约 0.002 秒、完成到可见 DOM 约 0.357 秒；同页独立 Chrome 温态可见内容约 0.11–0.40 秒。旧服务的单线程 `HTTPServer` 有可重复的空连接阻塞：保持一个未发完请求的本机 TCP 连接时，第二个页面请求 1 秒超时，断开空连接后约 0.0005 秒返回。Python [官方文档](https://docs.python.org/3.9/library/http.server.html#http.server.ThreadingHTTPServer) 正将浏览器预开连接列为使用 `ThreadingHTTPServer` 的原因。改为并发处理后，独立 8808 服务的相同演示数据在空连接存在时约 0.002 秒返回；WebKit 首次小窗可见约 0.116 秒，随后两次展开约 0.363/0.360 秒、一次收起约 0.368 秒。这个对照支持服务端排队是所见长延迟的机制；没有直接抓到那次 WebKit 的预开 socket，因此不把它写成唯一已证实的触发源。已运行的旧 8794 进程不会热更新，需重启服务后才会使用新服务类。
- 菜单栏鼠标穿透开关尚未做跨应用点击命中验证；默认关闭穿透，防止内容看得见却点不到。
- macOS 文件选择与照片生成链路未在此窗口验证；网页本身仅有私有原照输入，不能据此声称已生成个人形象。

设计上没有把画面压到桌面最底层，也没有把闲置半透明等同于鼠标穿透。两者由用户可见的窗口菜单独立控制；后续 #20/ #17 应以 Codex、浏览器和全屏应用中的真实遮挡与点击测试选择默认层级。
