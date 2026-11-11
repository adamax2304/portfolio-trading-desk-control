<#
  LOCAL launcher for the Control Plane Mini App.
  Runs the FastAPI backend on 127.0.0.1:8010 (serves the built UI + /api, auth off
  for local-only use) and opens it in the default browser. NO public tunnel — works
  offline, never rotates, no Telegram needed. Idempotent: safe to double-click any
  number of times (won't start a second backend if one is already healthy).
  Operational only; never touches trading logic / live locks.
#>
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
$here = $PSScriptRoot
$root = Split-Path $here -Parent
$envFile = Join-Path $root '.env'
$url = 'http://127.0.0.1:8010'

function Test-Healthy {
  try { return (Invoke-WebRequest "$url/api/health" -UseBasicParsing -TimeoutSec 5).StatusCode -eq 200 }
  catch { return $false }
}

if (-not (Test-Healthy)) {
  # load .env so the detached backend inherits real config (DESK_DB_PATH, AUTH_DISABLED=1, ...)
  if (Test-Path $envFile) {
    Get-Content $envFile -Encoding UTF8 | ForEach-Object {
      if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
      }
    }
  }
  $py = Join-Path $root 'backend\venv\Scripts\python.exe'
  if (-not (Test-Path $py)) { $py = 'python' }
  Start-Process $py -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8010' `
    -WorkingDirectory (Join-Path $root 'backend') -WindowStyle Hidden
  for ($i = 0; $i -lt 40; $i++) { Start-Sleep -Seconds 1; if (Test-Healthy) { break } }
}

# open the app in the default browser
Start-Process $url
