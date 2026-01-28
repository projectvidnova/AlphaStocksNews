import os
import json
import logging
import pandas as pd
from datetime import datetime
import threading
import uuid
from typing import Optional

from ..data import DataLayerInterface
from ..utils.logger_setup import setup_logger
from ..utils.timezone_utils import get_current_time, to_ist, to_utc, is_market_hours

logger = setup_logger("signal_manager")

class Signal:
    """
    Represents a trading signal with entry, stop-loss, and target prices
    """
    
    def __init__(self, symbol, strategy, signal_type, entry_price, stop_loss, target, timestamp=None, metadata=None):
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
        self.metadata = metadata or {}  # Dictionary for strategy-specific data
        self.exit_reason = None  # "STOP_LOSS", "TARGET", "MANUAL", etc.
    
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
            "exit_reason": self.exit_reason
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
            timestamp=data["timestamp"],
            metadata=data.get("metadata", {})
        )
        signal.id = data["id"]
        signal.status = data["status"]
        signal.order_id = data["order_id"]
        signal.exit_price = data["exit_price"]
        signal.exit_timestamp = data["exit_timestamp"]
        signal.profit_loss = data["profit_loss"]
        signal.exit_reason = data.get("exit_reason")
        return signal

class SignalManager:
    """
    Manages trading signals from all strategies with persistent storage.
    """
    
    def __init__(self, config, api_client=None, data_layer: Optional[DataLayerInterface] = None):
        """Initialize with configuration and optional data layer."""
        self.config = config
        self.api_client = api_client
        self.data_layer = data_layer
        self.signals_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "signals")
        self.signals_file = os.path.join(self.signals_dir, "signals.json")
        self.active_signals = {}  # id -> Signal
        self.lock = threading.Lock()
        
        # Ensure signals directory exists (fallback for file-based storage)
        os.makedirs(self.signals_dir, exist_ok=True)
        
        # Load existing signals
        # Note: load_signals is now async, but __init__ is sync
        # We'll load signals during first use or via explicit call
    
    async def initialize(self):
        """Initialize the signal manager and load existing signals."""
        await self.load_signals()
    
    async def load_signals(self):
        """Load signals from data layer or file fallback."""
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
    
    async def save_signal(self, signal: 'Signal'):
        """Save a single signal to data layer or file."""
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
        """Save signals to file (fallback method)."""
        try:
            # Get all signals (active and completed)
            all_signals = []
            
            # First load existing signals from file
            if os.path.exists(self.signals_file):
                with open(self.signals_file, "r") as f:
                    all_signals = json.load(f)
            
            # Update with current active signals
            active_signal_ids = set(self.active_signals.keys())
            all_signals = [s for s in all_signals if s["id"] not in active_signal_ids]
            all_signals.extend([s.to_dict() for s in self.active_signals.values()])
            
            with open(self.signals_file, "w") as f:
                json.dump(all_signals, f, indent=2)
            
            logger.info(f"Saved {len(all_signals)} signals to file")
        except Exception as e:
            logger.error(f"Error saving signals to file: {e}")
    
    async def add_signal(self, symbol, strategy, signal_type, entry_price, stop_loss_pct=None, target_pct=None):
        """
        Add a new signal with calculated stop-loss and target
        
        Args:
            symbol: Stock symbol
            strategy: Strategy name
            signal_type: 'BUY' or 'SELL'
            entry_price: Entry price
            stop_loss_pct: Stop-loss percentage (optional)
            target_pct: Target percentage (optional)
        """
        with self.lock:
            # Calculate stop-loss and target if not provided
            if stop_loss_pct is None:
                stop_loss_pct = self.config.get("trading", {}).get("default_stop_loss_pct", 2.0)
            
            if target_pct is None:
                target_pct = self.config.get("trading", {}).get("default_target_pct", 4.0)
            
            # Calculate stop-loss and target prices
            if signal_type == "BUY":
                stop_loss = entry_price * (1 - stop_loss_pct / 100)
                target = entry_price * (1 + target_pct / 100)
            else:  # SELL
                stop_loss = entry_price * (1 + stop_loss_pct / 100)
                target = entry_price * (1 - target_pct / 100)
            
            # Create signal
            signal = Signal(
                symbol=symbol,
                strategy=strategy,
                signal_type=signal_type,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target=target
            )
            
            # Add to active signals
            self.active_signals[signal.id] = signal
            
            # Save signal (async if using data layer, sync for file fallback)
            try:
                await self.save_signal(signal)
            except Exception as e:
                logger.error(f"Failed to save signal: {e}")
                # Fallback to sync file save
                self.save_signals()
            
            logger.info(f"Added new {signal_type} signal for {symbol} from {strategy} strategy")
            logger.info(f"Entry: {entry_price}, Stop-loss: {stop_loss}, Target: {target}")
            
            return signal
    
    async def add_signal_from_strategy(self, strategy_name: str, symbol: str, 
                                       strategy_signal) -> 'Signal':
        """
        Add signal from strategy output (adapter method).
        
        Args:
            strategy_name: Strategy name
            symbol: Trading symbol
            strategy_signal: StrategySignal object from strategy.analyze()
        
        Returns:
            Created Signal object
        """
        # Extract data from strategy signal
        signal_type = strategy_signal.action  # "BUY" or "SELL"
        entry_price = strategy_signal.price
        
        # Extract or calculate stop-loss and target percentages
        if hasattr(strategy_signal, 'stop_loss') and strategy_signal.stop_loss:
            stop_loss = strategy_signal.stop_loss
            stop_loss_pct = abs((stop_loss - entry_price) / entry_price * 100)
        else:
            stop_loss_pct = None
        
        if hasattr(strategy_signal, 'target') and strategy_signal.target:
            target = strategy_signal.target
            target_pct = abs((target - entry_price) / entry_price * 100)
        else:
            target_pct = None
        
        # Call existing add_signal method with correct parameters
        signal = await self.add_signal(
            symbol=symbol,
            strategy=strategy_name,
            signal_type=signal_type,
            entry_price=entry_price,
            stop_loss_pct=stop_loss_pct,
            target_pct=target_pct
        )
        
        # Add extra metadata
        if hasattr(strategy_signal, 'metadata') and strategy_signal.metadata:
            signal.metadata.update(strategy_signal.metadata)
        
        if hasattr(strategy_signal, 'confidence'):
            signal.metadata['confidence'] = strategy_signal.confidence
        
        # Also store to database directly
        if self.data_layer:
            try:
                signal_data = {
                    "timestamp": get_current_time(),
                    "signal_id": signal.id,
                    "symbol": symbol,
                    "asset_type": "EQUITY",
                    "strategy": strategy_name,
                    "action": signal_type,
                    "price": entry_price,
                    "quantity": 0,
                    "confidence": getattr(strategy_signal, 'confidence', 0.0),
                    "target": signal.target,
                    "stop_loss": signal.stop_loss,
                    "metadata": str(signal.metadata)
                }
                
                success = await self.data_layer.store_signal(signal_data)
                if success:
                    logger.debug(f"Signal {signal.id} stored to database")
                
            except Exception as e:
                logger.error(f"Failed to store signal to database: {e}")
        
        logger.info(f"Signal {signal.id} created for {symbol} via {strategy_name}")
        
        return signal
    
    def get_active_signals_list(self) -> list:
        """Get active signals as list of dictionaries (for options executor)."""
        with self.lock:
            return [signal.to_dict() for signal in self.active_signals.values()]
    
    async def update_signal(self, signal_id, **kwargs):
        """Update signal properties"""
        with self.lock:
            if signal_id in self.active_signals:
                signal = self.active_signals[signal_id]
                
                for key, value in kwargs.items():
                    if hasattr(signal, key):
                        setattr(signal, key, value)
                
                # Save signals
                self.save_signals()
                
                logger.info(f"Updated signal {signal_id} with {kwargs}")
                return signal
            else:
                logger.warning(f"Signal {signal_id} not found")
                return None
    
    def complete_signal(self, signal_id, exit_price, exit_timestamp=None):
        """Mark a signal as completed"""
        with self.lock:
            if signal_id in self.active_signals:
                signal = self.active_signals[signal_id]
                signal.status = "COMPLETED"
                signal.exit_price = exit_price
                signal.exit_timestamp = exit_timestamp or get_current_time().isoformat()
                
                # Calculate profit/loss
                if signal.signal_type == "BUY":
                    signal.profit_loss = (exit_price - signal.entry_price) / signal.entry_price * 100
                else:  # SELL
                    signal.profit_loss = (signal.entry_price - exit_price) / signal.entry_price * 100
                
                # Save signals
                self.save_signals()
                
                logger.info(f"Completed signal {signal_id} with exit price {exit_price}")
                logger.info(f"Profit/Loss: {signal.profit_loss:.2f}%")
                
                # Remove from active signals
                del self.active_signals[signal_id]
                
                return signal
            else:
                logger.warning(f"Signal {signal_id} not found")
                return None
    
    def get_active_signals(self):
        """Get all active signals"""
        with self.lock:
            return list(self.active_signals.values())
    
    def get_signal(self, signal_id):
        """Get a specific signal by ID"""
        with self.lock:
            return self.active_signals.get(signal_id)