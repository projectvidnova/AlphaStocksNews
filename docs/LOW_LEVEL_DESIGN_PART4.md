# AlphaStocks Trading System - Low Level Design Documentation (Part 4)

## Component Class Details (Continued)

### 4.5 SignalManager

```python
class SignalManager:
    """
    Manages signal lifecycle with database persistence
    
    Storage:
    - Primary: ClickHouse (trading_signals table)
    - Fallback: JSON file (data/signals/signals.json)
    - Cache: In-memory (active_signals dict)
    """
    
    # Key Attributes
    config: Dict
    api_client: KiteAPIClient
    data_layer: ClickHouseDataLayer
    active_signals: Dict[str, Signal]  # signal_id → Signal
    signals_file: str = "data/signals/signals.json"
    
    # Key Methods
    async def add_signal_from_strategy(strategy_name, symbol, strategy_signal) -> Signal:
        """
        Create signal from strategy output
        
        Process:
        1. Extract signal data (action, price, SL, target)
        2. Create Signal object with UUID
        3. Store to database (INSERT INTO trading_signals)
        4. Add to in-memory cache
        5. Save to JSON file (fallback)
        6. Emit SIGNAL_GENERATED event
        7. Return Signal object
        
        Returns: Signal with id, symbol, strategy, type, prices, metadata
        """
        
    async def save_signal(signal):
        """
        Persist signal to database
        
        SQL: INSERT INTO trading_signals (
               timestamp, signal_id, symbol, asset_type, strategy,
               action, price, quantity, confidence, target, stop_loss, metadata
             ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
    def save_signals():
        """Fallback: save to JSON file"""
        
    async def get_signals(symbol=None, strategy=None, start_time=None) -> List[Signal]:
        """Query signals from database"""
```

### 4.6 EventDrivenOptionsExecutor

```python
class EventDrivenOptionsExecutor:
    """
    Event-driven options trade executor (lock-free)
    
    Thread Safety:
    - Each signal = independent asyncio task
    - No shared state between signal processing
    - Database queries for idempotency
    - Atomic stats with Counter
    """
    
    # Key Attributes
    config: Dict
    api_client: KiteAPIClient
    data_layer: ClickHouseDataLayer
    event_bus: EventBus
    
    enabled: bool                 # Options trading enabled
    paper_trading: bool          # Paper/live mode
    logging_only_mode: bool      # Just log signals
    
    strike_selector: StrikeSelector
    greeks_calculator: OptionsGreeksCalculator
    position_manager: OptionsPositionManager
    
    stats: Counter  # Atomic statistics
    
    # Key Methods
    def initialize():
        """
        Subscribe to events
        
        Subscriptions:
        - SIGNAL_GENERATED → _on_signal_generated()
        """
        
    async def _on_signal_generated(event):
        """
        Handle SIGNAL_GENERATED event (runs in independent task)
        
        Process:
        1. Extract signal data from event
        2. Log receipt with task name
        3. Update stats (atomic)
        4. Validate signal (_validate_signal_event)
        5. If valid: _process_signal()
        6. If invalid: reject and log
        
        Thread Safety:
        - Runs in isolated asyncio task
        - No blocking other signal handlers
        - Database for state (idempotency)
        """
        
    async def _validate_signal_event(event_data) -> bool:
        """
        Validate signal before processing
        
        Checks:
        1. Idempotency: Already processed? (DB query)
        2. Symbol validity: Valid for options?
        3. Age check: Too old? (>24h)
        4. Configuration: Trading enabled?
        5. Risk limits: Max positions reached?
        
        Returns: True if valid, False otherwise
        """
        
    async def _process_signal(signal_data):
        """
        Process valid signal
        
        Steps:
        1. Select strike (_select_strike)
        2. Calculate position size
        3. Calculate exit levels (SL, target)
        4. Execute based on mode:
           - LOGGING_ONLY: Log details only
           - PAPER: Create paper position
           - LIVE: Place real order
        5. Update stats
        6. Emit events
        """
        
    async def _is_signal_already_processed(signal_id) -> bool:
        """
        Check if signal already processed (idempotency)
        
        Query: SELECT * FROM positions WHERE signal_id = ?
        Returns: True if position exists, False otherwise
        """
        
    async def _select_strike(symbol, action, underlying_price, expected_move):
        """
        Delegate to StrikeSelector
        
        Returns: {
          symbol, strike, type, expiry, ltp, delta, iv, lot_size
        }
        """
```

