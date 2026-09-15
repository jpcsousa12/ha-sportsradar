@echo off
echo ================================================================================
echo   SofaScore Test Environment Setup
echo ================================================================================
echo.
echo This will install the required Python packages for testing.
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher from python.org
    pause
    exit /b 1
)

echo Installing dependencies...
echo.
pip install -r requirements_test.txt

if errorlevel 0 (
    echo.
    echo ================================================================================
    echo   Setup Complete!
    echo ================================================================================
    echo.
    echo You can now run the tests:
    echo   - Double-click run_tests.bat
    echo   - Or run: python test_sofascore.py "FC Porto"
    echo.
) else (
    echo.
    echo ERROR: Failed to install dependencies
    echo Please check your internet connection and try again
    echo.
)

pause
