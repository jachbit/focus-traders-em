@echo off
title Focus Traders Weekly EM — Server
color 0A
echo.
echo  ================================================
echo   FOCUS TRADERS WEEKLY EM  —  Starting Server
echo  ================================================
echo.

:: Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python not found. Please install Python from python.org
    pause
    exit /b 1
)

:: Install dependencies if needed
echo  Checking dependencies...
pip show flask >nul 2>&1
if errorlevel 1 (
    echo  Installing required packages...
    pip install flask yfinance reportlab pandas numpy
    echo.
)

:: Open browser after a short delay
echo  Opening browser...
start "" timeout /t 2 >nul
start "" "http://localhost:5000"

:: Start server
echo  ================================================
echo   Dashboard: http://localhost:5000
echo   Press Ctrl+C to stop
echo  ================================================
echo.
python focus_traders_server.py
pause
