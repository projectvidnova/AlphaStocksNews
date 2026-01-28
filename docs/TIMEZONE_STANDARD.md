# Timezone Management Standard

## Overview

**AlphaStocks uses IST (Indian Standard Time - Asia/Kolkata) as the standard timezone across the entire application.** This document defines the timezone handling standards to ensure consistency across all modules.

**Implementation Date**: November 7, 2025  
**Status**: Mandatory Standard ✅

---

## The Problem

Before standardization, the system had **inconsistent timezone usage**:

| Component | Timezone | Issue |
|-----------|----------|-------|
| `trading_signals` table | UTC | Required conversion for IST display |
| `market_data` table | IST | Inconsistent with signals |
| `historical_data` table | UTC | Inconsistent with market_data |
| Code (datetime.now()) | Local (Windows) | Platform-dependent |
| Market hours checks | IST | Correct, but not centralized |

This caused:
- ❌ Timezone comparison errors
- ❌ Incorrect time-based filtering
- ❌ Display inconsistencies
- ❌ Signal deduplication failures (comparing UTC vs IST)

---

## The Solution

**Single Source of Truth**: `src/utils/timezone_utils.py`

All time-related operations MUST use this centralized utility module.

---

## Centralized Timezone Utility

### Core Configuration

```python
# src/utils/timezone_utils.py
APP_TIMEZONE_NAME = "Asia/Kolkata"  # IST - Single source of truth
APP_TIMEZONE = pytz.timezone(APP_TIMEZONE_NAME)
```

### Required Imports

**ALWAYS import from timezone_utils:**

```python
from src.utils.timezone_utils import (
    get_current_time,       # Current time in IST
    get_timezone,           # IST timezone object
    to_ist,                 # Convert any datetime to IST
    to_utc,                 # Convert to UTC
    get_today_market_open,  # 9:15 AM IST
    get_today_market_close, # 3:30 PM IST
    is_market_hours,        # Check if within trading hours
    format_ist_time,        # Format for display
    make_aware,             # Convert naive to aware
)
```

---

## Mandatory Rules

### Rule 1: Never Use datetime.now() or datetime.utcnow()

❌ **WRONG:**
```python
import datetime
timestamp = datetime.now()      # Platform-dependent
timestamp = datetime.utcnow()   # UTC, not IST
```

✅ **CORRECT:**
```python
from src.utils.timezone_utils import get_current_time
timestamp = get_current_time()  # IST, timezone-aware
```

### Rule 2: Database Storage Pattern

**Store in UTC, Display in IST:**

✅ **Storing to Database:**
```python
from src.utils.timezone_utils import get_current_time, to_utc

# Get current time in IST
current_time_ist = get_current_time()

# Convert to UTC for database storage
db_timestamp = to_utc(current_time_ist)

await data_layer.store_signal({
    'timestamp': db_timestamp,  # Stored as UTC
    ...
})
```

✅ **Reading from Database:**
```python
from src.utils.timezone_utils import to_ist

# Read from database (UTC)
signals = await data_layer.get_signals(symbol="RELIANCE")

# Convert to IST for processing/display
for signal in signals:
    ist_timestamp = to_ist(signal['timestamp'])
    print(f"Signal at: {ist_timestamp}")
```

### Rule 3: Market Hours Checks

✅ **CORRECT:**
```python
from src.utils.timezone_utils import (
    is_market_hours,
    get_today_market_open,
    get_today_market_close
)

# Check if market is open
if is_market_hours():
    execute_trade()

# Get market times
market_open = get_today_market_open()   # 9:15 AM IST
market_close = get_today_market_close() # 3:30 PM IST
```

❌ **WRONG:**
```python
# Don't hardcode times or use naive datetime
now = datetime.now()  # ❌ No timezone
if now.hour >= 9 and now.hour < 15:  # ❌ Incomplete logic
    execute_trade()
```

### Rule 4: Signal Timestamps

✅ **Creating Signals:**
```python
from src.utils.timezone_utils import get_current_time

signal = Signal(
    symbol="RELIANCE",
    timestamp=get_current_time().isoformat(),  # IST
    ...
)
```

✅ **Signal Deduplication (Current Session):**
```python
from src.utils.timezone_utils import get_today_market_open

# Get last signal from today's session (9:15 AM IST onwards)
today_session_start = get_today_market_open()

last_signal = await data_layer.get_last_signal(
    symbol=symbol,
    strategy=strategy,
    since=today_session_start  # Timezone-aware IST
)
```

### Rule 5: Time Comparisons

