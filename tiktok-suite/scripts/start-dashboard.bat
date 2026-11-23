@echo off
rem TikTok Lead Suite 一键启动 Dashboard（FastAPI 8790 + Node 网关 8788）
rem 局域网访问 http://<本机IP>:8788
cd /d D:\agent\carcustomer\tiktok-suite
set PYTHONIOENCODING=utf-8

echo [1/2] Starting FastAPI (127.0.0.1:8790) ...
start "ttkitc-api" cmd /k "ttkitc serve --port 8790"

timeout /t 3 /nobreak >nul

echo [2/2] Starting Dashboard gateway (0.0.0.0:8788) ...
start "ttkitc-web" cmd /k "cd /d D:\agent\carcustomer\tiktok-suite\web\server && node index.js"

echo.
echo Dashboard: http://localhost:8788  (phone on same Wi-Fi: use the LAN IP printed by the web window)
echo Close the two opened windows to stop.
pause
