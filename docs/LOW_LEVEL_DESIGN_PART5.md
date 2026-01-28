# AlphaStocks Trading System - Low Level Design Documentation (Part 5)

## Additional Component Details

### 5.1 StrikeSelector

```python
class StrikeSelector:
    """
    Selects optimal option strike for signal execution
    
    Algorithm:
    1. Fetch option chain for underlying
    2. Filter by expiry (weekly preferred)
    3. Filter by liquidity (volume/OI thresholds)
    4. Score each strike (distance, IV, delta, liquidity)
    5. Return highest-scoring strike
    """
    
    # Key Attributes
    api_client: KiteAPIClient
    config: Dict
    
    prefer_atm: bool = True
    max_strikes_from_atm: int = 3
    min_volume: int = 100
    min_oi: int = 1000
    expiry_preference: str = "weekly"  # "weekly" or "monthly"
    
    # Key Methods
    async def select_strike(symbol, action, underlying_price, expected_move_pct):
        """
        Select optimal strike for option trade
        
        Process:
        1. Get option chain (fetch_option_chain)
        2. Filter by expiry preference
        3. Filter by action type (CE/PE)
        4. Filter by liquidity thresholds
        5. Calculate ATM strike
        6. Filter by distance from ATM
        7. Score remaining strikes
        8. Return best strike
        
        Returns: {
          symbol: "NIFTY24JAN24000CE",
          strike: 24000.0,
          type: "CE",
          expiry: "2024-01-25",
          ltp: 150.5,
          delta: 0.52,
          iv: 18.5,
          lot_size: 50,
          volume: 15000,
          oi: 50000
        }
        """
        
    async def fetch_option_chain(symbol, expiry=None):
        """
        Fetch complete option chain from API
        
        API: api_client.get_option_chain(symbol)
        Returns: List of option contracts with strikes, premiums, Greeks
        """
        
    def filter_by_liquidity(option_chain):
        """
        Filter options by volume/OI thresholds
        
        Filters:
        - volume >= min_volume
        - oi >= min_oi
        - bid_ask_spread < 5% of premium
        """
        
    def calculate_strike_score(option):
        """
        Score option strike (higher = better)
        
        Scoring:
        - Distance from ATM (closer = higher)
        - Delta proximity to 0.5 (closer = higher)
        - IV rank (lower = higher, cheaper premium)
        - Liquidity (volume + OI, higher = higher)
        - Bid-ask spread (tighter = higher)
        
        Formula:
          score = w1 * distance_score 
                + w2 * delta_score 
                + w3 * iv_score 
                + w4 * liquidity_score
                + w5 * spread_score
        
        Weights: w1=0.3, w2=0.2, w3=0.15, w4=0.25, w5=0.1
        """
```

### 5.2 OptionsGreeksCalculator

```python
class OptionsGreeksCalculator:
    """
    Calculate option Greeks using Black-Scholes model
    
    Greeks Computed:
    - Delta: Price sensitivity to underlying
    - Gamma: Delta sensitivity to underlying
    - Theta: Time decay per day
    - Vega: Price sensitivity to IV
    - Rho: Price sensitivity to interest rate
    """
    
    # Key Methods
    def calculate_greeks(spot, strike, time_to_expiry, volatility, rate, option_type):
        """
        Calculate all Greeks using Black-Scholes
        
        Inputs:
        - spot: Current underlying price
        - strike: Option strike price
        - time_to_expiry: Years to expiry (days/365)
        - volatility: Implied volatility (IV)
        - rate: Risk-free rate (typically 0.06 for India)
        - option_type: "CE" or "PE"
        
        Returns: {
          delta: 0.52,
          gamma: 0.015,
          theta: -25.3,
          vega: 12.5,
          rho: 8.2
        }
        """
        
    def calculate_delta(spot, strike, time_to_expiry, volatility, rate, option_type):
        """
        Calculate Delta
        
        CE Delta: N(d1) [0 to 1]
        PE Delta: N(d1) - 1 [-1 to 0]
        
        where d1 = [ln(S/K) + (r + σ²/2)T] / (σ√T)
              N(x) = cumulative normal distribution
        """
        
    def calculate_gamma(spot, strike, time_to_expiry, volatility, rate):
        """
        Calculate Gamma (same for CE/PE)
        
        Gamma = N'(d1) / (S * σ * √T)
        where N'(x) = normal probability density
        """
        
    def calculate_theta(spot, strike, time_to_expiry, volatility, rate, option_type):
        """
        Calculate Theta (time decay per day)
        
        CE Theta: -(S * N'(d1) * σ) / (2√T) - r * K * e^(-rT) * N(d2)
        PE Theta: -(S * N'(d1) * σ) / (2√T) + r * K * e^(-rT) * N(-d2)
        """
```

