@echo off
REM Test script runner for SofaScore integration

echo ================================================================================
echo   SofaScore Integration Test Runner
echo ================================================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher
    pause
    exit /b 1
)

echo Python found!

REM Check if required packages are installed
python -c "import aiohttp" >nul 2>&1
if errorlevel 1 (
    echo.
    echo WARNING: Required Python packages not found
    echo Installing dependencies...
    echo.
    pip install -r requirements_test.txt
    echo.
)

echo.

:menu
echo Choose a test to run:
echo.
echo   1. Quick API Test (checks if SofaScore API is accessible)
echo   2. Full Integration Test (test with your team)
echo   3. Full Integration Test - Manchester United (default)
echo   4. Full Integration Test - Barcelona
echo   5. Full Integration Test - Custom team
echo   6. Exit
echo.

set /p choice="Enter your choice (1-6): "

if "%choice%"=="1" goto quick_test
if "%choice%"=="2" goto custom_test
if "%choice%"=="3" goto man_utd_test
if "%choice%"=="4" goto barcelona_test
if "%choice%"=="5" goto input_team
if "%choice%"=="6" goto end

echo Invalid choice, please try again.
echo.
goto menu

:quick_test
echo.
echo Running quick API test...
echo.
python quick_test.py
pause
goto menu

:custom_test
echo.
echo Running full test with custom input...
echo.
python test_sofascore.py
pause
goto menu

:man_utd_test
echo.
echo Running full test with Manchester United...
echo.
python test_sofascore.py "Manchester United"
pause
goto menu

:barcelona_test
echo.
echo Running full test with Barcelona...
echo.
python test_sofascore.py "Barcelona"
pause
goto menu

:input_team
echo.
set /p team_name="Enter team name: "
set /p sport="Enter sport (football/basketball/tennis/etc) [default: football]: "

if "%sport%"=="" set sport=football

echo.
echo Running test with %team_name% (%sport%)...
echo.
python test_sofascore.py "%team_name%:%sport%"
pause
goto menu

:end
echo.
echo Goodbye!
exit /b 0
