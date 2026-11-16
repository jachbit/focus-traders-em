@echo off
title F.O.C.U.S. Traders Weekly EM - backup
rem Timestamped copies of the project files into backups\ (run before every edit session).
cd /d "%~dp0"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set TS=%%i
if not exist backups mkdir backups
copy "focus-traders-em.html"   "backups\focus-traders-em_%TS%.html" >nul && echo   [OK] focus-traders-em.html
copy "focus_traders_server.py" "backups\focus_traders_server_%TS%.py" >nul && echo   [OK] focus_traders_server.py
copy "em_build.py"             "backups\em_build_%TS%.py" >nul && echo   [OK] em_build.py
copy "tickers.txt"             "backups\tickers_%TS%.txt" >nul && echo   [OK] tickers.txt
copy ".github\workflows\em.yml" "backups\em_%TS%.yml" >nul && echo   [OK] em.yml
copy "README.md"               "backups\README_%TS%.md" >nul && echo   [OK] README.md
echo.
echo Backup done: backups\*_%TS%.*
