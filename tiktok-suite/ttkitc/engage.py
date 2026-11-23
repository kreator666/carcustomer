"""三个原子动作：reply / follow / dm。

每个动作返回 {status: success|blocked|error, platform_msg}；上层（cli/server）负责
写 interactions 表（这里提供 record_interaction 辅助）。

平台 quirks（2026-11 验证）：
- 评论回复：直接改 innerText 无效（Draft.js 状态不同步，发送按钮不亮），必须用
  ClipboardEvent('paste') + DataTransfer 注入。
- 回复结果确认靠注入 fetch 拦截 /api/comment/publish|reply，看 status_msg
  是否为 "Comment sent successfully"。
- follow：新版主页没有 [data-e2e=follow-button]，实测有效的是坐标点击；
  选择器方式仅作 fallback 尝试。
- dm：新账号对陌生人私信全被平台拦（连 "Hi" 都发不出），表现为发送后页面出现
  "无法发送"/"违反" 字样——此 blocked 状态要原样上报，不要重试风暴。
- 所有坐标点击前必须确认视口 1280x665（window.innerWidth/Height），
  不一致时按比例缩放：CSS 坐标 = 基准坐标 * 实际视口 / 基准视口。
"""

import json
import os
import time

from .cdp import CDP, Input, Tab, list_tabs, screenshot

# ---- 基准视口与坐标（2026-11 验证，1280x665 CSS 视口，DSF=2 实测）----
BASE_VIEWPORT = (1280, 665)
FOLLOW_BTN_XY = (525, 139)     # 主页「关注」按钮
DM_MSG_BTN_XY = (621, 137)     # 主页「消息」按钮
DM_INPUT_XY = (832, 633)       # 会话输入框
DM_SEND_XY = (1247, 633)       # 发送按钮

# 选择器（2026-11 验证；失效时优先检查这里）
SEL_FOLLOW_BTN = '[data-e2e="follow-button"]'      # 新版主页已无，仅 fallback
SEL_REPLY_POST_BTN = '[data-e2e="comment-reply-post"]'
SEL_CONTENTEDITABLE = 'div[contenteditable=true]'
SEL_COMMENT_MAIN = 'div[class*=DivCommentMain]'
SEL_COMMENT_ITEM = 'div[class*=DivCommentItemWrapper]'

SHOT_DIR = os.path.join(os.path.expanduser("~"), ".ttkitc", "shots")
os.makedirs(SHOT_DIR, exist_ok=True)

# 注入 reply 结果的 fetch 拦截（在视频页导航前注入）
HOOK_PUBLISH_JS = """(()=>{
  window.__cap2=[];
  if(!window.__hooked2){
    window.__hooked2=true;
    const of=window.fetch;
    window.fetch=function(...a){
      const u=String(a[0]&&a[0].url||a[0]);
      return of.apply(this,a).then(async resp=>{
        if(/comment\\/(publish|reply)\\/|im\\/send/.test(u)){
          try{ window.__cap2.push({u:u.slice(0,150), code:resp.status, j:await resp.clone().json()}); }
          catch(e){ window.__cap2.push({u:u.slice(0,150), code:resp.status, raw:'parse-fail'}); }
        }
        return resp;
      });
    };
  }
  return 'ok';
})()"""

# 内联回复：找评论项 → 点「回复」→ paste 注入 → 等发送按钮可用 → 点击
REPLY_JS = """(async(uname, text)=>{
  const main=[...document.querySelectorAll('div')].find(e=>String(e.className).includes('DivCommentMain'));
  if(!main) return 'ERR:no-main';
  const item=[...main.querySelectorAll('div[class*=DivCommentItemWrapper]')].find(w=>w.querySelector('a[href="/@'+uname+'"]'));
  if(!item) return 'ERR:no-item';
  const rb=[...item.querySelectorAll('*')].filter(e=>e.children.length===0&&e.innerText==='\\u56de\\u590d');
  if(!rb.length) return 'ERR:no-reply-btn';
  rb[0].click();
  await new Promise(r=>setTimeout(r,1200));
  const ce=document.querySelector('div[contenteditable=true]');
  if(!ce) return 'ERR:no-editor';
  ce.focus();
  const dt=new DataTransfer();
  dt.setData('text/plain', text);
  ce.dispatchEvent(new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true}));
  await new Promise(r=>setTimeout(r,800));
  const b=document.querySelector('[data-e2e=comment-reply-post]');
  if(!b) return 'ERR:no-post';
  if(b.disabled) return 'ERR:disabled';
  b.click();
  return 'OK posted';
})()"""

