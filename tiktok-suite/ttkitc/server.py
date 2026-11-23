"""FastAPI 服务：实现 CONTRACT.md 全部 /api 路由。

- POST /api/actions/execute 调 engage + guard + 写 interactions；
  克隆 Chrome 没开 → 409 {"ok":false,"error":"browser_not_running"}；
  dm_enabled=false 时 dm → 403。
- CORS 允许全部（Node 网关会做代理，直连调试方便）。
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .db import Database
from . import session as chrome_session
from . import engage as engage_mod
from . import guard as guard_mod
from .harvest import parse_video_url

app = FastAPI(title="TikTok Lead Suite")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=False,
    allow_methods=["*"], allow_headers=["*"])

db = Database()


@app.exception_handler(HTTPException)
def http_exc_handler(request, exc):
    # 统一响应契约：{"ok":false,"error":...}
    return JSONResponse(status_code=exc.status_code, content=fail(exc.detail))


def ok(data):
    return {"ok": True, "data": data}


def fail(msg):
    return {"ok": False, "error": msg}


# ---------- leads ----------

@app.get("/api/leads")
def api_leads(q: str = None, status: str = None, lang: str = None,
              region: str = None, limit: int = 200, offset: int = 0):
    return ok(db.leads.search(q=q, status=status, lang=lang, region=region,
                              limit=limit, offset=offset))


@app.get("/api/leads/{lead_id}")
def api_lead_detail(lead_id: int):
    lead = db.leads.get(lead_id)
    if not lead:
        raise HTTPException(404, "lead not found")
    lead["interactions"] = db.interactions.list(lead_id=lead_id, limit=100)
    return ok(lead)


class LeadPatch(BaseModel):
    status: str = None
    notes: str = None
    intent_score: int = None


@app.patch("/api/leads/{lead_id}")
def api_lead_patch(lead_id: int, body: LeadPatch):
    lead = db.leads.update(lead_id, status=body.status, notes=body.notes,
                           intent_score=body.intent_score)
    if not lead:
        raise HTTPException(404, "lead not found")
    return ok(lead)


# ---------- interactions ----------

@app.get("/api/interactions")
def api_interactions(lead_id: int = None, action_type: str = None,
                     status: str = None, limit: int = 200, offset: int = 0):
    return ok(db.interactions.list(lead_id=lead_id, action_type=action_type,
                                   status=status, limit=limit, offset=offset))


# ---------- videos ----------

@app.get("/api/videos")
def api_videos():
    return ok(db.videos.list())


class VideoIn(BaseModel):
    url: str
    title: str = None


@app.post("/api/videos", status_code=201)
def api_video_create(body: VideoIn):
    try:
        canonical, author = parse_video_url(body.url)
    except ValueError as e:
        raise HTTPException(400, str(e))
    video_id, created = db.videos.get_or_create(canonical, author_username=author,
                                                title=body.title)
    return ok(db.videos.get(video_id))


class VideoPatch(BaseModel):
    monitor: bool = None
    title: str = None


@app.patch("/api/videos/{video_id}")
def api_video_patch(video_id: int, body: VideoPatch):
    video = db.videos.update(video_id, monitor=body.monitor, title=body.title)
    if not video:
        raise HTTPException(404, "video not found")
    return ok(video)


# ---------- stats ----------

@app.get("/api/stats/overview")
def api_stats_overview():
    lead_total = db.query("SELECT COUNT(*) AS c FROM leads")[0]["c"]
    by_status = {r["status"]: r["c"] for r in db.query(
        "SELECT status, COUNT(*) AS c FROM leads GROUP BY status")}
    by_lang = {r["language"] or "unknown": r["c"] for r in db.query(
        "SELECT language, COUNT(*) AS c FROM leads GROUP BY language")}
    by_region = {r["region"] or "unknown": r["c"] for r in db.query(
        "SELECT region, COUNT(*) AS c FROM leads GROUP BY region")}
    funnel = {k: by_status.get(k, 0) for k in ("new", "replied", "followed", "qualified")}
    rows = db.query(
        """SELECT date(created_at) AS d, action_type, COUNT(*) AS c
           FROM interactions GROUP BY d, action_type ORDER BY d DESC LIMIT 30""")
    daily = {}
    for r in rows:
        daily.setdefault(r["d"], {"date": r["d"], "reply": 0, "follow": 0, "dm": 0})
        daily[r["d"]][r["action_type"]] = r["c"]
    blocked_count = db.query(
        "SELECT COUNT(*) AS c FROM interactions WHERE status='blocked'")[0]["c"]
    return ok({
        "lead_total": lead_total, "by_status": by_status, "by_lang": by_lang,
        "by_region": by_region, "funnel": funnel,
        "daily_actions": list(daily.values()), "blocked_count": blocked_count})


# ---------- templates ----------

@app.get("/api/templates")
def api_templates(lang: str = None, action_type: str = None):
    return ok(db.templates.list(lang=lang, action_type=action_type))


class TemplateIn(BaseModel):
    lang: str
    action_type: str
    name: str
    body: str


@app.post("/api/templates", status_code=201)
def api_template_create(body: TemplateIn):
    tid = db.templates.add(body.lang, body.action_type, body.name, body.body)
    return ok(db.templates.get(tid))


class TemplatePatch(BaseModel):
    active: bool = None


@app.patch("/api/templates/{template_id}")
def api_template_patch(template_id: int, body: TemplatePatch):
    if body.active is not None:
        db.templates.set_active(template_id, body.active)
    tpl = db.templates.get(template_id)
    if not tpl:
        raise HTTPException(404, "template not found")
    return ok(tpl)


@app.delete("/api/templates/{template_id}")
def api_template_delete(template_id: int):
    db.templates.delete(template_id)
    return ok({"deleted": template_id})


# ---------- settings ----------

@app.get("/api/settings")
def api_settings():
    return ok(db.settings.all())


@app.put("/api/settings")
def api_settings_put(body: dict):
    db.settings.set_many(body)
    return ok(db.settings.all())


# ---------- actions ----------

class ActionIn(BaseModel):
    lead_id: int
    action: str  # reply|follow|dm
    content: str = None


@app.post("/api/actions/execute")
def api_action_execute(body: ActionIn):
    if body.action not in ("reply", "follow", "dm"):
        raise HTTPException(400, f"unsupported action: {body.action}")
    st = chrome_session.status(db)
    if not st.get("running"):
        raise HTTPException(409, "browser_not_running")
    lead = db.leads.get(body.lead_id)
    if not lead:
        raise HTTPException(404, "lead not found")
    if body.action == "dm" and not db.settings.get_bool("dm_enabled", False):
        raise HTTPException(403, "dm_disabled")
    limit_hit = guard_mod.check_daily_limit(db, body.action)
    if limit_hit:
        result = limit_hit
    else:
        guard_mod.cooldown(db, enabled=True)
        text = body.content or ""
        if body.action == "reply":
            video = db.videos.get(lead["source_video_id"]) if lead.get("source_video_id") else None
            result = engage_mod.reply(video["url"] if video else None,
                                      lead["username"], text)
        elif body.action == "follow":
            result = engage_mod.follow(lead["username"])
        else:
            result = engage_mod.dm(lead["username"], text, db=db)
    engage_mod.record_interaction(db, lead["username"], body.action, text, result)
    return ok(result)


def run(host="127.0.0.1", port=8790):
    import uvicorn
    uvicorn.run(app, host=host, port=port)
