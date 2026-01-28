# Event-Driven Architecture for AlphaStocks

**Date:** October 9, 2025  
**Status:** ✅ IMPLEMENTED - Complete event-driven system

---

## Overview

This document describes the **event-driven architecture** that decouples trading system components using a publish-subscribe pattern. Instead of direct method calls, components communicate through events emitted to a central event bus.

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                         STRATEGIES                                │
│  (RSI, MACD, BollingerBands, CustomStrategies)                   │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         │ emit_signal()
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                  EVENT-DRIVEN SIGNAL MANAGER                      │
│  - Creates Signal object                                          │
│  - Stores to database/JSON/memory                                 │
│  - Publishes SIGNAL_GENERATED event                               │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         │ SIGNAL_GENERATED event
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                      EVENT BUS (Central Hub)                      │
│  - Receives all events                                            │
│  - Routes to subscribers                                          │
│  - Priority queue                                                 │
│  - Event history                                                  │
│  - Dead letter queue                                              │
└───────┬──────────────────────────────────────────────────────────┘
        │
        │ Routes event to subscribers
        │
        ├──────────────────────────┬───────────────────────┐
        │                          │                       │
        ▼                          ▼                       ▼
┌───────────────────┐   ┌─────────────────────┐   ┌─────────────────┐
│ OPTIONS EXECUTOR  │   │  NOTIFICATION SVC   │   │   ANALYTICS     │
│ (Subscribes to    │   │  (Email/Telegram)   │   │   (ML Models)   │
│ SIGNAL_GENERATED) │   │                     │   │                 │
└─────────┬─────────┘   └─────────────────────┘   └─────────────────┘
          │
          │ 1. Validate signal
          │ 2. Select strike (StrikeSelector)
          │ 3. Calculate position size
          │ 4. Place entry order
          │
          ▼
┌──────────────────────────────────────────────────────────────────┐
│         Emits SIGNAL_ACTIVATED & POSITION_OPENED events           │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│              OPTIONS POSITION MANAGER                             │
│  - Monitors position                                              │
│  - Checks SL/Target/Trailing                                      │
│  - Executes exits                                                 │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         │ When exit triggered
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│      Emits POSITION_CLOSED, SIGNAL_COMPLETED/STOPPED events       │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
                      EVENT BUS
                         │
                         ▼
                   All Subscribers
           (Signal Manager, Analytics, Notifications)
```

---

## Event Types

### Signal Events

| Event Type | Description | When Emitted | Data Included |
|------------|-------------|--------------|---------------|
| `SIGNAL_GENERATED` | Strategy generates signal | When strategy finds trade opportunity | signal_id, symbol, action, entry_price, stop_loss, target, signal_strength, expected_move_pct |
| `SIGNAL_ACTIVATED` | Signal converted to order | When order is placed | signal_id, order_id, symbol, action, price, quantity |
| `SIGNAL_UPDATED` | Signal information updated | During signal lifecycle | signal_id, updates |
| `SIGNAL_COMPLETED` | Signal target hit | When target is reached | signal_id, exit_price, profit_loss, profit_loss_pct |
| `SIGNAL_STOPPED` | Signal stop-loss hit | When SL is triggered | signal_id, exit_price, profit_loss, profit_loss_pct |

### Position Events

| Event Type | Description | When Emitted | Data Included |
|------------|-------------|--------------|---------------|
| `POSITION_OPENED` | New position created | After entry order placed | position_id, signal_id, option_symbol, strike, quantity, entry_premium |
| `POSITION_UPDATED` | Position status updated | During monitoring | position_id, current_premium, unrealized_pnl |
| `POSITION_CLOSED` | Position fully exited | When all quantity exited | position_id, exit_premium, realized_pnl, holding_duration |

### Order Events

| Event Type | Description | When Emitted | Data Included |
|------------|-------------|--------------|---------------|
| `ORDER_PLACED` | Order sent to exchange | When order submitted | order_id, symbol, action, quantity, price |
| `ORDER_FILLED` | Order execution confirmed | When exchange confirms | order_id, filled_quantity, filled_price |
| `ORDER_CANCELLED` | Order cancelled | When order cancelled | order_id, reason |
| `ORDER_REJECTED` | Order rejected | When exchange rejects | order_id, reason |

---

## Component Breakdown

### 1. EventBus (`src/events/event_bus.py`)

**Central event distribution system.**

#### Features:
- ✅ Async event processing
- ✅ Priority-based queue (CRITICAL → HIGH → NORMAL → LOW)
- ✅ Subscribe with filters
- ✅ Event history (last 1000 events)
- ✅ Dead letter queue (failed handlers)
- ✅ Statistics tracking
- ✅ Wildcard subscriptions

#### Key Methods:
```python
# Publishing events
await event_bus.publish(
    event_type=EventType.SIGNAL_GENERATED,
    data={"signal_id": "abc123", ...},
    source="strategy.RSI",
    priority=EventPriority.HIGH
)

