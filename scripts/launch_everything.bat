@echo off
title Launch ALL - Trading Desk + Telegram App
echo ============================================================
echo  [1/2] Starting the Trading Desk monitor / scheduler...
echo ============================================================
call "C:\Users\adama\Documents\crypto-ai-desk\scripts\start_monitor_scheduler.bat"
echo.
echo ============================================================
echo  [2/2] Starting the Telegram Mini App (backend + tunnel + bot)...
echo  ~1 minute to detect the public tunnel URL.
echo ============================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch_robust.ps1"
echo.
echo ============================================================
echo  ALL launched.
echo  - Desk monitor: running in background (Telegram alerts).
echo  - Mini App: open @aitradingdesk1_bot in Telegram -> menu button / Open Trading Desk.
echo  You can close this window; everything keeps running.
echo ============================================================
pause
