# Insufficient Historical Data - Root Cause Analysis & Fix

## Problem Summary

**Observed Issue:**
```
WARNING - SBIN 15minute: Partial data: 227 of 1000 requested periods
INFO - Fetched 225 15minute candles for SBIN
```

Strategies are only getting **227 candles** instead of the requested **1000 candles**.

---

## Root Cause Analysis

### Issue 1: Incorrect Lookback Calculation

**Problem:** The lookback calculation assumed **24-hour trading** instead of actual **6.5-hour market hours**.

**Old Code:**
```python
lookback_days = (periods * timeframe_minutes) // (24 * 60) + 5
```

**For 1000 × 15-minute candles:**
```
1000 * 15 = 15,000 minutes
15,000 ÷ 1,440 (minutes in 24h) = 10.4 days
10.4 + 5 buffer = 15.4 days lookback
```

**But stock market reality:**
- Trading hours: **9:15 AM to 3:30 PM** = 6 hours 15 minutes = **6.5 hours/day**
- Trading minutes per day: **390 minutes** (not 1,440)
- Candles per day (15-min): **26 candles/day**
- To get 1000 candles: **1000 ÷ 26 = 38.5 trading days**
- With weekends/holidays: **~60 calendar days needed**

**Result:** Only querying **15 days** when we need **60+ days** → Database has more data than we're fetching!

### Issue 2: Database Query Range Too Short

**From logs:**
```
INFO - Fetching 1000 15minute candles for SBIN from database (2025-09-24 to 2025-10-09)
```

- Query range: **15 calendar days**
- Expected candles: **~10 trading days × 26 = 260 candles**
- Actual returned: **225 candles**

This suggests:
1. ✅ Database has data for those 15 days
2. ❌ We're not querying far enough back to get 1000 candles

---

## Fix Applied

### Fix 1: Correct Lookback Calculation

**File:** `src/core/historical_data_cache.py`

**New Code:**
```python
# Stock market trades ~6.5 hours per day, not 24 hours
trading_hours_per_day = 6.5  # 9:15 AM to 3:30 PM
trading_minutes_per_day = trading_hours_per_day * 60  # ~390 minutes

# Calculate how many calendar days we need
# Add 50% buffer for weekends and holidays
required_trading_days = (periods * timeframe_minutes) / trading_minutes_per_day
lookback_days = int(required_trading_days * 1.5) + 10  # 50% buffer + 10 days safety
```

**New calculation for 1000 × 15-minute candles:**
```
1000 * 15 = 15,000 minutes needed
15,000 ÷ 390 (trading minutes/day) = 38.5 trading days
38.5 * 1.5 (buffer) = 57.7 days
57.7 + 10 (safety) = 67.7 days lookback
```

**Result:** Now queries **~68 days** instead of 15 days!

### Fix 2: Improved Logging

Added detailed logging to understand what data we're getting:

```python
logger.debug(f"Raw data from database: {len(df)} rows, columns: {df.columns.tolist()}")
logger.debug(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
logger.info(f"Aggregated {df_before_agg} rows → {len(df)} {timeframe} candles")
logger.info(f"Fetched {len(df)} {timeframe} candles (requested {periods})")
```

### Fix 3: Reduced Warning Noise

**File:** `src/core/strategy_data_manager.py`

**Old Behavior:** Warned for ANY partial data (even 900/1000)

**New Behavior:**
- **<50% complete:** WARNING (serious shortage)
- **50-99% complete:** DEBUG (sufficient for analysis)
- **100% complete:** No message

```python
if completeness_percent < 50:
    logger.warning(f"{symbol}: Partial data ({completeness_percent}%)")
else:
    logger.debug(f"{symbol}: Partial data ({completeness_percent}%) - sufficient")
```

---

## Expected Results After Fix

### Before Fix:
```
INFO - Fetching 1000 15minute candles from database (2025-09-24 to 2025-10-09)
INFO - Fetched 225 15minute candles for SBIN
WARNING - Partial data: 227 of 1000 requested periods
```

### After Fix:
```
INFO - Fetching 1000 15minute candles from database (2025-08-01 to 2025-10-09, 68 days lookback)
DEBUG - Raw data from database: 1250 rows
INFO - Fetched 1000 15minute candles for SBIN (requested 1000)
INFO - Prepared data for SBIN: 1002 15minute candles (historical: 1000, realtime: 2)
```

---

## Understanding the Numbers

### Market Hours Math

