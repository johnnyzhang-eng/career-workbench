# macOS 角落窗口实验

状态：2026-09-25 可编译、可在本机实机显示的实验；不是安装包或完成的桌面应用。它把现有本机目标工作台放进一个 `WKWebView`/`NSPanel`。任务状态仍由 Python loopback 服务和本地 SQLite 保存，窗口层没有自己的任务副本。

## 运行

在仓库根目录开两个终端：

```sh
python3 scripts/serve_goal_companion.py --workspace private/goal-companion --port 8794
prototype/macos/build.sh
open private/CareerWorkbenchCompanion.app
```

构建产物只在被 Git 忽略的 `private/` 下。默认加载 `http://127.0.0.1:8794/compact`；也可直接运行 `private/CareerWorkbenchCompanion.app/Contents/MacOS/CompanionWindow --url http://127.0.0.1:PORT/compact`。URL 校验仅接受带端口的 `127.0.0.1` HTTP 和 `/`、`/compact`、`/collapsed` 三个入口；WebView 拒绝跳出这个源。尚未让窗口自行启动或管理 Python 服务，必须先启动服务。

Web 页的「收起／展开工作台／角落小窗」改变路由；原生窗口跟随路由切成 74×74 图标、360×480 角落面板或最大 1100×760 工作台。图标态上方是原生按钮，用于从别的应用回来时单击展开；角落面板闲置六秒且指针在窗外时透明度降到 0.82。窗口保持浮在普通窗口之上，跟随所有 Spaces；菜单栏房子图标可重新打开小窗、切换整个窗口的鼠标穿透或退出。穿透开启后需用菜单栏恢复点击，不能点窗口本身恢复。

这些选择是可替换的交互实验。Apple 的 [NSWindow](https://developer.apple.com/documentation/appkit/nswindow) 提供窗口透明度和鼠标穿透，[NSWindow CollectionBehavior](https://developer.apple.com/documentation/appkit/nswindow/collectionbehavior-swift.struct) 控制 Spaces/全屏行为，[WKWebView](https://developer.apple.com/documentation/webkit/wkwebview) 负责本机页面；这些 API 的存在不代表跨应用体验已验收。

## 已复核和待验边界

- `swiftc` 编译与 `plutil -lint` 成功。本机用实际 WKWebView 验到 360×480 角落画面显示夜间像素房间、74×74 图标显示，并从原生图标返回角落画面。
- 目前只验证了单屏上的展示和展开/收起。普通应用、浏览器、全屏应用、Mission Control、双屏、开机启动和长时间资源占用还没有系统测试。
- WebView 在应用不活跃时第一次点击的行为需用实体鼠标再测；本次自动化中网页链接有过一次仅激活窗口、下一次才导航的情况。原生图标按钮已能一次展开。不能把「浮窗可以显示」当成「不会挡操作」。
- 菜单栏鼠标穿透开关尚未做跨应用点击命中验证；默认关闭穿透，防止内容看得见却点不到。
- macOS 文件选择与照片生成链路未在此窗口验证；网页本身仅有私有原照输入，不能据此声称已生成个人形象。

设计上没有把画面压到桌面最底层，也没有把闲置半透明等同于鼠标穿透。两者由用户可见的窗口菜单独立控制；后续 #20/ #17 应以 Codex、浏览器和全屏应用中的真实遮挡与点击测试选择默认层级。
