$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location -LiteralPath "$Root\frontend"
if (-not (Test-Path -LiteralPath "node_modules")) { npm install }
npm run dev

