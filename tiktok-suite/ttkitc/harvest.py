"""评论采集（照 hook2.py / readcap4.py 实战流程工程化）。

平台 quirks（2026-11 验证）：
- 直接 fetch /api/comment/list 会返回 status_code=5（需 X-Bogus 等签名），
  所以改为注入页面 fetch 拦截，抓页面自身请求的响应。
- window.byted_acrawler.frontierSign 可以算 X-Bogus，但只有 X-Bogus 不够
  （还有 a_bogus / msToken 链路），性价比低，不如拦截。
- 评论面板由「评论数按钮」点开：div[class*=ButtonActionItemV1] 且 innerText
  恰为评论数字（如 "4"）。
"""

import json
import re
import time

from .cdp import CDP
from .scoring import score_lead

# 选择器集中定义，2026-11 验证；失效时优先检查这里
SEL_COMMENT_COUNT_BTN = "div[class*=ButtonActionItemV1]"  # innerText == 评论数
API_COMMENT_LIST = "/api/comment/list"
API_COMMENT_PUBLISH = "/api/comment/publish/"
API_COMMENT_REPLY = "/api/comment/reply/"

# bio 里的 whatsapp/手机号提取（2026-11 验证够用，误报可接受）
RE_WHATSAPP = re.compile(r"(?:whatsapp|wa\.me/|wa\.cc/|t\.me/)\D{0,4}(\+?\d[\d\s\-()]{7,}\d)", re.I)
RE_PHONE = re.compile(r"(\+?\d[\d\s\-()]{7,}\d)")

HOOK_JS = """(()=>{
  window.__caps=[];
  const of=window.fetch;
  window.fetch=function(...a){
    const u=String(a[0]&&a[0].url||a[0]);
    return of.apply(this,a).then(async resp=>{
      if(u.includes('/api/comment/list')){ try{ window.__caps.push({u:u.slice(0,220), j:await resp.clone().json()}); }catch(e){} }
      return resp;
    });
  };
  return 'ok';
})()"""

READ_JS = """(()=>{
  if(!window.__caps||!window.__caps.length) return null;
  const j=window.__caps[0].j;
  const list=(j.comments||[]).map(cm=>{
    const u=cm.user||{};
    return {user:String(u.unique_id||''), uid:String(u.uid||''), nickname:String(u.nickname||''),
            cid:String(cm.cid||''), text:(cm.text||'').replace(/\\n/g,' ').slice(0,500),
            region:String(u.region||''), language:String(u.language||''),
            followers:u.follower_count||0, following_count:u.following_count||0,
            aweme_count:u.aweme_count||0, bio:String(u.signature||u.bio||'')};
  });
  return JSON.stringify({status:j.status_code, has_more:j.has_more, cursor:String(j.cursor||''), list:list});
})()"""

# 评论数按钮点击（重试循环由 Python 驱动）
# 2026-11 验证：数字 innerText 的按钮有多个（赞/评论/收藏/分享），
# 必须按 data-e2e=comment-icon 或 aria-label 含「评论 / Read or add」锁定，否则会点到点赞
CLICK_COMMENTS_JS = """(()=>{
  const all=[...document.querySelectorAll('div[class*=ButtonActionItemV1]')];
  const b=all.find(e=>e.getAttribute('data-e2e')==='comment-icon'
      ||/评论|Read or add/i.test(e.getAttribute('aria-label')||''));
  if(!b) return null;
  b.click(); return (b.innerText||'').trim();
})()"""


def parse_video_url(url):
    """规范化为 https://www.tiktok.com/@author/video/id，返回 (canonical, author)。"""
    m = re.search(r"tiktok\.com/@([^/?#]+)/video/(\d+)", url)
    if not m:
        raise ValueError(f"不是有效的 TikTok 视频链接: {url}")
    author, vid = m.group(1), m.group(2)
    return f"https://www.tiktok.com/@{author}/video/{vid}", author


def extract_whatsapp(bio):
    """从 bio 提取 whatsapp/手机号；harvest 与 enrich 共用。"""
    if not bio:
        return None
    m = RE_WHATSAPP.search(bio) or RE_PHONE.search(bio)
    if not m:
        return None
    digits = re.sub(r"\D", "", m.group(1))
    return m.group(1).strip() if len(digits) >= 9 else None


# 兼容旧名
_extract_whatsapp = extract_whatsapp


def normalize_lead(raw):
    """把 READ_JS 解析出的评论 dict 转成 leads 表行 + 评分。"""
    lead = {
        "username": raw.get("user"),
        "uid": raw.get("uid"),
        "nickname": raw.get("nickname"),
        "region": raw.get("region"),
        "language": raw.get("language"),
        "comment_text": raw.get("text"),
        "comment_id": raw.get("cid"),
        "followers": raw.get("followers") or 0,
        "following_count": raw.get("following_count") or 0,
        "bio": raw.get("bio"),
    }
    lead["whatsapp"] = extract_whatsapp(lead["bio"])
    lead["intent_score"] = score_lead({
        "comment_text": lead["comment_text"], "bio": lead["bio"],
        "followers": lead["followers"], "aweme_count": raw.get("aweme_count") or 0})
    return lead


def harvest(video_url, tab_index=0, nav_wait=12, open_timeout=24):
    """采集视频评论。返回 {video_url, canonical_url, status_code, count, leads:[lead]}。

    leads 元素为 normalize_lead 后的 dict（未入库）。
    """
    canonical, author = parse_video_url(video_url)
    c = CDP(tab_index)
    try:
        c.eval(HOOK_JS)
        c.nav(canonical, wait=nav_wait)
        # 重新注入：导航后 JS 环境被重置
        c.eval(HOOK_JS)
        # 点评论数按钮开面板
        clicked = None
        for _ in range(open_timeout // 3):
            clicked = c.eval(CLICK_COMMENTS_JS)
            if clicked:
                break
            time.sleep(3)
        if not clicked:
            return {"video_url": video_url, "canonical_url": canonical, "error": "comment_button_not_found"}
        time.sleep(8)  # 等 /api/comment/list 请求发出并被拦截
        raw = c.eval(READ_JS)
        if not raw or isinstance(raw, dict):  # dict 即 {"__error__":...}
            return {"video_url": video_url, "canonical_url": canonical,
                    "error": f"no_captures: {raw}"}
        data = json.loads(raw)
        leads = [normalize_lead(r) for r in data["list"] if r.get("user")]
        return {"video_url": video_url, "canonical_url": canonical, "author": author,
                "status_code": data.get("status"), "has_more": data.get("has_more"),
                "cursor": data.get("cursor"), "count": len(leads), "leads": leads}
    finally:
        try:
            c.ws.close()
        except Exception:
            pass


def import_leads(db, video_url, leads):
    """入库：video 不存在则创建（url 规范化），leads 按 username upsert + 打分 + 更新 last_scanned_at。

    返回 {video_id, inserted, updated}。
    """
    canonical, author = parse_video_url(video_url)
    video_id, _ = db.videos.get_or_create(canonical, author_username=author)
    inserted = updated = 0
    for lead in leads:
        lead = dict(lead)
        lead["source_video_id"] = video_id
        _, created = db.leads.upsert(lead)
        if created:
            inserted += 1
        else:
            updated += 1
    db.videos.touch_scanned(video_id)
    return {"video_id": video_id, "inserted": inserted, "updated": updated}
