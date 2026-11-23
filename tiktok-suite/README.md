# ttkitc — TikTok 获客套件

把一套已实战验证的 TikTok 自动化流程工程化：评论采集 → 线索评分入库 → 回复 / 关注 / 私信。
纯 CDP（Chrome DevTools Protocol）驱动本机 Chrome，不依赖 selenium / playwright。

## 安装

```bash
# Windows 下先设 UTF-8 输出，避免中文乱码
set PYTHONIOENCODING=utf-8

pip install -e D:\agent\carcustomer\tiktok-suite
```

依赖：fastapi、uvicorn、websocket-client、requests（Python >= 3.10）。

## 快速开始

```bash
# 1. 初始化数据库（建表 + 默认 settings）
ttkitc db init

# 2. 启动克隆 Chrome（独立 profile，首次需人工登录一次 TikTok）
ttkitc session launch
ttkitc session status        # running=true logged_in=true 即可

# 3. 采集视频评论并入库
ttkitc harvest https://www.tiktok.com/@someone/video/123456 --import

# 4. 扫所有监控视频
ttkitc scan

# 5. 起 REST 服务（127.0.0.1:8790）
ttkitc serve --port 8790
```

## CLI 示例

```bash
ttkitc leads list --status new --q price
ttkitc leads show evcars.tj
ttkitc leads update evcars.tj --status qualified --notes "问价 Leapmotor C10"

ttkitc templates add --lang en --action-type reply --name "quote-ask" --body "Hi! Price depends on model & quantity. Which car and how many units?"
ttkitc templates list

ttkitc engage reply evcars.tj --video https://www.tiktok.com/@someone/video/123 --template 1
ttkitc engage follow evcars.tj
ttkitc engage dm evcars.tj --text "Hi! We export cars from China."   # dm_enabled=false 时会被拒

ttkitc session status --json
```

所有输出人类可读，加 `--json` 输出 JSON。

## REST API

前缀 `/api`，统一响应 `{"ok": true, "data": ...}` 或 `{"ok": false, "error": "..."}`。
路由详见 `CONTRACT.md`：leads / interactions / videos / stats/overview / templates / settings / actions/execute。

- `POST /api/actions/execute`：需要克隆 Chrome 运行，否则 `409 {"ok":false,"error":"browser_not_running"}`；
  `dm_enabled=false` 时 dm 返回 403。
- CORS 全开，方便前端 / curl 直连调试；局域网部署走 Node 网关（8788）反代。

## 数据库

`TTKITC_DB_URL` 指定，默认 `sqlite:///D:/agent/carcustomer/tiktok-suite/data/leads.db`。
首次连接自动执行 `ttkitc/schema.sql` 建表。Python 侧负责建表/迁移，Node 只走 REST。

## 已知限制（2026-11 验证）

- **Cookie 不可复制**：Chrome 157 起 Cookie 为 App-Bound 加密，直接复制 Cookies 文件到新
  profile 会被 Chrome 丢弃。方案：克隆 Chrome（独立 profile）里人工登录一次 TikTok。
- **Google/Facebook OAuth**：在内嵌自动化浏览器会被拒，必须用真 Chrome。
- **评论 API 无法直接调**：`/api/comment/list` 直接 fetch 返回 status_code=5（缺 X-Bogus 等签名），
  所以采集用「页面自身请求 + fetch 拦截」。`window.byted_acrawler.frontierSign` 能算 X-Bogus，
  但只有它不够。
- **回复编辑器是 Draft.js**：直接改 innerText 状态不同步（发送按钮不亮），必须用
  ClipboardEvent('paste') + DataTransfer 注入。
- **新账号私信全被拦**：对陌生人连 "Hi" 都发不出，表现为页面出现「无法发送 / 违反」。
  此 blocked 状态原样上报，不会自动重试。
- **坐标脆弱**：follow/dm 依赖固定坐标（基准视口 1280x665），页面改版会失效；
  选择器集中在各模块顶部常量并标注「2026-11 验证」，失效时优先检查那里。
- 每日限额：reply 20 / follow 30 / dm 5，动作间隔 20s（settings 可调，CLI 可 `--no-cooldown`）。