### 4.7 OptionsPositionManager

```python
class OptionsPositionManager:
    """
    Monitors and manages options positions
    
    Features:
    - Real-time position monitoring
    - Automatic exit on SL/target
    - P&L tracking
    - Paper/live mode support
    """
    
    # Key Attributes
    config: Dict
    api_client: KiteAPIClient
    data_layer: ClickHouseDataLayer
    paper_trading: bool
    logging_only_mode: bool
    
    active_positions: List[OptionsPosition]
    monitoring_task: asyncio.Task
    
    # Key Methods
    def add_position(position):
        """
        Add position to monitoring
        
        Steps:
        1. Add to active_positions list
        2. Store to database
        3. Emit POSITION_OPENED event
        4. Start monitoring (if not already running)
        """
        
    async def _monitor_positions():
        """
        Background task: monitor all active positions
        
        Loop (every 5 seconds):
        1. For each active position:
           a. Fetch current option LTP
           b. Calculate unrealized P&L
           c. Check exit conditions:
              - Stop loss hit?
              - Target reached?
              - Expiry approaching?
           d. If exit condition: close_position()
           e. Update position in database
        """
        
    async def close_position(position, reason):
        """
        Close position (paper or live)
        
        Steps:
        1. If PAPER: Just update records
        2. If LIVE: Place exit order
        3. Calculate realized P&L
        4. Update database (status=CLOSED)
        5. Remove from active_positions
        6. Emit POSITION_CLOSED event
        7. Log results
        """
        
    def get_position_by_signal(signal_id) -> Optional[OptionsPosition]:
        """
        Get position by signal ID (for idempotency)
        
        Query: SELECT * FROM positions WHERE signal_id = ?
        """
```

### 4.8 ClickHouseDataLayer

```python
class ClickHouseDataLayer:
    """
    Database interface for all persistence
    
    Thread Safety:
    - Thread-local clients (one per thread)
    - No locks needed
    - Concurrent queries safe
    """
    
    # Key Attributes
    config: Dict
    host: str
    port: int
    database: str
    _thread_local: threading.local()  # Thread-local storage
    
    # Tables
    TABLES = [
        'market_data',           # Real-time ticks
        'historical_data',       # OHLCV history
        'trading_signals',       # Generated signals
        'options_data',          # Options chain data
        'positions',             # Active/closed positions
        'performance_metrics'    # System performance
    ]
    
    # Key Methods
    def _get_thread_client():
        """Get or create thread-local ClickHouse client"""
        
    async def initialize():
        """
        Initialize database
        
        Steps:
        1. Connect to ClickHouse
        2. Create database if not exists
        3. Create all tables
        4. Verify connectivity
        """
        
    async def store_signal(signal_data) -> bool:
        """
        Store signal to trading_signals table
        
        SQL: INSERT INTO trading_signals (
               timestamp, signal_id, symbol, asset_type, strategy,
               action, price, quantity, confidence, target, stop_loss, metadata
             ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
    async def get_signals(symbol=None, strategy=None, start_time=None, end_time=None):
        """
        Query signals from trading_signals table
        
        SQL: SELECT * FROM trading_signals
             WHERE 1=1
               AND (symbol = ? OR ? IS NULL)
               AND (strategy = ? OR ? IS NULL)
               AND (timestamp >= ? OR ? IS NULL)
               AND (timestamp <= ? OR ? IS NULL)
             ORDER BY timestamp DESC
        """
        
    async def store_position(position_data) -> bool:
        """Store position to positions table"""
        
    async def get_historical_data(symbol, interval, limit) -> DataFrame:
        """
        Fetch historical candles
        
        SQL: SELECT timestamp, open, high, low, close, volume, vwap, trades
             FROM historical_data
             WHERE symbol = ? AND interval = ?
             ORDER BY timestamp DESC
             LIMIT ?
        """
```

---

## 5. Sequence Diagrams

### 5.1 Complete Signal Generation & Execution Flow

