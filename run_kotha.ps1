# Kotha Runner for PowerShell
Set-Location $PSScriptRoot

Write-Host "Starting Kotha Backend (FastAPI on port 8000)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$PSScriptRoot\backend'; .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

Write-Host "Starting Kotha Frontend (Vite on port 5173)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$PSScriptRoot\frontend'; npm run dev"

Start-Sleep -Seconds 3
Write-Host "Opening Kotha UI in browser (http://localhost:5173)..." -ForegroundColor Green
Start-Process "http://localhost:5173"
