# Launch backend + frontend together (each in its own window). Bot is started separately.
$root = $PSScriptRoot
Start-Process powershell -ArgumentList "-NoExit", "-File", (Join-Path $root "start_backend.ps1")
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit", "-File", (Join-Path $root "start_frontend.ps1")
Write-Host "Backend  -> http://127.0.0.1:8010"
Write-Host "Frontend -> http://localhost:5173  (open this in the browser, or set MINI_APP_URL for Telegram)"
Write-Host "Bot      -> run ./scripts/start_bot.ps1 separately (needs TELEGRAM_BOT_TOKEN)"
Write-Host "Stop: close the spawned windows, or Ctrl+C in each."