```
User/Scheduler          Orchestrator         DataManager         Strategy           SignalMgr         EventBus         OptionsExec         PositionMgr
     │                       │                    │                   │                  │                │                 │                   │
     ├──START SYSTEM─────────▶                    │                   │                  │                │                 │                   │
     │                       │                    │                   │                  │                │                 │                   │
     │                       ├─initialize()───────┤                   │                  │                │                 │                   │
     │                       │                    │                   │                  │                │                 │                   │
     │                       ├────────────────────┴─initialize()──────┤                  │                │                 │                   │
     │                       │                                         │                  │                │                 │                   │
     │                       ├─────────────────────────────────────────┴─initialize()─────┤                │                 │                   │
     │                       │                                                             │                │                 │                   │
     │                       ├──────────────────────────────────────────────────────────────────────────────┴─initialize()───┤                   │
     │                       │                                                                                                │                   │
     │                       ├─────────────────────────────────────────────────────────────────────────────────────────────────┴─initialize()────┤
     │                       │                                                                                                                    │
     │                   [SYSTEM READY]                                                                                                           │
     │                       │                                                                                                                    │
     │              [MAIN LOOP STARTS - Every 5 seconds]                                                                                          │
     │                       │                                                                                                                    │
     │                       ├─execute_strategies_for_symbol("NIFTY")─────────────────────▶                                                      │
     │                       │                                                             │                                                      │
     │                       │                              get_strategy_data("NIFTY") ────┤                                                      │
     │                       │                                                             │                                                      │
     │                       │                              [Merges Historical + Realtime] │                                                      │
     │                       │                                                             │                                                      │
     │                       │                              DataFrame (1000 candles) ◀─────┤                                                      │
     │                       │                                                                                                                    │
     │                       ├────────────────────────────────────analyze(symbol, data)────▶                                                      │
     │                       │                                                             │                                                      │
     │                       │                              [Calculate Indicators: EMA 9/21]│                                                     │
     │                       │                              [Detect Crossover]              │                                                      │
     │                       │                              [If crossover: generate signal] │                                                      │
     │                       │                                                             │                                                      │
     │                       │                                          StrategySignal ◀────┤                                                      │
     │                       │                                          (or None)                                                                  │
     │                       │                                                                                                                    │
     │                   [IF SIGNAL GENERATED]                                                                                                    │
     │                       │                                                                                                                    │
     │                       ├─_process_signal()──────────────────────────────────────────────────────▶                                           │
     │                       │                                                                         │                                           │
     │                       │                              add_signal_from_strategy() ───────────────┤                                           │
     │                       │                                                                         │                                           │
     │                       │                              [Create Signal object with UUID]           │                                           │
     │                       │                              [Store to trading_signals table]          │                                           │
     │                       │                              [Add to in-memory cache]                  │                                           │
     │                       │                              [Save to JSON file]                       │                                           │
     │                       │                                                                         │                                           │
     │                       │                              Signal(id, symbol, action...) ◀────────────┤                                           │
     │                       │                                                                         │                                           │
     │                       │                              publish(SIGNAL_GENERATED, {...})──────────▶                                           │
     │                       │                                                                                   │                                 │
     │                       │                              [EventBus dispatches to all subscribers]            │                                 │
     │                       │                                                                                   │                                 │
     │                       │                              [Creates independent task per subscriber]           │                                 │
     │                       │                                                                                   │                                 │
     │                       │                                                                         Task 1────┴──on_signal_generated(event)────▶
     │                       │                                                                                                                    │
     │                       │                                                                                  [Extract signal data]             │
     │                       │                                                                                  [Log with task name]              │
     │                       │                                                                                  [Update stats (atomic)]           │
     │                       │                                                                                                                    │
     │                       │                                                                                  [Validate signal]                 │
     │                       │                                                                                  ├─_is_signal_processed?()──────────▶
     │                       │                                                                                  │                   [DB Query]    │
     │                       │                                                                                  │                   False ◀────────┤
     │                       │                                                                                  │                                 │
     │                       │                                                                                  [Check symbol validity]           │
     │                       │                                                                                  [Check age]                       │
     │                       │                                                                                  [Check config]                    │
     │                       │                                                                                                                    │
     │                       │                                                                              [IF VALID]                             │
     │                       │                                                                                  │                                 │
     │                       │                                                                                  ├─_process_signal()               │
     │                       │                                                                                  │                                 │
     │                       │                                                                                  ├─select_strike()                 │
     │                       │                                                                                  │  [Get option chain]             │
     │                       │                                                                                  │  [Filter by liquidity]          │
     │                       │                                                                                  │  [Calculate scores]             │
     │                       │                                                                                  │  [Return best strike]           │
     │                       │                                                                                  │                                 │
     │                       │                                                                                  ├─calculate_position_size()      │
     │                       │                                                                                  │                                 │
     │                       │                                                                                  ├─calculate_exit_levels()        │
     │                       │                                                                                  │                                 │
     │                       │                                                                          [MODE CHECK]                               │
     │                       │                                                                                  │                                 │
     │                   [IF LOGGING_ONLY_MODE = TRUE]  ← CURRENT DEFAULT                                      │                                 │
     │                       │                                                                                  │                                 │
     │                       │                                                                                  ├─Log signal details              │
     │                       │                                                                                  │  • Symbol, action, prices       │
     │                       │                                                                                  │  • Strike, premium, quantity    │
     │                       │                                                                                  │  • SL, target, P&L estimates    │
     │                       │                                                                                  │  • "No order placed (logging)"  │
     │                       │                                                                                  │                                 │
     │                       │                                                                                  ├─Update stats                    │
     │                       │                                                                                  │  logging_only_trades++          │
     │                       │                                                                                  │                                 │
     │                       │                                                                                  ├─publish(SIGNAL_ACTIVATED)──────▶
     │                       │                                                                                  │                                 │
     │                       │                                                                                  └─[DONE - No execution]          │
     │                       │                                                                                                                    │
     │                   [IF PAPER_TRADING = TRUE]                                                                                                │
     │                       │                                                                                  │                                 │
     │                       │                                                                                  ├─create_paper_position()─────────▶
     │                       │                                                                                  │                   [Create pos]  │
     │                       │                                                                                  │                   [Store DB]    │
     │                       │                                                                                  │                   [Start monitor]│
     │                       │                                                                                  │                   Position ◀─────┤
     │                       │                                                                                  │                                 │
     │                       │                                                                                  └─[Position monitored in background]
     │                       │                                                                                                                    │
     │                   [IF LIVE_TRADING = TRUE]                                                                                                 │
     │                       │                                                                                  │                                 │
     │                       │                                                                                  ├─place_order()                   │
     │                       │                                                                                  │  [Validate balance]             │
     │                       │                                                                                  │  [Place real order]             │
     │                       │                                                                                  │  [Wait for fill]                │
     │                       │                                                                                  │  [Create position]──────────────▶
     │                       │                                                                                  │                                 │
     │                       │                                                                                  └─[Position monitored in background]
     │                       │                                                                                                                    │
     │              [LOOP CONTINUES - Next symbol/strategy]                                                                                       │
     │                       │                                                                                                                    │
```

