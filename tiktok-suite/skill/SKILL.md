---
name: tiktok-lead-engagement
description: 从 TikTok 视频评论区采集潜在客户（询价用户），并执行回复评论、关注、私信跟进。当用户要求"找视频评论里的客户/给评论用户回复/加好友/私信/TikTok 获客"时使用。依赖本机 ttkitc CLI 与克隆 Chrome 登录态。
---

# TikTok 评论获客（tiktok-lead-engagement）

把目标视频的评论用户当线索：采集入库 → 打分 → 回复/关注/私信 → 记录跟进。所有重活在 `ttkitc` CLI（D:\agent\carcustomer\tiktok-suite），本 skill 只做决策与异常处理。

## 前置条件检查（每次任务开始必做）

1. `ttkitc session status` — 克隆 Chrome 须在运行且 tiktok sessionid 存在。
   - 没运行：`ttkitc session launch` 后让用户在弹出的 Chrome 窗口里手动登录 TikTok（Google/Facebook 第三方登录均可，人工操作能过平台风控），等用户确认后重新 `status`。
   - 登录态约 30 天有效；失效重复上述流程。不要用其它方式折腾登录（见 references/session.md 的踩坑记录）。
2. Windows 环境跑 python/ttkitc 时设 `PYTHONIOENCODING=utf-8`。

## 标准工作流

```bash
# 1. 采集目标视频评论并入库（自动打分、去重）
ttkitc harvest "https://www.tiktok.com/@author/video/<id>" --import

# 2. 查看线索（按意向分排序优先跟进高分）
ttkitc leads list --json

# 3. 逐用户执行动作（guard 自动限速、写互动日志）
ttkitc engage reply <username> --video "<url>" --text "..."
ttkitc engage follow <username>
ttkitc engage dm <username> --text "..."   # 默认关闭，需先在 settings 开 dm_enabled

# 4. 更新线索状态
ttkitc leads update <username> --status qualified --notes "whatsapp +992..."
```

批量模式：agent 逐用户执行，每个动作之间依赖 guard 的冷却；动作结果以 interactions 表为准（status=blocked 要停下分析，见下方熔断）。

## 监控模式（采集新评论，不动手）

`ttkitc scan` 扫所有 monitor=1 的视频，新评论自动入库为 new 线索。**只采集不执行动作**；是否跟进由人/agent 决策。可用 cron/计划任务每天 1-2 次。

## 风控红线（必须遵守）

- 触发任何 blocked（私信拦截、验证码、操作频繁）→ **立即停止全部动作**，报告用户，当天不再执行。
- 单日额度（settings 可调，默认值见 CONTRACT.md）：回复 20 / 关注 30 / 私信 5。新账号按一半执行。
- 私信默认关闭（dm_enabled=false）。新注册/新登录账号对陌生人私信必被拦（连 "Hi" 都发不出），养号数周后再试。
- 永远不在回复/私信里写"check your DM"这类指向私信的引导，除非确认私信能发出去（会误导客户）。
- 动作节奏要有人味：不做无间隔连发；同一视频的用户按评论时间分散处理。

## 平台 quirks（速查，细节见 references/）

- 直接调评论/关注 API 返回 `status_code=5`（缺 X-Bogus/a_bogus 签名）。做法：注入 fetch 拦截，让页面自己发请求并抓响应。
- 评论框是 Draft.js：直接改 innerText 不同步状态（发布按钮不亮）；必须用 `ClipboardEvent('paste')` + `DataTransfer` 注入文本。
- 关注按钮 DOM 选择器不稳定：优先坐标点击（1280x665 视口 DSF=2 → CSS 525,139），点完必须验证"已关注"。
- 私信入口：用户主页点"消息"(坐标 621,137) → /messages 里出现会话 → 输入框(832,633) → `Input.insertText` → 发送按钮(1247,633)。发完检查页面文本含"无法发送/违反"=被拦。
- 克隆 Chrome 需启动参数 `--remote-debugging-port=9222 --remote-allow-origins=*`（后者缺了 CDP websocket 403）。
- Chrome ≥157 的 Cookie 是 App-Bound 加密：复制 Cookies 文件到新 profile 会被静默丢弃，Cookie 导出方案在无管理员权限时无解——登录唯一可靠路径就是克隆 Chrome + 人工登录一次。
- 内嵌自动化浏览器（如各类 agent 面板浏览器）会被 Google 以"浏览器或应用不安全"拒登、Facebook 登录静默卡死。不要尝试。

## 话术规范

- 用对方评论的语言回复（英语/俄语/中文/意大利语…）。模板库 `ttkitc templates list`。
- 回复 = 一句价值 + 一个具体问题（车型？数量？目的港？），引导对方回评论或主动私信（对方私信我们不受限）。
- 首条私信默认短（<30 字符）+ 不含链接/报价词；长话术分多条。
- 见 references/templates.md。

## Dashboard

数据在 Dashboard 可视化管理（局域网 http://<本机IP>:8788）：线索列表/详情、互动日志、监控视频、统计、话术、设置。启动：`D:\agent\carcustomer\tiktok-suite\scripts\start-dashboard.bat`。需要 FastAPI(8790) 与 Node(8788) 两个进程。
