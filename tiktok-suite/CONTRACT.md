# TikTok Lead Suite — 共享契约 (Python 后端 / Node 前端 共同遵守)

## 端口约定
- FastAPI (内部): 127.0.0.1:8790
- Node 网关 (局域网): 0.0.0.0:8788，静态服务 + `/api/*` 反代到 127.0.0.1:8790

## 数据库
- URL 由环境变量 `TTKITC_DB_URL` 指定，默认 `sqlite:///D:/agent/carcustomer/tiktok-suite/data/leads.db`
- Python 侧负责建表/迁移；Node 只通过 REST 访问，不直连 DB

## Schema (SQLite)

```sql
leads(
  id INTEGER PK, platform TEXT DEFAULT 'tiktok',
  username TEXT UNIQUE, uid TEXT, nickname TEXT, region TEXT, language TEXT,
  source_video_id INTEGER REFERENCES videos(id),
  comment_text TEXT, comment_id TEXT,
  followers INTEGER DEFAULT 0, following_count INTEGER DEFAULT 0,
  whatsapp TEXT, phone TEXT, bio TEXT,
  intent_score INTEGER DEFAULT 0,
  status TEXT DEFAULT 'new',   -- new/replied/followed/contacted/qualified/dead
  first_seen_at TEXT, last_interaction_at TEXT, notes TEXT
)
interactions(
  id INTEGER PK, lead_id INTEGER REFERENCES leads(id),
  action_type TEXT,            -- reply/follow/dm
  content TEXT, status TEXT,   -- success/blocked/error
  platform_msg TEXT, created_at TEXT
)
videos(
  id INTEGER PK, url TEXT UNIQUE, author_username TEXT, title TEXT,
  monitor INTEGER DEFAULT 0, last_scanned_at TEXT, last_comment_cursor TEXT,
  created_at TEXT
)
templates(id INTEGER PK, lang TEXT, action_type TEXT, name TEXT, body TEXT, active INTEGER DEFAULT 1)
settings(key TEXT PK, value TEXT)
```

## REST API (FastAPI, 前缀 /api)

统一响应: `{"ok": true, "data": ...}` 或 `{"ok": false, "error": "msg"}`；时间 ISO8601 本地字符串。

- `GET /api/leads` query: q, status, lang, region, limit(默认200), offset → `{total, items:[lead]}`
- `GET /api/leads/{id}` → lead + `interactions: [...]`
- `PATCH /api/leads/{id}` body: {status?, notes?, intent_score?} → updated lead
- `GET /api/interactions` query: lead_id, action_type, status, limit → items
- `GET /api/videos` → items(含 last_scanned_at, 关联 lead_count)
- `POST /api/videos` body: {url} → 创建(自动解析 author/video_id)，重复返回已有
- `PATCH /api/videos/{id}` body: {monitor?, title?}
- `GET /api/stats/overview` →
  `{lead_total, by_status:{}, by_lang:{}, by_region:{}, funnel:{new,replied,followed,qualified}, daily_actions:[{date,reply,follow,dm}], blocked_count}`
- `GET /api/templates` query: lang, action_type → items
- `POST /api/templates` / `PATCH /api/templates/{id}` / `DELETE /api/templates/{id}`
- `GET /api/settings` → {key:value...}
- `PUT /api/settings` body: {key:value,...}
- `POST /api/actions/execute` body: {lead_id, action: reply|follow|dm, content?} →
  调用 ttkitc engage，返回 `{status: success|blocked|error, platform_msg}` 并写 interactions 表。
  需要克隆 Chrome 在运行；否则 409 `{ok:false, error:"browser_not_running"}`。
  settings.dm_enabled=false 时 dm 返回 403。

## 默认 settings 键
```
daily_reply_limit=20, daily_follow_limit=30, daily_dm_limit=5,
cooldown_seconds=20, dm_enabled=false, browser_port=9222,
chrome_path=C:\Program Files\Google\Chrome\Application\chrome.exe,
profile_dir=C:\Users\tiger\tiktok-chrome-profile
```

## 意向评分规则 (scoring)
问价关键词(how much/price/prezzo/prezzo?/价格/多少钱/quote/прейскурант) +40；
bio 含 whatsapp/phone/数字连号 ≥9位 +30；
dealer 关键词(auto/cars/motor/ev/export/dealer/электро/ Cars.TJ 等) +20；
followers>500 +10；aweme_count>0 +10；上限 100。
```
