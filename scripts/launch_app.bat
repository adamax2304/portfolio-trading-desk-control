@echo off
title Trading App (Telegram Mini App)
echo ============================================================
echo  Starting the Telegram Mini App (backend + tunnel + bot)...
echo  This takes ~1 minute (detecting the public tunnel URL).
echo ============================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch_robust.ps1"
echo.
echo ============================================================
echo  Done. In Telegram open  @aitradingdesk1_bot
echo  -> tap the menu button (bottom-left) or /start -> Open Trading Desk
echo  You can close this window; the services keep running.
echo ============================================================
pause
