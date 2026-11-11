<#
  ONE-COMMAND robust launcher for the Telegram Mini App.

  Design (fixes the fragile dev-server + duplicate-bot problems):
    * Backend (FastAPI) serves the BUILT frontend/dist at "/" → single HTTPS origin,
      no Vite dev server / HMR (which Telegram's mobile webview chokes on).
    * cloudflared quick-tunnel points at the backend :8010 (not :5173).
    * Exactly ONE bot instance (kills any duplicates → no getUpdates 409 conflict).
    * Updates BOTH the inline /start button (MINI_APP_URL in .env) AND the persistent
      Telegram menu button (setChatMenuButton) to the fresh tunnel URL.

  Scope: touches ONLY this Control Plane (backend/frontend/tunnel/bot) + the bot's
  Telegram menu button. It NEVER touches the crypto-ai-desk trading system or any
  trading logic — its kill filters match only uvicorn:8010 / bot/bot.py / cloudflared
  / this repo's vite, none of which the desk uses.

  Usage:  ./scripts/launch_robust.ps1            (uses prebuilt dist)
          ./scripts/launch_robust.ps1 -Build     (rebuild dist first)
#>
param([switch]$Build)

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"
$here = $PSScriptRoot
$root = Split-Path -Parent $here
$envFile = Join-Path $root ".env"
$dist = Join-Path $root "frontend\dist"

function Say($m, $c="Cyan") { Write-Host $m -ForegroundColor $c }

if (-not (Test-Path $envFile)) { Say ".env not found at $envFile" Red; return }

# 0) optional rebuild of the static bundle
if ($Build -or -not (Test-Path (Join-Path $dist "index.html"))) {
  Say "[0/6] building frontend/dist ..."
  Push-Location (Join-Path $root "frontend")
  npm run build | Out-Null
  Pop-Location
}
if (-not (Test-Path (Join-Path $dist "index.html"))) { Say "dist missing; run with -Build" Red; return }

# load .env into THIS session so detached children inherit real config.
# -Encoding UTF8 is REQUIRED: without it PS 5.1 reads as cp1252, and the
# read->modify->write cycle below would re-encode any non-ASCII byte every run
# (the em-dash doom-loop that ballooned .env to 1.8GB on 2026-06-21).
Get-Content $envFile -Encoding UTF8 | ForEach-Object {
  if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
    $n = $matches[1].Trim(); $v = ($matches[2] -replace '\s+#.*$','').Trim()
    if ($v -ne '') { [Environment]::SetEnvironmentVariable($n, $v, 'Process') }
  }
}
$token = [Environment]::GetEnvironmentVariable('TELEGRAM_BOT_TOKEN','Process')
if (-not $token) { Say "TELEGRAM_BOT_TOKEN missing in .env" Red; return }

# 1) stop ONLY this app's processes (scoped; never the desk)
Say "[1/6] stopping old Control Plane processes (backend / tunnel / bot / vite) ..."
Get-CimInstance Win32_Process -Filter "Name='cloudflared.exe'" |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
  # ONLY this Mini App's backend (uvicorn app.main:app on OUR port 8010) + this repo's bot.
  # The port scope is deliberate: another local project runs `uvicorn app.main:app` on :8000 —
  # we must NEVER kill it. That collision is exactly why the Mini App moved off :8000.
  $_.CommandLine -match 'bot[\\/]bot\.py' -or
  ($_.CommandLine -match 'uvicorn app\.main:app' -and $_.CommandLine -match '--port 8010')
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -match 'trading-desk-control\\frontend' -and $_.CommandLine -match 'vite'
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
# free :8010 (loop a few times in case of reload-supervisor respawn)
for ($i=0; $i -lt 6; $i++) {
  $own = (Get-NetTCPConnection -State Listen -LocalPort 8010 -ErrorAction SilentlyContinue).OwningProcess | Sort-Object -Unique
  if (-not $own) { break }
  $own | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
  Start-Sleep -Seconds 2
}

# 2) backend (serves /api + static dist), no --reload, detached
Say "[2/6] starting backend on :8010 (serves built Mini App + API) ..."
Start-Process python -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8010' `
  -WorkingDirectory (Join-Path $root "backend") -WindowStyle Minimized
$ok = $false
# ~60s window — cold uvicorn import on a loaded box (scheduler + tunnels running)
# can take >20s; too short a wait made launch_robust (and the keeper that calls it)
# abort before starting cloudflared/bot, leaving a healthy backend with no tunnel.
foreach ($i in 1..60) {
  Start-Sleep -Seconds 1
  try { if ((Invoke-WebRequest "http://127.0.0.1:8010/api/health" -UseBasicParsing -TimeoutSec 4).StatusCode -eq 200) { $ok=$true; break } } catch {}
}
if (-not $ok) { Say "backend did not become healthy on :8010" Red; return }
Say "      backend healthy" Green

