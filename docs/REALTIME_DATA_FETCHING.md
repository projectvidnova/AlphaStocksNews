# Real-Time Market Data Fetching in AlphaStocks

## 📊 Overview

The AlphaStocks system uses **TWO methods** to fetch real-time market data:

1. **Polling Method** (HTTP REST API) - **Currently Active**
2. **WebSocket Streaming** (Real-time push) - **Available but not actively used**

---

## 🔄 METHOD 1: POLLING (HTTP REST API) - **CURRENT IMPLEMENTATION**

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 MarketDataRunner                             │
│          (src/core/market_data_runner.py)                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ Runs every 5 seconds
                       ↓
┌──────────────────────────────────────────────────────────────┐
│              KiteAPIClient.get_ohlc()                         │
│              (src/api/kite_client.py)                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ HTTP GET Request
                       ↓
┌──────────────────────────────────────────────────────────────┐
│         self.kite.ohlc(tokens)                                │
│         (Official KiteConnect SDK)                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ HTTPS POST
                       ↓
┌──────────────────────────────────────────────────────────────┐
│         https://api.kite.trade/quote/ohlc                     │
│         (Zerodha Kite Servers)                                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ JSON Response
                       ↓
┌──────────────────────────────────────────────────────────────┐
│         Parse & Store in Cache                                │
│         Notify Strategy Callbacks                             │
└──────────────────────────────────────────────────────────────┘
```

---

## 📝 DETAILED FLOW: Polling Method

### Step 1: Initialization

**File**: `src/orchestrator.py`

```python
# Orchestrator initializes MarketDataRunner
async def _initialize_market_data_runner(self):
    """Initialize the market data collection runner"""
    
    # Get symbols from configuration
    symbols = self.config.get("data_collection", {}).get("symbols", [])
    # Example: ["RELIANCE", "TCS", "INFY", "SBIN"]
    
    # Get collection frequency (default: 5 seconds)
    interval_seconds = self.config.get("data_collection", {}).get(
        "interval_seconds", 5
    )
    
    # Create MarketDataRunner instance
    self.market_data_runner = MarketDataRunner(
        api_client=self.api_client,      # KiteAPIClient
        data_cache=self.data_cache,      # SimpleDataCache
        symbols=symbols,                  # List of symbols to track
        interval_seconds=interval_seconds # Collection frequency
    )
    
    # Set up callback for new data
    self.market_data_runner.add_callback(self._on_new_market_data)
    
    logger.info(f"Market data runner initialized for {len(symbols)} symbols")
```

### Step 2: Start Collection Loop

**File**: `src/core/market_data_runner.py`

```python
def start_collection(self):
    """Start the data collection process"""
    
    if self.is_running:
        logger.warning("Market Data Runner is already running")
        return
    
    self.is_running = True
    self.stats['start_time'] = datetime.now()
    
    # Start in a SEPARATE THREAD (non-blocking)
    self.runner_thread = threading.Thread(
        target=self._run_collection_loop, 
        daemon=True
    )
    self.runner_thread.start()
    
    logger.info("Market Data Runner started")

def _run_collection_loop(self):
    """Main collection loop that runs in a separate thread"""
    
    logger.info("Market Data Runner collection loop started")
    
    while self.is_running:
        start_time = time.time()
        
        try:
            # COLLECT DATA FOR ALL SYMBOLS
            self._collect_batch_data()
            
            # Update statistics
            self.stats['total_updates'] += 1
            self.stats['successful_updates'] += 1
            self.stats['last_successful_update'] = datetime.now()
            
        except Exception as e:
            logger.error(f"Error in market data collection loop: {e}")
            self.stats['failed_updates'] += 1
        
        # Calculate sleep time to maintain frequency
        elapsed_time = time.time() - start_time
        sleep_time = max(0, self.interval_seconds - elapsed_time)
        
        if sleep_time > 0:
            time.sleep(sleep_time)  # Wait before next iteration
    
    logger.info("Market Data Runner collection loop ended")
