# Market Hours Protection System

## Overview

The AlphaStocks trading system implements comprehensive market hours protection to ensure data integrity and prevent corruption by stopping all data collection activities after market close (3:30 PM IST).

---

## Indian Market Hours

### NSE/BSE Trading Hours
- **Market Open**: 9:15 AM IST
- **Market Close**: 3:30 PM IST (15:30)
- **Trading Days**: Monday to Friday (weekdays only)
- **Total Trading Hours**: 6 hours 15 minutes per day

### Pre-market Session
- **Pre-market**: 9:00 AM - 9:15 AM (not currently tracked by the system)

### Post-market Session
- **Post-market**: 3:40 PM - 4:00 PM (not currently tracked by the system)

---

## Why Market Hours Protection is Critical

### 1. **Data Corruption Prevention**
After 3:30 PM, the market is closed and no new trades occur. Any data fetched after this time may contain:
- Stale prices (last traded price from 3:30 PM)
- Zero volume
- No bid/ask updates
- Misleading indicators

**Problem**: If we continue fetching data after 3:30 PM, we might:
- Create artificial candles with duplicate close prices
- Store invalid tick data
- Generate false signals based on stale data
- Corrupt historical data with post-market noise

### 2. **API Rate Limiting**
Zerodha Kite Connect has strict rate limits:
- 3 requests per second
- Quota resets daily

**Problem**: Wasting API calls on closed-market data:
- Reduces available quota for next trading day
- May trigger rate limit errors
- Wastes computational resources

### 3. **Strategy Accuracy**
Trading strategies rely on accurate, live market data:
- Technical indicators need real price movements
- Volume analysis requires actual trading activity
- Signal generation depends on valid market conditions

**Problem**: Running strategies on stale data:
- Generates false signals
- Misleads backtesting
- Produces incorrect P&L calculations

---

## Implementation

### 1. Market Hours Configuration

**File**: `config/production.json`

```json
{
  "market": {
    "open_time": "09:15",
    "close_time": "15:30",
    "timezone": "Asia/Kolkata",
    "trading_days": [0, 1, 2, 3, 4]  // Monday=0, Friday=4
  }
}
```

### 2. Market Hours Utility

**File**: `src/utils/market_hours.py`

#### Key Functions

```python
def is_market_open(config=None) -> bool:
    """
    Check if Indian stock market is currently open.
    
    Returns:
        True if market is open (9:15 AM - 3:30 PM IST on weekdays)
        False if market is closed
    """
```

#### Class: MarketHours

```python
class MarketHours:
    def is_market_open(self) -> bool:
        """Check if market is currently open"""
        
    def time_to_market_open(self) -> int:
        """Get seconds until market opens"""
        
    def time_to_market_close(self) -> int:
        """Get seconds until market closes"""
```

### 3. Protection Points

#### A. MarketDataRunner (Real-time Data Collection)

**File**: `src/core/market_data_runner.py`

**Protection**: Checks market hours before each data fetch cycle

```python
def _run_collection_loop(self):
    """Main collection loop"""
    while self.is_running:
        # Check if market is open before collecting data
        if not is_market_open():
            logger.debug("Market is closed, skipping data collection")
            time.sleep(60)  # Check every minute when market is closed
            continue
        
        # Collect data only during market hours
        self._collect_batch_data()
```

**Behavior**:
- ✅ **During Market Hours (9:15 AM - 3:30 PM)**: Fetches data every 5 seconds
- 🛑 **After Market Close (3:30 PM+)**: Stops fetching, sleeps for 60 seconds
- ⏰ **Before Market Open (before 9:15 AM)**: Waits, checks every minute

#### B. CandleAggregator (Tick-to-Candle Conversion)

**File**: `src/core/candle_aggregator.py`

**Protection**: Rejects ticks received after market close

```python
def add_tick(self, symbol: str, tick_data: Dict) -> Optional[Dict]:
    """Add tick and aggregate into candles"""
    
    # Check if market is open - reject ticks after market close
    if not is_market_open():
        logger.debug(f"Market is closed, rejecting tick for {symbol}")
        return None
    
    # Process tick only during market hours
    # ...
```