### 5.3 KiteAPIClient

```python
class KiteAPIClient:
    """
    Wrapper for Kite Connect API (Zerodha)
    
    Features:
    - Authentication (access token management)
    - Market data (quotes, option chain, historical)
    - Order placement (market, limit, SL orders)
    - Position management
    - Rate limiting
    """
    
    # Key Attributes
    api_key: str
    access_token: str
    kite: KiteConnect  # Official SDK instance
    
    rate_limiter: RateLimiter  # 3 calls/sec limit
    
    # Key Methods
    async def get_quote(symbol):
        """
        Fetch current market quote
        
        API: kite.quote(symbol)
        Returns: {
          last_price, volume, oi, ohlc, depth, ...
        }
        """
        
    async def get_option_chain(underlying, expiry=None):
        """
        Fetch option chain for underlying
        
        Process:
        1. Get all instruments for underlying
        2. Filter by option type (CE/PE)
        3. Filter by expiry (if provided)
        4. Fetch quotes for all options (batch)
        5. Return structured data
        
        Returns: List[{
          symbol, strike, type, expiry, 
          ltp, bid, ask, volume, oi, iv
        }]
        """
        
    async def place_order(symbol, transaction_type, quantity, order_type, price=None, trigger_price=None, variety="regular"):
        """
        Place order on exchange
        
        API: kite.place_order(
          variety="regular",
          exchange="NFO",
          tradingsymbol=symbol,
          transaction_type=transaction_type,  # BUY/SELL
          quantity=quantity,
          order_type=order_type,              # MARKET/LIMIT/SL
          price=price,
          trigger_price=trigger_price,
          product="MIS"                       # Intraday
        )
        
        Returns: order_id
        """
        
    async def get_positions():
        """
        Get current open positions
        
        API: kite.positions()
        Returns: {
          net: [...],  # Net positions
          day: [...]   # Day positions
        }
        """
        
    async def get_historical_data(symbol, from_date, to_date, interval):
        """
        Fetch historical OHLCV data
        
        API: kite.historical_data(
          instrument_token=token,
          from_date=from_date,
          to_date=to_date,
          interval=interval  # "minute", "5minute", "15minute", etc.
        )
        
        Returns: List[{
          date, open, high, low, close, volume
        }]
        """
```

### 5.4 HistoricalDataCache

```python
class HistoricalDataCache:
    """
    Caches historical data to reduce API calls
    
    Storage:
    - ClickHouse (historical_data table)
    - In-memory LRU cache for hot data
    
    Features:
    - Automatic refresh (configurable interval)
    - Gap detection & filling
    - Efficient range queries
    """
    
    # Key Attributes
    data_layer: ClickHouseDataLayer
    api_client: KiteAPIClient
    cache: Dict[str, DataFrame]  # symbol → DataFrame cache
    
    cache_ttl_hours: int = 24
    last_refresh: Dict[str, datetime]
    
    # Key Methods
    async def get_historical_data(symbol, interval, lookback_periods):
        """
        Get historical data (cache or fetch)
        
        Process:
        1. Check in-memory cache
        2. If cached & fresh: return
        3. If stale: check database
        4. If DB has data: update cache, return
        5. If DB missing/gaps: fetch from API
        6. Store to DB, update cache, return
        
        Returns: DataFrame with columns [timestamp, open, high, low, close, volume]
        """
        
    async def fetch_and_store(symbol, interval, from_date, to_date):
        """
        Fetch from API and store to database
        
        Process:
        1. Call api_client.get_historical_data()
        2. Convert to DataFrame
        3. Store to ClickHouse (historical_data table)
        4. Update in-memory cache
        5. Return DataFrame
        """
        
    def is_cache_fresh(symbol, interval):
        """
        Check if cached data is still fresh
        
        Logic:
        - last_refresh[key] + cache_ttl_hours > now()
        """
```