CHECK_REPLY_JS = """(()=>{
  const caps=(window.__cap2||[]).filter(c=>/comment\\/(publish|reply)\\//.test(c.u||''));
  if(!caps.length) return null;
  const c=caps[caps.length-1];
  return JSON.stringify({code:c.code, status_msg:c.j&&c.j.status_msg});
})()"""

FOLLOW_STATE_JS = """(()=>{
  const t=document.body.innerText;
  const hasFollowed=/已关注|Following|Friends|好友/.test(t);
  const btn=[...document.querySelectorAll('button')].find(e=>/^(关注|Follow)$/.test((e.innerText||'').trim()));
  return JSON.stringify({has_followed:hasFollowed, standalone_follow_btn:!!btn});
})()"""


def _ok(status, msg):
    return {"status": status, "platform_msg": msg}


def record_interaction(db, username, action_type, content, result):
    """写 interactions 表并按需更新 lead 状态/last_interaction_at。返回 lead_id（或 None）。"""
    lead = db.leads.get_by_username(username) if db else None
    lead_id = lead["id"] if lead else None
    if lead is None and db is not None:
        # CLI 直接对陌生人动作时兜底建一条 lead
        lead_id, _ = db.leads.upsert({"username": username})
    if db is not None and lead_id is not None:
        db.interactions.add(lead_id, action_type, content,
                            result.get("status"), result.get("platform_msg", ""))
        if result.get("status") == "success":
            db.leads.touch(lead_id)
            status_map = {"reply": "replied", "follow": "followed", "dm": "contacted"}
            cur = db.leads.get(lead_id)
            if cur and cur.get("status") == "new":
                db.leads.update(lead_id, status=status_map.get(action_type, cur["status"]))
    return lead_id


def _viewport_scale(c):
    """实测视口，返回 (scale_x, scale_y) 相对基准 1280x665。"""
    r = c.eval("JSON.stringify({w:window.innerWidth,h:window.innerHeight,dpr:window.devicePixelRatio})")
    try:
        v = json.loads(r)
        return v["w"] / BASE_VIEWPORT[0], v["h"] / BASE_VIEWPORT[1], v.get("dpr", 1)
    except Exception:
        return 1.0, 1.0, 1


def _scaled_click(c, x, y):
    sx, sy, _ = _viewport_scale(c)
    Input.click(c, round(x * sx), round(y * sy))


