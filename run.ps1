# Run from project root in VS Code terminal:  .\run.ps1
# Starts all 3 services in separate windows

$root = $PSScriptRoot
if (-not $root) { $root = (Get-Location).Path }

Write-Host ""
Write-Host "Air Cooler Inspection System" -ForegroundColor Cyan
Write-Host "=============================" -ForegroundColor Cyan

# Kill anything on our ports first
foreach ($p in @(8000, 8001, 3000, 3001)) {
    Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique |
        ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
}
Start-Sleep -Seconds 1

# Window 1 — AI Engine (port 8001)
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$root\ai-engine'; `$env:AI_MODE='simulation'; .\venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload"
) -WindowStyle Normal

Start-Sleep -Seconds 2

# Window 2 — Backend API (port 8000)
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$root\backend'; .\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
) -WindowStyle Normal

Start-Sleep -Seconds 2

# Window 3 — Dashboard (port 3001)
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$root\dashboard'; npm run dev"
) -WindowStyle Normal

Write-Host ""
Write-Host "Launched 3 windows. Wait 10 seconds, then open:" -ForegroundColor Green
Write-Host "  Dashboard  ->  http://localhost:3001" -ForegroundColor Yellow
Write-Host "  Backend    ->  http://localhost:8000/health" -ForegroundColor Yellow
Write-Host "  AI Engine  ->  http://localhost:8001/health" -ForegroundColor Yellow
Write-Host ""