### 5.5 CandleAggregator

```python
class CandleAggregator:
    """
    Aggregates real-time ticks into OHLCV candles
    
    Features:
    - Multiple timeframe support (1m, 5m, 15m, etc.)
    - Tick-to-candle conversion
    - Incomplete candle handling
    - Database persistence
    """
    
    # Key Attributes
    data_layer: ClickHouseDataLayer
    
    # Candle buffers (one per symbol/timeframe)
    candle_buffers: Dict[str, List[Tick]]
    current_candles: Dict[str, Candle]
    
    # Supported timeframes
    timeframes: List[str] = ["1minute", "5minute", "15minute", "30minute", "60minute"]
    
    # Key Methods
    async def on_tick(tick):
        """
        Process incoming tick
        
        Process:
        1. Extract tick data (symbol, ltp, timestamp)
        2. For each tracked timeframe:
           a. Determine candle period (e.g., 5-min bucket)
           b. Check if new candle started
           c. If new: close previous, start new
           d. Update current candle (OHLCV)
        3. Store completed candles to DB
        4. Publish CANDLE_CLOSED event
        """
        
    def aggregate_ticks_to_candle(ticks, timeframe):
        """
        Aggregate list of ticks into single candle
        
        Logic:
        - open = first tick LTP
        - high = max tick LTP
        - low = min tick LTP
        - close = last tick LTP
        - volume = sum of tick volumes
        - timestamp = candle period start time
        """
        
    def get_current_candles(symbol, timeframe):
        """
        Get incomplete (current) candles
        
        Returns: List of incomplete candles for symbol/timeframe
        Used by strategies that want real-time data
        """
        
    def get_completed_candles(symbol, timeframe, limit):
        """
        Get completed candles from database
        
        Query: SELECT * FROM market_data
               WHERE symbol = ? AND interval = ?
               ORDER BY timestamp DESC
               LIMIT ?
        """
```

---

## 8. Database Schema Details

### 8.1 trading_signals Table

```sql
CREATE TABLE IF NOT EXISTS trading_signals (
    timestamp DateTime64(3),
    signal_id String,
    symbol String,
    asset_type String,         -- 'EQUITY', 'INDEX', 'OPTION'
    strategy String,            -- Strategy name that generated signal
    action String,              -- 'BUY' or 'SELL'
    price Float64,              -- Underlying price when signal generated
    quantity Int32,             -- Number of shares/lots
    confidence Float64,         -- Signal strength (0.0 to 1.0)
    target Float64,             -- Target price
    stop_loss Float64,          -- Stop loss price
    metadata String,            -- JSON metadata (indicators, parameters, etc.)
    
    INDEX idx_timestamp timestamp TYPE minmax GRANULARITY 3,
    INDEX idx_signal_id signal_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_symbol symbol TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_strategy strategy TYPE bloom_filter(0.01) GRANULARITY 1
) ENGINE = MergeTree()
ORDER BY (timestamp, signal_id)
PARTITION BY toYYYYMM(timestamp)
TTL timestamp + INTERVAL 90 DAY;
```

**Query Examples**:

```sql
-- Get all signals for symbol
SELECT * FROM trading_signals
WHERE symbol = 'NIFTY'
ORDER BY timestamp DESC
LIMIT 100;

-- Get signals by strategy
SELECT * FROM trading_signals
WHERE strategy = 'MACrossoverStrategy'
ORDER BY timestamp DESC;

-- Get recent signals (last 24 hours)
SELECT * FROM trading_signals
WHERE timestamp >= now() - INTERVAL 1 DAY
ORDER BY timestamp DESC;

-- Get signals with high confidence
SELECT * FROM trading_signals
WHERE confidence >= 0.7
ORDER BY confidence DESC, timestamp DESC;

-- Count signals by strategy
SELECT strategy, COUNT(*) as signal_count
FROM trading_signals
GROUP BY strategy
ORDER BY signal_count DESC;
```

