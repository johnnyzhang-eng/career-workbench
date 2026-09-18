# Issue #9 最小数据与安全契约

状态：首条岗位发现切片的实现契约，2026-09-19。父任务 #5；外部课程 #8 后续接入。

## 来源与身份

首个适配器只读 Ashby 官方 Public Job Postings API：`GET https://api.ashbyhq.com/posting-api/job-board/{board}`。`board` 仅允许 ASCII 字母、数字、下划线、连字符，源地址由程序拼接，不接受用户提交的服务器抓取 URL。适配器接口保留后续来源类型。当前演示 board 为 `Ashby`；一个 board 不是全网搜索，也不保证职位仍开放。

只保留 `isListed=true` 的公开职位。主键为 `(source='ashby', board, source_job_id)`；`source_job_id` 从已校验的原站职位 URL 中提取 UUID。`jobUrl` 和 `applyUrl` 仅接受 HTTPS、`jobs.ashbyhq.com`、同一 board 与 UUID 的路径；缺失或非法 apply URL 记为 unknown，仅展示详情页。职位内容、位置、部门、团队、发布日期等是来源原始字段，不推断资格、合同主体或招聘状态。

## 本地数据

每个 `private/<workspace>/discovery.sqlite3` 独立保存来源同步状态、岗位快照、用户偏好、收藏/已查看状态，不跨 workspace 汇总；旧 CLI 的 `state.sqlite3` 仍由原有 `init` 创建。成功刷新先完整获取、解析、验证，再在一个 SQLite 事务中 upsert；同 ID 更新字段并保留 `first_seen_at`，出现时更新 `last_seen_at`。本次未出现仅标 `not_seen_latest/needs_review`，不标关闭。失败不清空上次成功快照，记录失败时间与下次允许重试时间。刷新频率有下限、超时、大小限制和失败退避。周期刷新只在本地程序运行时进行。

筛选是字符串条件匹配：地点、岗位方向、关键词、排除词；届别只根据来源明确出现的文字筛选，缺失标 unknown 并可保留在结果中。筛中不等于资格符合或可投。点击原站只可标已查看，收藏是本地个人动作；不会调用申请接口，也不会设置 submitted。若要记录真实投递，仍用旧 CLI 完成核验、材料确认与回执门槛。

## 网页边界

HTTP 只绑定 `127.0.0.1`；请求 Host 必须是对应 loopback 主机和当前端口，写请求检查 Origin、随机防跨站令牌、Content-Type、体积与字段。普通跨站 Origin 拒绝；内置浏览器送 `Origin: null` 时仍必须有本页令牌。页面文本一律转义，不嵌入来源 HTML；无通用静态文件服务，因此 `private/` 不可能由静态路由读取。出站链接在解析时校验且只以 `https` 开新标签，设置 `noopener noreferrer`。不上传画像、简历或回执，不读外站账号，不运行模型或付费接口。

## 验收

离线 fixture 验去重、更新、不同 workspace 隔离、失败保留快照、缺失待核查、空字段、非法 ID/URL/重定向、筛选未知项和旧 CLI 回归；真实公开来源做少量只读核验，记录时间和覆盖限制。浏览器用虚构本地偏好完成刷新、筛选、原站详情/投递入口及返回查看；不能把点击显示成已投递。
