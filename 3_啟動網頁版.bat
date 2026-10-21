@echo off
chcp 65001 >nul
title Technical Chip Analyzer (Web) - Starting...

echo.
echo  ============================================
echo   Technical Chip Analyzer - Web Version
echo   Browser will open automatically.
echo   URL: http://localhost:8000/技術籌碼分析工具.html
echo.
echo   Must use this launcher (not double-click the
echo   html file) - it runs a local proxy so the page
echo   can fetch FinMind data without hitting browser
echo   CORS restrictions.
echo.
echo   Close this window to stop the server.
echo  ============================================
echo.

cd /d "%~dp0"

REM Use confirmed Python path
set PYTHON=%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe

if exist "%PYTHON%" (
    start "" cmd /c "timeout /t 2 >nul & start "" http://localhost:8000/技術籌碼分析工具.html"
    "%PYTHON%" finmind_proxy_server.py
    goto done
)

REM Fallback: search AppData for any python.exe
set FOUND=
for /f "tokens=*" %%i in ('dir /b /s "%LOCALAPPDATA%\Python\*\python.exe" 2^>nul') do (
    if not defined FOUND set FOUND=%%i
)
if defined FOUND (
    start "" cmd /c "timeout /t 2 >nul & start "" http://localhost:8000/技術籌碼分析工具.html"
    "%FOUND%" finmind_proxy_server.py
    goto done
)

echo  [ERROR] Python not found at expected location.
echo  Please run this manually in CMD from this folder:
echo    "%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe" finmind_proxy_server.py
echo  Then open http://localhost:8000/技術籌碼分析工具.html in your browser.
pause
exit /b 1

:done
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Startup failed.
    pause
)