### 8.2 positions Table

```sql
CREATE TABLE IF NOT EXISTS positions (
    position_id String,
    signal_id String,           -- Foreign key to trading_signals
    symbol String,              -- Option symbol (e.g., "NIFTY24JAN24000CE")
    underlying String,          -- Underlying symbol (e.g., "NIFTY")
    strike Float64,
    option_type String,         -- "CE" or "PE"
    expiry Date,
    
    entry_timestamp DateTime64(3),
    entry_premium Float64,
    quantity Int32,
    lot_size Int32,
    total_investment Float64,   -- entry_premium * quantity * lot_size
    
    stop_loss_premium Float64,
    target_premium Float64,
    
    current_premium Float64,
    unrealized_pnl Float64,
    
    exit_timestamp Nullable(DateTime64(3)),
    exit_premium Nullable(Float64),
    exit_reason Nullable(String),  -- "STOP_LOSS_HIT", "TARGET_REACHED", "EXPIRY_APPROACHING", "MANUAL"
    realized_pnl Nullable(Float64),
    
    status String,              -- "OPEN", "CLOSED"
    paper_trade Bool,           -- True if paper trading
    
    metadata String,            -- JSON metadata
    
    updated_at DateTime64(3) DEFAULT now(),
    
    INDEX idx_position_id position_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_signal_id signal_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_status status TYPE bloom_filter(0.01) GRANULARITY 1
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (entry_timestamp, position_id)
PARTITION BY toYYYYMM(entry_timestamp)
TTL entry_timestamp + INTERVAL 180 DAY;
```

**Query Examples**:

```sql
-- Get all open positions
SELECT * FROM positions
WHERE status = 'OPEN'
ORDER BY entry_timestamp DESC;

-- Get position by signal ID (for idempotency)
SELECT * FROM positions
WHERE signal_id = 'uuid-here'
LIMIT 1;

-- Get closed positions with P&L
SELECT position_id, symbol, entry_premium, exit_premium, realized_pnl, exit_reason
FROM positions
WHERE status = 'CLOSED'
ORDER BY exit_timestamp DESC
LIMIT 50;

-- Calculate total P&L
SELECT 
    COUNT(*) as total_trades,
    SUM(realized_pnl) as total_pnl,
    AVG(realized_pnl) as avg_pnl_per_trade,
    SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
    SUM(CASE WHEN realized_pnl <= 0 THEN 1 ELSE 0 END) as losing_trades
FROM positions
WHERE status = 'CLOSED';

-- Get positions for specific underlying
SELECT * FROM positions
WHERE underlying = 'NIFTY'
ORDER BY entry_timestamp DESC;
```

### 8.3 market_data Table

```sql
CREATE TABLE IF NOT EXISTS market_data (
    timestamp DateTime64(3),
    symbol String,
    interval String,            -- "1minute", "5minute", "15minute", etc.
    open Float64,
    high Float64,
    low Float64,
    close Float64,
    volume UInt64,
    vwap Float64,
    trades UInt32,
    
    INDEX idx_symbol symbol TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_timestamp timestamp TYPE minmax GRANULARITY 3
) ENGINE = MergeTree()
ORDER BY (symbol, interval, timestamp)
PARTITION BY (symbol, toYYYYMM(timestamp))
TTL timestamp + INTERVAL 30 DAY;
```

### 8.4 historical_data Table

```sql
CREATE TABLE IF NOT EXISTS historical_data (
    timestamp DateTime64(3),
    symbol String,
    interval String,
    open Float64,
    high Float64,
    low Float64,
    close Float64,
    volume UInt64,
    vwap Nullable(Float64),
    trades Nullable(UInt32),
    
    INDEX idx_symbol symbol TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_timestamp timestamp TYPE minmax GRANULARITY 3
) ENGINE = MergeTree()
ORDER BY (symbol, interval, timestamp)
PARTITION BY (symbol, toYYYYMM(timestamp))
TTL timestamp + INTERVAL 365 DAY;
```