# Subscribing to events
event_bus.subscribe(
    event_type=EventType.SIGNAL_GENERATED,
    handler=my_async_handler,
    subscriber_id="options_executor",
    priority=10  # Higher priority = executed first
)

# Get statistics
stats = event_bus.get_stats()
# {
#   "events_published": 150,
#   "events_processed": 150,
#   "handlers_executed": 450,
#   "queue_size": 0
# }
```

---

### 2. EventDrivenSignalManager (`src/trading/signal_manager_event_driven.py`)

**Manages signals and publishes signal events.**

#### Workflow:
1. Strategy calls `emit_signal()`
2. Creates Signal object
3. Stores to database/JSON/memory
4. Publishes `SIGNAL_GENERATED` event
5. Subscribes to `SIGNAL_ACTIVATED`, `SIGNAL_COMPLETED`, `SIGNAL_STOPPED` for lifecycle tracking

#### Key Methods:
```python
# Emit a signal (called by strategies)
signal = await signal_manager.emit_signal(
    symbol="NIFTY",
    strategy="RSI_Strategy",
    action="BUY",
    entry_price=21500,
    stop_loss=21350,
    target=21700,
    signal_strength=7.5,
    expected_move_pct=0.93,
    timeframe="5min",
    metadata={"rsi": 32.5}
)

# Get active signals
signals = signal_manager.get_active_signals_list()
```

#### Event Emissions:
- ✅ `SIGNAL_GENERATED` - When signal created

#### Event Subscriptions:
- ✅ `SIGNAL_ACTIVATED` - Updates signal status to ACTIVE
- ✅ `SIGNAL_COMPLETED` - Marks signal as completed, calculates P&L
- ✅ `SIGNAL_STOPPED` - Marks signal as stopped, calculates P&L

---

### 3. EventDrivenOptionsExecutor (`src/trading/options_executor_event_driven.py`)

**Subscribes to signal events and executes options trades.**

#### Workflow:
1. Subscribes to `SIGNAL_GENERATED` events
2. When event received:
   - Validates signal (strength, expected move)
   - Checks risk limits (max positions)
   - Selects optimal strike using `StrikeSelector`
   - Calculates position size
   - Places entry order (respecting paper trading mode)
   - Creates position in `OptionsPositionManager`
3. Emits `SIGNAL_ACTIVATED` and `POSITION_OPENED` events

#### Key Methods:
```python
# Initialize and subscribe
await options_executor.initialize()