```

**Timeline Example**:
```
10:15:00 AM - Fetch data (takes 0.3 seconds)
10:15:00.3 AM - Sleep for 4.7 seconds
10:15:05 AM - Fetch data (takes 0.3 seconds)
10:15:05.3 AM - Sleep for 4.7 seconds
10:15:10 AM - Fetch data...
```

### Step 3: Batch Data Collection

**File**: `src/core/market_data_runner.py`

```python
def _collect_batch_data(self):
    """Collect data for all symbols in batch"""
    
    if not self.symbols:
        return
    
    try:
        # CALL KITE API TO GET OHLC DATA FOR ALL SYMBOLS AT ONCE
        ohlc_data = self.api_client.get_ohlc(self.symbols)
        # Example: get_ohlc(['RELIANCE', 'TCS', 'INFY', 'SBIN'])
        
        if not ohlc_data:
            logger.warning("No market data received from API")
            return
        
        current_time = datetime.now()
        
        # Process each symbol's data
        for symbol, data in ohlc_data.items():
            try:
                # Create DataFrame with current data
                market_data = pd.DataFrame([{
                    'timestamp': current_time,
                    'open': data.get('open', 0),
                    'high': data.get('high', 0),
                    'low': data.get('low', 0),
                    'close': data.get('last_price', 0),  # Current close = last_price
                    'volume': data.get('volume', 0),
                    'ltp': data.get('last_price', 0)     # Last Traded Price
                }])
                
                # Store in cache
                cache_key = f"market_data:{symbol}"
                
                # Get existing data from cache
                existing_data = self.data_cache.get(cache_key)
                if existing_data is not None and isinstance(existing_data, pd.DataFrame):
                    # Append new data to existing
                    combined_data = pd.concat([existing_data, market_data], ignore_index=True)
                    # Keep only last 100 records to manage memory
                    if len(combined_data) > 100:
                        combined_data = combined_data.tail(100)
                else:
                    combined_data = market_data
                
                # Update cache with 5-minute TTL
                self.data_cache.set(cache_key, combined_data, ttl=300)
                
                # Update statistics
                self.last_update_time[symbol] = current_time
                self.error_counts[symbol] = 0  # Reset error count on success
                
                # NOTIFY CALLBACKS (trigger strategy execution)
                for callback in self.callbacks:
                    try:
                        callback(symbol, combined_data)
                    except Exception as e:
                        logger.error(f"Error in callback for {symbol}: {e}")
                
                # Update stats
                self.stats['successful_requests'] += 1
            
            except Exception as e:
                logger.error(f"Error processing data for {symbol}: {e}")
                self._handle_symbol_error(symbol)
        
        self.stats['last_success_time'] = current_time
        logger.debug(f"Successfully collected data for {len(ohlc_data)} symbols")
    
    except Exception as e:
        logger.error(f"Error in batch data collection: {e}")
        self.stats['failed_requests'] += 1
        self.stats['last_error_time'] = datetime.now()
```

### Step 4: Kite API Call

**File**: `src/api/kite_client.py`

```python
def get_ohlc(self, symbols: Union[str, List[str]]) -> Dict[str, Dict[str, float]]:
    """
    Get OHLC data for symbols.
    
    Args:
        symbols: Symbol or list of symbols
        
    Returns:
        Dictionary with OHLC data
    """
    if isinstance(symbols, str):
        symbols = [symbols]
    
    try:
        # RATE LIMITING (important to avoid API throttling)
        self._rate_limit()
        
        # Convert symbols to instrument tokens
        tokens = []
        symbol_token_map = {}
        
        for symbol in symbols:
            if symbol.isdigit():
                tokens.append(symbol)
                symbol_token_map[symbol] = symbol
            else:
                token = self.get_instrument_token(symbol)
                if token:
                    tokens.append(token)
                    symbol_token_map[str(token)] = symbol
        
        if not tokens:
            return {}
        
        # CALL KITE CONNECT SDK
        ohlc_data = self.kite.ohlc(tokens)
        # This calls: https://api.kite.trade/quote/ohlc
        
        # Convert token-based response to symbol-based
        result = {}
        for token, data in ohlc_data.items():
            symbol = symbol_token_map.get(str(token), token)
            result[symbol] = {
                'open': data['ohlc']['open'],
                'high': data['ohlc']['high'],
                'low': data['ohlc']['low'],
                'close': data['ohlc']['close'],
                'last_price': data['last_price'],
                'volume': data.get('volume', 0)
            }
        
        return result
        
    except Exception as e:
        self.logger.error(f"Error fetching OHLC: {e}")
        return {}