def reply(video_url, username, text, open_timeout=24):
    """在视频页对指定用户的评论做内联回复。

    流程：连视频标签页 → 注入拦截 →（不在视频页则导航）→ 开评论面板 →
    内联回复 → 拦截确认 status_msg。video_url 可为 None（用当前第一个标签页）。
    """
    c = None
    try:
        if video_url:
            from .harvest import parse_video_url
            canonical, _ = parse_video_url(video_url)
            c = CDP.connect_url(canonical) or CDP.connect_url("tiktok.com")
            if c is None:
                pages = list_tabs()
                if not pages:
                    return _ok("error", "no_tab")
                c = CDP(0)
            c.eval(HOOK_PUBLISH_JS)
            c.nav(canonical, wait=10)
        else:
            c = CDP(0)
            c.eval(HOOK_PUBLISH_JS)
        # 开评论面板（评论数按钮；按 data-e2e=comment-icon 锁定，勿按数字文本，会误点点赞）
        clicked = None
        for _ in range(open_timeout // 3):
            clicked = c.eval(
                """(()=>{const b=[...document.querySelectorAll('div[class*=ButtonActionItemV1]')]
                    .find(e=>e.getAttribute('data-e2e')==='comment-icon'||/评论|Read or add/i.test(e.getAttribute('aria-label')||''));
                    if(!b) return null; b.click(); return (b.innerText||'').trim();})()""")
            if clicked:
                break
            time.sleep(3)
        if not clicked:
            return _ok("error", "comment_button_not_found")
        time.sleep(5)
        # REPLY_JS 是 async 箭头函数表达式，直接调用即可（eval 已开 awaitPromise）
        r = c.eval(f"({REPLY_JS})({json.dumps(username)}, {json.dumps(text)})")
        if not isinstance(r, str) or not r.startswith("OK"):
            return _ok("error", f"reply_flow: {r}")
        # 等拦截结果
        for _ in range(10):
            time.sleep(1)
            raw = c.eval(CHECK_REPLY_JS)
            if raw:
                break
        if not raw:
            return _ok("error", "no_publish_capture")
        cap = json.loads(raw)
        if cap.get("status_msg") == "Comment sent successfully":
            return _ok("success", cap["status_msg"])
        return _ok("error", f"publish_rejected: {cap.get('status_msg') or cap.get('code')}")
    except Exception as e:
        return _ok("error", f"exception: {e}")
    finally:
        if c is not None:
            try:
                c.ws.close()
            except Exception:
                pass


def follow(username):
    """关注用户：新建标签页 → 截图 → 坐标点击关注（选择器 fallback）→ DOM 判定。"""
    t = None
    try:
        t = Tab(f"https://www.tiktok.com/@{username}")
        time.sleep(10)
        screenshot(t, os.path.join(SHOT_DIR, f"follow_{username}_before.png"))
        # fallback：先试选择器（已知新版页面没有，保留作兜底）
        sel = t.eval(
            """(()=>{const b=document.querySelector('[data-e2e=follow-button]');
                if(b){b.click(); return 'selector';} return null;})()""")
        if not sel:
            _scaled_click(t, *FOLLOW_BTN_XY)
        time.sleep(4)
        screenshot(t, os.path.join(SHOT_DIR, f"follow_{username}_after.png"))
        raw = t.eval(FOLLOW_STATE_JS)
        st = json.loads(raw) if raw else {}
        # 判定：页面文本含「已关注」且不再单独出现「关注」按钮文本
        if st.get("has_followed") and not st.get("standalone_follow_btn"):
            return _ok("success", "followed")
        if st.get("has_followed"):
            return _ok("success", "followed_maybe")
        return _ok("blocked", f"state_unclear: {raw}")
    except Exception as e:
        return _ok("error", f"exception: {e}")
    finally:
        if t is not None:
            t.close()


def dm(username, text, db=None):
    """私信用户。settings.dm_enabled=false 时直接 blocked('dm_disabled')。"""
    if db is not None and not db.settings.get_bool("dm_enabled", False):
        return _ok("blocked", "dm_disabled")
    t = None
    try:
        t = Tab(f"https://www.tiktok.com/@{username}")
        time.sleep(10)
        _scaled_click(t, *DM_MSG_BTN_XY)      # 点「消息」
        time.sleep(12)
        # 等会话出现：页面文本含目标 username
        appeared = False
        for _ in range(6):
            body = t.eval("document.body.innerText.slice(-500)")
            if isinstance(body, str) and username.lower() in body.lower():
                appeared = True
                break
            time.sleep(2)
        if not appeared:
            return _ok("blocked", "conversation_not_opened")
        _scaled_click(t, *DM_INPUT_XY)        # 点输入框
        time.sleep(1.5)
        Input.insert_text(t, text)
        time.sleep(1.5)
        _scaled_click(t, *DM_SEND_XY)         # 点发送
        time.sleep(5)
        body = t.eval("document.body.innerText.slice(-600)") or ""
        if any(k in body for k in ("无法发送", "违反")):
            return _ok("blocked", "platform_blocked")
        if text[:20] in body:
            return _ok("success", "sent")
        return _ok("error", "send_unconfirmed")
    except Exception as e:
        return _ok("error", f"exception: {e}")
    finally:
        if t is not None:
            t.close()
