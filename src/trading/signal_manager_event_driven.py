"""
Event-Driven Signal Manager
Publishes signal events instead of direct method calls.
"""

import os
import json
import logging
import asyncio
from datetime import datetime, time
import threading
import uuid
from typing import Optional, Dict, List, Tuple

from ..data import DataLayerInterface
from ..utils.logger_setup import setup_logger
from ..utils.timezone_utils import get_current_time, get_today_market_open
from ..events import (
    EventBus,
    get_event_bus,
    SignalGeneratedEvent,
    SignalActivatedEvent,
    SignalCompletedEvent,
    SignalStoppedEvent,
    EventType
)

logger = setup_logger("signal_manager_event_driven")


def is_signal_still_active(last_signal: Dict, current_price: float) -> bool:
    """
    Check if previous signal is still valid based on current price.
    
    A signal is considered "active" if the current price is still within
    the range between stop_loss and target.
    
    For BUY signals: Active if stop_loss < current_price < target
    For SELL signals: Active if target < current_price < stop_loss
    
    Args:
        last_signal: Dictionary containing previous signal data
        current_price: Current market price
    
    Returns:
        True if signal is still active, False otherwise
    """
    action = last_signal.get('action') or last_signal.get('signal_type')
    stop_loss = last_signal.get('stop_loss')
    target = last_signal.get('target')
    
    if not all([action, stop_loss, target]):
        # Missing required fields, consider signal inactive
        return False
    
    if action == 'BUY':
        # BUY signal active if: stop_loss < current_price < target
        return stop_loss < current_price < target
    else:  # SELL
        # SELL signal active if: target < current_price < stop_loss
        return target < current_price < stop_loss


