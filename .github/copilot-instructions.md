# AlphaStocks - AI Coding Agent Instructions

## System Overview

AlphaStocks is a **lock-free, event-driven algorithmic trading system** for Indian markets (NSE/BSE) using Zerodha Kite Connect API. The architecture eliminates locks entirely, using atomic operations and database-as-truth for 60K+ events/sec throughput.

## 🚨 Critical: Lock-Free Architecture Rules

**NEVER add locks to event-driven code.** See `.copilot-design-principles.md` before any changes.

### Core Principles

1. **No Locks**: Use `collections.Counter` for stats, `asyncio.Queue` for messaging, database queries for state
2. **Independent Tasks**: Each event handler runs in separate `asyncio.Task` via `asyncio.gather()`
3. **Database as Truth**: No in-memory tracking (no `self.processed_signals = set()`). Query database for idempotency
4. **Complete Event Context**: Pass ALL data in `event.data`. Handlers never lookup shared state
5. **Handler Isolation**: 30s timeouts, exceptions caught, failures don't cascade
6. **IST Timezone Consistency**: ALWAYS use `src.utils.timezone_utils` for all time operations. Never use `datetime.now()` or `datetime.utcnow()` directly.

**Reference**: `docs/LOCK_FREE_ARCHITECTURE.md`, `docs/EVENT_DRIVEN_ARCHITECTURE.md`, `docs/TIMEZONE_STANDARD.md`

## 🕐 Critical: Timezone Management Rules

**ALL timestamps MUST use IST (Indian Standard Time - Asia/Kolkata)** for consistency across the application.

### Required Imports
```python
from src.utils.timezone_utils import (
    get_current_time,      # Replace datetime.now()
    get_timezone,          # Get IST timezone object
    to_ist,                # Convert any datetime to IST
    to_utc,                # Convert to UTC for storage if needed
    get_today_market_open, # 9:15 AM IST
    get_today_market_close # 3:30 PM IST
)
```

### Mandatory Rules

1. **NEVER use `datetime.now()`** - Use `get_current_time()` instead
2. **NEVER use `datetime.utcnow()`** - Use `get_current_time()` (IST) or `to_utc(get_current_time())`
3. **Database timestamps**: Store in UTC, convert to IST on read using `to_ist()`
4. **Display timestamps**: Always show in IST using `format_ist_time()`
5. **Market hours**: Use `get_today_market_open()`, `get_today_market_close()`, `is_market_hours()`
6. **Comparisons**: Ensure both datetimes are timezone-aware before comparing

### ✅ Correct Patterns
```python
# Get current time
now = get_current_time()  # Returns timezone-aware IST datetime

# Store to database (convert to UTC)
db_timestamp = to_utc(get_current_time())

# Read from database (convert to IST)
ist_timestamp = to_ist(db_timestamp)

# Market hours check
if is_market_hours():
    # Trading logic
    
# Signal timestamp
signal_timestamp = get_current_time().isoformat()
```

### ❌ Forbidden Patterns
```python
# WRONG - No timezone awareness
timestamp = datetime.now()  # ❌

# WRONG - UTC time without conversion
timestamp = datetime.utcnow()  # ❌

# WRONG - Naive datetime
timestamp = datetime(2025, 11, 7, 10, 30)  # ❌
```

**Reference**: `docs/TIMEZONE_STANDARD.md`

## Architecture Components

### Entry Point Flow
```
main.py → AlphaStockOrchestrator → EventBus (pub-sub) → Component handlers
```