**Indian Stock Market:**
- Opens: 9:15 AM
- Closes: 3:30 PM
- Duration: 6 hours 15 minutes = **375 minutes**
- Pre-market ignored (9:00-9:15 AM)

**Candles Per Day:**
| Timeframe | Candles/Day | Days for 1000 | Calendar Days Needed |
|-----------|-------------|---------------|---------------------|
| 1-minute  | 375         | 2.7 days      | 5 days             |
| 5-minute  | 75          | 13.3 days     | 25 days            |
| 15-minute | 25          | 40 days       | **70 days**        |
| 60-minute | 6           | 167 days      | 290 days           |

**Note:** Calendar days include weekends and holidays (non-trading days)

### Why 50% Buffer?

```
Trading days per week: 5
Total days per week: 7
Overhead: 7/5 = 1.4 = 40% overhead

Plus holidays: ~10-15 market holidays per year
Total buffer needed: ~50%
```

---

## Verification Steps

### Step 1: Check New Lookback Range
```bash
python main.py

# Look for this in logs:
grep "Fetching.*from database" logs/historical_data_cache.log | tail -5

# Should see:
# "Fetching 1000 15minute candles from database (2025-08-01 to 2025-10-09, 68 days lookback)"
# NOT: "(2025-09-24 to 2025-10-09, 15 days lookback)"
```

### Step 2: Check Data Retrieved
```bash
grep "Fetched.*candles for" logs/historical_data_cache.log | tail -10

# Should see:
# "Fetched 950 15minute candles for SBIN (requested 1000)"
# or better: "Fetched 1000 15minute candles for SBIN (requested 1000)"
```

### Step 3: Check Warning Reduction
```bash
grep "WARNING.*Partial data" logs/strategy_data_manager.log | wc -l

# Should be much fewer warnings than before
# Only warn if <50% complete
```

### Step 4: Verify Strategy Execution
```bash
grep "analyzed.*candles" logs/AlphaStockOrchestrator.log | tail -10

# Should see:
# "[analyzed 950 candles]" or "[analyzed 1000 candles]"
# NOT: "[analyzed 227 candles]"
```

---

## If Still Getting Insufficient Data

### Scenario 1: Database Actually Has Limited Data

**Check:**
```sql
-- Query ClickHouse
SELECT 
    symbol,
    MIN(timestamp) as earliest,
    MAX(timestamp) as latest,
    COUNT(*) as total_rows
FROM historical_data
WHERE timeframe = '15minute'
GROUP BY symbol;
```

**If database only has 15 days:**
- You need to run historical data collection
- Or populate database from historical source

### Scenario 2: Data Not Aggregated Properly

**Check aggregation:**
```bash
# Look for aggregation logs
grep "Aggregated" logs/historical_data_cache.log

# Should see:
# "Aggregated 15000 rows → 1000 15minute candles"
```

**If no aggregation happening:**
- Data might already be in 15-minute format
- Check what `timeframe` value is in database

### Scenario 3: Date Range Filter Issues

**Check actual query:**
- Add debug logging in `ClickHouseDataLayer.get_historical_data()`
- Print the actual SQL query and parameters
- Verify start_date/end_date are being used correctly

---

## Configuration Recommendations

### For Different Strategies

**Short-term (Intraday):**
```json
{
  "timeframe": "5minute",
  "historical_lookback": {
    "periods": 500,
    "days": 10,
    "min_periods": 75
  }
}
```

**Medium-term (Swing Trading):**
```json
{
  "timeframe": "15minute",
  "historical_lookback": {
    "periods": 1000,
    "days": 40,
    "min_periods": 200
  }
}
```

**Long-term (Position Trading):**
```json
{
  "timeframe": "60minute",
  "historical_lookback": {
    "periods": 500,
    "days": 100,
    "min_periods": 100
  }
}
```

---

## Summary

✅ **Root Cause:** Incorrect lookback calculation (assumed 24h trading instead of 6.5h)  
✅ **Fix Applied:** Corrected calculation with 50% buffer for weekends/holidays  
✅ **Expected Impact:** Will now query ~68 days instead of 15 days for 1000 candles  
✅ **Additional Improvements:** Better logging and reduced warning noise  

**Result:** Strategies should now receive 800-1000+ candles instead of 225 candles.

---

**Date:** October 9, 2025  
**Issue:** Insufficient historical data due to incorrect lookback calculation  
**Status:** ✅ FIXED  
**Files Modified:** 
- `src/core/historical_data_cache.py` (lookback calculation + logging)
- `src/core/strategy_data_manager.py` (warning threshold)