class Signal:
    """
    Represents a trading signal with entry, stop-loss, and target prices
    """
    
    def __init__(self, symbol, strategy, signal_type, entry_price, stop_loss, target, 
                 timestamp=None, metadata=None, signal_strength=0.0, expected_move_pct=0.0,
                 timeframe="5min"):
        """Initialize a new signal"""
        self.id = str(uuid.uuid4())
        self.symbol = symbol
        self.strategy = strategy
        self.signal_type = signal_type  # 'BUY' or 'SELL'
        self.entry_price = entry_price
        self.stop_loss = stop_loss
        self.target = target
        self.timestamp = timestamp or get_current_time().isoformat()
        self.status = "NEW"  # NEW, ACTIVE, COMPLETED, STOPPED
        self.order_id = None
        self.exit_price = None
        self.exit_timestamp = None
        self.profit_loss = None
        self.metadata = metadata or {}
        self.exit_reason = None
        self.signal_strength = signal_strength
        self.expected_move_pct = expected_move_pct
        self.timeframe = timeframe
    
    def to_dict(self):
        """Convert signal to dictionary"""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "strategy": self.strategy,
            "signal_type": self.signal_type,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "target": self.target,
            "timestamp": self.timestamp,
            "status": self.status,
            "order_id": self.order_id,
            "exit_price": self.exit_price,
            "exit_timestamp": self.exit_timestamp,
            "profit_loss": self.profit_loss,
            "metadata": self.metadata,
            "exit_reason": self.exit_reason,
            "signal_strength": self.signal_strength,
            "expected_move_pct": self.expected_move_pct,
            "timeframe": self.timeframe
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create signal from dictionary"""
        signal = cls(
            symbol=data["symbol"],
            strategy=data["strategy"],
            signal_type=data["signal_type"],
            entry_price=data["entry_price"],
            stop_loss=data["stop_loss"],
            target=data["target"],
            timestamp=data.get("timestamp"),
            metadata=data.get("metadata", {}),
            signal_strength=data.get("signal_strength", 0.0),
            expected_move_pct=data.get("expected_move_pct", 0.0),
            timeframe=data.get("timeframe", "5min")
        )
        signal.id = data.get("id", signal.id)
        signal.status = data.get("status", "NEW")
        signal.order_id = data.get("order_id")
        signal.exit_price = data.get("exit_price")
        signal.exit_timestamp = data.get("exit_timestamp")
        signal.profit_loss = data.get("profit_loss")
        signal.exit_reason = data.get("exit_reason")
        return signal


class EventDrivenSignalManager:
    """
    Event-driven Signal Manager that publishes events instead of direct calls.
    
    This allows decoupled communication:
    - Strategies emit signals as events
    - Options executor subscribes to signal events
    - Position manager subscribes to position events
    """
    
    def __init__(
        self,
        config,
        api_client=None,
        data_layer: Optional[DataLayerInterface] = None,
        event_bus: Optional[EventBus] = None
    ):
        """
        Initialize event-driven signal manager.
        
        Args:
            config: System configuration
            api_client: API client for trading
            data_layer: Data layer for persistence
            event_bus: Event bus instance (uses global if None)
        """
        self.config = config
        self.api_client = api_client
        self.data_layer = data_layer
        self.event_bus = event_bus or get_event_bus()
        
        # Storage
        self.signals_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data", "signals"
        )
        self.signals_file = os.path.join(self.signals_dir, "signals.json")
        self.active_signals = {}  # id -> Signal
        self.lock = threading.Lock()
        
        # Ensure directory exists
        os.makedirs(self.signals_dir, exist_ok=True)
        
        # Statistics for deduplication
        self.stats = {
            'signals_generated': 0,
            'signals_skipped_duplicate': 0,
            'signals_reversal': 0,
            'signals_previous_invalidated': 0
        }
        
        logger.info("EventDrivenSignalManager initialized")
    
    async def initialize(self):
        """Initialize the signal manager and subscribe to events"""
        await self.load_signals()
        
        # Subscribe to signal lifecycle events (for internal tracking)
        self.event_bus.subscribe(
            EventType.SIGNAL_ACTIVATED,
            self._on_signal_activated,
            subscriber_id="signal_manager"
        )
        
        self.event_bus.subscribe(
            EventType.SIGNAL_COMPLETED,
            self._on_signal_completed,
            subscriber_id="signal_manager"
        )
        
        self.event_bus.subscribe(
            EventType.SIGNAL_STOPPED,
            self._on_signal_stopped,
            subscriber_id="signal_manager"
        )
        
        logger.info("EventDrivenSignalManager subscriptions set up")
    
    async def load_signals(self):
        """Load signals from data layer or file fallback"""
        try:
            # Try loading from data layer first
            if self.data_layer:
                try:
                    signals_data = await self.data_layer.get_signals()
                    if signals_data:
                        for signal_dict in signals_data:
                            signal = Signal.from_dict(signal_dict)
                            if signal.status in ["NEW", "ACTIVE"]:
                                self.active_signals[signal.id] = signal
                        logger.info(f"Loaded {len(self.active_signals)} active signals from data layer")
                        return
                except Exception as e:
                    logger.warning(f"Failed to load signals from data layer: {e}")
            
            # Fallback to file-based loading
            if os.path.exists(self.signals_file):
                with open(self.signals_file, "r") as f:
                    signals_data = json.load(f)
                
                for signal_data in signals_data:
                    signal = Signal.from_dict(signal_data)
                    if signal.status in ["NEW", "ACTIVE"]:
                        self.active_signals[signal.id] = signal
                
                logger.info(f"Loaded {len(self.active_signals)} active signals from file")
        
        except Exception as e:
            logger.error(f"Error loading signals: {e}")
    
    async def should_generate_signal(
        self,
        symbol: str,
        strategy: str,
        action: str,
        current_price: float
    ) -> Tuple[bool, str]:
        """
        Determine if a new signal should be generated based on deduplication rules.
        
        Rules:
        1. No previous signal today → Generate (first signal)
        2. Opposite direction signal → Always generate (reversal)
        3. Same direction + price within range → Skip (duplicate)
        4. Same direction + price outside range → Generate (previous invalidated)
        
        Args:
            symbol: Trading symbol
            strategy: Strategy name
            action: Signal action ('BUY' or 'SELL')
            current_price: Current entry price
        
        Returns:
            Tuple of (should_generate: bool, reason: str)
        """
        try:
            if not self.data_layer:
                # If no data layer, allow signal (no deduplication)
                return True, "No data layer available for deduplication"
            
            # Get today's market open time (9:15 AM IST)
            today_session_start = get_today_market_open()
            
            # Query last signal for this symbol+strategy from today's session
            last_signal = await self.data_layer.get_last_signal(
                symbol=symbol,
                strategy=strategy,
                since=today_session_start
            )
            
            # Case 1: No previous signal today → Generate
            if not last_signal:
                return True, "First signal of the day"
            
            last_action = last_signal.get('action') or last_signal.get('signal_type')
            
            # Case 2: Opposite direction → Always generate (reversal)
            if last_action != action:
                self.stats['signals_reversal'] += 1
                return True, f"Reversal signal ({last_action} → {action})"
            
            # Case 3 & 4: Same direction - check if previous signal is still active
            if is_signal_still_active(last_signal, current_price):
                # Previous signal still valid → Skip duplicate
                self.stats['signals_skipped_duplicate'] += 1
                return False, f"Duplicate {action} signal (price still in range: {last_signal.get('stop_loss'):.2f} - {last_signal.get('target'):.2f})"
            else:
                # Previous signal invalidated → Generate new signal
                self.stats['signals_previous_invalidated'] += 1
                return True, f"Previous {action} signal invalidated (target/SL reached)"
        
        except Exception as e:
            logger.error(f"Error in signal deduplication check: {e}")
            # On error, allow signal to be safe
            return True, f"Deduplication check failed: {e}"
    
    async def emit_signal(
        self,
        symbol: str,
        strategy: str,
        action: str,
        entry_price: float,
        stop_loss: float,
        target: float,
        signal_strength: float = 5.0,
        expected_move_pct: float = 0.0,
        timeframe: str = "5min",
        metadata: Optional[Dict] = None
    ) -> Optional[Signal]:
        """
        Create and emit a signal event with deduplication.
        
        This is the main entry point for strategies to generate signals.
        Implements deduplication logic to prevent redundant signals.
        
        Args:
            symbol: Trading symbol
            strategy: Strategy name
            action: 'BUY' or 'SELL'
            entry_price: Entry price
            stop_loss: Stop-loss price
            target: Target price
            signal_strength: Signal strength (0-10)
            expected_move_pct: Expected price move percentage
            timeframe: Timeframe
            metadata: Additional metadata
            
        Returns:
            Created signal object if generated, None if skipped
        """
        # Check if signal should be generated (deduplication)
        should_generate, reason = await self.should_generate_signal(
            symbol=symbol,
            strategy=strategy,
            action=action,
            current_price=entry_price
        )
        
        if not should_generate:
            logger.info(
                f"🚫 Signal skipped for {symbol} ({strategy}): {reason} "
                f"[Price: {entry_price:.2f}]"
            )
            return None
        
        # Log why signal is being generated
        logger.info(
            f"✅ Signal approved for {symbol} ({strategy}): {reason} "
            f"[Action: {action}, Price: {entry_price:.2f}]"
        )
        
        with self.lock:
            # Create signal
            signal = Signal(
                symbol=symbol,
                strategy=strategy,
                signal_type=action,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target=target,
                signal_strength=signal_strength,
                expected_move_pct=expected_move_pct,
                timeframe=timeframe,
                metadata=metadata
            )
            
            # Store signal
            self.active_signals[signal.id] = signal
            
            # Save to persistence
            await self.save_signal(signal)
            
            # Update stats
            self.stats['signals_generated'] += 1
            
            logger.info(
                f"Signal created: {signal.id[:8]} - {action} {symbol} @ {entry_price} "
                f"(SL: {stop_loss}, Target: {target}, Strength: {signal_strength})"
            )
        
        # Emit signal generated event
        await self.event_bus.publish(
            event_type=EventType.SIGNAL_GENERATED,
            data={
                "signal_id": signal.id,
                "symbol": symbol,
                "strategy": strategy,
                "action": action,
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "target": target,
                "signal_strength": signal_strength,
                "expected_move_pct": expected_move_pct,
                "timeframe": timeframe,
                "metadata": metadata or {},
            },
            source=f"strategy.{strategy}"
        )
        
        logger.info(f"✅ Signal event emitted: {signal.id[:8]}")
        
        return signal
    
    async def save_signal(self, signal: Signal):
        """Save a single signal to data layer or file"""
        try:
            # Try saving to data layer first
            if self.data_layer:
                try:
                    success = await self.data_layer.store_signal(signal.to_dict())
                    if success:
                        logger.debug(f"Saved signal {signal.id} to data layer")
                        return
                except Exception as e:
                    logger.warning(f"Failed to save signal to data layer: {e}")
            
            # Fallback to file-based saving
            self.save_signals()
            
        except Exception as e:
            logger.error(f"Error saving signal: {e}")
    
    def save_signals(self):
        """Save signals to file (fallback method)"""
        try:
            # Get all signals
            all_signals = []
            
            # Load existing signals from file
            if os.path.exists(self.signals_file):
                with open(self.signals_file, "r") as f:
                    all_signals = json.load(f)
            
            # Update with current active signals
            active_signal_ids = set(self.active_signals.keys())
            all_signals = [s for s in all_signals if s["id"] not in active_signal_ids]
            all_signals.extend([s.to_dict() for s in self.active_signals.values()])
            
            with open(self.signals_file, "w") as f:
                json.dump(all_signals, f, indent=2)
            
            logger.debug(f"Saved {len(all_signals)} signals to file")
        except Exception as e:
            logger.error(f"Error saving signals to file: {e}")
    
    async def _on_signal_activated(self, event):
        """Handle signal activated event"""
        signal_id = event.data["signal_id"]
        order_id = event.data["order_id"]
        
        if signal_id in self.active_signals:
            signal = self.active_signals[signal_id]
            signal.status = "ACTIVE"
            signal.order_id = order_id
            await self.save_signal(signal)
            logger.info(f"Signal {signal_id[:8]} activated with order {order_id}")
    
    async def _on_signal_completed(self, event):
        """Handle signal completed event"""
        signal_id = event.data["signal_id"]
        
        if signal_id in self.active_signals:
            signal = self.active_signals[signal_id]
            signal.status = "COMPLETED"
            signal.exit_price = event.data["exit_price"]
            signal.profit_loss = event.data["profit_loss"]
            signal.exit_reason = event.data["exit_reason"]
            signal.exit_timestamp = get_current_time().isoformat()
            
            await self.save_signal(signal)
            
            # Move to completed
            del self.active_signals[signal_id]
            
            logger.info(
                f"Signal {signal_id[:8]} completed - "
                f"P&L: ₹{signal.profit_loss:.2f} ({event.data['profit_loss_pct']:.2f}%)"
            )
    
    async def _on_signal_stopped(self, event):
        """Handle signal stopped event"""
        signal_id = event.data["signal_id"]
        
        if signal_id in self.active_signals:
            signal = self.active_signals[signal_id]
            signal.status = "STOPPED"
            signal.exit_price = event.data["exit_price"]
            signal.profit_loss = event.data["profit_loss"]
            signal.exit_reason = event.data["exit_reason"]
            signal.exit_timestamp = get_current_time().isoformat()
            
            await self.save_signal(signal)
            
            # Move to stopped
            del self.active_signals[signal_id]
            
            logger.info(
                f"Signal {signal_id[:8]} stopped - "
                f"P&L: ₹{signal.profit_loss:.2f} ({event.data['profit_loss_pct']:.2f}%)"
            )
    
    def get_active_signals_list(self) -> List[Signal]:
        """Get list of active signals"""
        return list(self.active_signals.values())
    
    def get_signal(self, signal_id: str) -> Optional[Signal]:
        """Get signal by ID"""
        return self.active_signals.get(signal_id)
    
    def get_stats(self) -> Dict:
        """Get signal manager statistics including deduplication metrics"""
        return {
            "active_signals": len(self.active_signals),
            "signals_by_symbol": {},
            "signals_by_strategy": {},
            "deduplication": {
                "signals_generated": self.stats['signals_generated'],
                "signals_skipped_duplicate": self.stats['signals_skipped_duplicate'],
                "signals_reversal": self.stats['signals_reversal'],
                "signals_previous_invalidated": self.stats['signals_previous_invalidated'],
                "skip_rate_pct": (
                    (self.stats['signals_skipped_duplicate'] / 
                     (self.stats['signals_generated'] + self.stats['signals_skipped_duplicate']) * 100)
                    if (self.stats['signals_generated'] + self.stats['signals_skipped_duplicate']) > 0
                    else 0.0
                )
            }
        }
