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

REM Check for historical data
echo.
echo Checking for historical lottery data...

if not exist "data\" (
    echo WARNING: Historical lottery data not found!
    echo.
    echo Do you want to scrape REAL historical lottery data now?
    echo This will take approximately 5-10 minutes and requires internet connection.
    echo.
    set /p SCRAPE_DATA="Scrape data now? (y/n): "
    
    if /i "%SCRAPE_DATA%"=="y" (
        echo.
        echo Scraping historical lottery data...
        python scrape_historical_data.py all
        
        if errorlevel 1 (
            echo ERROR: Data scraping failed. You can run it manually later:
            echo    python scrape_historical_data.py all
        ) else (
            echo Historical data scraped successfully
        )
    ) else (
        echo Skipping data scraping. You can run it later with:
        echo    python scrape_historical_data.py all
    )
) else (
    if exist "data\powerball_results.csv" (
        echo Historical lottery data found
    ) else (
        echo WARNING: data folder exists but no CSV files found
        echo You may need to run: python scrape_historical_data.py all
    )
)

REM Initialize database
echo.
echo Initializing lottery database...
python init_db.py

if errorlevel 1 (
    echo ERROR: Database initialization failed
    pause
    exit /b 1
)

echo Database initialized successfully

REM Copy database to both security version directories
echo.
echo Copying database to security implementations...
if not exist "selective-security\" mkdir selective-security
if not exist "blanket-security\" mkdir blanket-security

copy /y lottery_data.db selective-security\lottery_data.db >nul
copy /y lottery_data.db blanket-security\lottery_data.db >nul
echo Database copied

echo.
echo ================================================================
echo                     SETUP COMPLETE
echo ================================================================
echo.
echo You can now run the demo using one of these methods:
echo.
echo METHOD 1: Run servers manually
echo    Terminal 1: cd selective-security ^&^& python app.py
echo    Terminal 2: cd blanket-security ^&^& python app.py
echo    Terminal 3: python test_performance.py
echo.
echo METHOD 2: Run automated test
echo    run_demo.bat
echo.
echo The demo will generate:
echo    - performance_comparison.png
echo    - performance_report.txt
echo    - pipeline_diagrams.png
echo.
pause