```

### Step 5: Rate Limiting

**File**: `src/api/kite_client.py`

```python
def _rate_limit(self):
    """Enhanced rate limiting with burst capability"""
    
    current_time = time.time()
    elapsed = current_time - self.rate_limiter['last_refill']
    
    # Refill tokens based on elapsed time
    # Allows 3 requests per second with burst capability
    tokens_to_add = elapsed * self.rate_limiter['refill_rate']
    self.rate_limiter['tokens'] = min(
        self.rate_limiter['max_tokens'],
        self.rate_limiter['tokens'] + tokens_to_add
    )
    self.rate_limiter['last_refill'] = current_time
    
    # Check if we have tokens available
    if self.rate_limiter['tokens'] >= 1:
        self.rate_limiter['tokens'] -= 1
        return True
    else:
        # Calculate wait time
        wait_time = (1 - self.rate_limiter['tokens']) / self.rate_limiter['refill_rate']
        time.sleep(wait_time)
        self.rate_limiter['tokens'] = 0
        return True
```

**Rate Limiting Configuration**:
```python
self.rate_limiter = {
    'tokens': 10.0,           # Start with 10 tokens
    'max_tokens': 10.0,       # Max burst of 10 requests
    'refill_rate': 3.0,       # 3 tokens per second
    'last_refill': time.time()
}
```

This means:
- Can burst up to 10 requests immediately
- Then limited to 3 requests per second
- Prevents API throttling by Zerodha

### Step 6: Actual HTTP Request

**What happens under the hood**:

```
Python Code: self.kite.ohlc(['256265', '408065', '356865'])
    ↓
KiteConnect SDK formats request:
    ↓
HTTPS POST: https://api.kite.trade/quote/ohlc?i=NSE:256265&i=NSE:408065&i=NSE:356865
Headers:
    Authorization: token api_key:access_token
    X-Kite-Version: 3
    User-Agent: kiteconnect-python/4.x.x
    ↓
Zerodha Kite Servers process request
    ↓
Response (JSON):
{
    "status": "success",
    "data": {
        "256265": {
            "instrument_token": 256265,
            "timestamp": "2025-10-07T10:15:05+0530",
            "last_price": 2450.50,
            "ohlc": {
                "open": 2430.00,
                "high": 2455.00,
                "low": 2425.00,
                "close": 2448.00
            },
            "volume": 1250000
        },
        "408065": { ... },
        "356865": { ... }
    }
}
    ↓
