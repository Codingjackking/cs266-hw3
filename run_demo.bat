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

REM Check if required directories exist
if not exist "selective-security" (
    echo ERROR: selective-security directory not found
    echo Current directory: %CD%
    echo.
    echo Please ensure the project structure is correct:
    echo   - selective-security\
    echo   - blanket-security\
    echo   - lottery_data.db
    echo.
    echo The directory structure should look like:
    echo   cs266-hw3\
    echo     ^|-- selective-security\
    echo     ^|-- blanket-security\
    echo     ^|-- lottery_data.db
    echo     ^|-- run_demo.bat
    pause
    exit /b 1
)

if not exist "blanket-security" (
    echo ERROR: blanket-security directory not found
    echo Current directory: %CD%
    echo.
    echo Please ensure the project structure is correct:
    echo   - selective-security\
    echo   - blanket-security\
    echo   - lottery_data.db
    pause
    exit /b 1
)

REM Check if app.py files exist
if not exist "selective-security\app.py" (
    echo ERROR: selective-security\app.py not found
    echo.
    echo The selective-security implementation is missing the app.py file.
    echo Please ensure you have the complete project files.
    pause
    exit /b 1
)

if not exist "blanket-security\app.py" (
    echo ERROR: blanket-security\app.py not found
    echo.
    echo The blanket-security implementation is missing the app.py file.
    echo Please ensure you have the complete project files.
    pause
    exit /b 1
)

REM Check and copy databases to implementation directories
if not exist "selective-security\lottery_data.db" (
    echo Copying database to selective-security...
    if exist "lottery_data.db" (
        copy /y lottery_data.db selective-security\lottery_data.db >nul
        if errorlevel 1 (
            echo ERROR: Failed to copy database to selective-security
            pause
            exit /b 1
        )
        echo Database copied successfully
    ) else (
        echo ERROR: lottery_data.db not found in current directory
        echo Please run setup.bat first to initialize the database
        pause
        exit /b 1
    )
) else (
    echo Database found in selective-security
)

if not exist "blanket-security\lottery_data.db" (
    echo Copying database to blanket-security...
    if exist "lottery_data.db" (
        copy /y lottery_data.db blanket-security\lottery_data.db >nul
        if errorlevel 1 (
            echo ERROR: Failed to copy database to blanket-security
            pause
            exit /b 1
        )
        echo Database copied successfully
    ) else (
        echo ERROR: lottery_data.db not found in current directory
        echo Please run setup.bat first to initialize the database
        pause
        exit /b 1
    )
) else (
    echo Database found in blanket-security
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
if errorlevel 1 (
    echo ERROR: Cannot change to selective-security directory
    cd ..
    pause
    exit /b 1
)
start "Selective Security Server" cmd /k "python app.py || pause"
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
    echo The server window should still be open showing the error.
    echo Check the "Selective Security Server" window for error messages.
    echo.
    echo Common issues:
    echo 1. Missing app.py file in selective-security directory
    echo 2. Missing lottery_data.db in selective-security directory
    echo 3. Missing Python dependencies - run: pip install flask flask-cors pyjwt bcrypt
    echo 4. Port 5001 already in use
    echo 5. Python import errors (check the server window for details)
    echo.
    echo The server window is still open - please check it for the actual error.
    echo.
    pause
    exit /b 1
)

REM Start blanket security server
echo.
echo Starting Blanket Security server on port 5002...
cd blanket-security
if errorlevel 1 (
    echo ERROR: Cannot change to blanket-security directory
    cd ..
    REM Kill selective server
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5001 ^| findstr LISTENING 2^>nul') do (
        taskkill /F /PID %%a >nul 2>&1
    )
    pause
    exit /b 1
)
start "Blanket Security Server" cmd /k "python app.py || pause"
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