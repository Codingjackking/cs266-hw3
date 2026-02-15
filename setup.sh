#!/bin/bash

# Lottery Oracle - Security Demo Setup Script
# This script initializes the database and helps run the security comparison demo

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     LOTTERY ORACLE - SECURITY COMPARISON DEMO SETUP         ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check Python version
echo " Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "✅ Found Python $PYTHON_VERSION"

# Install dependencies
echo ""
echo " Installing Python dependencies..."
pip3 install --quiet flask flask-cors pyjwt bcrypt numpy pandas requests matplotlib beautifulsoup4 2>/dev/null || pip3 install flask flask-cors pyjwt bcrypt numpy pandas requests matplotlib beautifulsoup4

echo "✅ Dependencies installed"

# Check for historical data
echo ""
echo " Checking for historical lottery data..."

if [ ! -d "data" ] || [ ! -f "data/powerball_results.csv" ]; then
    echo "  Historical lottery data not found!"
    echo ""
    echo " Do you want to scrape REAL historical lottery data now?"
    echo "   This will take approximately 5-10 minutes and requires internet connection."
    echo ""
    read -p "Scrape data now? (y/n) " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🕸️  Scraping historical lottery data..."
        python3 scrape_historical_data.py all
        
        if [ $? -eq 0 ]; then
            echo "✅ Historical data scraped successfully"
        else
            echo "❌ Data scraping failed. You can run it manually later:"
            echo "   python3 scrape_historical_data.py all"
        fi
    else
        echo "⏩ Skipping data scraping. You can run it later with:"
        echo "   python3 scrape_historical_data.py all"
    fi
else
    echo "✅ Historical lottery data found"
fi

# Initialize database
echo ""
echo "  Initializing lottery database..."
python3 init_db.py

if [ $? -eq 0 ]; then
    echo "✅ Database initialized successfully"
else
    echo "❌ Database initialization failed"
    exit 1
fi

# Copy database to both security version directories
echo ""
echo " Copying database to security implementations..."
cp lottery_data.db selective-security/lottery_data.db
cp lottery_data.db blanket-security/lottery_data.db
echo "✅ Database copied"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    SETUP COMPLETE                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "You can now run the demo using one of these methods:"
echo ""
echo "📍 METHOD 1: Run servers manually"
echo "   Terminal 1: cd selective-security && python3 app.py"
echo "   Terminal 2: cd blanket-security && python3 app.py"
echo "   Terminal 3: python3 test_performance.py"
echo ""
echo "📍 METHOD 2: Run automated test"
echo "   ./run_demo.sh"
echo ""
echo " The demo will generate:"
echo "   - performance_comparison.png"
echo "   - performance_report.txt"
echo "   - pipeline_diagrams.png"
echo ""
