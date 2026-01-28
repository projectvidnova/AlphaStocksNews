# Database Queries Guide

## Overview

AlphaStocks uses **ClickHouse** database for high-performance time-series data storage. This guide shows you how to query stock data programmatically and via CLI.

---

## Database Tables

### Available Tables

1. **market_data** - Real-time market data
2. **historical_data** - Historical OHLC data
3. **trading_signals** - Generated trading signals
4. **options_data** - Options chain data
5. **strategy_performance** - Strategy backtest results

---

## Querying via Python Code

### 1. Using Data Layer (Recommended)

The easiest way is to use the built-in data layer:

```python
from src.data.clickhouse_data_layer import ClickHouseDataLayer
import asyncio
from datetime import datetime, timedelta

async def query_stocks():
    # Initialize data layer
    data_layer = ClickHouseDataLayer(
        host='localhost',
        port=8123,
        database='alphastock',
        username='default',
        password=''
    )
    
    await data_layer.initialize()
    
    # Query 1: Get latest market data for a stock
    latest_data = await data_layer.get_latest_market_data('RELIANCE')
    print(f"Latest RELIANCE data: {latest_data}")
    
    # Query 2: Get market data for specific time range
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=1)
    
    market_data = await data_layer.get_market_data(
        symbol='RELIANCE',
        start_time=start_time,
        end_time=end_time
    )
    print(f"Market data:\n{market_data}")
    
    # Query 3: Get historical data
    historical_data = await data_layer.get_historical_data(
        symbol='RELIANCE',
        timeframe='15minute',
        start_date=datetime.now() - timedelta(days=7),
        end_date=datetime.now()
    )
    print(f"Historical data:\n{historical_data}")
    
    # Query 4: Get trading signals
    signals = await data_layer.get_signals(
        symbol='RELIANCE',
        strategy='momentum',
        start_time=datetime.now() - timedelta(days=1)
    )
    print(f"Signals: {signals}")
    
    await data_layer.close()

# Run the query
asyncio.run(query_stocks())
```

### 2. Direct ClickHouse Client

For advanced queries:

```python
import clickhouse_connect
import pandas as pd

# Connect to ClickHouse
client = clickhouse_connect.get_client(
    host='localhost',
    port=8123,
    database='alphastock'
)

# Query 1: Get latest prices for all stocks
query = """
    SELECT symbol, ltp, price_change_pct, volume, timestamp
    FROM market_data
    WHERE asset_type = 'STOCK'
    ORDER BY timestamp DESC
    LIMIT 10
"""
result_df = client.query_df(query)
print(result_df)

# Query 2: Get top gainers today
query = """
    SELECT 
        symbol,
        MAX(price_change_pct) as max_gain,
        MAX(ltp) as current_price
    FROM market_data
    WHERE date = today()
    GROUP BY symbol
    ORDER BY max_gain DESC
    LIMIT 10
"""
top_gainers = client.query_df(query)
print(top_gainers)

# Query 3: Get stock data for specific symbols
symbols = ['RELIANCE', 'TCS', 'INFY']
query = """
    SELECT symbol, ltp, open, high, low, volume, timestamp
    FROM market_data
    WHERE symbol IN %(symbols)s
    ORDER BY timestamp DESC
    LIMIT 100
"""
result = client.query_df(query, parameters={'symbols': symbols})
print(result)

# Query 4: Get trading signals for today
query = """
    SELECT 
        symbol,
        strategy,
        action,
        price,
        confidence,
        target,
        stop_loss,
        timestamp
    FROM trading_signals
    WHERE date = today()
    ORDER BY timestamp DESC
"""
signals = client.query_df(query)
print(signals)

# Close connection
client.close()
```

---

## Querying via Docker CLI

### Connect to ClickHouse Container

```powershell
# Enter ClickHouse client
docker exec -it alphastock-clickhouse clickhouse-client --database=alphastock
```

### Example Queries

Once connected, run these SQL queries:

```sql
-- Query 1: List all available stocks
SELECT DISTINCT symbol 
FROM market_data 
WHERE asset_type = 'STOCK'
ORDER BY symbol;

-- Query 2: Get latest data for RELIANCE
SELECT symbol, ltp, price_change_pct, volume, timestamp
FROM market_data
WHERE symbol = 'RELIANCE'
ORDER BY timestamp DESC
LIMIT 10;

-- Query 3: Get top 10 gainers today
SELECT 
    symbol,
    MAX(price_change_pct) as gain_percent,
    MAX(ltp) as latest_price,
    MAX(volume) as volume
FROM market_data
WHERE date = today()
GROUP BY symbol
ORDER BY gain_percent DESC
LIMIT 10;

-- Query 4: Get historical data for last 7 days
SELECT 
    date,
    symbol,
    open,
    high,
    low,
    close,
    volume
FROM historical_data
WHERE symbol = 'RELIANCE'
  AND date >= today() - INTERVAL 7 DAY
ORDER BY timestamp DESC;

-- Query 5: Get trading signals
SELECT 
    symbol,
    strategy,
    action,
    price,
    confidence,
    timestamp
FROM trading_signals
WHERE date = today()
ORDER BY timestamp DESC
LIMIT 20;

-- Query 6: Get options data for Nifty
SELECT 
    strike,
    option_type,
    ltp,
    implied_volatility,
    open_interest,
    delta
FROM options_data
WHERE underlying = 'NIFTY'
  AND expiry_date = (SELECT MIN(expiry_date) FROM options_data WHERE underlying = 'NIFTY')
ORDER BY strike;

-- Query 7: Database statistics
SELECT 
    table,
    sum(rows) as total_rows,
    formatReadableSize(sum(bytes)) as size
FROM system.parts
WHERE database = 'alphastock'
  AND active = 1
GROUP BY table
ORDER BY sum(bytes) DESC;
```

---

## Common Use Cases

### 1. Check if Data is Being Stored

```python
from src.data.clickhouse_data_layer import ClickHouseDataLayer
import asyncio

async def check_data():
    data_layer = ClickHouseDataLayer()
    await data_layer.initialize()
    
    # Check latest market data
    latest = await data_layer.get_latest_market_data('RELIANCE')
    
    if latest is not None:
        print(f"✅ Data is being stored")
        print(f"Latest timestamp: {latest['timestamp']}")
        print(f"Latest price: {latest['ltp']}")
    else:
        print("❌ No data found")
    
    await data_layer.close()

asyncio.run(check_data())
```

### 2. Monitor Specific Stock

```python
from src.data.clickhouse_data_layer import ClickHouseDataLayer
import asyncio
from datetime import datetime, timedelta

async def monitor_stock(symbol: str):
    data_layer = ClickHouseDataLayer()
    await data_layer.initialize()
    
    # Get last 1 hour of data
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=1)
    
    data = await data_layer.get_market_data(
        symbol=symbol,
        start_time=start_time,
        end_time=end_time
    )
    
    if not data.empty:
        print(f"\n{symbol} - Last 1 Hour Data:")
        print(f"Current Price: {data['ltp'].iloc[-1]}")
        print(f"High: {data['high'].max()}")
        print(f"Low: {data['low'].min()}")
        print(f"Volume: {data['volume'].sum()}")
        print(f"Price Change: {data['price_change_pct'].iloc[-1]}%")
    else:
        print(f"No data found for {symbol}")
    
    await data_layer.close()

# Usage
asyncio.run(monitor_stock('RELIANCE'))
```

### 3. Get All Signals for a Strategy

```python
from src.data.clickhouse_data_layer import ClickHouseDataLayer
import asyncio
from datetime import datetime, timedelta

async def get_strategy_signals(strategy_name: str):
    data_layer = ClickHouseDataLayer()
    await data_layer.initialize()
    
    # Get signals from last 24 hours
    signals = await data_layer.get_signals(
        strategy=strategy_name,
        start_time=datetime.now() - timedelta(days=1)
    )
    
    print(f"\n{strategy_name} Strategy Signals (Last 24h):")
    for signal in signals:
        print(f"\n{signal['timestamp']} - {signal['symbol']}")
        print(f"  Action: {signal['action']}")
        print(f"  Price: {signal['price']}")
        print(f"  Target: {signal['target']}")
        print(f"  Stop Loss: {signal['stop_loss']}")
        print(f"  Confidence: {signal['confidence']}")
    
    await data_layer.close()

# Usage
asyncio.run(get_strategy_signals('momentum'))
```

### 4. Export Data to CSV