**Behavior**:
- ✅ **During Market Hours**: Processes all ticks, creates candles
- 🛑 **After Market Close**: Rejects all incoming ticks
- 🔒 **Prevents**: Artificial candles from stale data

#### C. AlphaStockOrchestrator (Main System Loop)

**File**: `src/orchestrator.py`

**Protection**: Main loop checks market hours

```python
async def run(self):
    """Main orchestrator loop"""
    while self.running:
        # Check if market is open
        if not is_market_open():
            self.logger.info("Market is closed, waiting...")
            await asyncio.sleep(60)  # Check every minute
            continue
        
        # Execute strategies only during market hours
        # ...
```

**Behavior**:
- ✅ **During Market Hours**: Runs strategies every 5 seconds
- 🛑 **After Market Close**: Pauses execution, waits
- ⏰ **Before Market Open**: Waits until 9:15 AM

---

## System Flow with Market Hours Protection

### Typical Trading Day Timeline

```
08:00 AM  - System starts, waiting for market open
            ↓
09:15 AM  - Market opens
            ↓ START DATA COLLECTION
09:15 AM  - MarketDataRunner starts fetching ticks (every 5 sec)
            - CandleAggregator starts processing ticks
            - Strategies start analyzing data
            ↓
10:00 AM  - [Normal trading hours]
            - Continuous data collection
            - Real-time strategy execution
            - Signal generation
            ↓
03:29 PM  - [Last minute of trading]
            - Final ticks being processed
            - Last candles being completed
            ↓
03:30 PM  - Market closes
            ↓ STOP DATA COLLECTION
03:30 PM  - MarketDataRunner: Stops fetching (checks every 60s)
            - CandleAggregator: Rejects new ticks
            - Orchestrator: Pauses strategy execution
            ↓
03:31 PM  - System in idle state
            - No data collection
            - No signal generation
            - Waiting for next trading day
            ↓
[Overnight]- System keeps running (optional)
            - Checks market hours every minute
            - Ready to resume at 9:15 AM next day
            ↓
09:15 AM  - Next day: Market opens, cycle repeats
```

---

## Verification

### Check if Protection is Working

#### 1. Monitor Logs

```powershell
# Watch real-time logs
Get-Content logs\AlphaStockOrchestrator.log -Tail 50 -Wait

# Look for these messages after 3:30 PM:
# "Market is closed, skipping data collection"
# "Market is closed, rejecting tick for SYMBOL"
# "Market is closed, waiting..."
```

#### 2. Check Database Records

```sql
-- Verify no data collected after 3:30 PM
SELECT 
    symbol,
    timestamp,
    close
FROM market_data
WHERE DATE(timestamp) = CURRENT_DATE()
  AND TIME(timestamp) > '15:30:00'
ORDER BY timestamp DESC;

-- Should return 0 rows if protection is working
```

#### 3. Check Last Data Timestamp

```sql
-- Get last collected data timestamp
SELECT 
    symbol,
    MAX(timestamp) as last_update
FROM market_data
WHERE DATE(timestamp) = CURRENT_DATE()
GROUP BY symbol;

-- Last update should be <= 15:30:00 (3:30 PM)
```

---

## Configuration

### Modify Market Hours

If you need to adjust market hours (e.g., for testing or different markets):

**File**: `config/production.json`

```json
{
  "market": {
    "open_time": "09:15",      // HH:MM format (24-hour)
    "close_time": "15:30",     // HH:MM format (24-hour)
    "timezone": "Asia/Kolkata", // Python timezone string
    "trading_days": [0, 1, 2, 3, 4]  // 0=Mon, 1=Tue, ..., 4=Fri
  }
}
```

### Testing Outside Market Hours

For development/testing purposes, you can temporarily override market hours:

**Option 1**: Modify `config/production.json` (not recommended for production)

**Option 2**: Use environment variables (future enhancement)

**Option 3**: Manual override in code (for testing only)

```python
# In src/utils/market_hours.py (for testing only)
def is_market_open(config=None):
    return True  # Always return True for testing
    # Remember to revert this change!
```

