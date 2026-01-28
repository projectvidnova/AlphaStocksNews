#!/bin/bash
# ClickHouse Analytics Demo
# Show the power of ClickHouse for trading data analysis

echo "🚀 CLICKHOUSE TRADING ANALYTICS DEMO"
echo "===================================="

echo ""
echo "📊 HISTORICAL DATA ANALYSIS"
echo "----------------------------"

echo "📈 Bank Nifty Daily OHLC Summary:"
docker exec alphastock-clickhouse clickhouse-client --database=alphastock --query="
SELECT 
    symbol,
    COUNT(*) as days,
    MIN(low) as lowest_price,
    MAX(high) as highest_price,
    AVG(close) as avg_close,
    (MAX(high) - MIN(low)) / MIN(low) * 100 as price_range_pct
FROM historical_data 
GROUP BY symbol
FORMAT PrettyCompact"

echo ""
echo "📊 Daily Price Movement Analysis:"
docker exec alphastock-clickhouse clickhouse-client --database=alphastock --query="
SELECT 
    symbol,
    timestamp,
    close,
    (close - open) as daily_change,
    ((close - open) / open * 100) as daily_change_pct,
    (high - low) as intraday_range,
    ((high - low) / open * 100) as volatility_pct
FROM historical_data 
ORDER BY timestamp
FORMAT PrettyCompact"

echo ""
echo "🎯 TRADING SIGNALS ANALYSIS"
echo "----------------------------"

echo "📈 Signal Summary by Strategy:"
docker exec alphastock-clickhouse clickhouse-client --database=alphastock --query="
SELECT 
    strategy,
    symbol,
    signal_type,
    COUNT(*) as signal_count,
    AVG(entry_price) as avg_entry_price,
    MIN(entry_price) as min_entry,
    MAX(entry_price) as max_entry
FROM trading_signals 
GROUP BY strategy, symbol, signal_type
ORDER BY signal_count DESC
FORMAT PrettyCompact"

echo ""
echo "⏰ Signals Timeline:"
docker exec alphastock-clickhouse clickhouse-client --database=alphastock --query="
SELECT 
    id,
    symbol,
    signal_type,
    entry_price,
    stop_loss,
    target,
    timestamp,
    status
FROM trading_signals 
ORDER BY timestamp DESC
FORMAT PrettyCompact"

echo ""
echo "💰 Risk-Reward Analysis:"
docker exec alphastock-clickhouse clickhouse-client --database=alphastock --query="
SELECT 
    symbol,
    strategy,
    signal_type,
    entry_price,
    stop_loss,
    target,
    (entry_price - stop_loss) as risk,
    (target - entry_price) as reward,
    (target - entry_price) / (entry_price - stop_loss) as risk_reward_ratio
FROM trading_signals
WHERE signal_type = 'SELL'
FORMAT PrettyCompact"

echo ""
echo "⚡ PERFORMANCE METRICS"
echo "----------------------"

echo "🗂️ Database Size and Performance:"
docker exec alphastock-clickhouse clickhouse-client --database=alphastock --query="
SELECT 
    table,
    sum(rows) as total_rows,
    formatReadableSize(sum(data_compressed_bytes)) as compressed_size,
    formatReadableSize(sum(data_uncompressed_bytes)) as uncompressed_size
FROM system.parts 
WHERE database = 'alphastock' AND active = 1
GROUP BY table
FORMAT PrettyCompact"

echo ""
echo "✅ ClickHouse is now ready for high-performance trading analytics!"
echo "🔍 Connect directly: docker exec -it alphastock-clickhouse clickhouse-client --database=alphastock"
