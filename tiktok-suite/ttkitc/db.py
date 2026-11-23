"""数据库连接抽象层与 repository 实现。

设计：
- Backend 接口：execute / query / transaction 三个原语。新增后端（如 postgres）时：
  1. 实现 Backend 接口（用对应驱动替换 sqlite3）；
  2. 在 Database._create_backend 的 URL 解析里加新 scheme 分支；
  3. schema.sql 换成目标库方言（或加迁移目录）。
- 连接池：SQLite 下用 thread-local，每个线程一个连接（sqlite3 连接非线程安全）。
  高并发场景可替换为 queue.Queue 连接池，Backend 接口不变。
- 时间统一 ISO8601 本地字符串：datetime.now().isoformat(timespec="seconds")。
"""

import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime

DEFAULT_DB_URL = "sqlite:///D:/agent/carcustomer/tiktok-suite/data/leads.db"

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")

DEFAULT_SETTINGS = {
    "daily_reply_limit": "20",
    "daily_follow_limit": "30",
    "daily_dm_limit": "5",
    "cooldown_seconds": "20",
    "dm_enabled": "false",
    "browser_port": "9222",
    "chrome_path": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "profile_dir": r"C:\Users\tiger\tiktok-chrome-profile",
}


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


class Backend:
    """连接后端接口。新增后端请实现这三个方法。"""

    def execute(self, sql, params=()):
        """执行写操作，返回 cursor（可用 lastrowid / rowcount）。"""
        raise NotImplementedError

    def query(self, sql, params=()):
        """执行读操作，返回 list[dict]。"""
        raise NotImplementedError

    @contextmanager
    def transaction(self):
        """事务上下文：块内多条 execute 要么全提交要么全回滚。"""
        raise NotImplementedError


