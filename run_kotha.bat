@echo off
title Kotha Healthcare Intake Platform
echo ===================================================
echo Starting Kotha (কথা) Healthcare Platform...
echo ===================================================

cd /d "%~dp0"

echo [1/2] Starting Backend API (FastAPI on port 8000)...
start "Kotha Backend" cmd /k "cd backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

echo [2/2] Starting Frontend UI (Vite on port 5173)...
start "Kotha Frontend" cmd /k "cd frontend && npm run dev"

timeout /t 3 /nobreak >nul
echo.
echo ===================================================
echo Kotha is running! Opening browser...
echo Frontend UI: http://localhost:5173
echo Backend API: http://127.0.0.1:8000/docs
echo ===================================================
start http://localhost:5173
