# Quick Start: Historical Data Pipeline

## What Changed?

**Before:** Strategies analyzed only ~8 minutes of cached real-time ticks
**Now:** Strategies analyze 20-60 days of historical data + real-time candles

## For Strategy Developers

### 1. Your Strategy Now Receives Proper Data

Instead of:
```python
# OLD: Only 8 minutes of 5-second ticks
def analyze(self, symbol, historical_data):
    # historical_data: ~100 rows of ticks
    # Too little data for meaningful analysis
```

You now get:
```python
# NEW: 20-60 days of proper candles
def analyze(self, symbol, historical_data):
    # historical_data: 1000+ rows of 15-minute OHLCV candles
    # Sufficient for MA crossovers, S/R detection, trend analysis
    # Columns: timestamp, open, high, low, close, volume
```

### 2. Configure Your Strategy's Data Requirements

In `config/production.json`:

```json
{
  "your_strategy": {
    "enabled": true,
    "timeframe": "15minute",           // Required: Candle timeframe
    "historical_lookback": {           // Required: How much history
      "periods": 1000,                 // Number of candles
      "days": 20,                      // Approximate days
      "min_periods": 50                // Minimum required
    },
    "realtime_aggregation": {          // Optional: Real-time settings
      "enabled": true,
      "match_historical_timeframe": true
    },
    "cache": {                         // Optional: Cache settings
      "enabled": true,
      "refresh_interval_seconds": 300,
      "preload_on_startup": true
    }
  }
}
```

### 3. Choosing the Right Timeframe

| Strategy Type | Recommended Timeframe | Lookback | Min Periods |
|--------------|----------------------|----------|-------------|
| **Scalping** | 1minute | 500 periods (8 hours) | 50 |
| **Intraday** | 5minute | 500 periods (3 days) | 78 |
| **Swing** | 15minute | 1000 periods (20 days) | 50 |
| **Position** | 60minute/day | 500 periods (60 days) | 30 |

### 4. Strategy Code (No Changes Needed!)

Your existing strategy code works unchanged:

```python
class MyStrategy(BaseStrategy):
    def analyze(self, symbol: str, historical_data: pd.DataFrame) -> TradingSignal:
        # historical_data is now complete with historical + real-time data
        
        # Calculate indicators as before
        data = historical_data.copy()
        data['MA_fast'] = data['close'].rolling(window=9).mean()
        data['MA_slow'] = data['close'].rolling(window=21).mean()
        
        # Generate signals
        if data['MA_fast'].iloc[-1] > data['MA_slow'].iloc[-1]:
            return TradingSignal(action="BUY", ...)
        
        return TradingSignal(action="HOLD", ...)
```

## For System Operators

### Quick Health Check

**1. Check Initialization Logs:**
```bash
# Look for these messages in logs/AlphaStockOrchestrator.log
grep "CandleAggregator initialized" logs/AlphaStockOrchestrator.log
grep "HistoricalDataCache initialized" logs/AlphaStockOrchestrator.log
grep "StrategyDataManager initialized" logs/AlphaStockOrchestrator.log
```

Expected output:
```
INFO - CandleAggregator initialized for 15minute timeframe
INFO - HistoricalDataCache initialized with 300s refresh interval
INFO - StrategyDataManager initialized successfully
```

**2. Check Strategy Execution:**
```bash
# Look for data size in strategy logs
grep "analyzed.*candles" logs/AlphaStockOrchestrator.log | tail -5
```

Expected output:
```
INFO - Strategy 'ma_crossover' generated BUY signal for 'SBIN' at price 745.50 (confidence: 75.00%) [analyzed 1000 candles]
```

If you see **"[analyzed 1000 candles]"** → ✅ Working correctly
If you see **"[analyzed 100 candles]"** → ⚠️ Using legacy flow (check errors)

**3. Check Cache Performance:**
```bash
# Search for cache statistics
grep "cache_hits" logs/AlphaStockOrchestrator.log | tail -1
```

Expected hit rate: **>80%**

### Memory Usage

Monitor with:
```bash
# Linux/Mac
ps aux | grep python | grep main.py

# Expected memory: Base + (50 MB × enabled_strategies)
# Example: 200 MB base + 50 MB data pipeline = 250 MB total
```

### Common Issues

**Issue:** "No historical data available"
**Solution:** Check database has data for the symbol and timeframe

**Issue:** Cache hit rate < 50%
**Solution:** Increase `refresh_interval_seconds` in config (default 300)

**Issue:** High memory usage
**Solution:** Reduce `lookback.periods` in strategy configurations

## Architecture Quick Reference

```
Tick Data (5-sec)  →  CandleAggregator  →  15-min Candles
                              ↓
                     Real-time Candles (last ~100)
                              ↓
Historical DB  →  HistoricalCache  →  Historical Candles (last 1000)
                              ↓
              StrategyDataManager.get_strategy_data()
                              ↓
                 Merged Dataset (1000+ candles)
                              ↓
                   strategy.analyze()
```

## File Locations

**New Components:**
- `src/core/candle_aggregator.py` - Tick-to-candle conversion
- `src/core/historical_data_cache.py` - Smart caching layer
- `src/core/strategy_data_manager.py` - Data coordination

**Modified:**
- `src/orchestrator.py` - Integration with new pipeline
- `config/production.json` - All strategies updated

**Documentation:**
- `docs/HISTORICAL_DATA_PIPELINE_IMPLEMENTATION.md` - Full details
- `docs/HISTORICAL_DATA_REQUIREMENTS_ANALYSIS.md` - Original analysis

## Testing Checklist

Before deploying to production:

- [ ] Check initialization logs for all 3 components
- [ ] Verify strategies receive >500 candles (check logs)
- [ ] Monitor cache hit rate (should be >80% after 10 minutes)
- [ ] Verify memory usage is acceptable (<500 MB for 5 symbols)
- [ ] Test with one strategy enabled first
- [ ] Gradually enable more strategies
- [ ] Monitor for errors in logs

## Performance Expectations

**Startup Time:**
- With preload: +10-30 seconds (loads historical data)
- Without preload: Same as before (loads on demand)

**Runtime:**
- Real-time tick processing: <10ms per tick
- Strategy execution: 50-200ms per strategy (depends on complexity)
- Cache queries: <1ms (cached), 100-500ms (DB fetch)

**Resource Usage:**
- Memory: +50 MB per 5 symbols
- CPU: +5-10% during strategy execution
- Database: -90% queries (due to caching)

## Need Help?

**Logs to check:**
1. `logs/AlphaStockOrchestrator.log` - Main orchestrator logs
2. `logs/candle_aggregator.log` - Aggregator-specific logs
3. `logs/historical_data_cache.log` - Cache-specific logs
4. `logs/strategy_data_manager.log` - Data manager logs

**Key metrics to monitor:**
- Cache hit rate (aim for >80%)
- Average data size per strategy execution (aim for 500-1000 candles)
- Memory usage (should be stable)
- Strategy execution time (should be <500ms)

**Debug mode:**
Set logging level to DEBUG in `config/production.json`:
```json
{
  "logging": {
    "level": "DEBUG"
  }
}
```