Parsed and returned to application
```

---

## 🌐 METHOD 2: WEBSOCKET STREAMING - **AVAILABLE BUT NOT ACTIVELY USED**

### Why WebSocket is Better for Real-Time

**Advantages**:
- ✅ **True real-time**: Data pushed immediately when price changes
- ✅ **Lower latency**: ~100ms vs ~5000ms with polling
- ✅ **Less API calls**: One connection vs 720 requests/hour
- ✅ **More efficient**: No wasted requests when price doesn't change
- ✅ **Tick-by-tick data**: Get every trade, not just snapshots

**Disadvantages**:
- ❌ More complex to implement
- ❌ Requires persistent connection management
- ❌ Need to handle reconnections
- ❌ More resource intensive

### WebSocket Implementation (Available but Not Active)

**File**: `src/api/kite_client.py`

```python
def start_websocket(self, symbols: List[str], on_tick_callback=None):
    """
    Start WebSocket for real-time data.
    
    Args:
        symbols: List of symbols to subscribe
        on_tick_callback: Callback function for tick data
    """
    if not self.access_token:
        raise ValueError("Access token required for WebSocket")
    
    try:
        # Initialize KiteTicker
        self.ticker = KiteTicker(self.api_key, self.access_token)
        
        # Define callback for tick data
        def on_ticks(ws, ticks):
            """Called when tick data is received"""
            if on_tick_callback:
                on_tick_callback(ticks)
            else:
                self.logger.debug(f"Received {len(ticks)} ticks")
        
        # Define callback for connection
        def on_connect(ws, response):
            """Called when WebSocket connects"""
            self.logger.info("WebSocket connected")
            
            # Convert symbols to tokens and subscribe
            tokens = []
            for symbol in symbols:
                token = self.get_instrument_token(symbol)
                if token:
                    tokens.append(int(token))
            
            if tokens:
                ws.subscribe(tokens)
                ws.set_mode(ws.MODE_FULL, tokens)  # Full mode with all data
                self.logger.info(f"Subscribed to {len(tokens)} instruments")
        
        # Define callback for disconnection
        def on_close(ws, code, reason):
            """Called when WebSocket closes"""
            self.logger.info(f"WebSocket closed: {code} - {reason}")
        
        # Set callbacks
        self.ticker.on_ticks = on_ticks
        self.ticker.on_connect = on_connect
        self.ticker.on_close = on_close
        
        # Start in separate thread
        self.ticker.connect(threaded=True)
        
    except Exception as e:
        self.logger.error(f"Error starting WebSocket: {e}")
        raise

def stop_websocket(self):
    """Stop WebSocket connection"""
    if self.ticker:
        self.ticker.close()
        self.ticker = None
        self.logger.info("WebSocket stopped")
```

### WebSocket Tick Data Structure

When data arrives via WebSocket:

```python
# Example tick data
tick = {
    'instrument_token': 256265,
    'mode': 'full',
    'tradable': True,
    'timestamp': datetime(2025, 10, 7, 10, 15, 5, 123456),
    
    # Price data
    'last_price': 2450.50,
    'last_traded_quantity': 100,
    'average_price': 2448.25,
    'volume': 1250000,
    
    # OHLC
    'ohlc': {
        'open': 2430.00,
        'high': 2455.00,
        'low': 2425.00,
        'close': 2448.00
    },
    
    # Market depth
    'depth': {
        'buy': [
            {'quantity': 500, 'price': 2450.25, 'orders': 3},
            {'quantity': 300, 'price': 2450.00, 'orders': 2},
            # ... 5 levels
        ],
        'sell': [
            {'quantity': 400, 'price': 2450.75, 'orders': 2},
            {'quantity': 600, 'price': 2451.00, 'orders': 4},
            # ... 5 levels
        ]
    }
}
```

### WebSocket Connection Flow

```
Application Start
    ↓
ticker = KiteTicker(api_key, access_token)
    ↓
ticker.connect(threaded=True)
    ↓
WebSocket connects to: wss://ws.kite.trade/
    ↓
on_connect() called
    ↓
ws.subscribe([256265, 408065, 356865])
ws.set_mode(MODE_FULL, [256265, 408065, 356865])
    ↓
Server starts streaming tick data
    ↓
on_ticks() called every time price changes
    ↓
