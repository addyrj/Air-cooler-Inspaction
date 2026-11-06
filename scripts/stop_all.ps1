Write-Host "Stopping Air Cooler Inspection System..." -ForegroundColor Cyan

foreach ($port in @(8000, 8001, 3000, 3001)) {
    $pids = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($pid in $pids) {
        if ($pid -and $pid -ne 0) {
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Write-Host "  Stopped PID $pid (port $port)" -ForegroundColor Yellow
        }
    }
}

Write-Host "Done." -ForegroundColor Green
