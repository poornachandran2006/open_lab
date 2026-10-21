@echo off
title GridGuard Master Launcher
echo ========================================================
echo       Starting GridGuard Power Quality System
echo ========================================================
echo.

cd /d "%~dp0"

echo [1/3] Starting FastAPI Backend (Port 8000)...
start "GridGuard Backend (FastAPI)" cmd /k "cd /d "%~dp0" && python -m uvicorn backend:app --host 0.0.0.0 --port 8000"

timeout /t 2 /nobreak >nul

echo [2/3] Starting React Dashboard (Port 3000)...
start "GridGuard Dashboard (Vite)" cmd /k "cd /d "%~dp0" && npm run dev"

timeout /t 3 /nobreak >nul

echo [3/3] Starting Disturbance Injector (ESP32 Simulator)...
start "GridGuard Injector (MQTT)" cmd /k "cd /d "%~dp0" && python injector.py"

echo.
echo Opening Dashboard in your browser...
start http://localhost:3000

echo.
echo ========================================================
echo GridGuard is now running!
echo - Backend:   http://localhost:8000 (API and WebSockets)
echo - Dashboard: http://localhost:3000 (React UI)
echo - Broker:    localhost:1883 (Mosquitto)
echo.
echo Keep the 3 opened terminal windows running.
echo To stop everything, close those windows or run stop.bat
echo ========================================================
pause
