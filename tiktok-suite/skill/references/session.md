# 登录态获取的踩坑记录（2026-11 验证）

## 唯一可靠路径：克隆 Chrome + 人工登录

```bash
# 1. 全新 profile 目录启动真 Chrome（带调试端口）
chrome.exe --user-data-dir=C:\Users\tiger\tiktok-chrome-profile \
  --remote-debugging-port=9222 --remote-allow-origins=* \
  --no-first-run --no-default-browser-check --start-maximized
# 2. 用户在这个窗口手动登录 TikTok（Google/Facebook 第三方均可）
# 3. ttkitc session status 确认 sessionid 存在
```

- 用户原有的 Chrome 不受影响，两个 Chrome 可同时开。
- 会话 cookie 约 30 天有效，过期重复上述流程。
- 登录后**不要**关这个 Chrome（关了就再启动即可，登录态在 profile 里）。

## 已证伪的路径（不要重试）

| 路径 | 结果 |
|---|---|
| Google OAuth 在内嵌自动化浏览器（agent 面板浏览器） | Google 返回"此浏览器或应用可能不安全"，硬拒（基于指纹，与凭据无关） |
| Facebook OAuth 同上 | 登录 POST 静默挂起，按钮永远转圈，无报错 |
| TikTok 邮箱密码登录 | 该账号纯第三方登录创建，无密码；重置密码/改密码入口不存在（未绑定邮箱手机时） |
| 复制 Chrome Cookies 文件到新 profile | Chrome 157 App-Bound 加密，复制后 Cookie 被静默丢弃（0 cookie） |
| 程序模拟 Google 登录（requests） | v3 登录页纯 JS+RPC 签名，POST 405，非浏览器不可行 |
| 手机扫码 | 用户环境装不了 TikTok App |
| 解密 Chrome Cookies（DPAPI/App-Bound） | Chrome 157 需管理员权限把程序放进 Chrome 安装目录调系统服务，无管理员不可行 |

## 技术要点

- CDP 连接必须 `--remote-allow-origins=*`，否则 websocket 握手 403。
- Chrome 136+ 默认 profile 禁止 remote debugging，所以必须用独立 --user-data-dir。
- 检查登录态：`Network.getAllCookies` 里找 host 含 tiktok、name=sessionid 的 cookie。