---

## Edge Cases Handled

### 1. **Exactly at 3:30 PM**
- `close_time` check uses `<=` (less than or equal)
- Last tick at 3:30:00 PM is accepted
- First tick at 3:30:01 PM is rejected

### 2. **System Start After Market Close**
- System checks market hours on startup
- If after 3:30 PM: Enters idle state immediately
- Waits until next trading day (9:15 AM)

### 3. **Holidays**
- Currently not handled (system assumes weekdays are trading days)
- **Future Enhancement**: Integrate holiday calendar API
- **Workaround**: Manually stop system on holidays

### 4. **Timezone Handling**
- All times are in `Asia/Kolkata` timezone (IST)
- System automatically converts UTC timestamps to IST
- Handles daylight saving (though India doesn't observe DST)

### 5. **Partial Trading Days**
- Special cases like Muhurat trading (Diwali)
- Currently not handled
- **Workaround**: Manually adjust `close_time` in config

---

## Benefits

### ✅ Data Integrity
- No stale data after market close
- Clean, accurate historical data
- Reliable backtesting results

### ✅ Resource Efficiency
- Saves API quota
- Reduces database writes
- Lower CPU usage during non-trading hours

### ✅ System Reliability
- Prevents false signals
- Avoids strategy confusion
- Maintains consistent data quality

### ✅ Compliance
- Respects market hours
- Follows trading regulations
- Proper time-based controls

---

## Troubleshooting

### Issue 1: Data Still Being Collected After 3:30 PM

**Check**:
1. Verify system timezone: `python -c "import pytz; print(datetime.now(pytz.timezone('Asia/Kolkata')))"`
2. Check config: `type config\production.json | Select-String "close_time"`
3. Check logs: `Get-Content logs\AlphaStockOrchestrator.log -Tail 100 | Select-String "market"`

**Solution**:
- Ensure `close_time` is "15:30" in config
- Verify timezone is "Asia/Kolkata"
- Restart the system

### Issue 2: System Not Starting Before 9:15 AM

**Check**:
1. Verify current time: `python -c "from datetime import datetime; import pytz; print(datetime.now(pytz.timezone('Asia/Kolkata')))"`
2. Check logs for "Market is closed, waiting..."

**Solution**:
- This is expected behavior
- System will auto-start at 9:15 AM
- For testing, modify `open_time` in config

### Issue 3: System Not Stopping at 3:30 PM

**Check**:
1. Verify `is_market_open()` function is imported in all runners
2. Check if market hours validation is enabled

**Solution**:
- Update code with the protection logic
- Restart the system
- Verify logs show market hours checks

---

## Future Enhancements

### 1. Holiday Calendar Integration
- Integrate NSE holiday calendar API
- Auto-detect trading holidays
- Avoid unnecessary system runs on holidays

### 2. Pre-market/Post-market Support
- Optionally track pre-market session (9:00-9:15 AM)
- Optionally track post-market session (3:40-4:00 PM)
- Separate data channels for different sessions

### 3. Smart Restart
- Auto-detect next market open time
- Schedule system restart before market open
- Reduce idle time

### 4. Market Hours Dashboard
- Visual indicator of market status
- Countdown to market open/close
- Historical market hours statistics

---

## Summary

The market hours protection system is **critical** for data integrity. By stopping all data collection activities at 3:30 PM IST:

- ✅ **Prevents data corruption** from stale prices
- ✅ **Saves API quota** for actual trading hours
- ✅ **Maintains strategy accuracy** with live data only
- ✅ **Ensures system reliability** with proper time controls

The protection is implemented at **three levels**:
1. **MarketDataRunner**: Stops fetching ticks
2. **CandleAggregator**: Rejects post-market ticks
3. **Orchestrator**: Pauses strategy execution

This multi-layer approach ensures **no data is collected or processed** after the market closes, maintaining the integrity of our trading system.

---

**Last Updated**: October 10, 2025  
**System Version**: 1.0  
**Market**: NSE/BSE (Indian Stock Market)
