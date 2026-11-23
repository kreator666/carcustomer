# TikTok 网页版结构备忘（2026-11-23 验证，class 含哈希会过期，找特征不抄全名）

## 视频页评论

- 评论区容器：`div[class*=DivCommentMain]`；评论项：`div[class*=DivCommentItemWrapper]`（用户链接 `a[href="/@username"]`）。
- 评论按钮：动作栏 `div[class*=ButtonActionItemV1]`，innerText 是评论数；第一个匹配即目标视频。
- 打开评论后面板若空：等 5-8s；确认点在视频自己的评论按钮上而不是推荐流的。

## 评论回复（Draft.js 编辑器）

- 点评论项内叶子文本"回复"的按钮 → 项下方内联编辑器 `DivTextInputWithPostContainer`。
- 编辑器是 `div[contenteditable=true]`（Draft.js，class 含 DraftEditor）。
- **直接 innerText 赋值无效**：显示有字但 Draft 状态为空，发布按钮 `[data-e2e=comment-reply-post]` 保持 disabled。
- 正确注入：`ce.focus()` → `dispatchEvent(new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true}))`，dt 为 `new DataTransfer()` 并 `setData('text/plain', text)`。
- 等按钮 `disabled=false` 再 click。成功标志：拦截到 `/api/comment/publish/` 或 `/api/comment/reply/` 200 且 `status_msg=="Comment sent successfully"`。
- 删除自己评论：评论行 `div[class*=DivMoreTriggerWrapper]` → 菜单"删除"→ 对话框粉色"删除"按钮（注意对话框出现有延迟，点太快会点到旧元素）。

## 关注

- 主页 `/@username` 加载 10s 后：粉色关注按钮在固定位置（1280x665 视口、DSF=2）：CSS 坐标 **(525,139)**。
- 选择器 `[data-e2e=follow-button]` 当前版本不存在；按钮文本在子节点，leaf 搜索找不到。
- 验证：页面文本出现"已关注"。
- 点击前用 `window.devicePixelRatio` + 截图尺寸换算：CSS = 设备像素 / dpr。

## 私信

- 主页点"消息"按钮 CSS **(621,137)** → URL 变 `/messages` → 右栏出现会话（等 10-15s，页面文本含对方 @username）。
- 输入框 CSS **(832,633)**；先点击聚焦，再 `Input.insertText`（CDP 原生输入事件，Draft/slate 都认）。
- 输入后右下角出现发送按钮（纸飞机）CSS **(1247,633)**。
- 发送后检查页面文本：含"无法发送"或"违反《社区自律公约》" = 被风控拦（新号必现）。
- 若后续开放，首条消息要短；含链接/长报价词易触发内容过滤。

## 数据采集（签名绕过）

- 直接 `fetch('/api/comment/list/?aweme_id=...')` → `status_code:5`（要 X-Bogus/a_bogus/msToken）。
- `window.byted_acrawler.frontierSign({url})` 能拿 X-Bogus，但只有它不够。
- 正解：注入 fetch 拦截器（把 `/api/comment/list` 响应存 `window.__caps`）→ 点评论按钮让页面自己请求 → 读 `__caps[0].j`。
- 返回体：comments[].user{unique_id,uid,nickname,region,language,followers,aweme_count,signature} + text + cid + reply_comment_total；has_more/cursor 分页。
- aweme_id 就是视频 URL 最后一段数字。

## 会话/连接

- CDP：`http://localhost:9222/json` 列标签页；每个标签页有独立 webSocketDebuggerUrl。
- 页面导航会清掉注入的 window 钩子——拦截器要在最终页面加载完后注入。
- `Runtime.evaluate` 返回循环引用/不可序列化对象会得到 {"__error__":"Uncaught"}；大对象先在页面内 JSON.stringify 再取出。
