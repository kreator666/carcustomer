"""线索 enrichment：访问用户主页，抓 /api/user/detail 补全 leads 行。

背景（2026-11 验证）：comment/list 返回的 user 对象是精简版——region/language/
follower_count/signature 全空；而主页加载时页面会发签名的 /api/user/detail，
返回完整用户信息（userInfo.user + userInfo.stats）。

实现要点：
- 导航会清空普通 eval 注入的钩子，所以用 Page.addScriptToEvaluateOnNewDocument
  （cdp.py 的 add_init_script）在每次新文档的页面脚本运行前注入拦截器。
- 兜底：若 TikTok 页面脚本后于钩子重写了 window.fetch（钩子被覆盖），
  则加载后再 eval 注入一次并 Page.reload 重抓。
- whatsapp/手机号提取复用 harvest.extract_whatsapp；intent_score 用 scoring 重算
  （comment_text 沿用库中已有值）。
"""

import json
import time

from .cdp import Tab
from .harvest import extract_whatsapp
from .scoring import score_lead

API_USER_DETAIL = "/api/user/detail"  # 2026-11 验证

# 拦截器：init script 用（无 IIFE 包裹，直接作为文档初始化代码执行）
HOOK_JS = """window.__enrich=null;
(function(){
  const of=window.fetch;
  window.fetch=function(...a){
    const u=String(a[0]&&a[0].url||a[0]);
    return of.apply(this,a).then(async resp=>{
      if(u.includes('/api/user/detail')){ try{ window.__enrich=await resp.clone().json(); }catch(e){} }
      return resp;
    });
  };
})();"""

READ_JS = """(()=>{
  const j=window.__enrich; if(!j) return null;
  const ui=j.userInfo||j.data||{};
  const u=ui.user||j.user||{};
  const s=ui.stats||j.stats||{};
  return JSON.stringify({
    uid:String(u.id||u.uid||''),
    username:String(u.uniqueId||u.unique_id||''),
    nickname:String(u.nickname||''),
    region:String(u.region||''),
    language:String(u.language||''),
    followers:s.followerCount||u.follower_count||0,
    following_count:s.followingCount||u.following_count||0,
    aweme_count:s.videoCount||u.aweme_count||0,
    bio:String(u.signature||u.bio||'')
  });
})()"""

FIELDS = ("uid", "region", "language", "followers", "following_count",
          "bio", "whatsapp", "intent_score")


def _read_detail(tab):
    raw = tab.eval(READ_JS)
    if not raw or isinstance(raw, dict):  # dict 即 {"__error__":...}
        return None
    return json.loads(raw)


def fetch_user_detail(username, wait=10):
    """开主页抓 /api/user/detail。返回 detail dict 或 None（失败）。"""
    t = Tab("about:blank")
    try:
        t.add_init_script(HOOK_JS)
        t.nav(f"https://www.tiktok.com/@{username}", wait=wait)
        detail = _read_detail(t)
        if detail is None:
            # 兜底：钩子可能被页面脚本重写覆盖 → 加载后补注入 + 重载重抓
            t.eval(HOOK_JS)
            t.send("Page.reload", {"ignoreCache": True})
            time.sleep(wait)
            detail = _read_detail(t)
        return detail
    finally:
        t.close()


def enrich_user(db, username, wait=10):
    """enrich 单个 username，更新 leads 行。返回 {username, before, after} 或 {username, error}。"""
    lead = db.leads.get_by_username(username)
    if not lead:
        return {"username": username, "error": "lead_not_found"}
    before = {f: lead.get(f) for f in FIELDS}
    detail = fetch_user_detail(username, wait=wait)
    if not detail:
        return {"username": username, "error": "user_detail_not_captured", "before": before}
    aweme_count = detail.get("aweme_count") or 0
    score = score_lead({
        "comment_text": lead.get("comment_text"), "bio": detail.get("bio"),
        "followers": detail.get("followers"), "aweme_count": aweme_count})
    after = db.leads.update(
        lead["id"],
        uid=detail.get("uid") or None,
        region=detail.get("region") or None,
        language=detail.get("language") or None,
        followers=detail.get("followers") or None,
        following_count=detail.get("following_count") or None,
        bio=detail.get("bio") or None,
        whatsapp=extract_whatsapp(detail.get("bio")),
        intent_score=score)
    return {"username": username,
            "before": before,
            "after": {f: after.get(f) for f in FIELDS}}


def enrich_all_new(db, sleep_secs=5, wait=10):
    """对所有 status='new' 且 region 为空的 lead 逐个 enrich，lead 间 sleep 5s。"""
    results = []
    targets = db.leads.list_enrich_targets()
    for i, lead in enumerate(targets):
        if i > 0 and sleep_secs > 0:
            time.sleep(sleep_secs)
        results.append(enrich_user(db, lead["username"], wait=wait))
    return {"total": len(targets), "results": results}
