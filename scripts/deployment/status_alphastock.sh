#!/bin/bash
# Check AlphaStock Trading System Status

BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}📊 AlphaStock Trading System Status${NC}"
echo "===================================="

# Check main application
if [ -f "alphastock.pid" ]; then
    PID=$(cat alphastock.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo -e "Main Application: ${GREEN}✅ Running (PID: $PID)${NC}"
    else
        echo -e "Main Application: ${RED}❌ Not Running${NC}"
    fi
else
    echo -e "Main Application: ${RED}❌ PID file not found${NC}"
fi

# Check ClickHouse
if docker ps | grep -q "alphastock-clickhouse"; then
    echo -e "ClickHouse Database: ${GREEN}✅ Running${NC}"
    # Test connection
    if docker exec alphastock-clickhouse clickhouse-client --query "SELECT 1" &> /dev/null; then
        echo -e "Database Connection: ${GREEN}✅ OK${NC}"
    else
        echo -e "Database Connection: ${RED}❌ Failed${NC}"
    fi
else
    echo -e "ClickHouse Database: ${RED}❌ Not Running${NC}"
fi

# Check logs
echo ""
echo "Recent Log Entries:"
if [ -f "logs/alphastock.log" ]; then
    tail -5 logs/alphastock.log
else
    echo "No log file found"
fi

echo ""
echo "Commands:"
echo "  Start:  ./start_alphastock.sh"
echo "  Stop:   ./stop_alphastock.sh"
echo "  Logs:   tail -f logs/alphastock.log"