# Signal processing happens automatically via event subscription
```

#### Event Subscriptions:
- ✅ `SIGNAL_GENERATED` - Main entry point, processes signal

#### Event Emissions:
- ✅ `SIGNAL_ACTIVATED` - When order placed
- ✅ `POSITION_OPENED` - When position created

---

### 4. OptionsPositionManager (`src/trading/options_position_manager.py`)

**Monitors positions and handles exits.**

#### Workflow:
1. Receives position from `OptionsExecutor`
2. Monitors position in background loop
3. Checks:
   - Stop-loss levels
   - Target levels
   - Trailing stop-loss
   - Time-based exits
4. When exit triggered:
   - Places exit order (respecting paper trading mode)
   - Calculates P&L
   - Emits `POSITION_CLOSED` event
   - Emits `SIGNAL_COMPLETED` or `SIGNAL_STOPPED` event

#### Event Emissions:
- ✅ `POSITION_UPDATED` - Periodic position updates
- ✅ `POSITION_CLOSED` - When position fully exited
- ✅ `SIGNAL_COMPLETED` - Target hit
- ✅ `SIGNAL_STOPPED` - Stop-loss hit

---

## Benefits of Event-Driven Architecture

### 1. **Decoupling** 🔗
- Strategies don't know about options executor
- Options executor doesn't know about position manager
- Components can be added/removed without changing others

### 2. **Scalability** 📈
- Multiple subscribers can react to same event
- Add new features (notifications, analytics) by subscribing
- No code changes to existing components

### 3. **Testability** 🧪
- Easy to test components in isolation
- Mock event bus for unit tests
- Replay events for debugging

### 4. **Observability** 👁️
- Event history provides audit trail
- Dead letter queue catches errors
- Statistics for monitoring

### 5. **Flexibility** 🔄
- Enable/disable features by subscribing/unsubscribing
- Change event flow without code changes
- Priority-based processing

---

## Usage Examples

### Example 1: Strategy Emitting Signal

```python
from src.trading.signal_manager_event_driven import EventDrivenSignalManager

class RSI_Strategy:
    def __init__(self, signal_manager: EventDrivenSignalManager):
        self.signal_manager = signal_manager
    
    async def on_candle(self, candle):
        # Calculate RSI
        rsi = self.calculate_rsi()
        
        if rsi < 30:  # Oversold
            # Emit signal event
            await self.signal_manager.emit_signal(
                symbol="NIFTY",
                strategy="RSI_Strategy",
                action="BUY",
                entry_price=candle['close'],
                stop_loss=candle['close'] * 0.995,
                target=candle['close'] * 1.01,
                signal_strength=8.0,
                expected_move_pct=1.0,
                timeframe="5min",
                metadata={"rsi": rsi, "oversold": True}
            )
```

### Example 2: Subscribing to Position Events (Notifications)

```python
from src.events import EventBus, EventType, get_event_bus

class NotificationService:
    def __init__(self):
        self.event_bus = get_event_bus()
    
    async def initialize(self):
        # Subscribe to all signal events
        self.event_bus.subscribe(
            EventType.SIGNAL_GENERATED,
            self.on_signal_generated,
            "notification_service"
        )
        
        self.event_bus.subscribe(
            EventType.POSITION_OPENED,
            self.on_position_opened,
            "notification_service"
        )
        
        self.event_bus.subscribe(
            EventType.POSITION_CLOSED,
            self.on_position_closed,
            "notification_service"
        )
    
    async def on_signal_generated(self, event):
        # Send Telegram notification
        await self.send_telegram(
            f"📊 New Signal: {event.data['action']} {event.data['symbol']} "
            f"@ {event.data['entry_price']}"
        )
    
    async def on_position_opened(self, event):
        await self.send_telegram(
            f"✅ Position Opened: {event.data['option_symbol']} "
            f"x {event.data['quantity']}"
        )
    
    async def on_position_closed(self, event):
        pnl = event.data['realized_pnl']
        emoji = "🎉" if pnl > 0 else "😞"
        await self.send_telegram(
            f"{emoji} Position Closed: P&L = ₹{pnl:.2f}"
        )
