#!/bin/bash
# Stop AlphaStock Trading System

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${RED}🛑 Stopping AlphaStock Trading System${NC}"
echo "====================================="

# Stop the main application
if [ -f "alphastock.pid" ]; then
    PID=$(cat alphastock.pid)
    if ps -p $PID > /dev/null 2>&1; then
        kill $PID
        echo -e "${GREEN}✅ AlphaStock process stopped (PID: $PID)${NC}"
    else
        echo "Process not running"
    fi
    rm -f alphastock.pid
else
    echo "PID file not found, trying to find process..."
    pkill -f "python scheduler.py" && echo -e "${GREEN}✅ AlphaStock processes stopped${NC}" || echo "No processes found"
fi

# Optionally stop ClickHouse (uncomment if you want to stop it)
# docker stop alphastock-clickhouse

echo -e "${GREEN}✅ AlphaStock Trading System Stopped${NC}"
