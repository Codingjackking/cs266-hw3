@echo off
REM Lottery Oracle - Demo Runner (Improved)
REM Starts both security implementations and runs performance tests

echo ================================================================
echo         LOTTERY ORACLE - SECURITY COMPARISON DEMO
echo ================================================================
echo.

REM Check if database exists
if not exist "lottery_data.db" (
    echo ERROR: Database not found in current directory
    echo Current directory: %CD%
    echo.
    echo Please run setup.bat first or ensure you're in the correct directory
    pause
    exit /b 1
)

REM Check and copy databases to implementation directories
if not exist "selective-security\lottery_data.db" (
    echo Copying database to selective-security...
    copy /y lottery_data.db selective-security\lottery_data.db >nul
    echo Database copied
)

if not exist "blanket-security\lottery_data.db" (
    echo Copying database to blanket-security...
    copy /y lottery_data.db blanket-security\lottery_data.db >nul
    echo Database copied
)

REM Kill any existing processes on ports 5001 and 5002
echo Cleaning up existing processes...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5001 ^| findstr LISTENING 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5002 ^| findstr LISTENING 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul

REM Start selective security server
echo.
echo Starting Selective Security server on port 5001...
cd selective-security
start "Selective Security Server" python app.py
cd ..

echo Waiting for server to start...
set SELECTIVE_READY=0
for /L %%i in (1,1,15) do (
    timeout /t 1 /nobreak >nul
    netstat -an | findstr "5001" | findstr "LISTENING" >nul 2>&1
    if not errorlevel 1 (
        echo    Server is READY on port 5001
        set SELECTIVE_READY=1
        goto selective_started
    )
)

:selective_started
if %SELECTIVE_READY%==0 (
    echo.
    echo ERROR: Selective Security server failed to start
    echo.
    echo Check the "Selective Security Server" window for error messages
    echo.
    echo Troubleshooting:
    echo 1. Check if selective-security\lottery_data.db exists
    echo 2. Verify all dependencies are installed: pip list
    echo 3. Make sure port 5001 is not in use
    echo.
    pause
    exit /b 1
)

REM Start blanket security server
echo.
echo Starting Blanket Security server on port 5002...
cd blanket-security
start "Blanket Security Server" python app.py
cd ..

echo Waiting for server to start...
set BLANKET_READY=0
for /L %%i in (1,1,15) do (
    timeout /t 1 /nobreak >nul
    netstat -an | findstr "5002" | findstr "LISTENING" >nul 2>&1
    if not errorlevel 1 (
        echo    Server is READY on port 5002
        set BLANKET_READY=1
        goto blanket_started
    )
)

:blanket_started
if %BLANKET_READY%==0 (
    echo.
    echo ERROR: Blanket Security server failed to start
    echo Check the "Blanket Security Server" window for errors
    echo.
    REM Kill selective server
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5001 ^| findstr LISTENING 2^>nul') do (
        taskkill /F /PID %%a >nul 2>&1
    )
    pause
    exit /b 1
)

REM Run performance tests
echo.
echo ================================================================
echo Running performance tests (2-3 minutes)...
echo ================================================================
echo.

python test_performance.py

REM Cleanup
echo.
echo Shutting down servers...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5001 ^| findstr LISTENING 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5002 ^| findstr LISTENING 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo.
echo ================================================================
echo                     DEMO COMPLETE
echo ================================================================
echo.
echo Results: performance_comparison.png, performance_report.txt
echo.
pause