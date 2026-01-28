# Quick Start: Event-Driven Trading System

**Ready-to-use event-driven architecture for AlphaStocks**

---

## What Changed?

Instead of **direct method calls**, components now communicate via **events**:

### Before (Direct Calls):
```python
Strategy → SignalManager.add_signal() → OptionsExecutor.process_signal()
```

### After (Event-Driven):
```python
Strategy → emit_signal() → EVENT BUS → All Subscribers
                                ↓
                        OptionsExecutor (auto-processes)
                        NotificationService (auto-notifies)
                        AnalyticsService (auto-tracks)
```

---

## Step-by-Step Integration

### Step 1: Start Event Bus in Orchestrator

**File:** `src/orchestrator.py`

```python
# Add imports at top
from src.events import EventBus, set_event_bus

class AlphaStockOrchestrator:
    def __init__(self, config):
        # ... existing init code ...
        
        # NEW: Initialize event bus
        self.event_bus = EventBus(max_history=1000, enable_history=True)
        set_event_bus(self.event_bus)
        
    async def initialize(self):
        # Start event bus
        await self.event_bus.start()
        
        # ... rest of initialization ...
```

---

### Step 2: Replace SignalManager with Event-Driven Version

**File:** `src/orchestrator.py`

```python
# Change import
from src.trading.signal_manager_event_driven import EventDrivenSignalManager

class AlphaStockOrchestrator:
    def __init__(self, config):
        # ... after event bus initialization ...
        
        # NEW: Use event-driven signal manager
        self.signal_manager = EventDrivenSignalManager(
            config=self.config,
            api_client=self.api_client,
            data_layer=self.data_layer,
            event_bus=self.event_bus
        )
    
    async def initialize(self):
        await self.event_bus.start()
        
        # Initialize signal manager (subscribes to events)
        await self.signal_manager.initialize()
        
        # ... rest of initialization ...
```

---

### Step 3: Replace OptionsExecutor with Event-Driven Version

**File:** `src/orchestrator.py`

```python
# Change import
from src.trading.options_executor_event_driven import EventDrivenOptionsExecutor

class AlphaStockOrchestrator:
    def __init__(self, config):
        # ... existing code ...
        
        # Check if options trading enabled
        if self.config.get("options_trading", {}).get("enabled", False):
            # NEW: Use event-driven executor
            self.options_trade_executor = EventDrivenOptionsExecutor(
                config=self.config,
                api_client=self.api_client,
                data_layer=self.data_layer,
                event_bus=self.event_bus
            )
    
    async def initialize(self):
        # ... existing initialization ...
        
        # Initialize options executor (subscribes to signal events)
        if self.options_trade_executor:
            await self.options_trade_executor.initialize()
```

---

### Step 4: Update Strategy Signal Emission

**File:** `src/orchestrator.py` in `_process_signal()` method

```python
async def _process_signal(self, signal):
    """Process trading signal (now emits events)"""
    try:
        symbol = signal.get('symbol')
        action = signal.get('action')
        price = signal.get('price')
        strategy = signal.get('strategy', 'Unknown')
        
        if action == "HOLD":
            return
        
        logger.info(f"Processing signal: {action} {symbol} @ {price}")
        
        # Calculate SL and Target (example logic)
        sl_pct = 0.5  # 0.5%
        target_pct = 1.0  # 1.0%
        
        if action == "BUY":
            stop_loss = price * (1 - sl_pct / 100)
            target = price * (1 + target_pct / 100)
        else:
            stop_loss = price * (1 + sl_pct / 100)
            target = price * (1 - target_pct / 100)
        
        # Get signal strength and expected move from signal
        signal_strength = signal.get('signal_strength', 5.0)
        expected_move_pct = signal.get('expected_move_pct', 0.5)
        timeframe = signal.get('timeframe', '5min')
        
        # NEW: Emit signal event instead of calling add_signal
        await self.signal_manager.emit_signal(
            symbol=symbol,
            strategy=strategy,
            action=action,
            entry_price=price,
            stop_loss=stop_loss,
            target=target,
            signal_strength=signal_strength,
            expected_move_pct=expected_move_pct,
            timeframe=timeframe,
            metadata={
                'original_signal': signal
            }
        )
        
        logger.info(f"✅ Signal event emitted for {symbol}")
        
    except Exception as e:
        logger.error(f"Error processing signal: {e}")
```

---

### Step 5: Clean Up Old Code

**Remove these if using event-driven mode:**

1. **Remove manual options executor calls:**
```python
# DELETE: No longer needed
# await self.options_trade_executor.process_signal(signal)
```

2. **Remove manual signal activation:**
```python
# DELETE: Now handled by event subscriptions
# await self.signal_manager.activate_signal(signal_id, order_id)
```

---

## Verification Steps

### Step 1: Test Event Bus

```python
# Run this in main.py
from src.events import get_event_bus

# Check event bus stats
event_bus = get_event_bus()
stats = event_bus.get_stats()
print(f"Event Bus Stats: {stats}")
```

### Step 2: Test Signal Emission

```powershell
# Run system and watch logs
python main.py

# In another terminal, monitor events
Get-Content logs/AlphaStockOrchestrator.log -Wait | Select-String "Signal event emitted|Received signal event"
```

### Step 3: Check Subscriptions

```python
# Check what's subscribed
event_bus = get_event_bus()
print(f"Active subscriptions: {len(event_bus.subscriptions)}")

for event_type, subs in event_bus.subscriptions.items():
    print(f"{event_type.value}: {len(subs)} subscribers")
    for sub in subs:
        print(f"  - {sub.subscriber_id}")
```

