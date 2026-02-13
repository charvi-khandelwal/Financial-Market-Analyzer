@echo off
setlocal

set "ROOT=%~dp0"
set "BACKEND=%ROOT%\backend"
set "FRONTEND=%ROOT%\frontend"

if not exist "%BACKEND%\ve\Scripts\activate.bat" (
  echo [ERROR] Virtual environment not found at backend\ve\Scripts\activate.bat
  exit /b 1
)

start "Market Analyzer Backend" cmd /k "cd /d \"%BACKEND%\" && call ve\Scripts\activate.bat && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
start "Market Analyzer Frontend" cmd /k "cd /d \"%FRONTEND%\" && npm run dev"

echo Started backend and frontend in separate CMD windows.
endlocal
