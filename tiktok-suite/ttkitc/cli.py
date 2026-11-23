"""ttkitc 命令行入口。

Windows 注意：跑 `ttkitc` 前建议 set PYTHONIOENCODING=utf-8，避免中文输出乱码。
"""

import argparse
import json
import sys

from .db import Database
from . import session as chrome_session
from . import engage as engage_mod
from . import guard as guard_mod
from .harvest import harvest as do_harvest, import_leads


def out(data, as_json=False, human=None):
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=1))
    elif human is not None:
        print(human)
    elif isinstance(data, (dict, list)):
        print(json.dumps(data, ensure_ascii=False, indent=1))


def get_db():
    return Database()


# ---------- db ----------

def cmd_db_init(args):
    db = get_db()  # Database() 即自动建表
    out({"db_url": db.url, "initialized": True}, args.json, f"已初始化: {db.url}")


# ---------- session ----------

def cmd_session_status(args):
    st = chrome_session.status(get_db())
    out(st, args.json,
        f"running={st['running']} logged_in={st['logged_in']} cookies={st['cookies_count']}")


def cmd_session_launch(args):
    launched = chrome_session.launch(get_db())
    out({"launched": launched}, args.json,
        "已新启动克隆 Chrome" if launched else "Chrome 已在运行（9222）")


# ---------- harvest / scan ----------

def cmd_harvest(args):
    db = get_db()
    r = do_harvest(args.video_url)
    if "error" in r:
        out(r, args.json, f"采集失败: {r['error']}")
        return 1
    human = f"抓到 {r['count']} 条评论（status_code={r.get('status_code')}）"
    if args.import_:
        res = import_leads(db, r["canonical_url"], r["leads"])
        human += f"，新增 {res['inserted']}，更新 {res['updated']}"
        r.update(res)
    out(r, args.json, human)
    return 0


def cmd_scan(args):
    db = get_db()
    videos = db.videos.monitored()
    if not videos:
        print("没有 monitor=1 的视频（可用 ttkitc serve 的 PATCH /api/videos/{id} 或先 harvest --import）")
        return 0
    for v in videos:
        r = do_harvest(v["url"])
        if "error" in r:
            print(f"[{v['url']}] 采集失败: {r['error']}")
            continue
        res = import_leads(db, r["canonical_url"], r["leads"])
        print(f"[{v['url']}] 新增线索 {res['inserted']}，更新 {res['updated']}（共抓到 {r['count']} 条评论）")
    return 0


# ---------- leads ----------

def cmd_leads_list(args):
    db = get_db()
    r = db.leads.search(q=args.q, status=args.status, limit=args.limit)
    if args.json:
        out(r, True)
    else:
        print(f"共 {r['total']} 条：")
        for l in r["items"]:
            print(f"  #{l['id']} @{l['username']} [{l['status']}] score={l['intent_score']} "
                  f"{(l['comment_text'] or '')[:40]}")


def cmd_leads_show(args):
    db = get_db()
    lead = db.leads.get_by_username(args.username.lstrip("@"))
    if not lead:
        print(f"未找到 @{args.username}")
        return 1
    lead["interactions"] = db.interactions.list(lead_id=lead["id"], limit=50)
    out(lead, args.json)
    return 0


def cmd_leads_update(args):
    db = get_db()
    lead = db.leads.get_by_username(args.username.lstrip("@"))
    if not lead:
        print(f"未找到 @{args.username}")
        return 1
    lead = db.leads.update(lead["id"], status=args.status, notes=args.notes,
                           intent_score=args.score)
    out(lead, args.json, f"已更新 @{lead['username']} status={lead['status']}")


def cmd_leads_enrich(args):
    from .enrich import enrich_user, enrich_all_new
    db = get_db()
    if not args.all_new and not args.username:
        print("用法: ttkitc leads enrich <username> | ttkitc leads enrich --all-new")
        return 1
    if args.all_new:
        r = enrich_all_new(db, sleep_secs=5)
        if args.json:
            out(r, True)
        else:
            print(f"共处理 {r['total']} 个线索：")
            for x in r["results"]:
                if "error" in x:
                    print(f"  @{x['username']}: 失败 {x['error']}")
                else:
                    a = x["after"]
                    print(f"  @{x['username']}: region={a['region']} lang={a['language']} "
                          f"followers={a['followers']} score={a['intent_score']} "
                          f"whatsapp={a['whatsapp']}")
        return 0
    r = enrich_user(db, args.username.lstrip("@"))
    if "error" in r:
        out(r, args.json, f"enrich 失败: {r['error']}")
        return 1
    a, b = r["after"], r["before"]
    out(r, args.json,
        f"@{r['username']}: region {b['region']!r}->{a['region']!r} "
        f"lang {b['language']!r}->{a['language']!r} "
        f"followers {b['followers']}->{a['followers']} "
        f"score {b['intent_score']}->{a['intent_score']} whatsapp={a['whatsapp']}")
    return 0


# ---------- engage ----------

def _engage_common(args, action):
    db = get_db()
    text = args.text
    if text is None and args.template is not None:
        tpl = db.templates.get(args.template)
        if not tpl:
            print(f"模板 #{args.template} 不存在")
            return 1
        text = tpl["body"]
    if action == "dm" and not db.settings.get_bool("dm_enabled", False):
        result = {"status": "blocked", "platform_msg": "dm_disabled"}
    else:
        limit_hit = guard_mod.check_daily_limit(db, action)
        if limit_hit:
            result = limit_hit
        else:
            guard_mod.cooldown(db, enabled=not args.no_cooldown)
            if action == "reply":
                if text is None:
                    print("reply 需要 --text 或 --template")
                    return 1
                result = engage_mod.reply(args.video, args.username.lstrip("@"), text)
            elif action == "follow":
                result = engage_mod.follow(args.username.lstrip("@"))
            else:
                if text is None:
                    print("dm 需要 --text 或 --template")
                    return 1
                result = engage_mod.dm(args.username.lstrip("@"), text, db=db)
    engage_mod.record_interaction(db, args.username.lstrip("@"), action, text or "", result)
    out(result, args.json,
        f"{action} @{args.username}: {result['status']} ({result['platform_msg']})")
    return 0 if result["status"] == "success" else 1


