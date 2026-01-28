#!/bin/bash
# AlphaStock Quick Reference Card
# Essential commands for daily operations

echo "🚀 ALPHASTOCK QUICK REFERENCE"
echo "============================="
echo ""
echo "📋 SYSTEM MANAGEMENT:"
echo "  Start System:     ./start_alphastock.sh"
echo "  Stop System:      ./stop_alphastock.sh" 
echo "  Check Status:     ./status_alphastock.sh"
echo "  View Dashboard:   python dashboard.py (http://localhost:8080)"
echo ""
echo "📊 MONITORING:"
echo "  Real-time Logs:   tail -f logs/alphastock.log"
echo "  Error Logs:       tail -f logs/scheduler_error.log"
echo "  System Resources: htop"
echo "  Docker Stats:     docker stats alphastock-clickhouse"
echo ""
echo "🗄️ DATABASE:"
echo "  Connect DB:       docker exec -it alphastock-clickhouse clickhouse-client --database=alphastock"
echo "  Check Data:       SELECT * FROM historical_data LIMIT 5;"
echo "  Check Signals:    SELECT * FROM trading_signals ORDER BY timestamp DESC LIMIT 5;"
echo "  Database Size:    SELECT table, sum(bytes) FROM system.parts WHERE database='alphastock' GROUP BY table;"
echo ""
echo "🔧 TROUBLESHOOTING:"
echo "  Check API:        python -c \"from src.api.kite_client import *; print('API OK')\""
echo "  Restart DB:       docker restart alphastock-clickhouse"
echo "  Clear Logs:       > logs/alphastock.log"
echo "  Check Processes:  ps aux | grep python"
echo ""
echo "📁 KEY FILES:"
echo "  API Config:       .env.dev"
echo "  Database Config:  config/database.json"
echo "  Trading Config:   config/production.json"
echo "  Main Logs:        logs/alphastock.log"
echo ""
echo "🎯 NEXT STEPS:"
if [ ! -f ".env.dev" ]; then
    echo "  1. ❌ Configure API credentials in .env.dev"
else
    echo "  1. ✅ API credentials configured"
fi

if [ -f "alphastock.pid" ]; then
    PID=$(cat alphastock.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "  2. ✅ System is running (PID: $PID)"
    else
        echo "  2. ❌ Start the system: ./start_alphastock.sh"
    fi
else
    echo "  2. ❌ Start the system: ./start_alphastock.sh"
fi

if docker ps | grep -q "alphastock-clickhouse"; then
    echo "  3. ✅ Database is running"
else
    echo "  3. ❌ Start database: docker start alphastock-clickhouse"
fi

echo "  4. 📊 Monitor via dashboard: python dashboard.py"
echo "  5. 📈 Test paper trading for 1 week minimum"
echo ""
echo "💡 TIP: Bookmark this command: ./quick_reference.sh"
