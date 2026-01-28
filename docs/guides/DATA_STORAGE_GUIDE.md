# AlphaStock Data Storage Setup Guide

## Quick Start

Your AlphaStock system now includes a high-performance data storage layer with support for multiple backends. Here's how to get started:

### 1. Choose Your Database Backend

**For Development (Easiest):**
- PostgreSQL (you mentioned you have this)
- Works immediately with existing PostgreSQL installation

**For Production (Fastest):**
- ClickHouse for time-series data (recommended)
- Ultra-fast queries and analytics

**Caching Layer:**
- Redis for ultra-fast data access (optional but recommended)

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- `clickhouse-driver`, `clickhouse-connect` (ClickHouse support)
- `psycopg2-binary`, `SQLAlchemy` (PostgreSQL support)  
- `redis`, `hiredis` (Redis caching)

### 3. Database Setup

#### Option A: Interactive Setup (Recommended)
```bash
python setup_database.py
```

This script will:
- Guide you through database configuration
- Test connections
- Create the configuration file
- Show you next steps

#### Option B: Manual Configuration

Edit `config/database.json`:

**For PostgreSQL:**
```json
{
  "storage": {
    "type": "postgresql",
    "postgresql": {
      "host": "localhost",
      "port": 5432,
      "database": "alphastock",
      "username": "postgres",
      "password": "your_password"
    },
    "cache": {
      "enabled": true,
      "host": "localhost",
      "port": 6379
    }
  }
}
```

**For ClickHouse:**
```json
{
  "storage": {
    "type": "clickhouse",
    "clickhouse": {
      "host": "localhost", 
      "port": 8123,
      "database": "alphastock",
      "username": "default"
    },
    "cache": {
      "enabled": true,
      "host": "localhost",
      "port": 6379
    }
  }
}
```

### 4. Database Migration

Create the database schema:

```bash
python migrate_database.py
```

This will:
- Create all necessary tables
- Verify the setup
- Test core functionality

### 5. Verify Installation

```bash
python migrate_database.py --verify
```

This checks that everything is working correctly.

## Database Features

### Performance Optimized Storage

**ClickHouse Features:**
- Columnar storage for fast analytics
- Automatic data compression
- Partitioned tables by date
- Optimized for time-series queries
- Sub-second query performance

**PostgreSQL Features:**
- TimescaleDB support for time-series
- Proper indexing for fast lookups
- JSONB storage for metadata
- Full SQL compatibility

### Intelligent Caching

**Redis Caching Layer:**
- Sub-millisecond data access
- Automatic cache invalidation
- Intelligent TTL management
- Market data caching (60s TTL)
- Options data caching (120s TTL)
- Signal caching (600s TTL)

### Multi-Tier Architecture

```
┌─────────────────┐
│   Application   │
└─────────────────┘
         │
┌─────────────────┐
│ Hybrid Data     │  ← Cache-first queries
│ Layer           │  ← Automatic fallbacks
└─────────────────┘
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌──▼──┐
│ Redis │ │ DB  │  ← PostgreSQL or ClickHouse
│ Cache │ │     │
└───────┘ └─────┘
```

## Usage in Your Code

The orchestrator automatically uses the configured data layer:

```python
# In your strategies or runners
data = await self.data_layer.get_market_data('RELIANCE')
await self.data_layer.store_signal(signal_data)
```

### Available Methods

**Market Data:**
- `store_market_data(symbol, asset_type, data, runner_name)`
- `get_market_data(symbol, start_time, end_time, limit)`
- `get_latest_market_data(symbol)`

**Historical Data:**
- `store_historical_data(symbol, asset_type, data, timeframe)`
- `get_historical_data(symbol, timeframe, start_date, end_date)`

**Signals:**
- `store_signal(signal_data)`
- `get_signals(symbol, strategy, start_time, end_time)`

**Options Data:**
- `store_options_data(underlying, expiry_date, data)`
- `get_options_chain(underlying, expiry_date)`

**Performance Data:**
- `store_performance_data(strategy, symbol, performance_data)`
- `get_performance_summary(strategy, symbol, days)`

## Performance Tips

### For High-Frequency Data

1. **Use Batch Operations:**
   ```python
   await data_layer.batch_store_market_data(batch_data)
   ```

2. **Enable Caching:**
   - Redis cache dramatically improves read performance
   - Automatic cache-first queries for recent data

3. **Choose ClickHouse for Production:**
   - 10-100x faster for time-series analytics
   - Better compression (save disk space)
   - Handles millions of data points easily

### Memory Usage

**ClickHouse:** Very memory efficient due to columnar storage
**PostgreSQL:** More memory usage but full SQL features
**Redis:** Uses memory for caching but provides sub-ms access

## Troubleshooting

### Connection Issues

1. **Check Database Status:**
   ```bash
   python migrate_database.py --verify
   ```

2. **Test Individual Components:**
   ```python
   from src.data.data_layer_factory import data_layer_factory
   # Test connection
   ```

### Performance Issues

1. **Enable Query Logging:**
   Set `"log_slow_queries": true` in database.json

2. **Check Cache Hit Rates:**
   Monitor Redis for cache effectiveness

3. **Optimize Batch Sizes:**
   Adjust `"batch_size"` in performance settings

### Storage Issues

1. **Auto-cleanup:**
   Old data is automatically cleaned up based on retention settings

2. **Manual Optimization:**
   ```bash
   # The data layer includes optimize_storage() method
   ```

## Migration from Old System

The new data layer is backward compatible. Your existing file-based signals will be automatically migrated when the system starts.

## Next Steps

1. **Start with PostgreSQL** if you want immediate setup
2. **Move to ClickHouse** when you need better performance
3. **Enable Redis caching** for fastest data access
4. **Monitor performance** and adjust settings as needed

The system automatically handles failovers and provides detailed logging for troubleshooting.

---

**Need Help?**
- Check the logs for detailed error messages
- Use the health check endpoint: `await data_layer.health_check()`
- Run the migration script with `--verify` flag for diagnostics
