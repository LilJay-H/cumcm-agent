$ErrorActionPreference = "Stop"

$project = Split-Path -Parent $PSScriptRoot
$env:PUPPETEER_CACHE_DIR = Join-Path $project ".puppeteer-cache"
$env:npm_config_cache = Join-Path $project ".npm-cache"

Set-Location $project
npx --no-install mmdc `
  -i "docs\architecture.mmd" `
  -o "docs\architecture.png" `
  -b white `
  -w 2400
