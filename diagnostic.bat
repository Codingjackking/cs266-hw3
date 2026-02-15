@echo off
REM Diagnostic Script - Check Setup
echo ================================================================
echo         LOTTERY ORACLE - DIAGNOSTIC CHECK
echo ================================================================
echo.

echo Current Directory:
echo %CD%
echo.

echo Checking Python...
python --version
if errorlevel 1 (
    echo ERROR: Python not found
    pause
    exit /b 1
)
echo.

echo Checking required packages...
python -c "import flask; print('  Flask:', flask.__version__)" 2>&1
python -c "import flask_cors; print('  Flask-CORS: OK')" 2>&1
python -c "import jwt; print('  PyJWT: OK')" 2>&1
python -c "import bcrypt; print('  Bcrypt: OK')" 2>&1
python -c "import pandas; print('  Pandas:', pandas.__version__)" 2>&1
python -c "import numpy; print('  Numpy:', numpy.__version__)" 2>&1
echo.

echo Checking directory structure...
if exist "selective-security" (
    echo  [OK] selective-security folder found
) else (
    echo  [ERROR] selective-security folder NOT found
)

if exist "blanket-security" (
    echo  [OK] blanket-security folder found
) else (
    echo  [ERROR] blanket-security folder NOT found
)

if exist "lottery_data.db" (
    echo  [OK] lottery_data.db found
) else (
    echo  [ERROR] lottery_data.db NOT found - run init_db.py
)

if exist "selective-security\lottery_data.db" (
    echo  [OK] selective-security\lottery_data.db found
) else (
    echo  [WARN] selective-security\lottery_data.db NOT found
    echo        Run: copy lottery_data.db selective-security\
)

if exist "blanket-security\lottery_data.db" (
    echo  [OK] blanket-security\lottery_data.db found
) else (
    echo  [WARN] blanket-security\lottery_data.db NOT found
    echo        Run: copy lottery_data.db blanket-security\
)

if exist "selective-security\app.py" (
    echo  [OK] selective-security\app.py found
) else (
    echo  [ERROR] selective-security\app.py NOT found
)

if exist "blanket-security\app.py" (
    echo  [OK] blanket-security\app.py found
) else (
    echo  [ERROR] blanket-security\app.py NOT found
)
echo.

echo Checking data directory...
if exist "data" (
    echo  [OK] data folder found
    dir /b data\*.csv 2>nul
) else (
    echo  [WARN] data folder NOT found - historical data not scraped
    echo        Run: python scrape_historical_data.py all
)
echo.

echo Testing selective-security app.py...
cd selective-security
python -c "import sys; sys.path.insert(0, '..'); import app" 2>&1
if errorlevel 1 (
    echo  [ERROR] Problem importing app.py
    echo.
    echo  Attempting to show the actual error...
    python app.py
) else (
    echo  [OK] app.py imports successfully
)
cd ..
echo.

echo Checking ports...
netstat -an | findstr "5001" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo  [WARN] Port 5001 is already in use
    echo        Kill the process or use a different port
) else (
    echo  [OK] Port 5001 is available
)

netstat -an | findstr "5002" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo  [WARN] Port 5002 is already in use
    echo        Kill the process or use a different port
) else (
    echo  [OK] Port 5002 is available
)
echo.

echo ================================================================
echo                  DIAGNOSTIC COMPLETE
echo ================================================================
echo.
echo If all checks passed, you can run: run_demo.bat
echo If there are errors, fix them and run this diagnostic again
echo.
pause