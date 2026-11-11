<#
  Persistent keeper for the Control Plane app stack (backend :8010 + public tunnel
  + Telegram bot). Runs as the CryptoAIDeskApp scheduled task so the Mini App
  survives session-end + reboot - exactly like the trading monitor.

  Every 60s it health-checks the stack; if ANY component is down it runs the
  idempotent launch_robust.ps1 (rebuilds backend+tunnel+bot). Steady-state
  (healthy) it just sleeps. The tunnel is considered up if EITHER ngrok.exe
  (stable domain) OR cloudflared.exe (quick-tunnel) is running - process-based,
  so a transient internet/530 blip does NOT trigger a needless full restart
  (ngrok/cloudflared reconnect on their own).

  Also: every cycle it re-asserts the Telegram menu button to the CURRENT
  MINI_APP_URL in .env. The free cloudflared quick-tunnel URL rotates on each
  reconnect; if launch_robust's own setChatMenuButton call failed during an
  internet blip, the menu button would point at a dead URL. This self-heal keeps
  the menu button correct within <=60s, so "open via the bot menu button" stays
  reliable. Best-effort; errors are swallowed.

  Operational only - NEVER touches trading logic / scoring / TP-SL / routing /
  live execution.
#>
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
$here = $PSScriptRoot
$launch = Join-Path $here 'launch_robust.ps1'
$envFile = Join-Path (Split-Path $here -Parent) '.env'

function Get-EnvVal($name) {
  try {
    $line = Get-Content $envFile -Encoding UTF8 -ErrorAction Stop | Where-Object { $_ -match "^$name=" } | Select-Object -First 1
    if ($line) { return ($line -split '=', 2)[1].Trim() }
  } catch { }
  return $null
}

function Test-StackHealthy {
  try {
    $h = (Invoke-WebRequest 'http://127.0.0.1:8010/api/health' -UseBasicParsing -TimeoutSec 6).StatusCode
    if ($h -ne 200) { return $false }
  } catch { return $false }
  $bot = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
          Where-Object { $_.CommandLine -match 'bot[\\/]bot\.py' } | Measure-Object).Count
  # tunnel up if EITHER the stable ngrok agent OR the cloudflared quick-tunnel is running
  $ng  = (Get-CimInstance Win32_Process -Filter "Name='ngrok.exe'" -ErrorAction SilentlyContinue |
          Measure-Object).Count
  $cf  = (Get-CimInstance Win32_Process -Filter "Name='cloudflared.exe'" -ErrorAction SilentlyContinue |
          Measure-Object).Count
  return ($bot -ge 1 -and ($ng -ge 1 -or $cf -ge 1))
}

function Get-BuildDrift {
  # Returns $true if the SERVED ui build_id (from /api/health) differs from the EXPECTED build_id
  # (frontend/dist/build_info.json on disk) — i.e. a stale backend process is serving an old bundle.
  try {
    $expectPath = Join-Path (Split-Path $here -Parent) 'frontend\dist\build_info.json'
    if (-not (Test-Path $expectPath)) { return $false }
    $expect = (Get-Content $expectPath -Raw | ConvertFrom-Json).build_id
    $served = (Invoke-WebRequest 'http://127.0.0.1:8010/api/health' -UseBasicParsing -TimeoutSec 6).Content | ConvertFrom-Json
    if ($expect -and $served.ui_build_id -and ($served.ui_build_id -ne $expect)) { return $true }
  } catch { }
  return $false
}

function Write-RestartReason($reason) {
  try {
    $p = Join-Path $here 'keeper_last_restart.json'
    @{ reason = $reason; at = (Get-Date).ToUniversalTime().ToString('o') } | ConvertTo-Json -Compress | Set-Content -Path $p -Encoding utf8
  } catch { }
}

function Sync-MenuButton {
  $u = Get-EnvVal 'MINI_APP_URL'
  $tok = Get-EnvVal 'TELEGRAM_BOT_TOKEN'
  if (-not $u -or -not $tok) { return }
  try {
    $body = @{ menu_button = @{ type = 'web_app'; text = 'Open Trading Desk'; web_app = @{ url = $u } } } | ConvertTo-Json -Depth 6 -Compress
    Invoke-RestMethod -Method Post -Uri "https://api.telegram.org/bot$tok/setChatMenuButton" -ContentType 'application/json' -Body $body -TimeoutSec 12 | Out-Null
  } catch { }
}

while ($true) {
  $reason = $null
  if (-not (Test-StackHealthy)) { $reason = 'health_fail' }
  elseif (Get-BuildDrift)       { $reason = 'build_id_drift' }   # stale backend serving old bundle
  if ($reason) {
    Write-RestartReason $reason
    & powershell -NoProfile -ExecutionPolicy Bypass -File $launch | Out-Null
  }
  Sync-MenuButton
  Start-Sleep -Seconds 60
}