**Expected Output:**
```
EventType.SIGNAL_GENERATED: 1 subscribers
  - options_executor
EventType.SIGNAL_ACTIVATED: 1 subscribers
  - signal_manager
EventType.SIGNAL_COMPLETED: 1 subscribers
  - signal_manager
EventType.SIGNAL_STOPPED: 1 subscribers
  - signal_manager
```

---

## Adding New Features (Example: Notifications)

### 1. Create Notification Service

**File:** `src/services/notification_service.py`

```python
from src.events import EventBus, EventType, get_event_bus
from src.utils.logger_setup import setup_logger

logger = setup_logger("notifications")

class NotificationService:
    def __init__(self, config, event_bus=None):
        self.config = config
        self.event_bus = event_bus or get_event_bus()
        self.telegram_enabled = config.get("notifications", {}).get("telegram", {}).get("enabled", False)
    
    async def initialize(self):
        """Subscribe to events"""
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
        
        logger.info("✅ NotificationService subscribed to events")
    
    async def on_signal_generated(self, event):
        """Handle signal generated event"""
        data = event.data
        message = (
            f"📊 New Signal\n"
            f"Symbol: {data['symbol']}\n"
            f"Action: {data['action']}\n"
            f"Entry: ₹{data['entry_price']:.2f}\n"
            f"Target: ₹{data['target']:.2f}\n"
            f"SL: ₹{data['stop_loss']:.2f}\n"
            f"Strength: {data['signal_strength']}/10"
        )
        
        logger.info(f"📨 Notification: {message}")
        
        if self.telegram_enabled:
            await self.send_telegram(message)
    
    async def on_position_opened(self, event):
        """Handle position opened event"""
        data = event.data
        message = (
            f"✅ Position Opened\n"
            f"Option: {data['option_symbol']}\n"
            f"Strike: {data['strike']}\n"
            f"Qty: {data['quantity']}\n"
            f"Entry: ₹{data['entry_premium']:.2f}"
        )
        
        logger.info(f"📨 Notification: {message}")
        
        if self.telegram_enabled:
            await self.send_telegram(message)
    
    async def on_position_closed(self, event):
        """Handle position closed event"""
        data = event.data
        pnl = data['realized_pnl']
        emoji = "🎉" if pnl > 0 else "😞"
        
        message = (
            f"{emoji} Position Closed\n"
            f"Exit: ₹{data['exit_premium']:.2f}\n"
            f"P&L: ₹{pnl:.2f} ({data['realized_pnl_pct']:.2f}%)\n"
            f"Reason: {data['exit_reason']}"
        )
        
        logger.info(f"📨 Notification: {message}")
        
        if self.telegram_enabled:
            await self.send_telegram(message)
    
    async def send_telegram(self, message):
        """Send Telegram notification (implement your logic)"""
        # TODO: Implement Telegram API call
        pass
```

### 2. Add to Orchestrator

```python
from src.services.notification_service import NotificationService

class AlphaStockOrchestrator:
    def __init__(self, config):
        # ... existing code ...
        
        # Add notification service
        self.notification_service = NotificationService(
            config=self.config,
            event_bus=self.event_bus
        )
    
    async def initialize(self):
        # ... existing code ...
        
        # Initialize notification service
        await self.notification_service.initialize()
```

**That's it!** No changes to strategies or executors needed. Notifications work automatically.

---

## Configuration

**File:** `config/production.json`

```json
{
  "events": {
    "enabled": true,
    "max_history": 1000,
    "enable_history": true
  },
  
  "options_trading": {
    "enabled": true,
    "paper_trading": true,
    "logging_only_mode": true,
    "min_signal_strength": 5.0,
    "min_expected_move_pct": 0.5,
    "max_concurrent_positions": 3
  },
  
  "notifications": {
    "telegram": {
      "enabled": true,
      "bot_token": "YOUR_BOT_TOKEN",
      "chat_id": "YOUR_CHAT_ID"
    }
  }
}
```

---

## Troubleshooting

### Problem: Events not being received

**Check:**
```python
# Are subscribers registered?
event_bus = get_event_bus()
print(event_bus.subscriptions)

# Is event bus running?
print(f"Event bus running: {event_bus.is_running}")

# Check queue size
print(f"Queue size: {event_bus.event_queue.qsize()}")
```

**Solution:**
- Ensure `await event_bus.start()` is called
- Ensure subscribers call `initialize()` after event bus starts
- Check for exceptions in handler functions

### Problem: Handler errors

**Check:**
```python
# Check dead letter queue
dlq = event_bus.dead_letter_queue
for failed in dlq:
    print(f"Failed handler: {failed['subscription'].subscriber_id}")
    print(f"Error: {failed['error']}")
    print(f"Event: {failed['event']}")
```

**Solution:**
- Add try/except in handler functions
- Check handler function signatures (must accept Event parameter)
- Ensure handlers are async if they use await

---

## Summary

✅ **Event Bus initialized and started**
✅ **EventDrivenSignalManager publishes signal events**
✅ **EventDrivenOptionsExecutor subscribes and processes**
✅ **Fully decoupled components**
✅ **Easy to add notifications, analytics, etc.**
✅ **No changes needed to strategies**

**Key Benefits:**
- Strategies just emit signals → Everything else is automatic
- Add new features by subscribing to events
- No tight coupling between components
- Easy to test and debug

---

**Ready to use! Start the system with `python main.py`**