### 8.5 options_data Table

```sql
CREATE TABLE IF NOT EXISTS options_data (
    timestamp DateTime64(3),
    symbol String,              -- Option symbol
    underlying String,
    strike Float64,
    option_type String,         -- "CE" or "PE"
    expiry Date,
    
    ltp Float64,
    bid Float64,
    ask Float64,
    volume UInt64,
    oi UInt64,                  -- Open interest
    
    iv Nullable(Float64),       -- Implied volatility
    delta Nullable(Float64),
    gamma Nullable(Float64),
    theta Nullable(Float64),
    vega Nullable(Float64),
    
    INDEX idx_symbol symbol TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_underlying underlying TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_timestamp timestamp TYPE minmax GRANULARITY 3
) ENGINE = ReplacingMergeTree(timestamp)
ORDER BY (underlying, expiry, strike, option_type, timestamp)
PARTITION BY (underlying, toYYYYMM(timestamp))
TTL timestamp + INTERVAL 7 DAY;
```

### 8.6 performance_metrics Table

```sql
CREATE TABLE IF NOT EXISTS performance_metrics (
    timestamp DateTime64(3),
    metric_name String,
    metric_value Float64,
    dimension String,           -- e.g., "strategy:MACrossover", "symbol:NIFTY"
    
    INDEX idx_metric_name metric_name TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_timestamp timestamp TYPE minmax GRANULARITY 3
) ENGINE = MergeTree()
ORDER BY (metric_name, dimension, timestamp)
PARTITION BY toYYYYMM(timestamp)
TTL timestamp + INTERVAL 90 DAY;
```

---

## 9. Event Types Reference

### 9.1 Complete Event Type Definitions

```python
from enum import Enum

class EventType(Enum):
    """All event types in the system"""
    
    # Data Events
    MARKET_DATA_TICK = "market_data_tick"           # New tick received
    CANDLE_CLOSED = "candle_closed"                 # Candle completed
    HISTORICAL_DATA_LOADED = "historical_data_loaded"  # Historical cache updated
    
    # Signal Events
    SIGNAL_GENERATED = "signal_generated"           # Strategy generated signal
    SIGNAL_VALIDATED = "signal_validated"           # Signal passed validation
    SIGNAL_REJECTED = "signal_rejected"             # Signal failed validation
    
    # Order Events
    ORDER_PLACED = "order_placed"                   # Order sent to exchange
    ORDER_FILLED = "order_filled"                   # Order executed
    ORDER_REJECTED = "order_rejected"               # Order rejected by exchange
    ORDER_CANCELLED = "order_cancelled"             # Order cancelled
    
    # Position Events
    POSITION_OPENED = "position_opened"             # New position created
    POSITION_UPDATED = "position_updated"           # Position values updated
    POSITION_CLOSED = "position_closed"             # Position exited
    
    # Risk Events
    RISK_LIMIT_REACHED = "risk_limit_reached"       # Risk limit triggered
    STOP_LOSS_HIT = "stop_loss_hit"                 # Position SL hit
    TARGET_REACHED = "target_reached"               # Position target reached
    
    # System Events
    STRATEGY_STARTED = "strategy_started"           # Strategy initialized
    STRATEGY_STOPPED = "strategy_stopped"           # Strategy shut down
    ERROR_OCCURRED = "error_occurred"               # System error
```

### 9.2 Event Data Structures

