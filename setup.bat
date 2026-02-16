@echo off
REM Lottery Oracle - Security Demo Setup Script
REM This script initializes the database and helps run the security comparison demo

echo ================================================================
echo      LOTTERY ORACLE - SECURITY COMPARISON DEMO SETUP
echo ================================================================
echo.

REM Check Python installation
echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python 3.8 or higher and add it to PATH.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Found Python %PYTHON_VERSION%

REM Install dependencies
echo.
echo Installing Python dependencies...
python -m pip install --quiet flask flask-cors pyjwt bcrypt numpy pandas requests matplotlib beautifulsoup4 2>nul
if errorlevel 1 (
    echo Warning: Some packages may have failed to install. Trying again...
    python -m pip install flask flask-cors pyjwt bcrypt numpy pandas requests matplotlib beautifulsoup4
)

echo Dependencies installed

REM Create backend/data directory if it doesn't exist
if not exist "backend" (
    echo.
    echo Creating backend directory...
    mkdir backend
)

if not exist "backend\data" (
    echo.
    echo Creating backend\data directory...
    mkdir backend\data
)

REM Check for historical data
echo.
echo Checking for historical lottery data...

if not exist "backend\data\powerball_results.csv" (
    echo WARNING: Historical lottery data not found!
    echo.
    echo Do you want to scrape REAL historical lottery data now?
    echo This will take approximately 5-10 minutes and requires internet connection.
    echo.
    set /p SCRAPE_DATA="Scrape data now? (y/n): "
    
    if /i "%SCRAPE_DATA%"=="y" (
        echo.
        echo Scraping historical lottery data...
        python backend/scrape_historical_data.py all
        
        if errorlevel 1 (
            echo ERROR: Data scraping failed. You can run it manually later:
            echo    python backend/scrape_historical_data.py all
        ) else (
            echo Historical data scraped successfully
        )
    ) else (
        echo Skipping data scraping. You can run it later with:
        echo    python backend/scrape_historical_data.py all
    )
) else (
    echo Historical lottery data found in backend\data
)

REM Initialize database
echo.
echo Initializing lottery database...
python backend/init_db.py

if errorlevel 1 (
    echo ERROR: Database initialization failed
    pause
    exit /b 1
)

echo Database initialized successfully

REM Create security implementation directories if they don't exist
echo.
echo Setting up security implementation directories...

if not exist "selective-security" (
    echo Creating selective-security directory...
    mkdir selective-security
    if errorlevel 1 (
        echo ERROR: Failed to create selective-security directory
        pause
        exit /b 1
    )
)

if not exist "blanket-security" (
    echo Creating blanket-security directory...
    mkdir blanket-security
    if errorlevel 1 (
        echo ERROR: Failed to create blanket-security directory
        pause
        exit /b 1
    )
)

REM Copy database to both security version directories
echo.
echo Copying database to security implementations...

if exist "lottery_data.db" (
    copy /y lottery_data.db selective-security\lottery_data.db >nul
    if errorlevel 1 (
        echo ERROR: Failed to copy database to selective-security
        pause
        exit /b 1
    )
    echo   Database copied to selective-security
    
    copy /y lottery_data.db blanket-security\lottery_data.db >nul
    if errorlevel 1 (
        echo ERROR: Failed to copy database to blanket-security
        pause
        exit /b 1
    )
    echo   Database copied to blanket-security
) else (
    echo WARNING: lottery_data.db not found in current directory
    echo Please ensure init_db.py created the database successfully
)

echo.
echo ================================================================
echo                     SETUP COMPLETE
echo ================================================================
echo.
echo Data directory: backend\data
echo Database: lottery_data.db
echo.
echo You can now run the demo using one of these methods:
echo.
echo METHOD 1: Run servers manually
echo    Terminal 1: cd selective-security ^&^& python backend/app.py
echo    Terminal 2: cd blanket-security ^&^& python backend/app.py
echo    Terminal 3: python backend/test_performance.py
echo.
echo METHOD 2: Run automated test
echo    run_demo.bat
echo.
echo The demo will generate:
echo    - performance_comparison.png
echo    - performance_report.txt
echo    - pipeline_diagrams.png
echo.
echo NOTE: Make sure app.py files exist in both directories:
echo    - selective-security\app.py
echo    - blanket-security\app.py
echo.
pause