# 3) public tunnel -> backend :8000.
#    Prefer a STABLE ngrok domain (NGROK_DOMAIN in .env) so the URL NEVER rotates
#    and the menu button stays valid forever; otherwise fall back to the cloudflared
#    quick-tunnel (free but rotates on every restart + flaky 530s).
$url = $null
$ngDomain = [Environment]::GetEnvironmentVariable('NGROK_DOMAIN','Process')
if ($ngDomain) {
  Say "[3/6] starting STABLE ngrok tunnel -> https://$ngDomain ..."
  $ngExe = $null
  $ngc = Get-Command ngrok -ErrorAction SilentlyContinue
  if ($ngc) { $ngExe = $ngc.Source }
  elseif (Test-Path "$env:LOCALAPPDATA\Microsoft\WinGet\Links\ngrok.exe") { $ngExe = "$env:LOCALAPPDATA\Microsoft\WinGet\Links\ngrok.exe" }
  elseif (Test-Path (Join-Path $here "bin\ngrok.exe")) { $ngExe = Join-Path $here "bin\ngrok.exe" }
  if (-not $ngExe) { Say "ngrok not found (winget install Ngrok.Ngrok)" Red; return }
  # kill any stray ngrok first (single agent session on free tier)
  Get-CimInstance Win32_Process -Filter "Name='ngrok.exe'" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  Start-Sleep -Seconds 1
  Start-Process $ngExe -ArgumentList 'http','--url',"https://$ngDomain",'8010' -WindowStyle Minimized
  $url = "https://$ngDomain"
  # Verify via the ngrok agent local API (127.0.0.1:4040), not an external fetch, so a
  # flaky connection cannot abort the launch and skip the bot.
  $up = $false
  foreach ($i in 1..20) {
    Start-Sleep -Seconds 2
    try {
      $tj = Invoke-RestMethod 'http://127.0.0.1:4040/api/tunnels' -TimeoutSec 4
      if ($tj.tunnels.public_url -contains $url) { $up = $true; break }
    } catch { }
  }
  if ($up) {
    Say "      stable ngrok tunnel up: $url" Green
  } else {
    $alive = @(Get-CimInstance Win32_Process -Filter "Name='ngrok.exe'" -EA SilentlyContinue).Count
    if ($alive -lt 1) { Say "ngrok not running (set authtoken: ngrok config add-authtoken TOKEN)" Red; return }
    Say "      ngrok agent up; tunnel not yet confirmed via local API, continuing" Yellow
  }
} else {
  Say "[3/6] starting cloudflared quick-tunnel -> :8010 (rotating; set NGROK_DOMAIN in .env for a stable URL) ..."
  $cf = Join-Path $here "bin\cloudflared.exe"
  if (-not (Test-Path $cf)) { $c = Get-Command cloudflared -ErrorAction SilentlyContinue; if ($c) { $cf = $c.Source } else { Say "cloudflared not found" Red; return } }
  $log = Join-Path $env:TEMP ("cp_tunnel_{0}.log" -f (Get-Date -Format HHmmss))
  # --protocol http2 : default QUIC/UDP is dropped by many routers/ISPs and causes
  # constant reconnects (tunnel keeps dying -> URL rotates -> Error 1033). HTTP/2 over
  # TCP/443 is far more stable on flaky/UDP-restricted connections.
  Start-Process $cf -ArgumentList 'tunnel','--url','http://localhost:8010','--protocol','http2','--logfile',$log -WindowStyle Minimized
  foreach ($i in 1..40) {
    Start-Sleep -Seconds 2
    if (Test-Path $log) {
      $m = Select-String -Path $log -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -ErrorAction SilentlyContinue | Select-Object -First 1
      if ($m) { $url = $m.Matches[0].Value; break }
    }
  }
  if (-not $url) { Say "tunnel URL not detected (see $log)" Red; return }
  Say "      quick-tunnel: $url" Green
}

# 4) write MINI_APP_URL into .env (read+write BOTH UTF-8 → symmetric, no doom-loop)
$content = Get-Content $envFile -Encoding UTF8
if ($content -match '^MINI_APP_URL=') { $content = $content -replace '^MINI_APP_URL=.*', "MINI_APP_URL=$url" } else { $content += "MINI_APP_URL=$url" }
[System.IO.File]::WriteAllLines($envFile, $content, (New-Object System.Text.UTF8Encoding $false))
[Environment]::SetEnvironmentVariable('MINI_APP_URL', $url, 'Process')
Say "[4/6] MINI_APP_URL written to .env"

# 5) set the persistent Telegram menu button to the fresh URL (so BOTH the always-on
#    menu button AND the /start inline button open the current app)
Say "[5/6] setting Telegram chat menu button ..."
try {
  $body = @{ menu_button = @{ type='web_app'; text='Open Trading Desk'; web_app=@{ url=$url } } } | ConvertTo-Json -Depth 6 -Compress
  $r = Invoke-RestMethod -Method Post -Uri "https://api.telegram.org/bot$token/setChatMenuButton" -ContentType 'application/json' -Body $body -TimeoutSec 15
  Say ("      setChatMenuButton ok=" + $r.ok) Green
} catch { Say "      setChatMenuButton failed (non-fatal): $($_.Exception.Message.Split([char]10)[0])" Yellow }

# 6) exactly one bot (inherits MINI_APP_URL), detached
Say "[6/6] starting the bot (single instance) ..."
Start-Process python -ArgumentList 'bot/bot.py' -WorkingDirectory $root -WindowStyle Minimized
Start-Sleep -Seconds 6

# verify
$botN = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'bot[\\/]bot\.py' } | Measure-Object).Count
$tunnelOk = $false; try { $tunnelOk = (Invoke-WebRequest "$url/api/health" -UseBasicParsing -TimeoutSec 20).StatusCode -eq 200 } catch {}
Write-Host ""
Say "ALL UP." Green
Write-Host "  public URL : $url"
Write-Host "  bot copies : $botN  (must be 1)"
Write-Host "  tunnel /api/health reachable: $tunnelOk"
Write-Host ""
Say "In Telegram: open @aitradingdesk1_bot -> tap the menu button (bottom-left) OR /start -> Open Trading Desk." Green
Write-Host "Re-run this script anytime to refresh the tunnel URL + restart cleanly."
