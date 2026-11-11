@echo off
REM Foreground keeper for the Control Plane app stack (run by the CryptoAIDeskApp
REM scheduled task, or double-click). Loops forever: keeps backend+tunnel+bot up
REM and self-heals via launch_robust.ps1. Operational only; no trading logic.
title Control Plane App Keeper
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0app_keeper.ps1"