✅ **CORRECT:**
```python
from src.utils.timezone_utils import get_current_time, to_ist

# Both timestamps are timezone-aware
current_time = get_current_time()  # IST
last_signal_time = to_ist(last_signal['timestamp'])

if current_time > last_signal_time:
    # Comparison works correctly
```

❌ **WRONG:**
```python
# Mixing naive and aware datetimes
current_time = datetime.now()  # Naive
last_signal_time = ...  # Timezone-aware

if current_time > last_signal_time:  # ❌ TypeError
```

---

## Common Use Cases

### 1. Get Current Time

```python
from src.utils.timezone_utils import get_current_time

# Get timezone-aware current time in IST
now = get_current_time()
print(now)  # 2025-11-07 14:30:00+05:30

# Get naive datetime (only if required for legacy systems)
from src.utils.timezone_utils import get_current_time_naive
now_naive = get_current_time_naive()
```

### 2. Convert Between Timezones

```python
from src.utils.timezone_utils import to_ist, to_utc
from datetime import datetime
import pytz

# UTC to IST
utc_time = datetime.now(pytz.utc)
ist_time = to_ist(utc_time)

# IST to UTC (for database storage)
ist_time = get_current_time()
utc_time = to_utc(ist_time)
```

### 3. Parse Timestamp Strings

```python
from src.utils.timezone_utils import parse_timestamp

# Parse ISO format string
timestamp_str = "2025-11-07 14:30:00"
dt = parse_timestamp(timestamp_str, input_timezone="IST")

# Parse UTC timestamp
utc_str = "2025-11-07 09:00:00"
dt = parse_timestamp(utc_str, input_timezone="UTC")
# Returns IST datetime
```

### 4. Format for Display

```python
from src.utils.timezone_utils import format_ist_time, get_current_time

# Format current time
formatted = format_ist_time()
print(formatted)  # "2025-11-07 14:30:00 IST"

# Format specific datetime
from datetime import datetime
dt = get_current_time()
formatted = format_ist_time(dt, format_str="%d %b %Y, %I:%M %p")
print(formatted)  # "07 Nov 2025, 02:30 PM"
```

### 5. Check Market Hours

```python
from src.utils.timezone_utils import is_market_hours

if is_market_hours():
    print("Market is open for trading")
else:
    print("Market is closed")
```

### 6. Get Session Boundaries

```python
from src.utils.timezone_utils import (
    get_today_start,
    get_today_market_open,
    get_today_market_close
)

# Start of day (00:00:00 IST)
day_start = get_today_start()

# Market open (9:15 AM IST)
session_start = get_today_market_open()

# Market close (3:30 PM IST)
session_end = get_today_market_close()

# Query data for current session
data = await data_layer.get_signals(
    start_time=session_start,
    end_time=session_end
)
```

---

## Migration Guide

### Step 1: Replace datetime.now()

**Find:**
```python
timestamp = datetime.now()
now = datetime.now()
```

**Replace with:**
```python
from src.utils.timezone_utils import get_current_time
timestamp = get_current_time()
now = get_current_time()
```

### Step 2: Replace datetime.utcnow()

**Find:**
```python
timestamp = datetime.utcnow()
```

**Replace with:**
```python
from src.utils.timezone_utils import get_current_time, to_utc
timestamp = to_utc(get_current_time())  # If UTC needed
# OR better: just use IST
timestamp = get_current_time()
```

### Step 3: Update Market Hours Logic

**Find:**
```python
now = datetime.now()
if now.hour >= 9 and now.hour < 15:
    ...
```

**Replace with:**
```python
from src.utils.timezone_utils import is_market_hours
if is_market_hours():
    ...
```

### Step 4: Update Signal Timestamps

**Find:**
```python
self.timestamp = timestamp or datetime.now().isoformat()
```

**Replace with:**
```python
from src.utils.timezone_utils import get_current_time
self.timestamp = timestamp or get_current_time().isoformat()
```

---

## Database Schema Standards

### Recommended Approach

| Table | Column | Storage Format | Display Format | Conversion |
|-------|--------|---------------|----------------|------------|
| `trading_signals` | `timestamp` | **UTC** (DateTime) | IST | `to_ist(db_value)` |
| `market_data` | `timestamp` | **IST** (DateTime) | IST | No conversion |
| `historical_data` | `timestamp` | **UTC** (DateTime) | IST | `to_ist(db_value)` |
| `options_data` | `timestamp` | **UTC** (DateTime) | IST | `to_ist(db_value)` |

