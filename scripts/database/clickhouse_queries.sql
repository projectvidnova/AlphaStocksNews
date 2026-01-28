-- AlphaStock ClickHouse Queries\n\n-- View Recent Data\nSELECT * FROM historical_data ORDER BY timestamp DESC LIMIT 10;\n\n-- Bank Nifty Summary\nSELECT 
    symbol,
    timeframe,
    COUNT(*) as data_points,
    MIN(timestamp) as first_date,
    MAX(timestamp) as last_date,
    AVG(close) as avg_price
FROM historical_data 
WHERE symbol = 'BANKNIFTY' 
GROUP BY symbol, timeframe;\n\n-- Daily Price Range\nSELECT 
    toDate(timestamp) as date,
    MIN(low) as daily_low,
    MAX(high) as daily_high,
    (MAX(high) - MIN(low)) as range
FROM historical_data 
WHERE symbol = 'BANKNIFTY'
GROUP BY toDate(timestamp)
ORDER BY date DESC;\n\n-- Moving Average\nSELECT 
    timestamp,
    close,
    avg(close) OVER (
        ORDER BY timestamp 
        ROWS 9 PRECEDING
    ) as sma_10
FROM historical_data 
WHERE symbol = 'BANKNIFTY' 
ORDER BY timestamp DESC 
LIMIT 20;\n\n