#!/bin/bash
# Start AlphaStock Trading System

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🚀 Starting AlphaStock Trading System${NC}"
echo "======================================"

# Start ClickHouse if not running
if ! docker ps | grep -q "alphastock-clickhouse"; then
    echo "Starting ClickHouse database..."
    docker start alphastock-clickhouse
    sleep 5
fi

# Activate Python environment
source .venv/bin/activate

# Start the scheduler (this will start the main application)
echo -e "${GREEN}✅ Starting AlphaStock Scheduler...${NC}"
nohup python scheduler.py > logs/alphastock.log 2>&1 &
echo $! > alphastock.pid

echo -e "${GREEN}✅ AlphaStock Trading System Started${NC}"
echo "PID: $(cat alphastock.pid)"
echo "Logs: tail -f logs/alphastock.log"
echo "Stop with: ./stop_alphastock.sh"
