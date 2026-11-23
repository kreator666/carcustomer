// TikTok Lead Suite 网关：0.0.0.0:8788
// - /api/* 反代到 FastAPI (127.0.0.1:8790)
// - 其余路径静态服务 frontend/dist，SPA fallback 到 index.html
const path = require('path');
const fs = require('fs');
const os = require('os');
const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');

const PORT = 8788;
const API_TARGET = 'http://127.0.0.1:8790';
const DIST = path.join(__dirname, '..', 'frontend', 'dist');

const app = express();

// /api 反代，后端未启动时透传 502
// 注意：不能 app.use('/api', proxy(...)) —— express 会剥掉挂载前缀，导致 FastAPI 收到 /leads 而 404。
// 用 pathFilter 自行匹配，保留完整原始路径。
app.use(createProxyMiddleware({
  target: API_TARGET,
  changeOrigin: true,
  pathFilter: '/api/**',
}));

// 静态资源 + SPA fallback
if (fs.existsSync(DIST)) {
  app.use(express.static(DIST));
  app.get(/^(?!\/api\/).*/, (req, res) => {
    res.sendFile(path.join(DIST, 'index.html'));
  });
} else {
  console.warn('[warn] 未找到 frontend/dist，请先执行 npm run build');
}

// 打印局域网 IP，方便手机访问
function lanIPs() {
  const ips = [];
  for (const [name, addrs] of Object.entries(os.networkInterfaces())) {
    for (const a of addrs || []) {
      if (a.family === 'IPv4' && !a.internal) ips.push({ iface: name, ip: a.address });
    }
  }
  return ips;
}

app.listen(PORT, '0.0.0.0', () => {
  console.log(`TikTok Suite Dashboard 已启动: http://localhost:${PORT}`);
  for (const { iface, ip } of lanIPs()) {
    console.log(`  局域网访问 (${iface}): http://${ip}:${PORT}`);
  }
  console.log(`API 反代目标: ${API_TARGET}`);
});
