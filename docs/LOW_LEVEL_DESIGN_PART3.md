# AlphaStocks Trading System - Low Level Design Documentation (Part 3)

## Execution Modes and Class Details

```
PHASE 5: ORDER PLACEMENT (MODE-DEPENDENT)
══════════════════════════════════════════

Step 13: Mode Selection & Execution
┌────────────────────────────────────────────────────────────────┐
│  EventDrivenOptionsExecutor._execute_trade()                   │
│                                                                │
│  Configuration Check:                                          │
│  ├─▶ self.logging_only_mode = config["logging_only_mode"]    │
│  ├─▶ self.paper_trading = config["paper_trading"]            │
│  └─▶ self.enabled = config["enabled"]                        │
│                                                                │
│  Decision Tree:                                                │
│                                                                │
│  if not self.enabled:                                         │
│    └─▶ Skip execution entirely                                │
│                                                                │
│  elif self.logging_only_mode:  ← CURRENT DEFAULT MODE        │
│    └─▶ Go to MODE 1: Logging Only                            │
│                                                                │
│  elif self.paper_trading:                                     │
│    └─▶ Go to MODE 2: Paper Trading                           │
│                                                                │
│  else:                                                         │
│    └─▶ Go to MODE 3: Live Trading                            │
└────────────────────────────────────────────────────────────────┘
                     │
                     ├─────────────┬─────────────┬─────────────┐
                     ▼             ▼             ▼             ▼
              ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌──────────┐
              │  MODE 1   │ │  MODE 2   │ │  MODE 3   │ │ DISABLED │
              │  LOGGING  │ │  PAPER    │ │   LIVE    │ │  SKIP    │
              │   ONLY    │ │  TRADING  │ │  TRADING  │ │          │
              └───────────┘ └───────────┘ └───────────┘ └──────────┘


MODE 1: LOGGING ONLY (Current Production Mode)
═══════════════════════════════════════════════

┌────────────────────────────────────────────────────────────────┐
│  Purpose: Log signals without any execution                    │
│  Use Case: Development, testing, signal validation             │
│  Risk: NONE - No actual trading                                │
└────────────────────────────────────────────────────────────────┘

Step 13.1: Log Signal Details
┌────────────────────────────────────────────────────────────────┐
│  Logger Output:                                                │
│    INFO - 📊 LOGGING ONLY MODE - Signal Details:              │
│    INFO -   Signal ID: abc123                                 │
│    INFO -   Symbol: NIFTY                                     │
│    INFO -   Action: BUY                                       │
│    INFO -   Underlying Price: ₹24,500.00                      │
│    INFO -   Selected Strike: NIFTY25OCT24500CE                │
│    INFO -   Strike Price: 24,500                              │
│    INFO -   Option Premium: ₹125.50                           │
│    INFO -   Quantity: 50 (1 lot)                              │
│    INFO -   Total Cost: ₹6,275.00                             │
│    INFO -   Stop Loss: ₹87.85 (-30%)                          │
│    INFO -   Target: ₹130.52 (+4%)                             │
│    INFO -   Max Loss: ₹1,882.50                               │
│    INFO -   Max Profit: ₹251.00                               │
│    INFO -   Risk/Reward: 1:0.13                               │
│    INFO - 📝 No order placed (logging only mode)              │
│                                                                │
│  Stats Update:                                                │
│    self.stats["logging_only_trades"] += 1                     │
│    self.stats["signals_processed"] += 1                       │
│                                                                │
│  Database Storage:                                             │
│  └─▶ INSERT INTO trading_signals                             │
│      SET status = 'LOGGED'                                    │
│      WHERE signal_id = 'abc123'                               │
│                                                                │
│  Event Publication:                                            │
│  └─▶ EventBus.publish(                                        │
│        EventType.SIGNAL_ACTIVATED,                            │
│        data={                                                  │
│          "signal_id": "abc123",                               │
│          "mode": "LOGGING_ONLY",                              │
│          "action_taken": "LOGGED"                             │
│        }                                                       │
│      )                                                         │
│                                                                │
│  Result: Signal logged, no further action                     │
└────────────────────────────────────────────────────────────────┘


MODE 2: PAPER TRADING (Simulation Mode)
════════════════════════════════════════

┌────────────────────────────────────────────────────────────────┐
│  Purpose: Simulate trades for backtesting & strategy validation│
│  Use Case: Strategy testing with realistic P&L tracking        │
│  Risk: NONE - Virtual trades only                              │
└────────────────────────────────────────────────────────────────┘

Step 13.2: Create Simulated Position
┌────────────────────────────────────────────────────────────────┐
│  PositionManager.create_paper_position()                       │
│                                                                │
│  Create Position Object:                                       │
│  └─▶ position = OptionsPosition(                              │
│        position_id = uuid4(),                                  │
│        signal_id = "abc123",                                   │
│        option_symbol = "NIFTY25OCT24500CE",                   │
│        underlying_symbol = "NIFTY",                            │
│        underlying_entry_price = 24500.0,                       │
│        strike = 24500.0,                                       │
│        option_type = "CE",                                     │
│        action = "BUY",                                         │
│        entry_premium = 125.50,                                 │
│        quantity = 50,                                          │
│        lot_size = 50,                                          │
│        stop_loss_premium = 87.85,                              │
│        target_premium = 130.52,                                │
│        status = "OPEN",                                        │
│        mode = "PAPER",                                         │
│        entry_timestamp = datetime.now(),                       │
│        is_paper_trade = True                                   │
│      )                                                          │
│                                                                │
│  Store to Database:                                            │
│  └─▶ INSERT INTO positions VALUES (...)                       │
│                                                                │
│  Logger Output:                                                │
│    INFO - 📄 PAPER TRADE - Position opened                    │
│    INFO -   Position ID: xyz789                               │
│    INFO -   Option: NIFTY25OCT24500CE @ ₹125.50              │
│    INFO -   Quantity: 50, Cost: ₹6,275.00                     │
│    INFO - 🔍 Monitoring started (paper mode)                  │
│                                                                │
│  Stats Update:                                                │
│    self.stats["paper_trades"] += 1                            │
│    self.stats["trades_executed"] += 1                         │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
Step 13.3: Position Monitoring (Paper)
┌────────────────────────────────────────────────────────────────┐
│  PositionManager._monitor_positions() [Background task]        │
│  Runs every 5 seconds                                          │
│                                                                │
│  For each open position:                                       │
│  ├─▶ Fetch current market price                              │
│  │   └─▶ current_premium = get_option_ltp(option_symbol)     │
│  │                                                             │
│  ├─▶ Calculate P&L                                            │
│  │   • unrealized_pnl = (current_premium - entry_premium) * qty│
│  │   • pnl_pct = (current_premium / entry_premium - 1) * 100 │
│  │                                                             │
│  ├─▶ Check Exit Conditions                                    │
│  │   if current_premium <= stop_loss_premium:                 │
│  │     └─▶ close_position(reason="STOP_LOSS_HIT")            │
│  │   elif current_premium >= target_premium:                  │
│  │     └─▶ close_position(reason="TARGET_REACHED")           │
│  │   elif time_to_expiry < 1 hour:                           │
│  │     └─▶ close_position(reason="EXPIRY_APPROACHING")       │
│  │                                                             │
│  └─▶ Update position in database                             │
│      └─▶ UPDATE positions SET                                │
│          current_premium = ?,                                 │
│          unrealized_pnl = ?,                                  │
│          updated_at = NOW()                                   │
│          WHERE position_id = ?                                │
│                                                                │
│  Logger Output:                                                │
│    DEBUG - Position xyz789: LTP=₹128.00, P&L=₹125 (+2%)      │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼ (if exit condition met)
Step 13.4: Position Exit (Paper)
┌────────────────────────────────────────────────────────────────┐
│  PositionManager.close_position(position, reason)              │
│                                                                │
│  Update Position:                                              │
│  └─▶ position.status = "CLOSED"                              │
│      position.exit_premium = current_premium                  │
│      position.exit_timestamp = datetime.now()                 │
│      position.exit_reason = "TARGET_REACHED"                  │
│      position.realized_pnl = (exit - entry) * quantity        │
│                                                                │
│  Store to Database:                                            │
│  └─▶ UPDATE positions SET                                    │
│        status = 'CLOSED',                                     │
│        exit_premium = ?,                                      │
│        exit_timestamp = NOW(),                                │
│        exit_reason = ?,                                       │
│        realized_pnl = ?                                       │
│      WHERE position_id = ?                                    │
│                                                                │
│  Logger Output:                                                │
│    INFO - 🎉 PAPER TRADE CLOSED                               │
│    INFO -   Position ID: xyz789                               │
│    INFO -   Exit Premium: ₹130.52                             │
│    INFO -   Exit Reason: TARGET_REACHED                       │
│    INFO -   Realized P&L: ₹251.00 (+4.0%)                     │
│    INFO -   Duration: 2h 15m                                  │
│                                                                │
│  Event Publication:                                            │
│  └─▶ EventBus.publish(                                        │
│        EventType.POSITION_CLOSED,                             │
│        data={                                                  │
│          "position_id": "xyz789",                             │
│          "signal_id": "abc123",                               │
│          "realized_pnl": 251.0,                               │
│          "exit_reason": "TARGET_REACHED",                     │
│          "mode": "PAPER"                                      │
│        }                                                       │
│      )                                                         │
└────────────────────────────────────────────────────────────────┘


MODE 3: LIVE TRADING (Real Money)
══════════════════════════════════

┌────────────────────────────────────────────────────────────────┐
│  Purpose: Execute real trades with actual capital              │
│  Use Case: Production trading after thorough testing           │
│  Risk: HIGH - Real money at stake                              │
│  ⚠️  Requires: Verified API credentials, sufficient balance    │
└────────────────────────────────────────────────────────────────┘

Step 13.5: Pre-Trade Validations
┌────────────────────────────────────────────────────────────────┐
│  Before placing real order:                                    │
│                                                                │
│  Check 1: Account Balance                                      │
│  ├─▶ available_margin = api_client.get_margins()             │
│  │   if available_margin < required_margin:                  │
│  │     └─▶ Reject: Insufficient funds                        │
│  │                                                             │
│  Check 2: Position Limits                                      │
│  ├─▶ open_positions = count_open_positions()                 │
│  │   if open_positions >= max_positions:                     │
│  │     └─▶ Reject: Position limit exceeded                   │
│  │                                                             │
│  Check 3: Daily Loss Limit                                     │
│  ├─▶ today_pnl = calculate_today_pnl()                       │
│  │   if today_pnl <= -max_daily_loss:                        │
│  │     └─▶ Reject: Daily loss limit hit                      │
│  │                                                             │
│  Check 4: Market Hours                                         │
│  └─▶ if not is_market_open():                                │
│      └─▶ Reject: Market closed                               │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼ (if all checks pass)
Step 13.6: Place Real Order
┌────────────────────────────────────────────────────────────────┐
│  KiteAPIClient.place_order()                                   │
│                                                                │
│  Order Parameters:                                             │
│  └─▶ order = {                                                │
│        "tradingsymbol": "NIFTY25OCT24500CE",                  │
│        "exchange": "NFO",                                     │
│        "transaction_type": "BUY",                             │
│        "order_type": "LIMIT",                                 │
│        "quantity": 50,                                         │
│        "price": 125.50,                                       │
│        "product": "NRML",  # Normal (delivery)                │
│        "validity": "DAY",                                     │
│        "variety": "regular"                                   │
│      }                                                          │
│                                                                │
│  API Call:                                                     │
│  └─▶ POST https://api.kite.trade/orders/regular              │
│      Headers: {                                                │
│        "Authorization": "token api_key:access_token"          │
│      }                                                          │
│      Body: order_params                                       │
│                                                                │
│  Response:                                                     │
│  └─▶ {                                                        │
│        "status": "success",                                   │
│        "data": {                                               │
│          "order_id": "220610000123456"                        │
│        }                                                       │
│      }                                                          │
│                                                                │
│  Logger Output:                                                │
│    INFO - 💰 LIVE ORDER PLACED                                │
│    INFO -   Order ID: 220610000123456                         │
│    INFO -   Symbol: NIFTY25OCT24500CE                         │
│    INFO -   Type: BUY LIMIT                                   │
│    INFO -   Quantity: 50 @ ₹125.50                            │
│    INFO - ⏳ Awaiting order confirmation...                   │
│                                                                │
│  Stats Update:                                                │
│    self.stats["live_trades"] += 1                             │
│    self.stats["trades_executed"] += 1                         │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
Step 13.7: Order Confirmation & Position Creation
┌────────────────────────────────────────────────────────────────┐
│  Wait for order fill (polling or webhook)                      │
│                                                                │
│  ├─▶ order_status = api_client.get_order_status(order_id)    │
│  │   if order_status == "COMPLETE":                           │
│  │     └─▶ Order filled successfully                          │
│  │         • avg_fill_price = 125.45  (might differ slightly) │
│  │         • filled_quantity = 50                             │
│  │                                                             │
│  │   elif order_status == "REJECTED":                         │
│  │     └─▶ Order rejected (insufficient margin, etc.)         │
│  │         Handle error, notify, cleanup                      │
│  │                                                             │
│  └─▶ Create Position (same as paper, but is_paper=False)     │
│                                                                │
│  Event Publication:                                            │
│  └─▶ EventBus.publish(EventType.ORDER_FILLED, {...})         │
│      EventBus.publish(EventType.POSITION_OPENED, {...})       │
│                                                                │
│  Logger Output:                                                │
│    INFO - ✅ ORDER FILLED                                      │
│    INFO -   Order ID: 220610000123456                         │
│    INFO -   Avg Price: ₹125.45 (better than limit!)          │
│    INFO -   Position ID: live-xyz789                          │
│    INFO - 📊 Real-time monitoring activated                   │
└────────────────────────────────────────────────────────────────┘

(Position monitoring for live trades follows same logic as paper,
 but with real-time price updates and actual order placement for exits)
```