Process tick data immediately
```

---

## 📊 COMPARISON: Polling vs WebSocket

### Polling (Current Method)

**Data Flow**:
```
10:15:00 - Fetch: RELIANCE @ 2450.50
10:15:05 - Fetch: RELIANCE @ 2450.50 (no change, wasted API call)
10:15:10 - Fetch: RELIANCE @ 2451.25 (detected after 10 seconds)
10:15:15 - Fetch: RELIANCE @ 2451.25 (no change)
10:15:20 - Fetch: RELIANCE @ 2452.00 (detected after 5 seconds)
```

**Characteristics**:
- Interval: 5 seconds
- API Calls: 720 per hour per symbol
- Latency: 0-5 seconds (average 2.5 seconds)
- Missed Ticks: Yes (can miss price changes between polls)

### WebSocket (Available but Not Active)

**Data Flow**:
```
10:15:00.123 - Tick: RELIANCE @ 2450.50
10:15:03.456 - Tick: RELIANCE @ 2451.25 (detected in 0.1 seconds)
10:15:07.789 - Tick: RELIANCE @ 2452.00 (detected in 0.1 seconds)
10:15:12.345 - Tick: RELIANCE @ 2451.75 (detected in 0.1 seconds)
```

**Characteristics**:
- Interval: Real-time (as price changes)
- API Calls: 1 connection (persistent)
- Latency: ~100ms
- Missed Ticks: No (every price change captured)

---

## 🔧 Current System Configuration

**File**: `config/production.json`

```json
{
  "data_collection": {
    "method": "polling",
    "interval_seconds": 5,
    "symbols": [
      "RELIANCE",
      "TCS",
      "INFY",
      "SBIN"
    ],
    "use_websocket": false
  }
}
```

---

## 🚀 Why System Uses Polling Instead of WebSocket

### Reasons:

1. **Simplicity**: Polling is easier to implement and maintain
2. **Sufficient for Strategy**: 5-second updates adequate for 15-minute MA crossover strategy
3. **Resource Efficient**: Less memory and CPU usage
4. **Easier Error Handling**: Simpler to retry failed requests
5. **No Connection Management**: No need to handle reconnections

### When to Switch to WebSocket:

Consider WebSocket if:
- ✅ Need tick-by-tick data
- ✅ Running high-frequency trading strategies
- ✅ Need sub-second latency
- ✅ Trading with scalping or day trading strategies
- ✅ Need market depth data

---

## 📊 Data Freshness Check

**File**: `src/core/market_data_runner.py`

```python
def is_data_fresh(self, symbol: str, max_age_seconds: int = 30) -> bool:
    """
    Check if data for a symbol is fresh (within max_age_seconds).
    
    Args:
        symbol: Trading symbol
        max_age_seconds: Maximum age in seconds
        
    Returns:
        True if data is fresh, False otherwise
    """
    if symbol not in self.last_update_time:
        return False
    
    age = (datetime.now() - self.last_update_time[symbol]).total_seconds()
    return age <= max_age_seconds
```

Usage:
```python
# Check if RELIANCE data is fresh (within 30 seconds)
if runner.is_data_fresh('RELIANCE', max_age_seconds=30):
    print("Data is fresh, can use for trading decisions")
else:
    print("Data is stale, wait for next update")
```

---

## 📈 Statistics & Monitoring

**File**: `src/core/market_data_runner.py`

```python
def get_statistics(self) -> Dict[str, Any]:
    """Get collection statistics"""
    
    stats = self.stats.copy()
    
    if stats['start_time']:
        stats['uptime_seconds'] = (datetime.now() - stats['start_time']).total_seconds()
    
    if stats['total_updates'] > 0:
        stats['success_rate'] = stats['successful_updates'] / stats['total_updates']
    else:
        stats['success_rate'] = 0.0
    
    stats['is_running'] = self.is_running
    stats['symbols_count'] = len(self.symbols)
    stats['frequency_seconds'] = self.frequency
    
    return stats
