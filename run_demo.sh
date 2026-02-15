#!/bin/bash

# Lottery Oracle - Demo Runner
# Starts both security implementations and runs performance tests

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║        LOTTERY ORACLE - SECURITY COMPARISON DEMO            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check if database exists
if [ ! -f "lottery_data.db" ]; then
    echo "❌ Database not found. Please run ./setup.sh first"
    exit 1
fi

# Kill any existing Flask processes on ports 5001 and 5002
echo " Cleaning up existing processes..."
lsof -ti:5001 | xargs kill -9 2>/dev/null || true
lsof -ti:5002 | xargs kill -9 2>/dev/null || true
sleep 1

# Start selective security server
echo ""
echo " Starting Selective Security server on port 5001..."
cd selective-security
python3 app.py > /tmp/selective.log 2>&1 &
SELECTIVE_PID=$!
cd ..

# Wait for selective server to start
echo "   Waiting for server to start..."
for i in {1..10}; do
    if curl -s http://localhost:5001/api/health > /dev/null 2>&1; then
        echo "   ✅ Selective Security server ready (PID: $SELECTIVE_PID)"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "   ❌ Selective Security server failed to start"
        kill $SELECTIVE_PID 2>/dev/null || true
        exit 1
    fi
    sleep 1
done

# Start blanket security server
echo ""
echo " Starting Blanket Security server on port 5002..."
cd blanket-security
python3 app.py > /tmp/blanket.log 2>&1 &
BLANKET_PID=$!
cd ..

# Wait for blanket server to start
echo "   Waiting for server to start..."
for i in {1..10}; do
    if curl -s http://localhost:5002/api/register > /dev/null 2>&1; then
        echo "   ✅ Blanket Security server ready (PID: $BLANKET_PID)"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "   ❌ Blanket Security server failed to start"
        kill $SELECTIVE_PID 2>/dev/null || true
        kill $BLANKET_PID 2>/dev/null || true
        exit 1
    fi
    sleep 1
done

# Run performance tests
echo ""
echo " Running performance comparison tests..."
echo "   This will take approximately 2-3 minutes..."
echo ""

python3 test_performance.py

# Cleanup
echo ""
echo " Shutting down servers..."
kill $SELECTIVE_PID 2>/dev/null || true
kill $BLANKET_PID 2>/dev/null || true

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    DEMO COMPLETE                             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo " Results generated:"
echo "    performance_comparison.png - Visual comparison charts"
echo "    performance_report.txt - Detailed metrics report"
echo "    pipeline_diagrams.png - Architecture diagrams"
echo ""
echo " Documentation available:"
echo "    README.md - Project overview"
echo "    THREAT_MODEL.md - Security analysis (1-2 pages)"
echo "    COMPARISON_TABLE.md - Detailed comparison"
echo ""
echo "View the results:"
echo "   cat performance_report.txt"
echo "   open performance_comparison.png  # On macOS"
echo "   xdg-open performance_comparison.png  # On Linux"
echo ""
