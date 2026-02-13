@echo off
setlocal

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"

echo Checking paths...
echo ROOT: %ROOT%
echo BACKEND: %BACKEND%
echo FRONTEND: %FRONTEND%

if not exist "%BACKEND%\ve\Scripts\activate.bat" (
  echo [ERROR] Virtual environment not found at %BACKEND%\ve\Scripts\activate.bat
  echo Please ensure the virtual environment is created in backend\ve\
  pause
  exit /b 1
)

echo Starting backend...
start "Market Analyzer Backend" cmd /k "cd /d "%BACKEND%" && call ve\Scripts\activate.bat && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo Starting frontend...
start "Market Analyzer Frontend" cmd /k "cd /d "%FRONTEND%" && npm run dev"

echo.
echo Started backend and frontend in separate CMD windows.
echo Backend: http://localhost:8000
echo Frontend: http://localhost:3000
echo.
pause