```

Example output:
```python
{
    'total_updates': 720,
    'successful_updates': 718,
    'failed_updates': 2,
    'success_rate': 0.997,
    'is_running': True,
    'symbols_count': 4,
    'frequency_seconds': 5,
    'uptime_seconds': 3600,
    'last_success_time': datetime(2025, 10, 7, 11, 15, 5)
}
```

---

## 🎯 Summary

### Current Implementation (Polling):

1. **MarketDataRunner** runs in separate thread
2. Every **5 seconds**, fetches OHLC data for all symbols
3. Uses **KiteAPIClient.get_ohlc()** → calls Kite REST API
4. Stores data in **cache** (last 100 records per symbol)
5. **Notifies callbacks** → triggers strategy execution
6. **Rate limited** to 3 requests/second with burst capability

### Key Components:

- **MarketDataRunner**: Orchestrates data collection
- **KiteAPIClient**: Wraps Kite Connect API
- **SimpleDataCache**: In-memory storage
- **Rate Limiter**: Prevents API throttling
- **Callbacks**: Trigger strategy analysis on new data

### Data Flow:

```
Polling Loop (5s) → Kite API Call → Rate Limiting → HTTP Request 
→ Zerodha Servers → JSON Response → Parse Data → Cache Storage 
→ Trigger Callbacks → Strategy Execution
```

The system **prefers polling over WebSocket** for simplicity and because 5-second updates are sufficient for the 15-minute MA crossover strategy currently implemented.

---

## 🔄 MarketDataRunner Enhancements (November 1, 2025)

### Daily Data Management

The `MarketDataRunner` now implements automatic data lifecycle management to maintain only today's intraday data in the `market_data` table.

#### Key Features

1. **Automatic Cleanup on Startup**
   - Clears all data older than today from `market_data` table
   - Uses ClickHouse mutation: `ALTER TABLE market_data DELETE WHERE toDate(timestamp) < '{today}'`
   - Runs once before data collection begins

2. **Intraday Historical Backfill**
   - Fetches data from market open (9:15 AM IST) to current time when starting mid-day
   - Uses 1-minute interval data from Kite API
   - Converts historical OHLCV to `market_data` table format
   - Ensures complete intraday coverage even if agent starts during trading session

3. **Seamless Real-time Collection**
   - Continues with normal 5-second polling after initial setup
   - No disruption to live data flow

#### Implementation

```python
# New methods in MarketDataRunner

async def _clear_old_market_data(self):
    """Clear old market data, keeping only today's data."""
    query = f"ALTER TABLE market_data DELETE WHERE toDate(timestamp) < '{today}'"
    await self.data_layer.execute_query(query)

async def _fetch_intraday_historical_data(self):
    """Fetch data from market open (9:15 AM) to current time."""
    # Fetches 1-minute data for each symbol
    historical_df = await self.api_client.get_historical_data(
        symbol=symbol,
        from_date=market_open_time,
        to_date=current_time,
        interval="minute"
    )
    # Stores in market_data table
```

#### Startup Scenarios

**Scenario 1: Start Before Market Open (9:00 AM)**
```
- Clears old data
- Market not open, skips historical fetch
- Waits for market open
- Starts real-time collection at 9:15 AM
```

**Scenario 2: Start Mid-Day (11:30 AM)**
```
- Clears old data
- Fetches historical: 9:15 AM → 11:30 AM (~135 records per symbol)
- Continues with real-time collection from 11:30 AM
```

**Scenario 3: Start After Market Close (4:00 PM)**
```
- Clears old data
- Market closed, skips historical fetch
- Waits for next trading day
```

#### Data Separation

- **`market_data` table**: Today's intraday data only (real-time + backfilled)
- **`historical_data` table**: Long-term historical OHLCV for backtesting

#### Benefits

- ✅ Clean data state (only today's records)
- ✅ Complete intraday coverage (even with mid-day starts)
- ✅ Automatic cleanup (no manual maintenance)
- ✅ Smaller table size (faster queries)
- ✅ No date filters needed in queries

#### Log Messages

```
INFO - Clearing market_data older than 2025-11-01...
INFO - Successfully cleared old market_data (older than 2025-11-01)
INFO - Fetching intraday data from 2025-11-01 09:15:00 to 2025-11-01 11:30:00...
INFO - Stored 135 historical records for SBIN
INFO - Completed intraday historical data fetch
INFO - Initial data setup completed successfully
```

---

*Last Updated: November 1, 2025*