```python
from src.data.clickhouse_data_layer import ClickHouseDataLayer
import asyncio
from datetime import datetime, timedelta

async def export_to_csv(symbol: str, days: int = 7):
    data_layer = ClickHouseDataLayer()
    await data_layer.initialize()
    
    # Get historical data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    data = await data_layer.get_historical_data(
        symbol=symbol,
        timeframe='15minute',
        start_date=start_date,
        end_date=end_date
    )
    
    if not data.empty:
        filename = f"{symbol}_{days}days.csv"
        data.to_csv(filename)
        print(f"✅ Exported {len(data)} records to {filename}")
    else:
        print(f"❌ No data found for {symbol}")
    
    await data_layer.close()

# Usage
asyncio.run(export_to_csv('RELIANCE', days=7))
```

---

## Quick Reference Commands

### Via Python CLI

```bash
# Activate virtual environment
venv\Scripts\activate

# Run Python query script
python your_query_script.py
```

### Via Docker

```powershell
# One-line query (from PowerShell)
docker exec alphastock-clickhouse clickhouse-client --database=alphastock --query="SELECT COUNT(*) FROM market_data"

# Interactive mode
docker exec -it alphastock-clickhouse clickhouse-client --database=alphastock
```

### Available Data Layer Methods

| Method | Description |
|--------|-------------|
| `get_market_data(symbol, start_time, end_time, limit)` | Get market data for symbol |
| `get_latest_market_data(symbol)` | Get latest market data point |
| `get_historical_data(symbol, timeframe, start_date, end_date)` | Get historical OHLC data |
| `get_signals(symbol, strategy, start_time, end_time)` | Get trading signals |
| `get_options_data(underlying, expiry_date, option_type)` | Get options chain data |

---

## Database Schema

### market_data Table

| Column | Type | Description |
|--------|------|-------------|
| timestamp | DateTime64 | Data timestamp |
| symbol | String | Stock symbol |
| asset_type | String | STOCK/INDEX/OPTION |
| ltp | Float64 | Last traded price |
| open | Float64 | Opening price |
| high | Float64 | High price |
| low | Float64 | Low price |
| close | Float64 | Closing price |
| volume | UInt64 | Trading volume |
| price_change_pct | Float64 | % price change |
| volatility | Float64 | Volatility |

### historical_data Table

| Column | Type | Description |
|--------|------|-------------|
| timestamp | DateTime | Candle timestamp |
| symbol | String | Stock symbol |
| timeframe | String | 5minute/15minute/day |
| open | Float64 | Open price |
| high | Float64 | High price |
| low | Float64 | Low price |
| close | Float64 | Close price |
| volume | UInt64 | Volume |

### trading_signals Table

| Column | Type | Description |
|--------|------|-------------|
| timestamp | DateTime64 | Signal timestamp |
| signal_id | String | Unique signal ID |
| symbol | String | Stock symbol |
| strategy | String | Strategy name |
| action | String | BUY/SELL/HOLD |
| price | Float64 | Signal price |
| target | Float64 | Target price |
| stop_loss | Float64 | Stop loss price |
| confidence | Float64 | Signal confidence |

---

## Troubleshooting

### Connection Issues

```python
# Test connection
import clickhouse_connect

try:
    client = clickhouse_connect.get_client(
        host='localhost',
        port=8123,
        database='alphastock'
    )
    result = client.query("SELECT 1")
    print("✅ Connection successful")
except Exception as e:
    print(f"❌ Connection failed: {e}")
```

### No Data Found

1. **Check if data is being stored:**
   ```sql
   SELECT COUNT(*) FROM market_data;
   ```

2. **Check latest timestamp:**
   ```sql
   SELECT MAX(timestamp) FROM market_data;
   ```

3. **Verify real-time system is running:**
   ```bash
   python main.py
   ```

### Performance Issues

For large queries, use time filters:

```python
# Good - Uses time filter
data = await data_layer.get_market_data(
    symbol='RELIANCE',
    start_time=datetime.now() - timedelta(hours=1),
    limit=100
)

# Bad - Retrieves all data
data = await data_layer.get_market_data(symbol='RELIANCE')
```

---

## See Also

- [Project Structure](PROJECT_STRUCTURE.md) - Application architecture
- [Quick Start](QUICK_START.md) - Getting started guide
- [Production Deployment](PRODUCTION_DEPLOYMENT.md) - Production setup

---

*Last Updated: October 7, 2025*


SHOW DATABASES;

SHOW TABLES FROM alphastock;

SELECT * FROM alphastock.market_data 
ORDER BY timestamp DESC 
LIMIT 100;