class SQLiteBackend(Backend):
    """SQLite 后端：thread-local 连接，每个线程独立连接避免线程安全问题。"""

    def __init__(self, path):
        self.path = path
        self._local = threading.local()
        self._init_schema()

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _conn(self):
        # thread-local：同一线程复用同一连接，保证事务内多条语句在同一连接上
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._connect()
            self._local.conn = conn
        return conn

    def _init_schema(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            schema = f.read()
        conn = self._connect()
        try:
            conn.executescript(schema)
            conn.commit()
        finally:
            conn.close()

    def execute(self, sql, params=()):
        conn = self._conn()
        cur = conn.execute(sql, params)
        conn.commit()
        return cur

    def query(self, sql, params=()):
        cur = self._conn().execute(sql, params)
        return [dict(r) for r in cur.fetchall()]

    @contextmanager
    def transaction(self):
        conn = self._conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


class Database:
    """从 TTKITC_DB_URL 解析连接（默认 sqlite:///path），并挂全部 repository。"""

    def __init__(self, url=None):
        self.url = url or os.environ.get("TTKITC_DB_URL", DEFAULT_DB_URL)
        self.backend = self._create_backend(self.url)
        self.leads = LeadRepo(self)
        self.interactions = InteractionRepo(self)
        self.videos = VideoRepo(self)
        self.templates = TemplateRepo(self)
        self.settings = SettingsRepo(self)

    @staticmethod
    def _create_backend(url):
        # 扩展点：postgres://... → PostgresBackend(...)
        if url.startswith("sqlite:///"):
            return SQLiteBackend(url[len("sqlite:///"):])
        raise ValueError(f"unsupported db url: {url}（目前仅支持 sqlite:///path）")

    def execute(self, sql, params=()):
        return self.backend.execute(sql, params)

    def query(self, sql, params=()):
        return self.backend.query(sql, params)

    @contextmanager
    def transaction(self):
        with self.backend.transaction() as conn:
            yield conn


class LeadRepo:
    def __init__(self, db):
        self.db = db

    def upsert(self, lead):
        """按 username 唯一 upsert；返回 (lead_id, created?)。"""
        existing = self.get_by_username(lead.get("username"))
        ts = now_iso()
        if existing:
            fields = ["uid", "nickname", "region", "language", "comment_text",
                      "comment_id", "followers", "following_count", "whatsapp",
                      "phone", "bio", "intent_score"]
            sets, params = [], []
            for f in fields:
                if lead.get(f) is not None:
                    sets.append(f"{f}=?")
                    params.append(lead[f])
            if lead.get("source_video_id") is not None:
                sets.append("source_video_id=?")
                params.append(lead["source_video_id"])
            if sets:
                params.append(existing["id"])
                self.db.execute(f"UPDATE leads SET {','.join(sets)} WHERE id=?", params)
            return existing["id"], False
        cur = self.db.execute(
            """INSERT INTO leads(username,uid,nickname,region,language,source_video_id,
                   comment_text,comment_id,followers,following_count,whatsapp,phone,bio,
                   intent_score,status,first_seen_at,last_interaction_at,notes)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (lead.get("username"), lead.get("uid"), lead.get("nickname"),
             lead.get("region"), lead.get("language"), lead.get("source_video_id"),
             lead.get("comment_text"), lead.get("comment_id"),
             lead.get("followers") or 0, lead.get("following_count") or 0,
             lead.get("whatsapp"), lead.get("phone"), lead.get("bio"),
             lead.get("intent_score") or 0, lead.get("status") or "new",
             ts, ts, lead.get("notes")))
        return cur.lastrowid, True

    def get(self, lead_id):
        rows = self.db.query("SELECT * FROM leads WHERE id=?", (lead_id,))
        return rows[0] if rows else None

    def get_by_username(self, username):
        rows = self.db.query("SELECT * FROM leads WHERE username=?", (username,))
        return rows[0] if rows else None

    def search(self, q=None, status=None, lang=None, region=None, limit=200, offset=0):
        """CONTRACT: GET /api/leads。q 匹配 username/nickname/comment_text/bio。"""
        where, params = [], []
        if q:
            where.append("(username LIKE ? OR nickname LIKE ? OR comment_text LIKE ? OR bio LIKE ?)")
            like = f"%{q}%"
            params += [like, like, like, like]
        if status:
            where.append("status=?")
            params.append(status)
        if lang:
            where.append("language=?")
            params.append(lang)
        if region:
            where.append("region=?")
            params.append(region)
        w = (" WHERE " + " AND ".join(where)) if where else ""
        total = self.db.query(f"SELECT COUNT(*) AS c FROM leads{w}", params)[0]["c"]
        items = self.db.query(
            f"SELECT * FROM leads{w} ORDER BY id DESC LIMIT ? OFFSET ?",
            params + [limit, offset])
        return {"total": total, "items": items}

    def update(self, lead_id, status=None, notes=None, intent_score=None,
               region=None, language=None, followers=None, following_count=None,
               bio=None, whatsapp=None, uid=None, nickname=None):
        sets, params = [], []
        for f, v in (("status", status), ("notes", notes), ("intent_score", intent_score),
                     ("region", region), ("language", language), ("followers", followers),
                     ("following_count", following_count), ("bio", bio),
                     ("whatsapp", whatsapp), ("uid", uid), ("nickname", nickname)):
            if v is not None:
                sets.append(f"{f}=?")
                params.append(v)
        if not sets:
            return self.get(lead_id)
        params.append(lead_id)
        self.db.execute(f"UPDATE leads SET {','.join(sets)} WHERE id=?", params)
        return self.get(lead_id)

    def list_enrich_targets(self):
        """enrich --all-new 目标：status='new' 且信息缺失的 lead。

        原标准是 region 为空；实测（2026-11）web user-detail 已不返回 region 字段，
        所以用「region 且 language 均为空」作为「尚未 enrich」的判据——
        enrich 后 language 必有值，会自动退出目标集。
        """
        return self.db.query(
            "SELECT * FROM leads WHERE status='new' "
            "AND (region IS NULL OR region='') AND (language IS NULL OR language='') ORDER BY id")

    def touch(self, lead_id):
        self.db.execute("UPDATE leads SET last_interaction_at=? WHERE id=?",
                        (now_iso(), lead_id))


class InteractionRepo:
    ACTION_TYPES = ("reply", "follow", "dm")

    def __init__(self, db):
        self.db = db

    def add(self, lead_id, action_type, content, status, platform_msg=""):
        cur = self.db.execute(
            """INSERT INTO interactions(lead_id,action_type,content,status,platform_msg,created_at)
               VALUES(?,?,?,?,?,?)""",
            (lead_id, action_type, content, status, platform_msg, now_iso()))
        return cur.lastrowid

    def list(self, lead_id=None, action_type=None, status=None, limit=200, offset=0):
        where, params = [], []
        if lead_id:
            where.append("lead_id=?")
            params.append(lead_id)
        if action_type:
            where.append("action_type=?")
            params.append(action_type)
        if status:
            where.append("status=?")
            params.append(status)
        w = (" WHERE " + " AND ".join(where)) if where else ""
        return self.db.query(
            f"SELECT * FROM interactions{w} ORDER BY id DESC LIMIT ? OFFSET ?",
            params + [limit, offset])

    def count_today(self, action_type):
        """当日某动作计数（guard 限流用）。created_at 为 ISO 本地串，date() 可直接取日期。"""
        return self.db.query(
            "SELECT COUNT(*) AS c FROM interactions WHERE action_type=? AND date(created_at)=date('now','localtime')",
            (action_type,))[0]["c"]


class VideoRepo:
    def __init__(self, db):
        self.db = db

    def get_or_create(self, url, author_username=None, title=None):
        """按 url 唯一 get_or_create，返回 (video_id, created?)。"""
        rows = self.db.query("SELECT * FROM videos WHERE url=?", (url,))
        if rows:
            return rows[0]["id"], False
        cur = self.db.execute(
            "INSERT INTO videos(url,author_username,title,monitor,created_at) VALUES(?,?,?,0,?)",
            (url, author_username, title, now_iso()))
        return cur.lastrowid, True

    def get(self, video_id):
        rows = self.db.query("SELECT * FROM videos WHERE id=?", (video_id,))
        return rows[0] if rows else None

    def list(self):
        """含每条视频的 lead_count（CONTRACT: GET /api/videos）。"""
        return self.db.query(
            """SELECT v.*, (SELECT COUNT(*) FROM leads l WHERE l.source_video_id=v.id) AS lead_count
               FROM videos v ORDER BY v.id DESC""")

    def update(self, video_id, monitor=None, title=None):
        sets, params = [], []
        if monitor is not None:
            sets.append("monitor=?")
            params.append(1 if monitor else 0)
        if title is not None:
            sets.append("title=?")
            params.append(title)
        if sets:
            params.append(video_id)
            self.db.execute(f"UPDATE videos SET {','.join(sets)} WHERE id=?", params)
        return self.get(video_id)

    def touch_scanned(self, video_id, cursor=None):
        sets = "last_scanned_at=?"
        params = [now_iso()]
        if cursor is not None:
            sets += ",last_comment_cursor=?"
            params.append(cursor)
        params.append(video_id)
        self.db.execute(f"UPDATE videos SET {sets} WHERE id=?", params)

    def monitored(self):
        return self.db.query("SELECT * FROM videos WHERE monitor=1 ORDER BY id")


class TemplateRepo:
    def __init__(self, db):
        self.db = db

    def list(self, lang=None, action_type=None, include_inactive=True):
        where, params = [], []
        if lang:
            where.append("lang=?")
            params.append(lang)
        if action_type:
            where.append("action_type=?")
            params.append(action_type)
        if not include_inactive:
            where.append("active=1")
        w = (" WHERE " + " AND ".join(where)) if where else ""
        return self.db.query(f"SELECT * FROM templates{w} ORDER BY id", params)

    def get(self, template_id):
        rows = self.db.query("SELECT * FROM templates WHERE id=?", (template_id,))
        return rows[0] if rows else None

    def add(self, lang, action_type, name, body):
        cur = self.db.execute(
            "INSERT INTO templates(lang,action_type,name,body,active) VALUES(?,?,?,?,1)",
            (lang, action_type, name, body))
        return cur.lastrowid

    def set_active(self, template_id, active):
        self.db.execute("UPDATE templates SET active=? WHERE id=?",
                        (1 if active else 0, template_id))

    def delete(self, template_id):
        self.db.execute("DELETE FROM templates WHERE id=?", (template_id,))


class SettingsRepo:
    def __init__(self, db):
        self.db = db
        self._ensure_defaults()

    def _ensure_defaults(self):
        for k, v in DEFAULT_SETTINGS.items():
            self.db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, v))

    def all(self):
        return {r["key"]: r["value"] for r in self.db.query("SELECT key,value FROM settings")}

    def get(self, key, default=None):
        rows = self.db.query("SELECT value FROM settings WHERE key=?", (key,))
        return rows[0]["value"] if rows else default

    def get_int(self, key, default=0):
        v = self.get(key)
        try:
            return int(v)
        except (TypeError, ValueError):
            return default

    def get_bool(self, key, default=False):
        v = self.get(key)
        if v is None:
            return default
        return str(v).lower() in ("1", "true", "yes", "on")

    def set_many(self, kv):
        with self.db.transaction() as conn:
            for k, v in kv.items():
                conn.execute(
                    "INSERT INTO settings(key,value) VALUES(?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, str(v)))