**Why UTC for storage?**
- Industry standard for multi-timezone systems
- Avoids DST (Daylight Saving Time) issues
- Easier for global distribution
- IST doesn't have DST, but UTC is still preferred

**Why IST for display?**
- All users are in India
- Market operates in IST
- Signal deduplication uses IST session boundaries

---

## Testing Timezone Consistency

### Validation Script

```python
"""Test timezone consistency across application."""

from src.utils.timezone_utils import (
    get_current_time,
    get_timezone,
    detect_timezone,
    to_ist,
    to_utc
)

def test_timezone_consistency():
    # Test 1: Current time is IST
    now = get_current_time()
    tz = detect_timezone(now)
    assert tz == "IST", f"Expected IST, got {tz}"
    print("✅ get_current_time() returns IST")
    
    # Test 2: Timezone object is Asia/Kolkata
    tz_obj = get_timezone()
    assert str(tz_obj) == "Asia/Kolkata"
    print("✅ get_timezone() is Asia/Kolkata")
    
    # Test 3: Conversions work
    utc_time = to_utc(now)
    ist_time = to_ist(utc_time)
    assert ist_time.hour == now.hour
    print("✅ UTC <-> IST conversion works")
    
    print("\n✅ All timezone tests passed!")

if __name__ == "__main__":
    test_timezone_consistency()
```

---

## API Response Handling

When fetching data from Kite API:

```python
from src.utils.timezone_utils import make_aware, to_ist

# Kite API returns timestamps as strings (IST)
api_response = {
    'timestamp': '2025-11-07 14:30:00',  # IST string
    'ltp': 1500.50
}

# Convert to timezone-aware datetime
timestamp = make_aware(
    datetime.strptime(api_response['timestamp'], '%Y-%m-%d %H:%M:%S'),
    assume_timezone='IST'
)
```

---

## Common Pitfalls

### Pitfall 1: Comparing Naive and Aware

❌ **ERROR:**
```python
TypeError: can't compare offset-naive and offset-aware datetimes
```

✅ **FIX:**
```python
from src.utils.timezone_utils import get_current_time, to_ist

# Ensure both are timezone-aware
current_time = get_current_time()  # Aware (IST)
last_time = to_ist(last_signal['timestamp'])  # Convert to aware (IST)

if current_time > last_time:  # Now works!
```

### Pitfall 2: Database Filter Timezone Mismatch

❌ **WRONG:**
```python
# Database has UTC, query with IST
start_time = get_current_time()  # IST
signals = await db.query("WHERE timestamp >= %s", start_time)
# Returns wrong results!
```

✅ **CORRECT:**
```python
from src.utils.timezone_utils import get_current_time, to_utc

# Convert filter to UTC to match database
start_time_ist = get_current_time()
start_time_utc = to_utc(start_time_ist)

signals = await db.query("WHERE timestamp >= %s", start_time_utc)
# Correct results!
```

### Pitfall 3: Hardcoded Market Hours

❌ **WRONG:**
```python
if hour >= 9 and hour <= 15:  # Assumes local time
```

✅ **CORRECT:**
```python
from src.utils.timezone_utils import is_market_hours
if is_market_hours():  # Uses IST correctly
```

---

## Quick Reference

| Task | Function | Example |
|------|----------|---------|
| Get current time | `get_current_time()` | `now = get_current_time()` |
| Get timezone | `get_timezone()` | `tz = get_timezone()` |
| Convert to IST | `to_ist(dt)` | `ist = to_ist(utc_time)` |
| Convert to UTC | `to_utc(dt)` | `utc = to_utc(ist_time)` |
| Market open time | `get_today_market_open()` | `open = get_today_market_open()` |
| Market close time | `get_today_market_close()` | `close = get_today_market_close()` |
| Check market hours | `is_market_hours()` | `if is_market_hours():` |
| Format for display | `format_ist_time(dt)` | `str = format_ist_time(now)` |
| Make timezone-aware | `make_aware(dt, 'IST')` | `aware = make_aware(naive)` |
| Parse timestamp | `parse_timestamp(str, 'IST')` | `dt = parse_timestamp('2025-11-07 14:30')` |

---

## See Also

- **Implementation**: `src/utils/timezone_utils.py`
- **Usage Examples**: All modules in `src/trading/`, `src/runners/`
- **Market Hours Logic**: `src/utils/market_hours.py`
- **Design Principles**: `.github/copilot-instructions.md`

---

**Last Updated**: November 7, 2025  
**Version**: 1.0.0  
**Status**: Mandatory Standard ✅
