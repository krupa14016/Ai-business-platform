
@echo off
title AI-BI Platform Startup

cd /d "%~dp0"

echo ====================================
echo       AI-BI PLATFORM STARTUP
echo ====================================

if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: Python virtual environment not found.
    pause
    exit /b 1
)

if not exist "frontend\package.json" (
    echo ERROR: Frontend package.json not found.
    pause
    exit /b 1
)

if not exist "frontend\node_modules" (
    echo Installing frontend dependencies...
    cd /d "%~dp0frontend"
    call npm install
    if errorlevel 1 (
        echo ERROR: npm install failed.
        pause
        exit /b 1
    )
)

echo Starting backend...
start "AI-BI Backend" cmd /k "cd /d ""%~dp0"" && call .venv\Scripts\activate.bat && python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000"

echo Starting frontend...
start "AI-BI Frontend" cmd /k "cd /d ""%~dp0frontend"" && npm run dev"

echo Waiting for services to start...
timeout /t 5 /nobreak >nul

start "" http://localhost:5173

echo Startup commands launched.
