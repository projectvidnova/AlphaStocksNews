# AlphaStocks Trading System - Complete Low Level Design

> **Comprehensive Documentation**: This document consolidates the complete low-level design of the AlphaStocks trading system, covering architecture, data flow, signal processing, execution modes, database schema, and operational procedures.

---

## 📑 Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Principles](#2-architecture-principles)
3. [Complete Data Flow](#3-complete-data-flow)
4. [Component Details](#4-component-details)
5. [Signal Processing Pipeline](#5-signal-processing-pipeline)
6. [Execution Modes](#6-execution-modes)
7. [Database Schema](#7-database-schema)
8. [Event-Driven Architecture](#8-event-driven-architecture)
9. [Configuration Reference](#9-configuration-reference)
10. [Monitoring & Operations](#10-monitoring--operations)
11. [Troubleshooting Guide](#11-troubleshooting-guide)
12. [Deployment Checklist](#12-deployment-checklist)

> **Note**: For detailed section-by-section documentation, see individual parts: [PART1](LOW_LEVEL_DESIGN_PART1.md) | [PART2](LOW_LEVEL_DESIGN_PART2.md) | [PART3](LOW_LEVEL_DESIGN_PART3.md) | [PART4](LOW_LEVEL_DESIGN_PART4.md) | [PART5](LOW_LEVEL_DESIGN_PART5.md) | [PART6](LOW_LEVEL_DESIGN_PART6.md)

---

## 1. System Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           ALPHASTOCK TRADING SYSTEM                              │
│                         Event-Driven Architecture (Lock-Free)                    │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│  Data Layer     │         │  Strategy Layer │         │ Execution Layer │
│                 │         │                 │         │                 │
│ • MarketData    │────────▶│ • MA Crossover  │────────▶│ • Signal Mgr    │
│ • Historical    │         │ • RSI Strategy  │         │ • Options Exec  │
│ • CandleAgg     │         │ • Momentum      │         │ • Position Mgr  │
└─────────────────┘         └─────────────────┘         └─────────────────┘
         │                           │                           │
         └───────────────────────────┼───────────────────────────┘
                                     │
                            ┌────────▼────────┐
                            │    EventBus     │
                            │  (Pub-Sub)      │
                            └─────────────────┘
                                     │
                            ┌────────▼────────┐
                            │  ClickHouse DB  │
                            │  (Persistence)  │
                            └─────────────────┘
```

### Key System Components

| Component | Purpose | Key Methods |
|-----------|---------|-------------|
| **AlphaStockOrchestrator** | Main coordinator, runs main loop | `run()`, `execute_strategies_for_symbol()` |
| **MarketDataRunner** | Fetch real-time ticks from Kite API | `fetch_realtime_data()`, `start()` |
| **CandleAggregator** | Convert ticks to OHLCV candles | `on_tick()`, `aggregate_ticks_to_candle()` |
| **HistoricalDataCache** | Cache & manage historical data | `get_historical_data()`, `fetch_and_store()` |
| **StrategyDataManager** | Merge historical + realtime data | `get_strategy_data()` |
| **Strategy** (Base) | Generate trading signals | `analyze()`, `should_buy()`, `should_sell()` |
| **SignalManager** | Store & manage signals | `add_signal_from_strategy()`, `save_signal()` |
| **EventBus** | Event distribution (pub-sub) | `publish()`, `subscribe()` |
| **EventDrivenOptionsExecutor** | Execute option trades | `_on_signal_generated()`, `_process_signal()` |
| **StrikeSelector** | Select optimal option strike | `select_strike()`, `calculate_strike_score()` |
| **OptionsPositionManager** | Monitor open positions | `add_position()`, `_monitor_positions()` |
| **ClickHouseDataLayer** | Database operations | `store_signal()`, `get_signals()`, `store_position()` |
| **KiteAPIClient** | Kite Connect API wrapper | `get_quote()`, `place_order()`, `get_option_chain()` |

---

## 2. Architecture Principles

### 2.1 Lock-Free Concurrency

**Design Philosophy**: No locks or mutexes; use atomic operations and database as source of truth.

**Key Techniques**:
- ✅ `asyncio.Task` for independent operations (parallel signal processing)
- ✅ `collections.Counter` for atomic statistics tracking
- ✅ Immutable event objects (dataclasses)
- ✅ Database queries for state (idempotency checks)
- ✅ No shared mutable state between handlers

**Benefits**:
- 🚀 No deadlocks possible
- 🚀 Better performance (no lock contention)
- 🚀 Simpler reasoning about concurrency
- 🚀 Easy to scale horizontally

### 2.2 Event-Driven Architecture

**Design Philosophy**: Components communicate via events, not direct calls.

**Key Patterns**:
- ✅ EventBus as central message broker
- ✅ Publishers emit events with complete context
- ✅ Subscribers register for specific event types
- ✅ Each handler runs in isolated asyncio task
- ✅ No blocking between handlers

**Benefits**:
- 🎯 Loose coupling between components
- 🎯 Easy to add new features (just subscribe)
- 🎯 Parallel processing by default
- 🎯 Better testability (mock events)

### 2.3 Database as Single Source of Truth

**Design Philosophy**: All persistent state lives in database; no in-memory state sharing.

**Key Practices**:
- ✅ Signals stored before processing
- ✅ Positions tracked in database
- ✅ Idempotency via DB queries (not memory)
- ✅ Crash recovery from database state

**Benefits**:
- 💾 Automatic crash recovery
- 💾 Perfect idempotency
- 💾 Complete auditability
- 💾 Horizontal scalability

### 2.4 Mode-Based Execution

**Design Philosophy**: Same code path, behavior changes via configuration flags.

**Three Modes**:
1. **Logging Only** (Default): Log signals, no execution
2. **Paper Trading**: Simulated positions, no real orders
3. **Live Trading**: Real orders with actual capital

**Benefits**:
- 🛡️ Safe testing progression (logging → paper → live)
- 🛡️ Easy rollback (change config flag)
- 🛡️ Same code in all environments
- 🛡️ Confidence building before live

---

## 3. Complete Data Flow

### End-to-End Trading Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         COMPLETE SIGNAL-TO-EXECUTION FLOW                        │
└─────────────────────────────────────────────────────────────────────────────────┘

[1] DATA COLLECTION PHASE
    ┌──────────────────┐
    │  Kite Connect    │
    │      API         │
    └────────┬─────────┘
             │ (WebSocket: Real-time ticks)
             ▼
    ┌──────────────────┐         ┌──────────────────┐
    │ MarketDataRunner │────────▶│ CandleAggregator │
    │  (Fetch Ticks)   │         │  (Tick→Candle)   │
    └──────────────────┘         └────────┬─────────┘
                                          │
                                          ▼
                                 ┌──────────────────┐
                                 │   ClickHouse     │
                                 │  market_data     │
                                 │     table        │
                                 └──────────────────┘

[2] HISTORICAL DATA PHASE
    ┌──────────────────┐
    │  Kite Connect    │
    │  Historical API  │
    └────────┬─────────┘
             │ (REST: Historical candles)
             ▼
    ┌──────────────────┐         ┌──────────────────┐
    │HistoricalCache   │────────▶│   ClickHouse     │
    │  (Fetch & Store) │         │ historical_data  │
    └──────────────────┘         │     table        │
                                 └──────────────────┘

[3] STRATEGY DATA PREPARATION
    ┌──────────────────┐         ┌──────────────────┐
    │HistoricalCache   │         │ CandleAggregator │
    │  (90d lookback)  │         │ (Current candles)│
    └────────┬─────────┘         └────────┬─────────┘
             │                            │
             └─────────┬──────────────────┘
                       ▼
              ┌──────────────────┐
              │StrategyDataMgr   │
              │ • Merge data     │
              │ • Align timeframes│
              │ • Return DF      │
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │  DataFrame       │
              │ (1000 candles +  │
              │  current)        │
              └──────────────────┘

[4] SIGNAL GENERATION
                       │
                       ▼
              ┌──────────────────┐
              │  Strategy        │
              │  .analyze()      │
              │                  │
              │ • Calculate EMA  │
              │ • Detect cross   │
              │ • Generate signal│
              └────────┬─────────┘
                       │
         ┌─────────────┴─────────────┐
         ▼                           ▼
    [No Signal]              [StrategySignal]
                                     │
                                     ▼
                            ┌──────────────────┐
                            │  SignalManager   │
                            │ • Create UUID    │
                            │ • Store to DB    │
                            │ • Cache in mem   │
                            │ • Save JSON      │
                            └────────┬─────────┘
                                     │
                                     ▼
                            INSERT INTO trading_signals (
                              timestamp, signal_id, symbol,
                              strategy, action, price,
                              target, stop_loss, metadata
                            )

[5] EVENT PUBLICATION
                                     │
                                     ▼
                            ┌──────────────────┐
                            │    EventBus      │
                            │ publish(         │
                            │  SIGNAL_GENERATED│
                            │ )                │
                            └────────┬─────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    ▼                                 ▼
          [Other Subscribers]        ┌──────────────────────────────┐
                                     │ EventDrivenOptionsExecutor   │
                                     │ _on_signal_generated()       │
                                     │ (Independent asyncio Task)   │
                                     └────────┬─────────────────────┘
                                              │
[6] SIGNAL VALIDATION                         │
                                              ▼
                                     ┌──────────────────┐
                                     │  Validate Signal │
                                     │ • Idempotency    │
                                     │ • Symbol valid?  │
                                     │ • Age OK?        │
                                     │ • Config enabled?│
                                     │ • Risk limits OK?│
                                     └────────┬─────────┘
                                              │
                                     ┌────────┴────────┐
                                     ▼                 ▼
                                [REJECT]          [ACCEPT]
                                                       │
[7] OPTIONS EXECUTION PREPARATION                     │
                                                       ▼
                        ┌──────────────────────────────┴──────────────┐
                        │                                             │
                        ▼                                             ▼
              ┌──────────────────┐                          ┌──────────────────┐
              │  StrikeSelector  │                          │  Calculate Size  │
              │ • Fetch chain    │                          │ • Risk 2%        │
              │ • Filter liquidity│                         │ • Max pos 10%    │
              │ • Score strikes  │                          │ • Account $      │
              │ • Return best    │                          └──────────────────┘
              └──────────────────┘
                        │
                        └─────────────┬────────────────────────┘
                                      │
                                      ▼
                            ┌──────────────────┐
                            │ Calculate Exits  │
                            │ • SL: -30%       │
                            │ • Target: +60%   │
                            └────────┬─────────┘
                                     │
[8] EXECUTION MODE CHECK              ▼
                            ┌──────────────────┐
                            │   MODE CHECK     │
                            └────────┬─────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  MODE 1:         │      │  MODE 2:         │      │  MODE 3:         │
│  LOGGING ONLY    │      │  PAPER TRADING   │      │  LIVE TRADING    │
│  ────────────    │      │  ──────────────  │      │  ──────────────  │
│ • Log details    │      │ • Create paper   │      │ • Validate funds │
│ • NO EXECUTION   │      │   position       │      │ • Place order    │
└──────────────────┘      │ • Store to DB    │      │ • Wait for fill  │
                          │ • Start monitor  │      │ • Create position│
                          │ • NO REAL ORDERS │      │ • REAL ORDERS    │
                          └────────┬─────────┘      └────────┬─────────┘
                                   │                         │
[9] POSITION MONITORING             ▼                         ▼
                          ┌──────────────────┐      ┌──────────────────┐
                          │ PositionManager  │      │ PositionManager  │
                          │ (Background Task)│      │ (Background Task)│
                          └────────┬─────────┘      └────────┬─────────┘
                                   │                         │
                          [Every 5 seconds]          [Every 5 seconds]
                                   │                         │
                          • Fetch current LTP        • Fetch current LTP
                          • Calculate P&L            • Calculate P&L
                          • Check SL/Target          • Check SL/Target
                          • If exit: close           • If exit: place
                          • Update DB                •   real exit order
                                   │                         │
                                   ▼                         ▼
                          POSITION_CLOSED            POSITION_CLOSED
                          (Event)                    (Event)
```

### Signal Storage Confirmation ✅

**Primary Storage**: `trading_signals` table in ClickHouse
- **Flow**: `Strategy.analyze()` → `SignalManager.add_signal_from_strategy()` → `ClickHouseDataLayer.store_signal()` → `INSERT INTO trading_signals`
- **Table**: 13 columns including signal_id, symbol, strategy, action, price, target, stop_loss
- **Access**: SQL queries (see [Database Schema](#7-database-schema))

**Fallback Storage**: `data/signals/signals.json` (JSON file)

**Log Storage**: `logs/AlphaStockOrchestrator.log`

---

## 4. Component Details

### 4.1 AlphaStockOrchestrator

**Purpose**: Main coordinator that runs the trading system

**Key Attributes**:
```python
config: Dict                    # System configuration
api_client: KiteAPIClient       # Kite Connect API
data_layer: ClickHouseDataLayer # Database interface
event_bus: EventBus             # Event distribution
strategies: List[Strategy]      # Registered strategies
data_manager: StrategyDataManager
running: bool                   # System state
```

**Key Methods**:
- `async def run()`: Main event loop (runs every 5 seconds)
- `async def execute_strategies_for_symbol(symbol)`: Execute all strategies for a symbol
- `def register_strategy(strategy)`: Register new strategy
- `async def _process_signal(signal)`: Handle strategy signal

**Main Loop Flow**:
```
LOOP (every 5 seconds):
  1. For each registered strategy:
     a. Get strategy data (historical + realtime)
     b. Call strategy.analyze(data)
     c. If signal generated:
        - Store signal
        - Publish SIGNAL_GENERATED event
  2. Sleep 5 seconds
  3. Repeat
```

### 4.2 StrategyDataManager

**Purpose**: Merges historical and real-time data for strategies

**Key Methods**:
```python
async def get_strategy_data(symbol, interval, lookback_periods):
    """
    Fetch and merge data for strategy
    
    Steps:
    1. Get historical data from cache (90 days)
    2. Get current incomplete candles from aggregator
    3. Merge into single DataFrame
    4. Return last `lookback_periods` rows
    
    Returns: DataFrame with OHLCV + indicators
    """
```

### 4.3 SignalManager

**Purpose**: Manages signal lifecycle with database persistence

**Key Methods**:
```python
async def add_signal_from_strategy(strategy_name, symbol, strategy_signal):
    """
    Create and store signal from strategy output
    
    Steps:
    1. Extract signal data
    2. Create Signal object with UUID
    3. Store to database (INSERT INTO trading_signals)
    4. Add to in-memory cache
    5. Save to JSON file (fallback)
    6. Emit SIGNAL_GENERATED event
    7. Return Signal object
    """
```

### 4.4 EventBus

**Purpose**: Lock-free event distribution (pub-sub pattern)

**Key Features**:
- ✅ Thread-safe subscriber registration
- ✅ Each event handler = independent asyncio task
- ✅ No blocking between handlers
- ✅ Atomic statistics tracking
- ✅ Complete event context (no external lookups)

**Usage**:
```python
# Subscribe
event_bus.subscribe(EventType.SIGNAL_GENERATED, handler_function)

# Publish
await event_bus.publish(EventType.SIGNAL_GENERATED, {
    "signal_id": "uuid",
    "symbol": "NIFTY",
    "action": "BUY",
    # ... full context
})
```

### 4.5 EventDrivenOptionsExecutor

**Purpose**: Event-driven options trade executor

**Key Methods**:
```python
async def _on_signal_generated(event):
    """
    Handle SIGNAL_GENERATED event (runs in independent task)
    
    Flow:
    1. Extract signal from event
    2. Validate signal (_validate_signal_event)
    3. If valid: _process_signal()
    4. If invalid: reject and log
    
    Thread Safety: Isolated asyncio task, no shared state
    """
    
async def _validate_signal_event(event_data) -> bool:
    """
    Validate signal before processing
    
    Checks:
    - Idempotency (already processed?)
    - Symbol validity
    - Age check (<24h)
    - Configuration (trading enabled?)
    - Risk limits (max positions)
    """
    
async def _process_signal(signal_data):
    """
    Process valid signal
    
    Steps:
    1. Select strike
    2. Calculate position size
    3. Calculate exit levels
    4. Execute based on mode (logging/paper/live)
    5. Update stats
    6. Emit events
    """
```

### 4.6 OptionsPositionManager

**Purpose**: Monitors and manages options positions

**Background Task**:
```python
async def _monitor_positions():
    """
    Monitor all active positions (every 5 seconds)
    
    Loop:
    1. For each active position:
       a. Fetch current option LTP
       b. Calculate unrealized P&L
       c. Check exit conditions (SL/target/expiry)
       d. If exit condition: close_position()
       e. Update database
    """
```

---

## 5. Signal Processing Pipeline

### 5.1 Signal Generation (13 Steps)

```
STEP 1: Strategy receives merged data (historical + realtime)
        ↓
STEP 2: Strategy calculates indicators (EMA 9, EMA 21)
        ↓
STEP 3: Strategy detects trading condition (bullish crossover)
        ↓
STEP 4: Strategy creates StrategySignal object
        ↓
STEP 5: Orchestrator calls SignalManager.add_signal_from_strategy()
        ↓
STEP 6: SignalManager creates Signal with UUID
        ↓
STEP 7: SignalManager stores to database (INSERT INTO trading_signals)
        ↓
STEP 8: SignalManager adds to in-memory cache
        ↓
STEP 9: SignalManager saves to JSON file (fallback)
        ↓
STEP 10: SignalManager emits SIGNAL_GENERATED event
        ↓
STEP 11: EventBus dispatches to all subscribers (parallel tasks)
        ↓
STEP 12: EventDrivenOptionsExecutor receives event
        ↓
STEP 13: Executor validates and processes signal
```

### 5.2 Signal Validation (5 Checks)

```python
async def _validate_signal_event(event_data) -> bool:
    # Check 1: Idempotency
    if await self._is_signal_already_processed(signal_id):
        return False
    
    # Check 2: Symbol validity
    if symbol not in VALID_UNDERLYINGS:
        return False
    
    # Check 3: Age check
    if signal_age > 24_hours:
        return False
    
    # Check 4: Configuration
    if not self.enabled or self.logging_only_mode:
        return True  # Valid but won't execute
    
    # Check 5: Risk limits
    if active_positions >= max_concurrent_positions:
        return False
    
    return True
```

### 5.3 Strike Selection Algorithm

```python
async def select_strike(symbol, action, underlying_price, expected_move_pct):
    """
    10-Step Strike Selection Process
    
    STEP 1: Fetch option chain from API
    STEP 2: Filter by expiry preference (weekly/monthly)
    STEP 3: Filter by option type (CE for BUY, PE for SELL)
    STEP 4: Filter by liquidity (volume >= 100, OI >= 1000)
    STEP 5: Calculate ATM strike (nearest to underlying price)
    STEP 6: Filter by distance from ATM (max 3 strikes)
    STEP 7: Calculate scores for each strike:
            - Distance from ATM (30% weight)
            - Delta proximity to 0.5 (20% weight)
            - IV rank (15% weight)
            - Liquidity (25% weight)
            - Bid-ask spread (10% weight)
    STEP 8: Sort by score (descending)
    STEP 9: Return highest-scoring strike
    STEP 10: Log selection details
    """
```

---

## 6. Execution Modes

### MODE 1: Logging Only (Current Default)

**Configuration**:
```json
{
  "options_trading": {
    "enabled": true,
    "logging_only_mode": true,  // ← Key flag
    "paper_trading": false
  }
}
```

**Behavior**:
```
SIGNAL RECEIVED
    ↓
VALIDATE SIGNAL (pass)
    ↓
SELECT STRIKE (e.g., NIFTY24JAN21500CE @ ₹150.5)
    ↓
CALCULATE SIZE (2 lots = 100 quantity)
    ↓
CALCULATE EXITS (SL: ₹105.35, Target: ₹301.0)
    ↓
LOG ALL DETAILS:
  ✅ Symbol: NIFTY24JAN21500CE
  ✅ Action: BUY
  ✅ Entry: ₹150.5
  ✅ Quantity: 100
  ✅ Investment: ₹15,050
  ✅ Stop Loss: ₹105.35 (-30%)
  ✅ Target: ₹301.0 (+100%)
  ✅ Max Loss: ₹4,515
  ✅ Expected Profit: ₹15,050
  ℹ️ NO ORDER PLACED (logging only mode)
    ↓
UPDATE STATS (logging_only_trades++)
    ↓
DONE
```

### MODE 2: Paper Trading

**Configuration**:
```json
{
  "options_trading": {
    "enabled": true,
    "logging_only_mode": false,
    "paper_trading": true  // ← Key flag
  }
}
```

**Behavior**:
```
SIGNAL RECEIVED → VALIDATE → SELECT STRIKE → CALCULATE SIZE/EXITS
    ↓
CREATE PAPER POSITION:
  • position_id: Generate UUID
  • entry_premium: ₹150.5
  • quantity: 100
  • paper_trade: TRUE
    ↓
STORE TO DATABASE (positions table)
    ↓
ADD TO MONITORING (PositionManager)
    ↓
BACKGROUND MONITORING (every 5 seconds):
  1. Fetch simulated current LTP (from API)
  2. Calculate P&L = (current - entry) × quantity
  3. Check exit conditions:
     - If current <= SL: CLOSE (reason: STOP_LOSS_HIT)
     - If current >= Target: CLOSE (reason: TARGET_REACHED)
     - If expiry < 1h: CLOSE (reason: EXPIRY_APPROACHING)
  4. If exit: Update DB, emit POSITION_CLOSED
    ↓
NO REAL ORDERS PLACED
TRACKS P&L FOR ANALYSIS
```

### MODE 3: Live Trading

**Configuration**:
```json
{
  "options_trading": {
    "enabled": true,
    "logging_only_mode": false,
    "paper_trading": false  // ← Both flags false
  }
}
```

**Behavior**:
```
SIGNAL RECEIVED → VALIDATE → SELECT STRIKE → CALCULATE SIZE/EXITS
    ↓
PRE-TRADE VALIDATIONS:
  ✅ Check available balance
  ✅ Verify margin requirements
  ✅ Confirm order limits
    ↓
PLACE REAL ORDER:
  API: kite.place_order(
    tradingsymbol="NIFTY24JAN21500CE",
    transaction_type="BUY",
    quantity=100,
    order_type="MARKET",
    product="MIS"
  )
    ↓
WAIT FOR ORDER FILL (with timeout)
    ↓
IF FILLED:
  • Create position record
  • Store to database
  • Start monitoring
  • Emit POSITION_OPENED event
    ↓
BACKGROUND MONITORING (same as MODE 2):
  • Track real-time P&L
  • Monitor SL/Target
  • Place EXIT orders when conditions met
    ↓
REAL CAPITAL AT RISK
ACTUAL PROFITS/LOSSES
```

---

## 7. Database Schema

### 7.1 trading_signals Table

**Purpose**: Store all generated trading signals

```sql
CREATE TABLE IF NOT EXISTS trading_signals (
    timestamp DateTime64(3),
    signal_id String,
    symbol String,
    asset_type String,         -- 'EQUITY', 'INDEX', 'OPTION'
    strategy String,            -- Strategy name
    action String,              -- 'BUY' or 'SELL'
    price Float64,              -- Underlying price
    quantity Int32,
    confidence Float64,         -- Signal strength (0.0 to 1.0)
    target Float64,
    stop_loss Float64,
    metadata String,            -- JSON metadata
    
    INDEX idx_timestamp timestamp TYPE minmax GRANULARITY 3,
    INDEX idx_signal_id signal_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_symbol symbol TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_strategy strategy TYPE bloom_filter(0.01) GRANULARITY 1
) ENGINE = MergeTree()
ORDER BY (timestamp, signal_id)
PARTITION BY toYYYYMM(timestamp)
TTL timestamp + INTERVAL 90 DAY;
```

**Common Queries**:
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

-- Count signals by strategy
SELECT strategy, COUNT(*) as signal_count
FROM trading_signals
GROUP BY strategy
ORDER BY signal_count DESC;
```

### 7.2 positions Table

**Purpose**: Track open and closed positions

```sql
CREATE TABLE IF NOT EXISTS positions (
    position_id String,
    signal_id String,           -- FK to trading_signals
    symbol String,              -- Option symbol
    underlying String,
    strike Float64,
    option_type String,         -- "CE" or "PE"
    expiry Date,
    
    entry_timestamp DateTime64(3),
    entry_premium Float64,
    quantity Int32,
    lot_size Int32,
    total_investment Float64,
    
    stop_loss_premium Float64,
    target_premium Float64,
    
    current_premium Float64,
    unrealized_pnl Float64,
    
    exit_timestamp Nullable(DateTime64(3)),
    exit_premium Nullable(Float64),
    exit_reason Nullable(String),
    realized_pnl Nullable(Float64),
    
    status String,              -- "OPEN", "CLOSED"
    paper_trade Bool,
    
    metadata String,
    updated_at DateTime64(3) DEFAULT now(),
    
    INDEX idx_position_id position_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_signal_id signal_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_status status TYPE bloom_filter(0.01) GRANULARITY 1
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (entry_timestamp, position_id)
PARTITION BY toYYYYMM(entry_timestamp);
```

**Common Queries**:
```sql
-- Get all open positions
SELECT * FROM positions
WHERE status = 'OPEN'
ORDER BY entry_timestamp DESC;

-- Calculate total P&L
SELECT 
    COUNT(*) as total_trades,
    SUM(realized_pnl) as total_pnl,
    AVG(realized_pnl) as avg_pnl_per_trade,
    SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as winning_trades
FROM positions
WHERE status = 'CLOSED';
```

### 7.3 Other Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `market_data` | Real-time candles | timestamp, symbol, interval, OHLCV |
| `historical_data` | Historical candles | timestamp, symbol, interval, OHLCV |
| `options_data` | Option chain data | symbol, strike, type, ltp, iv, greeks |
| `performance_metrics` | System metrics | timestamp, metric_name, metric_value |

---

## 8. Event-Driven Architecture

### 8.1 Event Types

```python
class EventType(Enum):
    # Data Events
    MARKET_DATA_TICK = "market_data_tick"
    CANDLE_CLOSED = "candle_closed"
    HISTORICAL_DATA_LOADED = "historical_data_loaded"
    
    # Signal Events
    SIGNAL_GENERATED = "signal_generated"
    SIGNAL_VALIDATED = "signal_validated"
    SIGNAL_REJECTED = "signal_rejected"
    
    # Order Events
    ORDER_PLACED = "order_placed"
    ORDER_FILLED = "order_filled"
    ORDER_REJECTED = "order_rejected"
    
    # Position Events
    POSITION_OPENED = "position_opened"
    POSITION_UPDATED = "position_updated"
    POSITION_CLOSED = "position_closed"
    
    # Risk Events
    STOP_LOSS_HIT = "stop_loss_hit"
    TARGET_REACHED = "target_reached"
```

### 8.2 Event Structure

**SIGNAL_GENERATED Event**:
```json
{
    "event_type": "signal_generated",
    "timestamp": "2024-01-15T10:30:00.000Z",
    "signal": {
        "signal_id": "uuid-1234",
        "symbol": "NIFTY",
        "strategy": "MACrossoverStrategy",
        "action": "BUY",
        "price": 21500.0,
        "confidence": 0.75,
        "target": 21650.0,
        "stop_loss": 21350.0,
        "expected_move_pct": 1.2
    }
}
```

### 8.3 EventBus Flow

```
Publisher                EventBus                 Subscribers
    │                        │                         │
    ├─publish(event)────────▶│                         │
    │                        ├─Create asyncio tasks────┤
    │                        │                         ├─Task 1: Handler A
    │                        │                         ├─Task 2: Handler B
    │                        │                         └─Task 3: Handler C
    │                        │                         (All run in parallel)
    │                        │                         │
    │◀─────────────────────────────────────────────────┤
    │                   (No blocking)
```

---

## 9. Configuration Reference

### 9.1 Complete Configuration

```json
{
  "api": {
    "api_key": "your_api_key",
    "api_secret": "your_api_secret",
    "access_token": "your_access_token"
  },
  
  "database": {
    "host": "localhost",
    "port": 9000,
    "database": "alphastock"
  },
  
  "data_collection": {
    "realtime": {
      "enabled": true,
      "interval_seconds": 5,
      "symbols": ["NIFTY", "BANKNIFTY"]
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
        "slow_period": 21
      }
    }
  },
  
  "options_trading": {
    "enabled": true,
    "paper_trading": true,
    "logging_only_mode": true,    // ← CURRENT DEFAULT
    
    "strike_selection": {
      "prefer_atm": true,
      "max_strikes_from_atm": 3,
      "min_volume": 100,
      "min_oi": 1000
    },
    
    "risk_management": {
      "max_concurrent_positions": 3,
      "risk_per_trade_pct": 2.0,
      "stop_loss_pct": 30.0,
      "target_multiplier": 2.0
    }
  }
}
```

---

## 10. Monitoring & Operations

### 10.1 System Health Checks

```sql
-- Check signal generation (last hour)
SELECT COUNT(*) as signals_last_hour
FROM trading_signals
WHERE timestamp >= now() - INTERVAL 1 HOUR;

-- Check active positions
SELECT COUNT(*) as open_positions
FROM positions
WHERE status = 'OPEN';

-- Check system performance
SELECT 
    strategy,
    COUNT(*) as total_signals,
    COUNT(DISTINCT symbol) as unique_symbols
FROM trading_signals
WHERE timestamp >= now() - INTERVAL 1 DAY
GROUP BY strategy;
```

### 10.2 Log Monitoring

```powershell
# Windows PowerShell

# Check recent logs
Get-Content logs\AlphaStockOrchestrator.log -Tail 50

# Search for signals
Get-Content logs\AlphaStockOrchestrator.log | Select-String "SIGNAL"

# Check for errors
Get-Content logs\AlphaStockOrchestrator.log | Select-String "ERROR"
```

### 10.3 Key Metrics

| Metric | Query | Meaning |
|--------|-------|---------|
| **Signal Rate** | `COUNT(*) FROM trading_signals WHERE timestamp >= now() - 1h` | Signals per hour |
| **Win Rate** | `SUM(CASE WHEN realized_pnl > 0 THEN 1 END) / COUNT(*)` | % of profitable trades |
| **Avg P&L** | `AVG(realized_pnl) FROM positions WHERE status='CLOSED'` | Average profit per trade |
| **Total P&L** | `SUM(realized_pnl) FROM positions WHERE status='CLOSED'` | Cumulative profit/loss |

---

## 11. Troubleshooting Guide

### Issue 1: No Signals Generated

**Symptoms**: `trading_signals` table empty

**Diagnosis**:
```sql
SELECT COUNT(*) FROM trading_signals 
WHERE timestamp >= now() - INTERVAL 1 HOUR;
-- Returns 0
```

**Possible Causes**:
1. **Strategy conditions not met** (normal) - Market not crossing over
2. **Insufficient historical data** - Need 50+ candles
3. **Strategy not registered** - Not added to orchestrator

**Fixes**:
```bash
# Fetch historical data
python complete_workflow.py

# Check logs for strategy execution
Get-Content logs\AlphaStockOrchestrator.log -Tail 100 | Select-String "Strategy"
```

### Issue 2: Signal Not in Database

**Symptoms**: Logs show "Signal generated" but DB empty

**Diagnosis**:
```powershell
Get-Content logs\AlphaStockOrchestrator.log -Tail 1000 | Select-String "SignalManager"
```

**Possible Causes**:
1. **ClickHouse down** - Database unavailable
2. **Exception during storage** - Check error logs
3. **Permission issue** - Database write access

**Fixes**:
```bash
# Check ClickHouse status
docker ps | grep clickhouse

# Restart ClickHouse if needed
docker restart alphastock-clickhouse

# Check fallback JSON file
type data\signals\signals.json
```

### Issue 3: Position Not Monitoring

**Symptoms**: Positions created but never close

**Diagnosis**:
```sql
SELECT position_id, entry_timestamp, updated_at
FROM positions
WHERE status = 'OPEN'
AND entry_timestamp < now() - INTERVAL 1 HOUR;
```

**Possible Causes**:
1. **Monitoring task crashed** - Check logs
2. **API failure** - Can't fetch current premium
3. **Wrong mode** - Paper trading flag mismatch

**Fixes**:
```bash
# Check position manager logs
Get-Content logs\AlphaStockOrchestrator.log | Select-String "PositionManager"

# Verify API token
python cli.py auth --validate-only
```

---

## 12. Deployment Checklist

### Phase 1: Logging Only Mode (Week 1-2)

- [ ] ✅ ClickHouse database installed
- [ ] ✅ Configuration file created
- [ ] ✅ API credentials configured
- [ ] ✅ Historical data fetched
- [ ] ✅ Set `logging_only_mode: true`
- [ ] ✅ Run system for 1-2 days
- [ ] ✅ Verify signals generated
- [ ] ✅ Review signal quality
- [ ] ✅ Check logs for errors

### Phase 2: Paper Trading (Week 3-4)

- [ ] Review logged signals (quantity, quality)
- [ ] Set `logging_only_mode: false`
- [ ] Set `paper_trading: true`
- [ ] Test strike selection
- [ ] Test position monitoring
- [ ] Run for 1-2 weeks
- [ ] Analyze paper P&L
- [ ] Verify exit logic (SL/target)

### Phase 3: Live Trading (Week 5+)

- [ ] Review paper trading results
- [ ] Verify acceptable win rate
- [ ] Test with small capital (10-20%)
- [ ] Set `paper_trading: false`
- [ ] Configure risk limits conservatively
- [ ] Set up alerts
- [ ] Run with small positions (1 week)
- [ ] Gradually increase size
- [ ] Monitor daily

---

## 13. Quick Reference

### Signal Storage Locations

1. **ClickHouse Database** (Primary):
   ```sql
   SELECT * FROM trading_signals ORDER BY timestamp DESC;
   ```

2. **JSON File** (Fallback):
   ```bash
   type data\signals\signals.json
   ```

3. **Log Files**:
   ```powershell
   Get-Content logs\AlphaStockOrchestrator.log -Tail 100 | Select-String "SIGNAL"
   ```

### Current System Mode

**Default**: LOGGING ONLY
- File: `config/production.json`
- Flags: `logging_only_mode: true`, `paper_trading: false`
- Behavior: Signals logged, no execution

### Component Cheat Sheet

| Component | Key File | Main Method |
|-----------|----------|-------------|
| Orchestrator | `src/orchestrator.py` | `run()` |
| Signal Manager | `src/trading/signal_manager.py` | `add_signal_from_strategy()` |
| Options Executor | `src/trading/options_executor_event_driven.py` | `_on_signal_generated()` |
| Event Bus | `src/events/event_bus.py` | `publish()` |
| Database Layer | `src/data/clickhouse_data_layer.py` | `store_signal()` |

---

## 14. Related Documentation

| Document | Description |
|----------|-------------|
| [WHERE_TO_FIND_SIGNALS.md](WHERE_TO_FIND_SIGNALS.md) | Signal location guide |
| [EVENT_DRIVEN_ARCHITECTURE.md](EVENT_DRIVEN_ARCHITECTURE.md) | Event bus deep dive |
| [LOCK_FREE_ARCHITECTURE.md](LOCK_FREE_ARCHITECTURE.md) | Concurrency design |
| [OPTIONS_TRADING_COMPLETE.md](OPTIONS_TRADING_COMPLETE.md) | Options trading guide |
| [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md) | Deployment guide |

**Detailed Parts**: [PART1](LOW_LEVEL_DESIGN_PART1.md) | [PART2](LOW_LEVEL_DESIGN_PART2.md) | [PART3](LOW_LEVEL_DESIGN_PART3.md) | [PART4](LOW_LEVEL_DESIGN_PART4.md) | [PART5](LOW_LEVEL_DESIGN_PART5.md) | [PART6](LOW_LEVEL_DESIGN_PART6.md)

---

## Glossary

- **ATM**: At-The-Money (strike price = underlying price)
- **CE**: Call Option
- **EventBus**: Pub-sub message broker for inter-component communication
- **Idempotency**: Operation produces same result when called multiple times
- **Lock-Free**: Concurrency without mutexes/locks
- **OI**: Open Interest
- **PE**: Put Option
- **Signal**: Trading recommendation from strategy
- **Strike**: Option contract exercise price

---

**Documentation Status**: ✅ Complete  
**System Status**: ✅ Production Ready (Logging Only Mode)  
**Last Updated**: October 10, 2025  
**Version**: 1.0
