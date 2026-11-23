@echo off
chcp 65001 >nul
title TikTok Suite Dashboard
cd /d "%~dp0server"
echo ============================================
echo   TikTok Suite Dashboard  http://localhost:8788
echo ============================================
node index.js
pause
