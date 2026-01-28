# AlphaStocks Trading System - Low Level Design Documentation (Part 2)

## Continuation of Data Flow Pipeline

```
PHASE 3: SIGNAL GENERATION & STORAGE
═════════════════════════════════════

Step 6: Signal Creation & Storage
┌────────────────────────────────────────────────────────────────┐
│  Orchestrator._process_signal(strategy_name, signal, symbol)   │
│  └─▶ SignalManager.add_signal_from_strategy()                 │
│                                                                │
│      Sub-step 6.1: Create Signal Object                       │
│      ├─▶ signal = Signal(                                     │
│      │     id=uuid4(),                                        │
│      │     symbol=symbol,                                     │
│      │     strategy=strategy_name,                            │
│      │     signal_type="BUY" or "SELL",                       │
│      │     entry_price=strategy_signal.price,                 │
│      │     stop_loss=calculated_sl,                           │
│      │     target=calculated_target,                          │
│      │     timestamp=datetime.now(),                          │
│      │     status="NEW",                                      │
│      │     metadata={                                         │
│      │       "confidence": 0.85,                              │
│      │       "expected_move_pct": 2.0                         │
│      │     }                                                   │
│      │   )                                                     │
│      │                                                         │
│      Sub-step 6.2: Store to Database                          │
│      ├─▶ ClickHouseDataLayer.store_signal({                  │
│      │     timestamp: signal.timestamp,                       │
│      │     signal_id: signal.id,                              │
│      │     symbol: signal.symbol,                             │
│      │     asset_type: "EQUITY",                              │
│      │     strategy: signal.strategy,                         │
│      │     action: signal.signal_type,                        │
│      │     price: signal.entry_price,                         │
│      │     quantity: 0,                                       │
│      │     confidence: 0.85,                                  │
│      │     target: signal.target,                             │
│      │     stop_loss: signal.stop_loss,                       │
│      │     metadata: json.dumps(signal.metadata)              │
│      │   })                                                    │
│      │   └─▶ INSERT INTO trading_signals VALUES (...)        │
│      │                                                         │
│      Sub-step 6.3: Add to In-Memory Cache                     │
│      ├─▶ self.active_signals[signal.id] = signal             │
│      │                                                         │
│      Sub-step 6.4: Save to JSON File (Fallback)              │
│      └─▶ _save_signals_to_file()                             │
│          └─▶ Write to data/signals/signals.json              │
│                                                                │
│  Logger Output:                                                │
│    INFO - Signal abc123 created for NIFTY via ma_crossover   │
│    INFO - Signal abc123 stored successfully                   │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
Step 7: Event Publication
┌────────────────────────────────────────────────────────────────┐
│  SignalManager (continues from Step 6)                         │
│  └─▶ EventBus.publish(                                        │
│        event_type=EventType.SIGNAL_GENERATED,                 │
│        data={                                                  │
│          "signal_id": signal.id,                              │
│          "symbol": symbol,                                     │
│          "action": "BUY",                                     │
│          "entry_price": 24500.0,                              │
│          "stop_loss": 24255.0,                                │
│          "target": 24990.0,                                   │
│          "signal_strength": 0.85,                             │
│          "expected_move_pct": 2.0,                            │
│          "strategy": "ma_crossover",                          │
│          "timestamp": "2025-10-10T09:15:00"                   │
│        },                                                      │
│        source="SignalManager",                                │
│        priority=EventPriority.HIGH                            │
│      )                                                         │
│                                                                │
│  EventBus Processing (Lock-Free):                             │
│  ├─▶ Create Event object (immutable)                         │
│  ├─▶ Find all matching subscriptions                         │
│  ├─▶ For each subscription:                                  │
│  │   └─▶ asyncio.create_task(                                │
│  │         _execute_handler(subscription, event)             │
│  │       )  # Independent task per handler                   │
│  │                                                             │
│  └─▶ All handlers execute in parallel (no blocking)          │
│                                                                │
│  Logger Output:                                                │
│    DEBUG - Published event: SIGNAL_GENERATED (abc123)         │
│    DEBUG - Dispatching to 3 subscribers                       │
└────────────────────────────────────────────────────────────────┘


PHASE 4: EVENT-DRIVEN OPTIONS EXECUTION
════════════════════════════════════════

Step 8: Options Executor Receives Event
┌────────────────────────────────────────────────────────────────┐
│  EventDrivenOptionsExecutor._on_signal_generated(event)        │
│  [Running in independent asyncio task]                         │
│                                                                │
│  task_name = asyncio.current_task().get_name()                │
│  signal_id = event.data["signal_id"]                          │
│  symbol = event.data["symbol"]                                │
│  action = event.data["action"]                                │
│  entry_price = event.data["entry_price"]                      │
│                                                                │
│  Logger Output:                                                │
│    INFO - 📨 [Task-Task-1] Received signal event: abc123 -   │
│           BUY NIFTY @ 24500.0                                 │
│                                                                │
│  Stats Update (atomic):                                       │
│    self.stats["signals_received"] += 1                        │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
Step 9: Signal Validation & Filtering
┌────────────────────────────────────────────────────────────────┐
│  EventDrivenOptionsExecutor._validate_signal_event()           │
│                                                                │
│  Check 1: Idempotency (Database Query)                        │
│  ├─▶ _is_signal_already_processed(signal_id)                 │
│  │   └─▶ position = PositionManager.get_position_by_signal() │
│  │       └─▶ SELECT * FROM positions                         │
│  │           WHERE signal_id = ?                              │
│  │       If exists → Signal already processed, skip          │
│  │                                                             │
│  Check 2: Symbol Validity                                     │
│  ├─▶ _validate_symbol(symbol)                                │
│  │   • Remove exchange prefix (NSE:, NFO:)                   │
│  │   • Check against VALID_OPTIONS_SYMBOLS                   │
│  │   • Filter test signals (TEST_*)                          │
│  │   • Map aliases (NIFTYBANK → BANKNIFTY)                   │
│  │                                                             │
│  Check 3: Signal Age                                          │
│  ├─▶ if signal_age > 24 hours:                               │
│  │   └─▶ Reject as stale                                     │
│  │                                                             │
│  Check 4: Configuration                                       │
│  ├─▶ if not self.enabled:                                    │
│  │   └─▶ Options trading disabled, skip                      │
│  │                                                             │
│  Check 5: Risk Limits                                         │
│  └─▶ if active_positions >= max_positions:                   │
│      └─▶ Risk limit exceeded, skip                           │
│                                                                │
│  Logger Output (if validation fails):                         │
│    DEBUG - Ignoring test signal: TEST_SIGNAL                  │
│    DEBUG - Signal already processed: abc123                   │
│    WARNING - Symbol 'UNKNOWN' is not valid options underlying│
│                                                                │
│  Stats Update:                                                │
│    self.stats["signals_rejected"] += 1                        │
│                                                                │
│  Result: True (proceed) or False (skip)                       │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼ (if validation passed)
Step 10: Strike Selection
┌────────────────────────────────────────────────────────────────┐
│  StrikeSelector.select_optimal_strike()                        │
│                                                                │
│  Input:                                                        │
│    • symbol: "NIFTY"                                          │
│    • action: "BUY"                                            │
│    • underlying_price: 24500.0                                │
│    • expected_move_pct: 2.0                                   │
│                                                                │
│  Sub-step 10.1: Get Option Chain                             │
│  ├─▶ KiteAPIClient.get_option_chain(symbol)                  │
│  │   └─▶ Returns all available strikes with:                 │
│  │       • strike_price                                      │
│  │       • expiry_date                                       │
│  │       • option_type (CE/PE)                               │
│  │       • ltp (last traded price)                           │
│  │       • bid, ask, volume, OI                              │
│  │       • greeks (delta, gamma, theta, vega, IV)            │
│  │                                                             │
│  Sub-step 10.2: Filter Options                               │
│  ├─▶ Filter by:                                               │
│  │   • Expiry: Weekly expiry (nearest Thursday)              │
│  │   • Type: CE if BUY, PE if SELL                           │
│  │   • Liquidity: volume > min_volume                        │
│  │   • Moneyness: ATM ± 3 strikes                            │
│  │                                                             │
│  Sub-step 10.3: Calculate Scores                             │
│  ├─▶ For each candidate option:                              │
│  │   score = (                                                │
│  │     liquidity_weight * normalized_volume +                │
│  │     delta_weight * delta +                                │
│  │     iv_weight * (1 / implied_volatility) +               │
│  │     moneyness_weight * moneyness_score                    │
│  │   )                                                        │
│  │                                                             │
│  Sub-step 10.4: Select Best Strike                           │
│  └─▶ best_option = max(candidates, key=lambda x: x.score)    │
│                                                                │
│  Result: {                                                     │
│    "symbol": "NIFTY25OCT24500CE",                             │
│    "strike": 24500.0,                                         │
│    "option_type": "CE",                                       │
│    "expiry": "2025-10-24",                                    │
│    "ltp": 125.50,                                             │
│    "delta": 0.52,                                             │
│    "iv": 18.5,                                                │
│    "lot_size": 50                                             │
│  }                                                             │
│                                                                │
│  Logger Output:                                                │
│    INFO - 🎯 Selected strike: NIFTY25OCT24500CE @ ₹125.50    │
│    DEBUG - Strike selection: delta=0.52, IV=18.5%, score=0.85│
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
Step 11: Position Sizing
┌────────────────────────────────────────────────────────────────┐
│  EventDrivenOptionsExecutor._calculate_position_size()         │
│                                                                │
│  Input:                                                        │
│    • option_premium: 125.50                                   │
│    • lot_size: 50                                             │
│    • risk_per_trade_pct: 2.0  (from config)                  │
│    • account_capital: 100000.0 (from config)                  │
│                                                                │
│  Calculation:                                                  │
│  ├─▶ max_risk_amount = account_capital * (risk_per_trade_pct/100)│
│  │                    = 100000 * 0.02 = 2000                 │
│  │                                                             │
│  ├─▶ position_cost = option_premium * lot_size                │
│  │                  = 125.50 * 50 = 6275                     │
│  │                                                             │
│  ├─▶ max_lots_by_risk = max_risk_amount / position_cost      │
│  │                     = 2000 / 6275 = 0.318... → 1 lot      │
│  │                                                             │
│  └─▶ quantity = 1 * lot_size = 50 units                      │
│                                                                │
│  Result:                                                       │
│    quantity = 50 (1 lot)                                      │
│    total_cost = 6275.0                                        │
│                                                                │
│  Logger Output:                                                │
│    DEBUG - Position sizing: 1 lot (50 units), cost=₹6,275    │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
Step 12: Stop-Loss & Target Calculation
┌────────────────────────────────────────────────────────────────┐
│  EventDrivenOptionsExecutor._calculate_exit_levels()           │
│                                                                │
│  Input:                                                        │
│    • entry_premium: 125.50                                    │
│    • expected_move_pct: 2.0                                   │
│    • config.risk_management.sl_pct: 30.0                     │
│    • config.risk_management.target_multiplier: 2.0           │
│                                                                │
│  Calculation:                                                  │
│  ├─▶ stop_loss_premium = entry_premium * (1 - sl_pct/100)    │
│  │                      = 125.50 * (1 - 0.30)                │
│  │                      = 87.85                               │
│  │                                                             │
│  └─▶ target_premium = entry_premium * (1 + expected_move * multiplier)│
│                     = 125.50 * (1 + 0.02 * 2.0)              │
│                     = 130.52                                  │
│                                                                │
│  Result:                                                       │
│    stop_loss_premium = 87.85                                  │
│    target_premium = 130.52                                    │
│                                                                │
│  Logger Output:                                                │
│    DEBUG - Exit levels: SL=₹87.85, Target=₹130.52            │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
