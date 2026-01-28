"""
Event-Driven Options Trade Executor
Subscribes to signal events and executes options trades.

THREAD SAFETY: Lock-free design using:
- Each signal processed in independent asyncio task (via EventBus)
- No shared state between signal processing
- Event data contains all context (no external lookups)
- Database queries for position state (single source of truth)
- Atomic statistics with collections.Counter
"""

import asyncio
import logging
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import uuid

from ..utils.logger_setup import setup_logger
from ..events import EventBus, get_event_bus, EventType, Event
from .strike_selector import StrikeSelector
from .options_greeks import OptionsGreeksCalculator
from .options_position_manager import OptionsPositionManager

logger = setup_logger("options_executor_event_driven")


class EventDrivenOptionsExecutor:
    """
    Event-driven options trade executor that subscribes to signal events.
    
    Workflow:
    1. Subscribe to SIGNAL_GENERATED events
    2. When signal received, validate it
    3. Select optimal strike using StrikeSelector
    4. Calculate position size
    5. Place entry order (respecting paper trading mode)
    6. Emit POSITION_OPENED event
    7. Hand off to PositionManager for monitoring
    """
    
    def __init__(
        self,
        config: Dict,
        api_client,
        data_layer,
        event_bus: Optional[EventBus] = None
    ):
        """
        Initialize event-driven options executor.
        
        Args:
            config: System configuration
            api_client: API client for trading
            data_layer: Data layer for market data
            event_bus: Event bus instance (uses global if None)
        """
        self.config = config
        self.api_client = api_client
        self.data_layer = data_layer
        self.event_bus = event_bus or get_event_bus()
        
        # Options trading config
        self.options_config = config.get("options_trading", {})
        self.enabled = self.options_config.get("enabled", False)
        self.paper_trading = self.options_config.get("paper_trading", True)
        self.logging_only_mode = self.options_config.get("logging_only_mode", True)
        
        # Initialize components
        self.strike_selector = StrikeSelector(config, api_client, data_layer)
        self.greeks_calculator = OptionsGreeksCalculator()
        self.position_manager = OptionsPositionManager(
            config=config,
            api_client=api_client,
            data_layer=data_layer,
            paper_trading=self.paper_trading,
            logging_only_mode=self.logging_only_mode
        )
        
        # ELIMINATED: self.processed_signals (idempotency via database check)
        # ELIMINATED: self.active_positions (database is single source of truth)
        
        # Atomic statistics using Counter (thread-safe)
        self.stats = Counter({
            "signals_received": 0,
            "signals_processed": 0,
            "signals_rejected": 0,
            "trades_executed": 0,
            "logging_only_trades": 0,
            "paper_trades": 0,
            "live_trades": 0,
        })
        
        logger.info(
            f"EventDrivenOptionsExecutor initialized (lock-free) - "
            f"Enabled: {self.enabled}, Paper: {self.paper_trading}, "
            f"Logging Only: {self.logging_only_mode}"
        )
    
    async def initialize(self):
        """Initialize the executor and subscribe to events"""
        if not self.enabled:
            logger.warning("Options trading is disabled in config")
            return
        
        # Subscribe to signal generated events
        self.event_bus.subscribe(
            event_type=EventType.SIGNAL_GENERATED,
            handler=self._on_signal_generated,
            subscriber_id="options_executor",
            priority=10  # High priority
        )
        
        # Start position manager monitoring
        await self.position_manager.start_monitoring()
        
        logger.info("✅ EventDrivenOptionsExecutor subscribed to SIGNAL_GENERATED events")
    
    async def _on_signal_generated(self, event: Event):
        """
        Handle signal generated event.
        
        This is the main entry point when a strategy emits a signal.
        Each signal is processed in an independent asyncio task (by EventBus).
        No shared state, no locks needed.
        """
        signal_id = event.data["signal_id"]
        
        # Atomic increment
        self.stats["signals_received"] += 1
        
        logger.info(
            f"📨 [Task-{asyncio.current_task().get_name()}] "
            f"Received signal event: {signal_id[:8]} - "
            f"{event.data['action']} {event.data['symbol']} @ {event.data['entry_price']}"
        )
        
        try:
            # Check idempotency via database (single source of truth)
            if await self._is_signal_already_processed(signal_id):
                logger.debug(f"Signal {signal_id[:8]} already processed (found in DB), skipping")
                return
            
            # Process the signal (all context in event.data, no shared state)
            await self._process_signal_event(event)
            
            # Atomic increment
            self.stats["signals_processed"] += 1
            
        except Exception as e:
            logger.error(f"Error processing signal {signal_id[:8]}: {e}", exc_info=True)
            self.stats["signals_rejected"] += 1
    
    async def _is_signal_already_processed(self, signal_id: str) -> bool:
        """
        Check if signal has already been processed (idempotency check).
        Uses database as single source of truth instead of in-memory set.
        
        Args:
            signal_id: Signal UUID
            
        Returns:
            bool: True if signal already has an active/closed position
        """
        try:
            # Check if position exists for this signal in position manager
            # Position manager uses database, so this is lock-free
            position = self.position_manager.get_position_by_signal(signal_id)
            return position is not None
        except Exception as e:
            logger.warning(f"Error checking signal idempotency: {e}")
            # On error, assume not processed (better to risk duplicate than miss signal)
            return False
    
    async def _process_signal_event(self, event: Event):
        """
        Process a signal event and execute options trade.
        
        Steps:
        1. Validate signal
        2. Select strike
        3. Calculate position size
        4. Place entry order
        5. Create position
        
        Each signal runs in an independent task with its own context.
        No shared state access, lock-free execution.
        """
        signal_data = event.data
        signal_id = signal_data["signal_id"]
        symbol = signal_data["symbol"]
        action = signal_data["action"]
        entry_price = signal_data["entry_price"]
        stop_loss = signal_data["stop_loss"]
        target = signal_data["target"]
        signal_strength = signal_data["signal_strength"]
        expected_move_pct = signal_data["expected_move_pct"]
        
        logger.info(f"🔍 Processing signal {signal_id[:8]} for {symbol}")
        
        # Step 1: Validate signal
        if not self._validate_signal(signal_data):
            logger.warning(f"Signal {signal_id[:8]} failed validation")
            return
        
        # Step 2: Check risk limits
        if not self._check_risk_limits():
            logger.warning(f"Risk limits exceeded, cannot process signal {signal_id[:8]}")
            return
        
        # Step 3: Select optimal strike
        logger.info(f"🎯 Selecting strike for {symbol}...")
        
        strike_selection = await self.strike_selector.select_best_strike(
            symbol=symbol,
            action=action,
            current_price=entry_price,
            expected_move_pct=expected_move_pct,
            signal_strength=signal_strength
        )
        
        if not strike_selection:
            logger.warning(f"No suitable strike found for {symbol}")
            return
        
        selected_strike = strike_selection["strike"]
        option_symbol = strike_selection["option_symbol"]
        option_type = strike_selection["option_type"]
        current_premium = strike_selection["premium"]
        
        logger.info(
            f"✅ Selected: {option_symbol} @ ₹{current_premium:.2f} "
            f"(Strike: {selected_strike}, Type: {option_type})"
        )
        
        # Step 4: Calculate stop-loss and target premiums
        sl_pct = self.options_config.get("stop_loss_pct", 30.0)
        target_pct = self.options_config.get("target_pct", 50.0)
        
        stop_loss_premium = current_premium * (1 - sl_pct / 100)
        target_premium = current_premium * (1 + target_pct / 100)
        
        # Step 5: Calculate position size
        lot_size = strike_selection.get("lot_size", 25)
        max_lots = self.options_config.get("max_lots_per_trade", 1)
        quantity = lot_size * max_lots
        
        total_value = current_premium * quantity
        
        logger.info(
            f"💰 Position: {quantity} units ({max_lots} lots) = ₹{total_value:.2f}"
        )
        
        # Step 6: Place entry order
        order_result = await self._place_entry_order(
            option_symbol=option_symbol,
            action=action,
            quantity=quantity,
            price=current_premium,
            strike=selected_strike,
            option_type=option_type
        )
        
        if not order_result:
            logger.error(f"Failed to place order for {option_symbol}")
            return
        
        order_id = order_result["order_id"]
        
        logger.info(f"✅ Order placed: {order_id}")
        
        # Step 7: Create position in position manager
        position_id = await self.position_manager.add_position(
            signal_id=signal_id,
            symbol=symbol,
            option_symbol=option_symbol,
            strike=selected_strike,
            option_type=option_type,
            action=action,
            quantity=quantity,
            entry_premium=current_premium,
            stop_loss_premium=stop_loss_premium,
            target_premium=target_premium,
            order_id=order_id
        )
        
        # ELIMINATED: self.active_positions tracking (database is source of truth)
        
        # Update stats (atomic)
        self.stats["trades_executed"] += 1
        if self.logging_only_mode:
            self.stats["logging_only_trades"] += 1
        elif self.paper_trading:
            self.stats["paper_trades"] += 1
        else:
            self.stats["live_trades"] += 1
        
        # Emit position opened event
        await self.event_bus.publish(
            event_type=EventType.POSITION_OPENED,
            data={
                "position_id": position_id,
                "signal_id": signal_id,
                "symbol": symbol,
                "option_symbol": option_symbol,
                "strike": selected_strike,
                "option_type": option_type,
                "quantity": quantity,
                "entry_premium": current_premium,
                "stop_loss_premium": stop_loss_premium,
                "target_premium": target_premium,
            },
            source="options_executor"
        )
        
        # Emit signal activated event
        await self.event_bus.publish(
            event_type=EventType.SIGNAL_ACTIVATED,
            data={
                "signal_id": signal_id,
                "order_id": order_id,
                "symbol": symbol,
                "action": action,
                "price": current_premium,
                "quantity": quantity,
            },
            source="options_executor"
        )
        
        logger.info(f"🎉 Options trade executed successfully for signal {signal_id[:8]}")
    
    def _validate_signal(self, signal_data: Dict) -> bool:
        """Validate signal meets criteria"""
        signal_strength = signal_data.get("signal_strength", 0)
        expected_move = signal_data.get("expected_move_pct", 0)
        
        min_strength = self.options_config.get("min_signal_strength", 5.0)
        min_move = self.options_config.get("min_expected_move_pct", 0.5)
        
        if signal_strength < min_strength:
            logger.warning(
                f"Signal strength {signal_strength} < minimum {min_strength}"
            )
            return False
        
        if expected_move < min_move:
            logger.warning(
                f"Expected move {expected_move}% < minimum {min_move}%"
            )
            return False
        
        return True
    
    def _check_risk_limits(self) -> bool:
        """Check if risk limits allow new position"""
        max_positions = self.options_config.get("max_concurrent_positions", 3)
        active_count = len(self.active_positions)
        
        if active_count >= max_positions:
            logger.warning(
                f"Max concurrent positions ({max_positions}) reached"
            )
            return False
        
        return True
    
    async def _place_entry_order(
        self,
        option_symbol: str,
        action: str,
        quantity: int,
        price: float,
        strike: float,
        option_type: str
    ) -> Optional[Dict]:
        """
        Place entry order respecting trading mode.
        
        Returns:
            Order result with order_id
        """
        total_value = price * quantity
        
        # LOGGING ONLY MODE
        if self.logging_only_mode:
            logger.info("=" * 64)
            logger.info("[LOGGING ONLY MODE] ORDER NOT PLACED")
            logger.info("=" * 64)
            logger.info("Order Details:")
            logger.info(f"   Symbol: {option_symbol}")
            logger.info(f"   Strike: {strike}")
            logger.info(f"   Option Type: {option_type}")
            logger.info(f"   Exchange: NFO")
            logger.info(f"   Action: {action}")
            logger.info(f"   Quantity: {quantity} units")
            logger.info(f"   Order Type: LIMIT")
            logger.info(f"   Price: ₹{price:.2f}")
            logger.info(f"   Product: MIS (Intraday)")
            logger.info(f"   Total Value: ₹{total_value:.2f}")
            logger.info(f"   Simulated Order ID: LOG_{uuid.uuid4().hex[:8]}")
            logger.info("=" * 64)
            logger.info("To execute real orders, set 'logging_only_mode': false")
            logger.info("=" * 64)
            
            return {
                "order_id": f"LOG_{uuid.uuid4().hex[:8]}",
                "status": "LOGGED",
                "price": price,
                "quantity": quantity
            }
        
        # PAPER TRADING MODE
        if self.paper_trading:
            order_id = f"PAPER_{uuid.uuid4().hex[:8]}"
            logger.info("=" * 60)
            logger.info(f"📄 Paper Trade Order: {action} {option_symbol} x {quantity} @ ₹{price:.2f}")
            logger.info(f"   Paper Order ID: {order_id}")
            logger.info("=" * 60)
            
            return {
                "order_id": order_id,
                "status": "PAPER",
                "price": price,
                "quantity": quantity
            }
        
        # LIVE TRADING MODE
        logger.info("=" * 80)
        logger.info("💰 LIVE TRADING - PLACING REAL ORDER WITH REAL MONEY!")
        logger.info("=" * 80)
        
        try:
            order_id = self.api_client.place_order(
                variety=self.api_client.VARIETY_REGULAR,
                exchange=self.api_client.EXCHANGE_NFO,
                tradingsymbol=option_symbol,
                transaction_type=self.api_client.TRANSACTION_TYPE_BUY if action == "BUY" else self.api_client.TRANSACTION_TYPE_SELL,
                quantity=quantity,
                order_type=self.api_client.ORDER_TYPE_LIMIT,
                price=price,
                product=self.api_client.PRODUCT_MIS
            )
            
            logger.info(f"✅ Real order placed: {order_id}")
            logger.info(f"   Symbol: {option_symbol}")
            logger.info(f"   Quantity: {quantity} units")
            logger.info(f"   Price: ₹{price:.2f}")
            logger.info(f"   Total: ₹{total_value:.2f}")
            logger.info("=" * 80)
            
            return {
                "order_id": order_id,
                "status": "PLACED",
                "price": price,
                "quantity": quantity
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to place live order: {e}")
            return None
    
    def get_statistics(self) -> Dict:
        """Get executor statistics (lock-free)"""
        return {
            "executor_stats": dict(self.stats),  # Convert Counter to dict
            "position_manager_stats": self.position_manager.get_performance_metrics(),
            "active_positions_count": len(self.position_manager.active_positions),
        }
    
    async def stop(self):
        """Stop the executor"""
        logger.info("Stopping EventDrivenOptionsExecutor...")
        await self.position_manager.stop_monitoring()
        logger.info("EventDrivenOptionsExecutor stopped")