---

## 4. Component Class Details

### 4.1 AlphaStockOrchestrator

```python
class AlphaStockOrchestrator:
    """
    Main system coordinator
    
    Responsibilities:
    - Initialize all components
    - Coordinate data flow
    - Manage system lifecycle
    - Handle graceful shutdown
    """
    
    # Key Attributes
    config: Dict                              # System configuration
    api_client: KiteAPIClient                 # Broker API
    data_layer: ClickHouseDataLayer          # Database
    event_bus: EventBus                      # Message bus
    market_data_runner: MarketDataRunner     # Tick collector
    candle_aggregator: CandleAggregator      # Tick→Candle
    historical_cache: HistoricalDataCache    # Historical data
    strategy_data_manager: StrategyDataManager  # Data coordinator
    strategy_factory: StrategyFactory        # Strategy creator
    signal_manager: SignalManager            # Signal handler
    options_executor: EventDrivenOptionsExecutor  # Trade executor
    
    # Key Methods
    async def initialize():
        """Initialize all components in correct order"""
        
    async def start():
        """Start main trading loop"""
        
    async def _execute_strategies_for_symbol(symbol, runner):
        """Execute strategies for one symbol"""
        # 1. Get data via StrategyDataManager
        # 2. Run each strategy
        # 3. Process signals
        
    async def _process_signal(strategy, signal, symbol):
        """Handle signal from strategy"""
        # 1. Log signal
        # 2. Store via SignalManager
        # 3. Emit event
        
    async def shutdown():
        """Graceful shutdown"""
```