```python
# SIGNAL_GENERATED Event
{
    "event_type": "signal_generated",
    "timestamp": "2024-01-15T10:30:00.000Z",
    "signal": {
        "signal_id": "uuid-1234-5678",
        "symbol": "NIFTY",
        "strategy": "MACrossoverStrategy",
        "action": "BUY",
        "price": 21500.0,
        "confidence": 0.75,
        "target": 21650.0,
        "stop_loss": 21350.0,
        "expected_move_pct": 1.2,
        "metadata": {
            "ema_9": 21480.0,
            "ema_21": 21400.0,
            "crossover_type": "bullish"
        }
    }
}

# POSITION_OPENED Event
{
    "event_type": "position_opened",
    "timestamp": "2024-01-15T10:30:15.000Z",
    "position": {
        "position_id": "pos-uuid-abcd",
        "signal_id": "uuid-1234-5678",
        "symbol": "NIFTY24JAN21500CE",
        "underlying": "NIFTY",
        "strike": 21500.0,
        "option_type": "CE",
        "entry_premium": 150.5,
        "quantity": 2,
        "lot_size": 50,
        "total_investment": 15050.0,
        "stop_loss_premium": 105.35,
        "target_premium": 301.0,
        "paper_trade": true
    }
}

# POSITION_CLOSED Event
{
    "event_type": "position_closed",
    "timestamp": "2024-01-15T12:45:30.000Z",
    "position": {
        "position_id": "pos-uuid-abcd",
        "exit_premium": 180.75,
        "exit_reason": "TARGET_REACHED",
        "realized_pnl": 3025.0,
        "holding_period_minutes": 135
    }
}
```

---

## 10. Monitoring & Observability

### 10.1 Log Structure

All components log to structured JSON format:

```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "INFO",
  "component": "EventDrivenOptionsExecutor",
  "task_name": "Task-signal-uuid-1234",
  "event_type": "signal_generated",
  "message": "Processing signal",
  "context": {
    "signal_id": "uuid-1234",
    "symbol": "NIFTY",
    "action": "BUY"
  }
}
```

### 10.2 Key Metrics

**System Metrics**:
- `signals_generated_count`: Total signals generated
- `signals_validated_count`: Signals passed validation
- `signals_rejected_count`: Signals rejected
- `events_published_count`: Total events published
- `event_handler_duration_ms`: Handler execution time

**Trading Metrics**:
- `positions_opened_count`: Positions created
- `positions_closed_count`: Positions exited
- `total_pnl`: Cumulative P&L
- `win_rate_pct`: Winning trades percentage
- `avg_pnl_per_trade`: Average profit per trade

**Performance Metrics**:
- `strategy_execution_time_ms`: Strategy analysis duration
- `database_query_time_ms`: Database operation duration
- `api_call_time_ms`: API request duration
- `event_dispatch_time_ms`: Event routing duration

### 10.3 Monitoring Queries

```sql
-- System health check
SELECT 
    COUNT(*) as total_signals,
    COUNT(DISTINCT symbol) as unique_symbols,
    COUNT(DISTINCT strategy) as active_strategies
FROM trading_signals
WHERE timestamp >= now() - INTERVAL 1 HOUR;

-- Recent signal activity
SELECT 
    strategy,
    symbol,
    action,
    COUNT(*) as count
FROM trading_signals
WHERE timestamp >= now() - INTERVAL 1 DAY
GROUP BY strategy, symbol, action
ORDER BY count DESC;

-- Position performance
SELECT 
    status,
    paper_trade,
    COUNT(*) as count,
    SUM(CASE WHEN status='CLOSED' THEN realized_pnl ELSE 0 END) as total_pnl
FROM positions
GROUP BY status, paper_trade;

-- Event bus statistics (from logs)
-- Use log aggregation tools (ELK, Splunk, etc.)
```

---

## 11. Error Handling & Recovery

### 11.1 Error Categories

**Data Errors**:
- Missing historical data → Fetch from API
- Stale cache → Refresh cache
- Database connection failure → Retry with backoff

**Validation Errors**:
- Invalid symbol → Reject signal
- Duplicate signal → Skip (idempotency)
- Insufficient balance → Reject order

**API Errors**:
- Rate limit exceeded → Wait and retry
- Network timeout → Retry with backoff
- Authentication failure → Refresh token

**Execution Errors**:
- Order rejection → Log and notify
- Position not found → Query database
- Exit order failure → Retry and alert

### 11.2 Recovery Strategies

