# ONE-COMMAND launcher for the full Telegram stack:
#   backend (:8010) + frontend (:5173) + cloudflared tunnel + bot.
# It auto-detects the public https tunnel URL, writes it into .env (MINI_APP_URL),
# then starts the bot. Open @your_bot in Telegram -> /start -> Open Trading Desk.
#
# Requires: cloudflared (winget install --id Cloudflare.cloudflared), a filled .env.
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$root = Split-Path -Parent $here
$envFile = Join-Path $root ".env"

if (-not (Test-Path $envFile)) { throw ".env not found at $envFile - copy .env.example and fill it." }

# prefer the bundled cloudflared.exe (scripts\bin), else fall back to one on PATH
$cfExe = Join-Path $here "bin\cloudflared.exe"
if (-not (Test-Path $cfExe)) {
  $onPath = Get-Command cloudflared -ErrorAction SilentlyContinue
  if ($onPath) { $cfExe = $onPath.Source }
  else { Write-Host "cloudflared not found (expected scripts\bin\cloudflared.exe)." -ForegroundColor Red; return }
}

# 1) backend in its own window
Start-Process powershell -ArgumentList "-NoExit", "-File", (Join-Path $here "start_backend.ps1")
Write-Host "[1/4] backend  -> http://127.0.0.1:8010" -ForegroundColor Cyan

# 2) frontend dev server in its own window (proxies /api -> backend)
Start-Process powershell -ArgumentList "-NoExit", "-File", (Join-Path $here "start_frontend.ps1")
Write-Host "[2/4] frontend -> http://localhost:5173 (waiting for it to bind...)" -ForegroundColor Cyan
Start-Sleep -Seconds 8

# 3) cloudflared quick tunnel -> capture the public https URL from its log
$log = Join-Path $env:TEMP "desk_cf_tunnel.log"
if (Test-Path $log) { Remove-Item $log -Force }
$cf = Start-Process $cfExe -ArgumentList "tunnel", "--url", "http://localhost:5173", "--logfile", $log -PassThru -WindowStyle Minimized
Write-Host "[3/4] tunnel   -> cloudflared pid $($cf.Id), detecting URL..." -ForegroundColor Cyan

$url = $null
foreach ($i in 1..40) {
  Start-Sleep -Seconds 2
  if (Test-Path $log) {
    $m = Select-String -Path $log -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($m) { $url = $m.Matches[0].Value; break }
  }
}
if (-not $url) {
  Write-Host "Could not detect tunnel URL within ~80s. Check $log and set MINI_APP_URL manually." -ForegroundColor Red
  return
}
Write-Host "      tunnel URL: $url" -ForegroundColor Green

# 4) write MINI_APP_URL into .env (UTF-8, no BOM), then start the bot
$content = Get-Content $envFile
if ($content -match '^MINI_APP_URL=') {
  $content = $content -replace '^MINI_APP_URL=.*', "MINI_APP_URL=$url"
} else {
  $content += "MINI_APP_URL=$url"
}
[System.IO.File]::WriteAllLines($envFile, $content, (New-Object System.Text.UTF8Encoding $false))
Write-Host "      MINI_APP_URL written to .env" -ForegroundColor Green

Start-Process powershell -ArgumentList "-NoExit", "-File", (Join-Path $here "start_bot.ps1")
Write-Host "[4/4] bot started." -ForegroundColor Cyan

Write-Host ""
Write-Host "ALL UP. In Telegram open your bot -> /start -> 'Open Trading Desk'." -ForegroundColor Green
Write-Host "Public URL: $url  (changes every run - this script re-writes it each time)"
Write-Host "Stop: close the 3 spawned PowerShell windows + kill cloudflared (Stop-Process -Id $($cf.Id))."
