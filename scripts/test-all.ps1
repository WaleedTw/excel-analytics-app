$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location -LiteralPath "$Root\backend"
if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) { python -m venv .venv }
& ".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
& ".venv\Scripts\python.exe" -m pytest --cov=app --cov-report=term-missing
Set-Location -LiteralPath "$Root\frontend"
if (-not (Test-Path -LiteralPath "node_modules")) { npm install }
npm run lint
npm run typecheck
npm run test
npm run build