```python
# Database Connection Recovery
async def execute_with_retry(func, max_retries=3):
    """
    Execute database operation with retry
    
    Strategy:
    1. Try operation
    2. If fails: wait (exponential backoff)
    3. Retry up to max_retries
    4. If all fail: raise exception
    """
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                await asyncio.sleep(wait_time)
            else:
                raise

# API Rate Limiting
class RateLimiter:
    """
    Rate limit API calls (3 calls/second for Kite)
    
    Strategy:
    - Token bucket algorithm
    - Async sleep when limit reached
    - Configurable rate and burst
    """
    async def acquire():
        # Wait if no tokens available
        pass

# Event Handler Errors
# Each handler runs in isolated task
# Handler errors don't affect other handlers
# Errors logged with full context
```

---

## 12. Configuration Deep Dive

### 12.1 Complete Configuration Structure

```json
{
  "api": {
    "api_key": "your_api_key",
    "api_secret": "your_api_secret",
    "access_token": "your_access_token",
    "rate_limit_per_second": 3
  },
  
  "database": {
    "host": "localhost",
    "port": 9000,
    "database": "alphastock",
    "username": "default",
    "password": ""
  },
  
  "data_collection": {
    "realtime": {
      "enabled": true,
      "interval_seconds": 5,
      "symbols": ["NIFTY", "BANKNIFTY"],
      "batch_size": 5
    },
    "historical": {
      "enabled": true,
      "default_lookback_days": 90,
      "cache_refresh_hours": 24
    }
  },
  
  "strategies": {
    "ma_crossover": {
      "enabled": true,
      "timeframe": "15minute",
      "symbols": ["NIFTY", "BANKNIFTY"],
      "parameters": {
        "fast_period": 9,
        "slow_period": 21,
        "min_signal_strength": 0.6
      },
      "historical_lookback": {
        "periods": 1000,
        "min_periods": 50
      }
    }
  },
  
  "options_trading": {
    "enabled": true,
    "paper_trading": true,
    "logging_only_mode": true,
    
    "entry_filters": {
      "min_signal_strength": 0.6,
      "min_expected_move_pct": 1.0,
      "valid_underlyings": ["NIFTY", "BANKNIFTY"]
    },
    
    "strike_selection": {
      "prefer_atm": true,
      "max_strikes_from_atm": 3,
      "min_volume": 100,
      "min_oi": 1000,
      "expiry_preference": "weekly"
    },
    
    "position_sizing": {
      "risk_per_trade_pct": 2.0,
      "max_position_size_pct": 10.0,
      "account_capital": 100000.0
    },
    
    "risk_management": {
      "max_concurrent_positions": 3,
      "max_daily_loss_pct": 5.0,
      "stop_loss_pct": 30.0,
      "target_multiplier": 2.0,
      "trailing_stop_enabled": false
    }
  },
  
  "logging": {
    "level": "INFO",
    "file": "logs/alphastock.log",
    "rotation": "1 day",
    "retention": "30 days",
    "format": "json"
  },
  
  "event_bus": {
    "max_concurrent_handlers": 10,
    "handler_timeout_seconds": 30
  }
}
```

### 12.2 Mode Configuration

**MODE 1: Logging Only** (Current Default)
```json
{
  "options_trading": {
    "enabled": true,
    "logging_only_mode": true,   // ← Key flag
    "paper_trading": false
  }
}
```
- Signals logged but not executed
- No orders placed
- No positions created
- Safe for production monitoring

**MODE 2: Paper Trading**
```json
{
  "options_trading": {
    "enabled": true,
    "logging_only_mode": false,
    "paper_trading": true         // ← Key flag
  }
}
```
- Simulated positions
- No real orders
- P&L tracking
- Position monitoring active

**MODE 3: Live Trading**
```json
{
  "options_trading": {
    "enabled": true,
    "logging_only_mode": false,
    "paper_trading": false        // ← Both flags false
  }
}
```
- Real orders placed
- Actual capital at risk
- Full position management
- Requires careful risk controls

---

**Documentation Status**: ✅ Complete (Part 5 of 5)  
**Next**: See Part 6 for consolidated summary and quick reference