```

### Example 3: Analytics Subscriber

```python
class AnalyticsService:
    def __init__(self):
        self.event_bus = get_event_bus()
        self.signals_count = 0
        self.win_rate = 0.0
    
    async def initialize(self):
        # Subscribe to completed signals
        self.event_bus.subscribe(
            EventType.SIGNAL_COMPLETED,
            self.track_win,
            "analytics"
        )
        
        self.event_bus.subscribe(
            EventType.SIGNAL_STOPPED,
            self.track_loss,
            "analytics"
        )
    
    async def track_win(self, event):
        self.signals_count += 1
        # Update win rate, track metrics, etc.
    
    async def track_loss(self, event):
        self.signals_count += 1
        # Update loss rate, track metrics, etc.
```

---

## Integration with Existing System

### Step 1: Initialize Event Bus

```python
from src.events import EventBus, set_event_bus

# In orchestrator.py __init__
self.event_bus = EventBus(max_history=1000, enable_history=True)
await self.event_bus.start()
set_event_bus(self.event_bus)
```

### Step 2: Use Event-Driven Signal Manager

```python
from src.trading.signal_manager_event_driven import EventDrivenSignalManager

# Replace SignalManager with EventDrivenSignalManager
self.signal_manager = EventDrivenSignalManager(
    config=self.config,
    api_client=self.api_client,
    data_layer=self.data_layer,
    event_bus=self.event_bus
)

await self.signal_manager.initialize()
```

### Step 3: Use Event-Driven Options Executor

```python
from src.trading.options_executor_event_driven import EventDrivenOptionsExecutor

self.options_executor = EventDrivenOptionsExecutor(
    config=self.config,
    api_client=self.api_client,
    data_layer=self.data_layer,
    event_bus=self.event_bus
)

await self.options_executor.initialize()
```

### Step 4: Strategies Emit Signals

```python
# In strategy execution
if signal_action != "HOLD":
    await self.signal_manager.emit_signal(
        symbol=symbol,
        strategy=strategy_name,
        action=signal_action,
        entry_price=current_price,
        stop_loss=stop_loss,
        target=target,
        signal_strength=signal_strength,
        expected_move_pct=expected_move,
        timeframe=timeframe
    )
```

---

## Monitoring & Debugging

### Check Event Bus Statistics

```python
stats = event_bus.get_stats()
print(f"Events Published: {stats['events_published']}")
print(f"Events Processed: {stats['events_processed']}")
print(f"Handlers Executed: {stats['handlers_executed']}")
print(f"Queue Size: {stats['queue_size']}")
```

### View Event History

```python
# Get recent signal events
signal_events = event_bus.get_history(
    event_type=EventType.SIGNAL_GENERATED,
    limit=10
)

for event in signal_events:
    print(f"{event.timestamp}: {event.data['symbol']} {event.data['action']}")
```

### Check Dead Letter Queue

```python
# Failed events
dlq = event_bus.dead_letter_queue
for failed in dlq:
    print(f"Failed: {failed['event']}, Error: {failed['error']}")
```

---

## Configuration

### Enable Event-Driven Mode

Add to `config/production.json`:

```json
{
  "events": {
    "enabled": true,
    "max_history": 1000,
    "enable_history": true
  },
  "signal_manager": {
    "mode": "event_driven"
  },
  "options_trading": {
    "mode": "event_driven",
    "enabled": true,
    "paper_trading": true,
    "logging_only_mode": true
  }
}
```

---

## Summary

✅ **Event-Driven Architecture Implemented**
✅ **Central Event Bus with Pub/Sub Pattern**
✅ **EventDrivenSignalManager publishes signal events**
✅ **EventDrivenOptionsExecutor subscribes to signals**
✅ **OptionsPositionManager emits position events**
✅ **Fully Decoupled Components**
✅ **Easy to Add New Subscribers (Notifications, Analytics)**
✅ **Event History for Audit Trail**
✅ **Dead Letter Queue for Error Handling**

**Benefits:**
- 🔗 Loose coupling between components
- 📈 Easy to scale and extend
- 🧪 Testable in isolation
- 👁️ Full observability
- 🔄 Flexible event routing

---

**End of Event-Driven Architecture Documentation**
