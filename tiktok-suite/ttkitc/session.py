"""克隆 Chrome 会话管理。

已知事实（2026-11 验证）：
- Chrome 157 起 Cookie 使用 App-Bound 加密，直接复制 Cookies 文件到新 profile
  无法解密（Chrome 静默丢弃），所以采用「克隆 Chrome 里人工登录一次 TikTok」的方式，
  之后自动化复用该 profile 的登录态。
- Google/Facebook OAuth 登录在内嵌自动化浏览器（pyppeteer 等）会被拒，
  真 Chrome 可正常过验证——这也是必须用本机 Chrome + 独立 profile 的原因。
- 登录态判据：.tiktok.com 域名下存在 sessionid cookie。
"""

import os
import subprocess
import time

import requests

from .cdp import CDP, list_tabs

LAUNCH_ARGS = [
    "--remote-debugging-port=9222",
    "--remote-allow-origins=*",
    "--no-first-run",
    "--no-default-browser-check",
    "--start-maximized",
]


def _browser_url(db=None):
    port = 9222
    if db is not None:
        port = db.settings.get_int("browser_port", 9222)
    return f"http://localhost:{port}"


def is_running(db=None, timeout=3):
    try:
        requests.get(f"{_browser_url(db)}/json/version", timeout=timeout)
        return True
    except requests.RequestException:
        return False


def status(db=None):
    """检查克隆 Chrome：返回 {running, logged_in, cookies_count}。"""
    result = {"running": False, "logged_in": False, "cookies_count": 0}
    if not is_running(db):
        return result
    result["running"] = True
    try:
        pages = list_tabs(_browser_url(db))
        if not pages:
            return result
        c = CDP._from_target(pages[0])
        # Network.getAllCookies 拿的是浏览器级全部 cookie
        resp = c.send("Network.getAllCookies")
        cookies = resp.get("result", {}).get("cookies", [])
        result["cookies_count"] = len(cookies)
        result["logged_in"] = any(
            ck.get("name") == "sessionid" and "tiktok.com" in (ck.get("domain") or "")
            for ck in cookies)
        try:
            c.ws.close()
        except Exception:
            pass
    except Exception as e:
        result["error"] = str(e)[:200]
    return result


def launch(db=None, extra_args=None):
    """按 settings(chrome_path/profile_dir) 启动克隆 Chrome。返回是否新启动。"""
    if is_running(db):
        return False
    chrome_path = db.settings.get("chrome_path") if db else r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    profile_dir = db.settings.get("profile_dir") if db else r"C:\Users\tiger\tiktok-chrome-profile"
    args = [chrome_path, f"--user-data-dir={profile_dir}"] + LAUNCH_ARGS + (extra_args or [])
    # Windows 下后台起 Chrome，不等待
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # 等调试端口就绪
    for _ in range(30):
        if is_running(db):
            return True
        time.sleep(1)
    return True