### 4.2 StrategyDataManager

```python
class StrategyDataManager:
    """
    Coordinates historical + realtime data for strategies
    
    Data Flow:
    HistoricalCache + CandleAggregator → Merged DataFrame → Strategy
    """
    
    # Key Attributes
    config: Dict
    data_layer: ClickHouseDataLayer
    candle_aggregator: CandleAggregator
    historical_cache: HistoricalDataCache
    
    # Key Methods
    def get_strategy_data(symbol, strategy_config, asset_type) -> DataFrame:
        """
        Get complete dataset for strategy
        
        Process:
        1. _get_historical_data() → Historical candles
        2. _get_realtime_candles() → Recent candles
        3. _merge_data() → Combined dataset
        4. _validate_data() → Quality check
        5. Return sliced DataFrame
        
        Returns: DataFrame with [timestamp, open, high, low, close, volume]
        """
        
    def _get_historical_data(symbol, timeframe, periods, asset_type) -> DataFrame:
        """Fetch from cache/database"""
        
    def _get_realtime_candles(symbol, timeframe, include_incomplete) -> DataFrame:
        """Fetch from aggregator"""
        
    def _merge_data(historical_df, realtime_df, timeframe) -> DataFrame:
        """Merge without duplicates, handle gaps"""
        
    def _validate_data(df, min_periods, required_periods, symbol, timeframe) -> Dict:
        """Check data quality"""
```

