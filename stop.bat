@echo off
title Stop GridGuard
echo Stopping GridGuard services...

:: Kill processes on port 8000 (Backend)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a 2>nul
)

:: Kill processes on port 3000 (Vite Frontend)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a 2>nul
)

:: Kill any stray injector.py
wmic process where "commandline like '%%injector.py%%'" call terminate 2>nul

echo All GridGuard services stopped successfully.
timeout /t 2 >nul
