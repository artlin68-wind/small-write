@echo off
title Taiwan Stock Analyzer - Starting...

echo.
echo  ============================================
echo   Taiwan Stock Analyzer - Starting...
echo   Browser will open automatically.
echo   URL: http://localhost:8501
echo.
echo   Close this window to stop the server.
echo  ============================================
echo.

cd /d "%~dp0"

REM Use confirmed Python path
set PYTHON=%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe

if exist "%PYTHON%" (
    "%PYTHON%" -m streamlit run app.py --server.headless false --browser.gatherUsageStats false
    goto done
)

REM Fallback: search AppData for any python.exe
set FOUND=
for /f "tokens=*" %%i in ('dir /b /s "%LOCALAPPDATA%\Python\*\python.exe" 2^>nul') do (
    if not defined FOUND set FOUND=%%i
)
if defined FOUND (
    "%FOUND%" -m streamlit run app.py --server.headless false --browser.gatherUsageStats false
    goto done
)

echo  [ERROR] Python not found at expected location.
echo  Please run this manually in CMD:
echo    "%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe" -m streamlit run app.py
pause
exit /b 1

:done
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Startup failed.
    pause
)