### 5.2 Position Monitoring Flow (Paper/Live)

```
PositionManager [Background Task - Every 5 seconds]         Database            API
       │                                                        │                 │
       ├─[MONITOR LOOP STARTS]                                 │                 │
       │                                                        │                 │
       ├─for each active_position:                             │                 │
       │                                                        │                 │
       ├──fetch_current_premium(option_symbol)─────────────────────────────────▶ │
       │                                                                current_ltp│
       │                                                                          │
       ├─calculate_pnl()                                                         │
       │  • unrealized_pnl = (current - entry) * quantity                        │
       │  • pnl_pct = (current / entry - 1) * 100                                │
       │                                                                          │
       ├─check_exit_conditions()                                                 │
       │  ┌─if current_ltp <= stop_loss_premium:                                │
       │  │   reason = "STOP_LOSS_HIT"                                           │
       │  │   exit_position()                                                    │
       │  │                                                                       │
       │  ├─elif current_ltp >= target_premium:                                  │
       │  │   reason = "TARGET_REACHED"                                          │
       │  │   exit_position()                                                    │
       │  │                                                                       │
       │  └─elif time_to_expiry < 1_hour:                                        │
       │      reason = "EXPIRY_APPROACHING"                                      │
       │      exit_position()                                                    │
       │                                                                          │
       ├─[IF EXIT CONDITION MET]                                                 │
       │                                                                          │
       ├──close_position(position, reason)                                       │
       │  │                                                                       │
       │  ├─if PAPER_TRADING:                                                    │
       │  │   [Just update records, no real order]                               │
       │  │                                                                       │
       │  ├─elif LIVE_TRADING:                                                   │
       │  │   place_exit_order()───────────────────────────────────────────────▶ │
       │  │                                                                       │
       │  ├─calculate_realized_pnl()                                             │
       │  │                                                                       │
       │  ├─UPDATE positions SET────────────────────────────────▶                │
       │  │   status='CLOSED',                                  │                │
       │  │   exit_premium=?,                                   │                │
       │  │   exit_timestamp=NOW(),                             │                │
       │  │   exit_reason=?,                                    │                │
       │  │   realized_pnl=?                                    │                │
       │  │   WHERE position_id=?                               │                │
       │  │                                                      │                │
       │  ├─remove_from_active_positions()                      │                │
       │  │                                                      │                │
       │  └─publish(POSITION_CLOSED, {...})──────────────────▶EventBus           │
       │                                                                          │
       ├─[ELSE: Update position]                                                 │
       │                                                                          │
       └──UPDATE positions SET────────────────────────────────▶                  │
          current_premium=?,                                   │                 │
          unrealized_pnl=?,                                    │                 │
          updated_at=NOW()                                     │                 │
          WHERE position_id=?                                  │                 │
                                                               │                 │
       [SLEEP 5 SECONDS]                                                         │
       [LOOP CONTINUES]                                                          │
```

