"""线索 enrichment：访问用户主页，抓 /api/user/detail 补全 leads 行。

背景（2026-11 验证）：comment/list 返回的 user 对象是精简版——region/language/
follower_count/signature 全空；而主页加载时页面会发签名的 /api/user/detail，
返回完整用户信息（userInfo.user + userInfo.stats）。

实现要点：
- 导航会清空普通 eval 注入的钩子，所以用 Page.addScriptToEvaluateOnNewDocument
  （cdp.py 的 add_init_script）在每次新文档的页面脚本运行前注入拦截器。
- 重要实测（2026-11）：直接地址栏开主页时，用户数据走 HTML 内嵌的
  __UNIVERSAL_DATA_FOR_REHYDRATION__，页面不发 /api/user/detail 请求；
  只有 SPA 站内跳转（如从视频页点评论者昵称）才发该请求。
  所以 READ_JS 两条路都读：拦截结果优先，内嵌数据兜底。
- 兜底：若 TikTok 页面脚本后于钩子重写了 window.fetch（钩子被覆盖），
  则加载后再 eval 注入一次并 Page.reload 重抓。
- 页面冷加载慢（15-20s 起步），期间 eval 会阻塞到 ws 超时，因此 Tab 用短超时
  （20s），整体有硬时间预算，拿不到就返回失败而不是挂死。
- whatsapp/手机号提取复用 harvest.extract_whatsapp；intent_score 用 scoring 重算
  （comment_text 沿用库中已有值）。
- 注意：web 版 user-detail 已不返回 region 字段（2026-11 实测 user 对象里根本没
  有该 key），地区信号用 language 代替；leads.region 保留但不期望被填充。
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

# 读取优先级：fetch 拦截的 /api/user/detail → DOM 里的 __UNIVERSAL_DATA_FOR_REHYDRATION__
# script 标签（2026-11 验证：直接开主页时页面不发 user/detail 请求，数据以 HTML 内嵌
# JSON 下发；window 上的变量会被应用删空，但 script 标签原文仍在 DOM 里；
# SPA 站内跳转才发 /api/user/detail，此时靠上面的拦截钩子）
READ_JS = """(()=>{
  const pick=(u,s)=>({
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
  const fromUserInfo=(ui)=>{const u=(ui||{}).user; return u?pick(u,(ui||{}).stats||{}):null;};
  const j=window.__enrich;
  if(j){ const d=fromUserInfo(j.userInfo||j.data); if(d) return JSON.stringify(d); }
  try{
    const el=document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__');
    if(el&&el.textContent){
      const ud=JSON.parse(el.textContent);
      const sc=(ud&&ud.__DEFAULT_SCOPE__)||{};
      const k=Object.keys(sc).find(k=>k.indexOf('user-detail')>=0);
      if(k){ const d=fromUserInfo(sc[k].userInfo); if(d) return JSON.stringify(d); }
    }
  }catch(e){}
  return null;
})()"""

FIELDS = ("uid", "region", "language", "followers", "following_count",
          "bio", "whatsapp", "intent_score")


def _read_detail(tab):
    try:
        raw = tab.eval(READ_JS)
    except Exception:
        # 页面加载中 eval 会阻塞/超时，视为「还没抓到」
        return None
    if not raw or isinstance(raw, dict):  # dict 即 {"__error__":...}
        return None
    return json.loads(raw)


def _wait_ready(tab, timeout=60):
    """轮询直到页面渲染出内容（body 有文本）。TikTok 冷加载 15-20s 起步。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            body_len = tab.eval("(document.body&&document.body.innerText||'').length") or 0
            if body_len > 100:
                return True
        except Exception:
            pass
        time.sleep(3)
    return False


def fetch_user_detail(username, wait=10, budget=120):
    """开主页抓 /api/user/detail。返回 detail dict 或 None（失败）。

    硬时间预算 budget 秒内拿不到就放弃；页面加载期 eval 阻塞由短 ws 超时兜底。
    """
    deadline = time.time() + budget
    t = Tab("about:blank", timeout=20)
    try:
        t.add_init_script(HOOK_JS)
        t.nav(f"https://www.tiktok.com/@{username}", wait=wait)
        _wait_ready(t, timeout=min(60, max(10, deadline - time.time())))
        detail = _read_detail(t)
        if detail is not None:
            return detail
        if time.time() > deadline:
            return None
        # 兜底：钩子可能被页面脚本重写覆盖 → 加载后补注入 + 重载重抓
        try:
            t.eval(HOOK_JS)
            t.send("Page.reload", {"ignoreCache": True})
        except Exception:
            return None
        _wait_ready(t, timeout=min(60, max(10, deadline - time.time())))
        return _read_detail(t)
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
