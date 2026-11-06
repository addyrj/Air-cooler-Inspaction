$root = Split-Path -Parent $PSScriptRoot

Write-Host "Starting Air Cooler Inspection System..." -ForegroundColor Cyan

# Terminal 1 — AI Engine (port 8001)
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$root\ai-engine'; .\venv\Scripts\Activate.ps1; `$env:AI_MODE='simulation'; python main.py"
)
Start-Sleep -Seconds 2

# Terminal 2 — Backend API (port 8000)
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$root\backend'; .\venv\Scripts\Activate.ps1; python app\main.py"
)
Start-Sleep -Seconds 2

# Terminal 3 — Next.js Dashboard (port 3001)
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$root\dashboard'; npm run dev"
)
Start-Sleep -Seconds 3

Write-Host ""
Write-Host "All services launched:" -ForegroundColor Green
Write-Host "  AI Engine  -> http://localhost:8001/health" -ForegroundColor Yellow
Write-Host "  Backend    -> http://localhost:8000/health" -ForegroundColor Yellow
Write-Host "  Dashboard  -> http://localhost:3001" -ForegroundColor Yellow
Write-Host ""
Write-Host "To stop all: .\scripts\stop_all.ps1" -ForegroundColor Gray