---

## 6. Configuration Reference

### 6.1 Options Trading Configuration

```json
{
  "options_trading": {
    "enabled": true,
    "paper_trading": true,
    "logging_only_mode": true,    // ← CURRENT DEFAULT
    
    "entry_filters": {
      "min_signal_strength": 0.6,
      "min_expected_move_pct": 1.0,
      "valid_underlyings": [
        "NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY",
        "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"
      ]
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
  }
}
```

### 6.2 Data Pipeline Configuration

```json
{
  "data_collection": {
    "realtime": {
      "enabled": true,
      "interval_seconds": 5,
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
      "timeframe": "15minute",
      "historical_lookback": {
        "periods": 1000,
        "min_periods": 50
      },
      "realtime_aggregation": {
        "enabled": true,
        "include_incomplete": true
      }
    }
  }
}
```

---

## 7. Summary

### Data Flow Summary

```
Historical Data (DB) ─┐
                      ├─▶ StrategyDataManager ─▶ Strategy ─▶ Signal ─▶ EventBus ─▶ OptionsExecutor
Realtime Ticks ──────┘                                                                      │
                                                                                            │
                                                                                            ▼
                                                                                     [MODE CHECK]
                                                                                            │
                                                                    ┌───────────────────────┼───────────────┐
                                                                    ▼                       ▼               ▼
                                                              LOGGING_ONLY            PAPER_TRADING    LIVE_TRADING
                                                              (Log only)              (Simulate)       (Real orders)
```

### Key Design Patterns

1. **Event-Driven Architecture**: EventBus with pub-sub for loose coupling
2. **Lock-Free Concurrency**: Atomic operations, immutable data, independent tasks
3. **Database as Truth**: ClickHouse for all persistent state
4. **Mode-Based Execution**: Logging → Paper → Live progression
5. **Complete Event Context**: Events contain all data (no external lookups)
6. **Handler Isolation**: Each event handler = independent asyncio task

### Production Ready Checklist

- ✅ Lock-free architecture implemented
- ✅ Event-driven signal processing
- ✅ Database persistence (trading_signals table)
- ✅ Logging only mode (default, safe)
- ✅ Paper trading mode (for testing)
- ✅ Live trading mode (requires activation)
- ✅ Comprehensive logging (27+ log points)
- ✅ Signal validation & filtering
- ✅ Idempotency checks
- ✅ Risk management controls

---

**Documentation Status**: ✅ Complete  
**System Status**: ✅ Production Ready (Logging Only Mode)  
**Next Steps**: Monitor in logging mode, validate signals, enable paper trading when ready