### 4.3 CandleAggregator

```python
class CandleAggregator:
    """
    Converts real-time ticks to candles (lock-free)
    
    Thread Safety:
    - Atomic operations with Counter
    - Immutable tick data
    - Independent processing per symbol
    """
    
    # Key Attributes
    active_candles: Dict[Tuple[str, str], Candle]  # (symbol, timeframe) → candle
    completed_candles: deque  # Circular buffer
    stats: Counter  # Atomic statistics
    
    # Key Methods
    def process_tick(symbol, tick_data):
        """
        Process incoming tick
        
        Steps:
        1. Get or create active candle for (symbol, timeframe)
        2. Update candle OHLCV atomically
        3. Check if candle period complete
        4. If complete: finalize_candle()
        """
        
    def finalize_candle(symbol, timeframe):
        """
        Finalize completed candle
        
        Steps:
        1. Calculate final values
        2. Store to database
        3. Add to completed_candles deque
        4. Emit CANDLE_COMPLETED event
        5. Create new active candle
        """
        
    def get_completed_candles(symbol, timeframe, count) -> List[Candle]:
        """Get recent completed candles"""
```

### 4.4 EventBus

```python
class EventBus:
    """
    Central pub-sub message bus (lock-free)
    
    Thread Safety:
    - Immutable Event objects
    - Independent task per handler
    - No shared mutable state
    - Atomic stats with Counter
    """
    
    # Key Attributes
    subscriptions: Dict[EventType, List[Subscription]]
    wildcard_subscriptions: List[Subscription]
    _stats: Counter  # Atomic counters
    _event_history: deque  # Circular buffer
    
    # Key Methods
    def subscribe(event_type, handler, subscriber_id, filter_fn=None):
        """Register event handler"""
        
    async def publish(event_type, data, source=None, priority=NORMAL):
        """
        Publish event to all subscribers
        
        Process:
        1. Create immutable Event object
        2. Find matching subscriptions
        3. For each subscription:
           asyncio.create_task(_execute_handler(sub, event))
        4. All handlers run in parallel (lock-free)
        """
        
    async def _execute_handler(subscription, event):
        """
        Execute handler in isolated task
        
        Features:
        - Timeout protection (30s)
        - Exception handling
        - Logging with task name
        - No blocking other handlers
        """
```