def cmd_reply(args):
    return _engage_common(args, "reply")


def cmd_follow(args):
    return _engage_common(args, "follow")


def cmd_dm(args):
    return _engage_common(args, "dm")


# ---------- templates ----------

def cmd_templates_list(args):
    db = get_db()
    items = db.templates.list(lang=args.lang, action_type=args.action_type,
                              include_inactive=True)
    if args.json:
        out(items, True)
    else:
        for t in items:
            print(f"  #{t['id']} [{t['lang']}/{t['action_type']}] {t['name']} "
                  f"({'on' if t['active'] else 'off'}) {(t['body'] or '')[:30]}")


def cmd_templates_add(args):
    db = get_db()
    tid = db.templates.add(args.lang, args.action_type, args.name, args.body)
    out({"id": tid}, args.json, f"已添加模板 #{tid}")


def cmd_templates_disable(args):
    db = get_db()
    db.templates.set_active(args.id, False)
    out({"id": args.id, "active": 0}, args.json, f"已禁用模板 #{args.id}")


# ---------- serve ----------

def cmd_serve(args):
    from .server import run
    print(f"FastAPI 监听 127.0.0.1:{args.port}")
    run(port=args.port)


def build_parser():
    p = argparse.ArgumentParser(prog="ttkitc", description="TikTok 获客套件 CLI")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("db", help="数据库")
    ssub = sp.add_subparsers(dest="sub", required=True)
    ssub.add_parser("init", help="初始化建表").set_defaults(func=cmd_db_init)

    sp = sub.add_parser("session", help="克隆 Chrome 会话")
    ssub = sp.add_subparsers(dest="sub", required=True)
    ssub.add_parser("status", help="浏览器/登录态检查").set_defaults(func=cmd_session_status)
    ssub.add_parser("launch", help="启动克隆 Chrome").set_defaults(func=cmd_session_launch)

    sp = sub.add_parser("harvest", help="采集视频评论")
    sp.add_argument("video_url")
    sp.add_argument("--import", dest="import_", action="store_true", help="入库")
    sp.set_defaults(func=cmd_harvest)

    sp = sub.add_parser("scan", help="扫描所有 monitor=1 视频并入库")
    sp.set_defaults(func=cmd_scan)

    sp = sub.add_parser("leads", help="线索")
    ssub = sp.add_subparsers(dest="sub", required=True)
    s = ssub.add_parser("list")
    s.add_argument("--status")
    s.add_argument("--q")
    s.add_argument("--limit", type=int, default=200)
    s.set_defaults(func=cmd_leads_list)
    s = ssub.add_parser("show")
    s.add_argument("username")
    s.set_defaults(func=cmd_leads_show)
    s = ssub.add_parser("update")
    s.add_argument("username")
    s.add_argument("--status")
    s.add_argument("--notes")
    s.add_argument("--score", type=int, default=None)
    s.set_defaults(func=cmd_leads_update)
    s = ssub.add_parser("enrich", help="访问主页抓 /api/user/detail 补全线索信息")
    s.add_argument("username", nargs="?", help="单个 username（与 --all-new 二选一）")
    s.add_argument("--all-new", action="store_true", help="对所有 new 且 region 为空的 lead 逐个 enrich")
    s.set_defaults(func=cmd_leads_enrich)

    sp = sub.add_parser("engage", help="执行动作")
    sp.add_argument("--no-cooldown", action="store_true", help="跳过动作间隔")
    ssub = sp.add_subparsers(dest="sub", required=True)
    for name, fn, need_text in (("reply", cmd_reply, True), ("follow", cmd_follow, False), ("dm", cmd_dm, True)):
        s = ssub.add_parser(name)
        s.add_argument("username")
        s.add_argument("--video", help="reply 时指定视频链接")
        s.add_argument("--text")
        s.add_argument("--template", type=int, help="用模板 ID 作为文案")
        s.set_defaults(func=fn)

    sp = sub.add_parser("templates", help="话术模板")
    ssub = sp.add_subparsers(dest="sub", required=True)
    s = ssub.add_parser("list")
    s.add_argument("--lang")
    s.add_argument("--action-type", dest="action_type", choices=["reply", "follow", "dm"])
    s.set_defaults(func=cmd_templates_list)
    s = ssub.add_parser("add")
    s.add_argument("--lang", required=True)
    s.add_argument("--action-type", dest="action_type", required=True, choices=["reply", "follow", "dm"])
    s.add_argument("--name", required=True)
    s.add_argument("--body", required=True)
    s.set_defaults(func=cmd_templates_add)
    s = ssub.add_parser("disable")
    s.add_argument("id", type=int)
    s.set_defaults(func=cmd_templates_disable)

    sp = sub.add_parser("serve", help="起 FastAPI 服务")
    sp.add_argument("--port", type=int, default=8790)
    sp.set_defaults(func=cmd_serve)

    return p


def main(argv=None):
    argv = list(argv or sys.argv[1:])
    # --json 允许放在子命令后面：预扫描并从参数里剔除
    force_json = False
    if "--json" in argv:
        argv.remove("--json")
        force_json = True
    args = build_parser().parse_args(argv)
    if force_json:
        args.json = True
    try:
        return args.func(args) or 0
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
