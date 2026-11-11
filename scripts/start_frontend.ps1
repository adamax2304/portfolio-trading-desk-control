# Start the frontend dev server (Vite). Proxies /api -> 127.0.0.1:8010.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $root "frontend")
if (-not (Test-Path "node_modules")) { npm install }
Write-Host "Frontend dev -> http://localhost:5173"
npm run dev
