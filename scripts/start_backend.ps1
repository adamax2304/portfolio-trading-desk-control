# Start the Control Plane backend (FastAPI). Loads ../.env if present.
# Usage:  ./scripts/start_backend.ps1            (uses .env / safe defaults)
#         $env:DEMO_MODE=1; ./scripts/start_backend.ps1   (force demo)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

# load .env (KEY=VALUE; inline "# comment" stripped; blanks skipped so config defaults apply)
$envFile = Join-Path $root ".env"
if (Test-Path $envFile) {
  Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
      $name = $matches[1].Trim()
      $val  = ($matches[2] -replace '\s+#.*$', '').Trim()
      if ($val -ne '') { [Environment]::SetEnvironmentVariable($name, $val) }
    }
  }
  Write-Host "Loaded .env"
}

Set-Location (Join-Path $root "backend")
Write-Host "Backend -> http://127.0.0.1:8010  (APP_ENV=$($env:APP_ENV)  DEMO_MODE=$($env:DEMO_MODE))"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
