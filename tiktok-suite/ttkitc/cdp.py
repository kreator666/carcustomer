"""CDP (Chrome DevTools Protocol) 客户端封装。

从 drive.py / follow.py 提炼。平台无关，只负责连调试 Chrome、发命令、eval JS。

平台 quirks（TikTok，2026-11 验证）：
- eval 必须开 awaitPromise，否则 async IIFE 返回 {}。
- JS 异常经 Runtime.evaluate 的 exceptionDetails 返回，这里统一转成 {"__error__": ...}。
- 坐标点击用 Input.dispatchMouseEvent（CSS 像素坐标），不要走 el.click() 以外的
  合成事件路径——TikTok 部分按钮只认 trusted 点击。
"""

import base64
import json
import time

import requests
import websocket

DEFAULT_BROWSER = "http://localhost:9222"


def list_tabs(browser=DEFAULT_BROWSER, timeout=10):
    """列出全部 page 类型标签页（/json 端点）。"""
    info = requests.get(f"{browser}/json", timeout=timeout).json()
    return [t for t in info if t.get("type") == "page"]


class CDP:
    """连接某个已存在标签页的 CDP 客户端（对应 drive.py 的 CDP 类）。"""

    def __init__(self, tab_index=0, browser=DEFAULT_BROWSER, timeout=60):
        pages = list_tabs(browser)
        if not pages:
            raise RuntimeError(f"no page tabs on {browser}")
        self.page = pages[min(tab_index, len(pages) - 1)]
        self.ws = websocket.create_connection(self.page["webSocketDebuggerUrl"], timeout=timeout)
        self.mid = 0
        self.send("Page.enable")
        self.send("Runtime.enable")

    @classmethod
    def connect_url(cls, url_substr, browser=DEFAULT_BROWSER, timeout=60):
        """按 URL 子串找标签页并连接，找不到返回 None。"""
        for t in list_tabs(browser):
            if url_substr in (t.get("url") or ""):
                return cls._from_target(t, timeout)
        return None

    @classmethod
    def _from_target(cls, target, timeout=60):
        obj = cls.__new__(cls)
        obj.page = target
        obj.ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=timeout)
        obj.mid = 0
        obj.send("Page.enable")
        obj.send("Runtime.enable")
        return obj

    def send(self, method, params=None):
        self.mid += 1
        self.ws.send(json.dumps({"id": self.mid, "method": method, "params": params or {}}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == self.mid:
                return m

    def eval(self, expr):
        """evaluate + awaitPromise + returnByValue；JS 异常返回 {"__error__": ...}。"""
        r = self.send("Runtime.evaluate", {
            "expression": expr, "returnByValue": True, "awaitPromise": True})
        res = r.get("result", {})
        if "exceptionDetails" in res:
            return {"__error__": res["exceptionDetails"].get("text", "js error")}
        return res.get("result", {}).get("value")

    def nav(self, url, wait=8):
        self.send("Page.navigate", {"url": url})
        time.sleep(wait)

    def add_init_script(self, source):
        """Page.addScriptToEvaluateOnNewDocument：每次新文档加载前自动执行 source。

        用于在导航前注入 fetch 拦截等钩子——普通 eval 注入会被导航清掉，
        而 init script 在每个新文档（含首次加载）的页面脚本运行前执行。
        """
        return self.send("Page.addScriptToEvaluateOnNewDocument", {"source": source})


class Tab:
    """新建标签页并连接（对应 follow.py 的 Tab 类）。用完 close()。"""

    def __init__(self, url=None, browser=DEFAULT_BROWSER):
        if url:
            info = requests.put(f"{browser}/json/new?{url}", timeout=15).json()
        else:
            info = requests.get(f"{browser}/json/new", timeout=15).json()
        self.id = info["id"]
        self.ws = websocket.create_connection(info["webSocketDebuggerUrl"], timeout=60)
        self.mid = 0
        self.send("Page.enable")
        self.send("Runtime.enable")

    def send(self, method, params=None):
        self.mid += 1
        self.ws.send(json.dumps({"id": self.mid, "method": method, "params": params or {}}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == self.mid:
                return m

    def eval(self, expr):
        r = self.send("Runtime.evaluate", {
            "expression": expr, "returnByValue": True, "awaitPromise": True})
        res = r.get("result", {})
        if "exceptionDetails" in res:
            return {"__error__": str(res["exceptionDetails"])[:300]}
        return res.get("result", {}).get("value")

    def nav(self, url, wait=8):
        self.send("Page.navigate", {"url": url})
        time.sleep(wait)

    def add_init_script(self, source):
        """Page.addScriptToEvaluateOnNewDocument：每次新文档加载前自动执行 source。

        用于在导航前注入 fetch 拦截等钩子——普通 eval 注入会被导航清掉，
        而 init script 在每个新文档（含首次加载）的页面脚本运行前执行。
        """
        return self.send("Page.addScriptToEvaluateOnNewDocument", {"source": source})

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass
        try:
            requests.get(f"{DEFAULT_BROWSER}/json/close/{self.id}", timeout=10)
        except Exception:
            pass


class Input:
    """Input domain 辅助：坐标点击 / 输入文本 / 滚轮。坐标均为 CSS 像素。"""

    @staticmethod
    def click(client, x, y):
        for typ in ("mousePressed", "mouseReleased"):
            client.send("Input.dispatchMouseEvent", {
                "type": typ, "x": x, "y": y, "button": "left", "clickCount": 1})

    @staticmethod
    def insert_text(client, text):
        client.send("Input.insertText", {"text": text})

    @staticmethod
    def mouse_wheel(client, x, y, delta_y=400):
        client.send("Input.dispatchMouseEvent", {
            "type": "mouseWheel", "x": x, "y": y, "deltaX": 0, "deltaY": delta_y})


def screenshot(client, path):
    """截图存 PNG 文件，返回文件路径。"""
    r = client.send("Page.captureScreenshot", {"format": "png"})
    with open(path, "wb") as f:
        f.write(base64.b64decode(r["result"]["data"]))
    return path
