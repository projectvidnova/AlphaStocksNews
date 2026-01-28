#!/bin/bash

# AlphaStock ClickHouse Setup - High-Performance Trading Data Storage
# Optimized for Bank Nifty and real-time trading data

echo "🏠 CLICKHOUSE SETUP FOR ALPHASTOCK"
echo "=================================="
echo "Setting up ultra-fast time-series database for trading data"
echo ""

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew not found. Installing Homebrew first..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

echo "🍺 Updating Homebrew..."
brew update

echo ""
echo "🏠 Installing ClickHouse..."
brew install clickhouse

echo ""
echo "🚀 Starting ClickHouse service..."
brew services start clickhouse

echo ""
echo "⏳ Waiting for ClickHouse to start..."
sleep 10

echo ""
echo "🔧 Creating AlphaStock database and tables..."

# Create the main database
clickhouse-client --query="CREATE DATABASE IF NOT EXISTS alphastock" 

# Create historical data table optimized for trading
clickhouse-client --database=alphastock --query="
CREATE TABLE IF NOT EXISTS historical_data (
    symbol String,
    timeframe String, 
    timestamp DateTime64(3),
    open Float64,
    high Float64,
    low Float64,
    close Float64,
    volume UInt64,
    created_at DateTime64(3) DEFAULT now64()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (symbol, timeframe, timestamp)
SETTINGS index_granularity = 8192
"

# Create real-time data table for live trading
clickhouse-client --database=alphastock --query="
CREATE TABLE IF NOT EXISTS realtime_data (
    symbol String,
    timestamp DateTime64(3),
    price Float64,
    volume UInt64,
    bid Float64,
    ask Float64,
    created_at DateTime64(3) DEFAULT now64()
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp) 
ORDER BY (symbol, timestamp)
SETTINGS index_granularity = 8192
"

# Create trading signals table
clickhouse-client --database=alphastock --query="
CREATE TABLE IF NOT EXISTS trading_signals (
    id String,
    symbol String,
    strategy String,
    signal_type Enum8('BUY' = 1, 'SELL' = 2, 'HOLD' = 3),
    entry_price Float64,
    stop_loss Float64,
    target Float64,
    timestamp DateTime64(3),
    status Enum8('NEW' = 1, 'ACTIVE' = 2, 'FILLED' = 3, 'CANCELLED' = 4, 'EXPIRED' = 5),
    exit_price Nullable(Float64),
    exit_timestamp Nullable(DateTime64(3)),
    profit_loss Nullable(Float64),
    created_at DateTime64(3) DEFAULT now64()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (symbol, strategy, timestamp)
SETTINGS index_granularity = 8192
"

# Create performance tracking table
clickhouse-client --database=alphastock --query="
CREATE TABLE IF NOT EXISTS strategy_performance (
    strategy String,
    symbol String,
    date Date,
    total_signals UInt32,
    winning_signals UInt32,
    losing_signals UInt32,
    total_profit_loss Float64,
    win_rate Float64,
    avg_profit Float64,
    avg_loss Float64,
    max_drawdown Float64,
    created_at DateTime64(3) DEFAULT now64()
) ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (strategy, symbol, date)
SETTINGS index_granularity = 8192
"

echo ""
echo "✅ CLICKHOUSE SETUP COMPLETE!"
echo ""
echo "🎯 DATABASE DETAILS:"
echo "   Database: alphastock"
echo "   Host: localhost"
echo "   Port: 8123"
echo "   HTTP Interface: http://localhost:8123"
echo ""
echo "📊 TABLES CREATED:"
echo "   ✅ historical_data - OHLCV data with partitioning by month"
echo "   ✅ realtime_data - Live tick data with daily partitioning" 
echo "   ✅ trading_signals - All trading signals and outcomes"
echo "   ✅ strategy_performance - Performance metrics by strategy"
echo ""
echo "🚀 OPTIMIZATIONS ENABLED:"
echo "   • Monthly/Daily partitioning for fast queries"
echo "   • Sorted by symbol and timestamp"
echo "   • Optimized for time-series analytics"
echo "   • Ready for millions of data points"
echo ""
echo "🔍 TO TEST:"
echo "   python3 data_inspector.py"
echo ""
echo "💡 TO POPULATE WITH BANK NIFTY DATA:"
echo "   python3 scheduler.py --manual-start"

# Test the connection
echo ""
echo "🧪 TESTING CONNECTION..."
result=$(clickhouse-client --database=alphastock --query="SELECT 'ClickHouse is ready for AlphaStock!' as message" 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "✅ $result"
else
    echo "⚠️ Connection test failed, but ClickHouse should be running"
fi

echo ""
echo "🎉 Your high-performance trading database is ready!"