### Key Components (src/)
- **orchestrator.py**: Main coordinator, initializes all components, runs main loop
- **events/event_bus.py**: Lock-free pub-sub (60K events/sec). Parallel handler execution with `asyncio.create_task()`
- **trading/signal_manager_event_driven.py**: Emits `SIGNAL_GENERATED` events from strategies
- **trading/options_executor_event_driven.py**: Subscribes to signals, executes trades (lock-free, DB idempotency)
- **trading/options_position_manager.py**: Monitors positions, handles exits
- **core/candle_aggregator.py**: Converts ticks → OHLCV candles (legacy, has locks - OK)
- **core/historical_data_cache.py**: Caches historical data (legacy, has locks - OK)
- **strategies/**: Trading strategies (MA Crossover, RSI, Momentum)
- **news/news_agent.py**: News analysis agent - fetches RSS feeds, analyzes with Llama, sends Telegram alerts

### Data Flow
```
Kite API → MarketDataRunner → CandleAggregator → StrategyDataManager
  → Strategy.analyze() → SignalManager.emit_signal() → EventBus.publish()
  → OptionsExecutor._on_signal_generated() → OptionsPositionManager
  → EventBus.publish(POSITION_CLOSED) → Database
```

## Development Workflows

### Daily Authentication (Tokens Expire Daily)
```bash
python cli.py auth                    # Opens browser, auto-saves to .env.dev
python test_auth.py                   # Quick validation
```

### Running the System
```bash
# Development (paper trading enabled by default)
python main.py

# CLI control
python cli.py start|stop|status|monitor
python cli.py signals --limit 20
```

### Testing
```bash
# Complete system validation
python complete_workflow.py           # Downloads historical data, validates flow

# Concurrent event tests (MUST pass before commits)
python tests/test_concurrent_events.py

# Unit tests
python -m pytest tests/
```

### Adding New Event Handlers
```python
# 1. Subscribe to events in initialize()
self.event_bus.subscribe(EventType.SIGNAL_GENERATED, self._on_signal, "my_service")

# 2. Handler must be async, accept Event, have complete context in event.data
async def _on_signal(self, event: Event):
    signal_id = event.data["signal_id"]  # All data in event.data
    # Use Counter for stats (atomic)
    self.stats["signals_processed"] += 1
    # Query DB for state (no in-memory tracking)
    if await self._already_processed(signal_id):
        return
```

## Configuration

### Three Execution Modes
1. **Logging Only** (default): `options_trading.logging_only_mode: true` - Logs signals, no execution
2. **Paper Trading**: `options_trading.paper_trading: true` - Simulated positions
3. **Live Trading**: Both false - Real orders (test thoroughly first!)

### Key Config Files
- **config/production.json**: Strategy params, risk limits, trading modes
- **.env.dev**: API credentials (NEVER commit!). Auto-generated by `cli.py auth`
- **config/database.json**: ClickHouse connection settings

### Market Hours Protection
System auto-stops data collection at 3:30 PM IST to prevent stale data corruption. See `docs/MARKET_HOURS_PROTECTION.md`.

## Critical Patterns

### ✅ Approved Patterns
```python
# Atomic statistics
from collections import Counter
self.stats = Counter({"processed": 0})
self.stats["processed"] += 1

# Parallel handlers (EventBus)
tasks = [asyncio.create_task(handler(event)) for handler in handlers]
await asyncio.gather(*tasks, return_exceptions=True)

# Database idempotency
if await db.get_position_by_signal(signal_id):
    return  # Already processed
```

### ❌ Forbidden Patterns
```python
# NO locks
self.lock = asyncio.Lock()  # ❌ NEVER

# NO in-memory tracking
self.processed_signals = set()  # ❌ Use DB queries

# NO sequential handlers
for h in handlers: await h(event)  # ❌ Use asyncio.gather()
```

## Strategy Development

Strategies inherit from `BaseStrategy` (src/strategies/base_strategy.py):

```python
class MyStrategy(BaseStrategy):
    async def analyze(self, symbol: str, historical_data: pd.DataFrame,
                     realtime_data: Optional[pd.DataFrame] = None) -> Optional[Dict]:
        # Calculate indicators on historical_data
        # Return signal dict or None
        if buy_signal:
            return {
                "action": "BUY",
                "entry_price": current_price,
                "stop_loss": sl_price,
                "target": target_price,
                "signal_strength": 0.8,  # 0-1
                "expected_move_pct": 1.5,
                "metadata": {...}
            }
```

Register in `config/production.json` under `strategies.<name>` with `enabled: true`.

## Database (ClickHouse)

### Key Tables (auto-created)
- `historical_data`: OHLCV candles (symbol, timestamp, open, high, low, close, volume)
- `signals`: Trading signals (signal_id, symbol, strategy, action, entry_price, sl, target)
- `options_positions`: Position tracking (position_id, signal_id, option_symbol, pnl)

### Access
```python
# Via data_layer (orchestrator.data_layer)
await data_layer.store_signal(signal_dict)
signals = await data_layer.get_signals(symbol="NIFTY", limit=100)
```

## Debugging

### Logs Location
- `logs/AlphaStockOrchestrator.log` - Main system log
- `logs/agent.log.*` - Daily agent logs
- `logs/*.log` - Component-specific logs

### Common Issues
- **"Authentication failed"**: Re-run `python cli.py auth` (tokens expire daily)
- **Database connection error**: Start ClickHouse Docker: `docker ps | grep clickhouse`
- **No data found**: Run `python complete_workflow.py` to download historical data
- **Race conditions**: Check `.copilot-design-principles.md`, use atomic operations

## Documentation Deep Dives

- **`docs/LOW_LEVEL_DESIGN.md`**: Complete system architecture (1200+ lines)
- **`docs/LOCK_FREE_ARCHITECTURE.md`**: Concurrency design principles
- **`.copilot-design-principles.md`**: Mandatory design rules (read before ANY changes)
- **`docs/AUTHENTICATION.md`**: Authentication flow details
- **`docs/MARKET_HOURS_PROTECTION.md`**: Why system stops at 3:30 PM IST
- **`README.md`**: User guide, quick start

## Pre-Commit Checklist

- [ ] No locks added to event-driven code (`event_bus.py`, `*_event_driven.py`)
- [ ] Using `Counter` for statistics, not dicts/lists
- [ ] Database queries for idempotency, not in-memory sets
- [ ] Events have complete context (all data in `event.data`)
- [ ] Handlers isolated with timeouts and exception handling
- [ ] `python tests/test_concurrent_events.py` passes
- [ ] Read `.copilot-design-principles.md` compliance checklist

## Quick Reference

| Task | Command/File |
|------|-------------|
| Start system | `python main.py` |
| Authenticate | `python cli.py auth` |
| Run tests | `python -m pytest tests/` |
| Check concurrency | `python tests/test_concurrent_events.py` |
| View signals | `python cli.py signals --limit 20` |
| Main coordinator | `src/orchestrator.py` |
| Event bus | `src/events/event_bus.py` |
| Design rules | `.copilot-design-principles.md` |
| Architecture | `docs/LOCK_FREE_ARCHITECTURE.md` |

---

**Last Updated**: October 31, 2025  
**System Status**: Production Ready ✅  
**Performance**: 60K events/sec, 150 signals/sec, 15ms avg latency
