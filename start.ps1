Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "       Starting GridGuard Power Quality System          " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# 1. Start Backend in new window
Write-Host "[1/3] Starting FastAPI Backend (Port 8000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$ScriptDir'; python -m uvicorn backend:app --host 0.0.0.0 --port 8000"

Start-Sleep -Seconds 2

# 2. Start Frontend in new window
Write-Host "[2/3] Starting React Dashboard (Port 3000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$ScriptDir'; npm run dev"

Start-Sleep -Seconds 3

# 3. Start Injector in new window
Write-Host "[3/3] Starting Disturbance Injector (ESP32 Simulator)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$ScriptDir'; python injector.py"

Write-Host ""
Write-Host "Opening Dashboard in default browser..." -ForegroundColor Green
Start-Process "http://localhost:3000"

Write-Host ""
Write-Host "========================================================" -ForegroundColor Green
Write-Host " GridGuard is now running!" -ForegroundColor Green
Write-Host " - Backend:   http://localhost:8000" -ForegroundColor White
Write-Host " - Dashboard: http://localhost:3000" -ForegroundColor White
Write-Host " - Broker:    localhost:1883" -ForegroundColor White
Write-Host ""
Write-Host " Keep the 3 opened terminal windows running." -ForegroundColor White
Write-Host " Run .\stop.bat to shut down all services." -ForegroundColor White
Write-Host "========================================================" -ForegroundColor Green
