-- TikTok Lead Suite 建表 SQL（CONTRACT.md Schema 节，SQLite）
-- 由 db.py 首次连接时自动执行；已有表则跳过（CREATE TABLE IF NOT EXISTS）

CREATE TABLE IF NOT EXISTS leads(
  id INTEGER PRIMARY KEY,
  platform TEXT DEFAULT 'tiktok',
  username TEXT UNIQUE,
  uid TEXT,
  nickname TEXT,
  region TEXT,
  language TEXT,
  source_video_id INTEGER REFERENCES videos(id),
  comment_text TEXT,
  comment_id TEXT,
  followers INTEGER DEFAULT 0,
  following_count INTEGER DEFAULT 0,
  whatsapp TEXT,
  phone TEXT,
  bio TEXT,
  intent_score INTEGER DEFAULT 0,
  status TEXT DEFAULT 'new',
  first_seen_at TEXT,
  last_interaction_at TEXT,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS interactions(
  id INTEGER PRIMARY KEY,
  lead_id INTEGER REFERENCES leads(id),
  action_type TEXT,
  content TEXT,
  status TEXT,
  platform_msg TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS videos(
  id INTEGER PRIMARY KEY,
  url TEXT UNIQUE,
  author_username TEXT,
  title TEXT,
  monitor INTEGER DEFAULT 0,
  last_scanned_at TEXT,
  last_comment_cursor TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS templates(
  id INTEGER PRIMARY KEY,
  lang TEXT,
  action_type TEXT,
  name TEXT,
  body TEXT,
  active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS settings(
  key TEXT PRIMARY KEY,
  value TEXT
);

-- 常用查询索引
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_source_video ON leads(source_video_id);
CREATE INDEX IF NOT EXISTS idx_interactions_lead ON interactions(lead_id);
CREATE INDEX IF NOT EXISTS idx_interactions_created ON interactions(created_at);
