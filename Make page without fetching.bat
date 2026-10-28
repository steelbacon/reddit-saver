@echo off
title Reddit Saver (links only)
REM Drag your Reddit export zip file onto this file to start.
if "%~1"=="" (
  echo.
  echo   Drag your Reddit export zip file onto this file to start.
  echo.
  pause
  exit /b
)
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%~dp0reddit_saver.py" "%~1" --no-fetch
) else (
  python "%~dp0reddit_saver.py" "%~1" --no-fetch
)
echo.
pause
