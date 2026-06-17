@echo off
title Install - Taiwan Stock Analyzer

echo.
echo  ============================================
echo   Taiwan Stock Analyzer - Install Packages
echo  ============================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Python not found!
    echo  Please install Python 3.10+ from:
    echo  https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo  Python detected:
python --version
echo.
echo  Installing packages...
echo.

pip install streamlit requests pandas plotly

if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Installation failed. Check your internet connection.
    pause
    exit /b 1
)

echo.
echo  ============================================
echo   Installation complete!
echo   Now run: 2_啟動工具.bat
echo  ============================================
echo.
pause
