# Run backend tests + frontend type-check/build.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "== backend tests ==" -ForegroundColor Cyan
Set-Location (Join-Path $root "backend")
python -m pytest tests/ -q

Write-Host "== frontend build ==" -ForegroundColor Cyan
Set-Location (Join-Path $root "frontend")
if (-not (Test-Path "node_modules")) { npm install }
npm run build
Write-Host "All checks done." -ForegroundColor Green
