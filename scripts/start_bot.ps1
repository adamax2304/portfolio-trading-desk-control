# Start the thin Telegram bot (launcher + emergency pause). Requires TELEGRAM_BOT_TOKEN + MINI_APP_URL.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

$envFile = Join-Path $root ".env"
if (Test-Path $envFile) {
  Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
      $name = $matches[1].Trim()
      $val  = ($matches[2] -replace '\s+#.*$', '').Trim()
      if ($val -ne '') { [Environment]::SetEnvironmentVariable($name, $val) }
    }
  }
}
if (-not $env:TELEGRAM_BOT_TOKEN) { throw "TELEGRAM_BOT_TOKEN required (set it in .env)" }
Set-Location $root
python bot/bot.py
