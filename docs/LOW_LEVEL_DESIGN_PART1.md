# AlphaStocks Trading System - Low Level Design Documentation

**Version**: 1.0  
**Date**: October 10, 2025  
**Status**: Production Ready

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Diagrams](#architecture-diagrams)
3. [Data Flow Pipeline](#data-flow-pipeline)
4. [Component Details](#component-details)
5. [Event-Driven Architecture](#event-driven-architecture)
6. [Signal Processing Flow](#signal-processing-flow)
7. [Options Execution Modes](#options-execution-modes)
8. [Class Diagrams](#class-diagrams)
9. [Sequence Diagrams](#sequence-diagrams)
10. [Configuration Reference](#configuration-reference)

---

## 1. System Overview

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AlphaStocks Trading System                            │
│                       (Event-Driven, Lock-Free Design)                       │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐          ┌──────────────────┐          ┌──────────────────┐
│   Data Sources   │          │  Core Processing │          │   Trading Layer  │
├──────────────────┤          ├──────────────────┤          ├──────────────────┤
│                  │          │                  │          │                  │
│ • Kite API       │─────────▶│ • Data Pipeline  │─────────▶│ • Signal Manager │
│ • ClickHouse DB  │          │ • Strategies     │          │ • Options Exec   │
│ • Historical Data│          │ • Event Bus      │          │ • Position Mgr   │
│                  │          │                  │          │                  │
└──────────────────┘          └──────────────────┘          └──────────────────┘
         │                             │                             │
         │                             │                             │
         └─────────────────────────────┴─────────────────────────────┘
                                       │
                                       ▼
                          ┌─────────────────────────┐
                          │   Persistent Storage    │
                          ├─────────────────────────┤
                          │ • trading_signals       │
                          │ • market_data           │
                          │ • historical_data       │
                          │ • options_data          │
                          │ • positions             │
                          │ • performance_metrics   │
                          └─────────────────────────┘
```

### 1.2 Key Design Principles

1. **Event-Driven Architecture**: Loose coupling via EventBus (publish-subscribe pattern)
2. **Lock-Free Concurrency**: No locks, atomic operations, independent tasks
3. **Database as Truth**: ClickHouse is single source of truth for state
4. **Immutable Events**: All events are immutable dataclasses
5. **Handler Isolation**: Each event handler runs in independent asyncio task
6. **Complete Context**: Events contain all necessary data (no external lookups)

### 1.3 System Components

| Component | Type | Purpose | Thread Safety |
|-----------|------|---------|---------------|
| `AlphaStockOrchestrator` | Coordinator | System lifecycle, component initialization | Single-threaded |
| `EventBus` | Message Bus | Event distribution (pub-sub) | Lock-free (parallel tasks) |
| `MarketDataRunner` | Data Collector | Real-time tick data collection | Async/await |
| `CandleAggregator` | Data Processor | Tick-to-candle aggregation | Lock-free (atomic operations) |
| `HistoricalDataCache` | Data Provider | Historical OHLCV data management | Read-heavy, cached |
| `StrategyDataManager` | Data Coordinator | Merges historical + realtime data | Stateless |
| `StrategyFactory` | Factory | Strategy instantiation | Stateless |
| `SignalManager` | Signal Handler | Signal lifecycle management | Database-backed |
| `EventDrivenOptionsExecutor` | Trade Executor | Options trade execution | Lock-free (task-per-signal) |
| `OptionsPositionManager` | Position Monitor | Position monitoring & exit | Database-backed |
| `ClickHouseDataLayer` | Persistence | Database operations | Thread-local clients |

---

## 2. Architecture Diagrams

### 2.1 Complete System Architecture

```
                                 ┌─────────────────────────────────┐
                                 │    AlphaStockOrchestrator       │
                                 │  (System Coordinator)           │
                                 │                                 │
                                 │  - Initializes all components   │
                                 │  - Manages lifecycle            │
                                 │  - Handles shutdown gracefully  │
                                 └────────────┬────────────────────┘
                                              │
                                              │ initializes & coordinates
                                              ▼
    ┌────────────────────────────────────────────────────────────────────────┐
    │                                                                        │
    ▼                          ▼                          ▼                 ▼
┌────────────┐         ┌──────────────┐         ┌──────────────┐   ┌──────────────┐
│  EventBus  │         │  Data Layer  │         │  API Client  │   │   Runners    │
│            │         │  (ClickHouse)│         │  (Kite)      │   │   Manager    │
│  Central   │         │              │         │              │   │              │
│  Message   │         │  Persistent  │         │  Market Data │   │  Equity/Opt/ │
│  Hub       │         │  Storage     │         │  Trading API │   │  Index/Fut   │
└────────────┘         └──────────────┘         └──────────────┘   └──────────────┘
    │                         │                         │                   │
    │                         │                         │                   │
    │ publishes events        │ stores/retrieves        │ fetches data      │
    ▼                         ▼                         ▼                   ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                          Core Processing Layer                             │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │
│  │ MarketDataRunner│  │ CandleAggregator │  │HistoricalDataCache│        │
│  │                 │  │                  │  │                   │         │
│  │ Fetches ticks   │─▶│ Tick → Candles  │  │ Historical OHLCV  │         │
│  │ every 1-5s      │  │ (15min/1hour)   │  │ DB queries        │         │
│  └─────────────────┘  └──────────────────┘  └──────────────────┘         │
│           │                    │                       │                   │
│           └────────────────────┴───────────────────────┘                  │
│                                │                                           │
│                                ▼                                           │
│                  ┌─────────────────────────────┐                          │
│                  │  StrategyDataManager        │                          │
│                  │                             │                          │
│                  │  Merges:                    │                          │
│                  │  Historical + Realtime      │                          │
│                  │  → Complete dataset         │                          │
│                  └──────────────┬──────────────┘                          │
│                                 │                                          │
└─────────────────────────────────┼──────────────────────────────────────────┘
                                  │
                                  │ provides data to
                                  ▼
                    ┌──────────────────────────────┐
                    │      Strategy Layer          │
                    ├──────────────────────────────┤
                    │                              │
                    │  • MA Crossover Strategy     │
                    │  • RSI Strategy              │
                    │  • Custom Strategies         │
                    │                              │
                    │  analyze(symbol, data)       │
                    │    → StrategySignal          │
                    │                              │
                    └──────────┬───────────────────┘
                               │
                               │ generates
                               ▼
                    ┌──────────────────────────────┐
                    │     SignalManager            │
                    │                              │
                    │  • Creates Signal object     │
                    │  • Stores to DB              │
                    │  • Emits SIGNAL_GENERATED    │
                    └──────────┬───────────────────┘
                               │
                               │ publishes event
                               ▼
                    ┌──────────────────────────────┐
                    │        EventBus              │
                    │                              │
                    │  SIGNAL_GENERATED event      │
                    │  → All subscribers notified  │
                    └──────────┬───────────────────┘
                               │
                               │ parallel dispatch
                               ▼
        ┌──────────────────────┴──────────────────────┐
        │                                              │
        ▼                                              ▼
┌──────────────────────────┐           ┌──────────────────────────┐
│ EventDrivenOptionsExecutor│          │   Other Subscribers      │
│                          │           │   (logging, analytics)   │
│  • Validates signal      │           └──────────────────────────┘
│  • Checks risk limits    │
│  • Selects strike        │
│  • Calculates size       │
│  • Places order (mode)   │
│                          │
└────────────┬─────────────┘
             │
             │ behavior depends on mode
             ▼
    ┌────────────────────┐
    │  Execution Mode    │
    ├────────────────────┤
    │                    │
    │ 1. LOGGING_ONLY:   │
    │    → Log signal    │
    │    → No execution  │
    │                    │
    │ 2. PAPER_TRADING:  │
    │    → Simulate      │
    │    → Track P&L     │
    │                    │
    │ 3. LIVE_TRADING:   │
    │    → Real orders   │
    │    → Actual trades │
    │                    │
    └────────────────────┘
```

---

## 3. Data Flow Pipeline

### 3.1 Complete Data Flow (Historical + Realtime → Strategy → Signal → Execution)

```
PHASE 1: DATA COLLECTION & PREPARATION
═══════════════════════════════════════

Step 1: Historical Data Loading
┌────────────────────────────────────────────────────────────────┐
│  Orchestrator.initialize()                                     │
│  └─▶ HistoricalDataCache.initialize()                         │
│      └─▶ ClickHouseDataLayer.get_historical_data()            │
│          └─▶ SELECT * FROM historical_data                     │
│              WHERE symbol = ? AND interval = ?                 │
│              ORDER BY timestamp DESC LIMIT ?                   │
│                                                                │
│  Result: DataFrame with columns [timestamp, open, high,       │
│          low, close, volume, vwap, trades]                    │
│          Cached in memory for fast access                     │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
Step 2: Real-time Tick Collection (Parallel, Every 1-5 seconds)
┌────────────────────────────────────────────────────────────────┐
│  MarketDataRunner._collect_batch_data()                        │
│  └─▶ KiteAPIClient.get_quote(symbols=[...])                   │
│      └─▶ HTTP GET to Kite API                                 │
│          Response: {                                           │
│            'RELIANCE': {                                       │
│              'last_price': 2450.50,                           │
│              'volume': 1234567,                               │
│              'ohlc': {...}                                    │
│            }                                                   │
│          }                                                     │
│                                                                │
│  └─▶ CandleAggregator.process_tick(symbol, tick_data)        │
│      └─▶ Aggregates ticks into candles (lock-free)           │
│          Uses atomic operations (collections.Counter)         │
│          Maintains candle state per symbol/timeframe         │
│                                                                │
│  └─▶ ClickHouseDataLayer.store_market_data(tick_data)        │
│      └─▶ INSERT INTO market_data VALUES (...)                │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
Step 3: Candle Completion & Storage
┌────────────────────────────────────────────────────────────────┐
│  CandleAggregator (monitors time)                              │
│  └─▶ if current_time >= candle_end_time:                      │
│      └─▶ finalize_candle()                                    │
│          • Calculate final OHLCV                              │
│          • Store to ClickHouse                                │
│          • Emit CANDLE_COMPLETED event                        │
│          • Reset for next candle                              │
│                                                                │
│  └─▶ EventBus.publish(EventType.CANDLE_COMPLETED, {...})     │
└────────────────────────────────────────────────────────────────┘


PHASE 2: STRATEGY EXECUTION
════════════════════════════

Step 4: Data Preparation for Strategy
┌────────────────────────────────────────────────────────────────┐
│  Orchestrator._execute_strategies_for_symbol(symbol, runner)   │
│  └─▶ StrategyDataManager.get_strategy_data(symbol, config)    │
│                                                                │
│      Sub-step 4.1: Get Historical Data                        │
│      ├─▶ HistoricalDataCache.get_data(symbol, timeframe)     │
│      │   └─▶ Returns cached DataFrame (1000 candles)         │
│      │                                                         │
│      Sub-step 4.2: Get Realtime Candles                       │
│      ├─▶ CandleAggregator.get_completed_candles()            │
│      │   └─▶ Returns recent complete candles                 │
│      │                                                         │
│      Sub-step 4.3: Merge Data                                 │
│      ├─▶ _merge_data(historical_df, realtime_df)             │
│      │   • Remove duplicates (by timestamp)                  │
│      │   • Sort by timestamp                                 │
│      │   • Validate no gaps                                  │
│      │                                                         │
│      Sub-step 4.4: Slice to Strategy Requirements             │
│      └─▶ merged_df.tail(required_periods)                    │
│                                                                │
│  Result: Complete DataFrame ready for strategy analysis       │
│          [timestamp, open, high, low, close, volume]          │
│          Size: historical (1000) + realtime (1-5) candles     │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
Step 5: Strategy Analysis
┌────────────────────────────────────────────────────────────────┐
│  Strategy.analyze(symbol, historical_data)                     │
│  Example: MovingAverageCrossoverStrategy                       │
│                                                                │
│  ├─▶ Calculate Indicators:                                    │
│  │   • fast_ema = data['close'].ewm(span=9).mean()           │
│  │   • slow_ema = data['close'].ewm(span=21).mean()          │
│  │   • current_price = data['close'].iloc[-1]                │
│  │                                                             │
│  ├─▶ Detect Crossover:                                        │
│  │   • fast_crossed_above = (fast_ema[-1] > slow_ema[-1]) and│
│  │                          (fast_ema[-2] <= slow_ema[-2])   │
│  │   • fast_crossed_below = (fast_ema[-1] < slow_ema[-1]) and│
│  │                          (fast_ema[-2] >= slow_ema[-2])   │
│  │                                                             │
│  ├─▶ Generate Signal (if conditions met):                    │
│  │   if fast_crossed_above:                                  │
│  │     return StrategySignal(                                │
│  │       action="BUY",                                       │
│  │       price=current_price,                                │
│  │       confidence=0.85,                                    │
│  │       target=current_price * 1.02,  # 2% gain            │
│  │       stop_loss=current_price * 0.99  # 1% loss          │
│  │     )                                                      │
│  │                                                             │
│  └─▶ Return None if no signal                                │
│                                                                │
│  Result: StrategySignal object (or None)                      │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
