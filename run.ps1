# One-command launcher (Windows PowerShell): installs everything, builds the UI, checks your NVIDIA key, starts Atlas on :8000.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host ">> Created .env" }
if (-not ((Get-Content .env -Raw) -match '(?m)^NVIDIA_API_KEY=.+') -and -not $env:NVIDIA_API_KEY) {
  $k = Read-Host ">> Paste your NVIDIA API key (nvapi-...), or press Enter to skip"
  if ($k) { (Get-Content .env) -replace '^NVIDIA_API_KEY=.*', "NVIDIA_API_KEY=$k" | Set-Content .env }
}
Set-Location backend
if (-not (Test-Path .venv)) { python -m venv .venv }
& .\.venv\Scripts\Activate.ps1
pip install -q -r requirements.txt
python -m playwright install chromium
Set-Location ..\frontend
if (-not (Test-Path node_modules)) { npm install }
if (-not (Test-Path dist)) { npm run build }
Set-Location ..\backend
try { python -m app.check } catch { }
Write-Host ">> Open http://localhost:8000"
uvicorn app.main:app --port 8000
