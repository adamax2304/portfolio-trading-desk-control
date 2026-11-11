# Type-check + production build of the frontend (outputs frontend/dist).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $root "frontend")
if (-not (Test-Path "node_modules")) { npm install }
npm run build
Write-Host "Built -> frontend/dist"
