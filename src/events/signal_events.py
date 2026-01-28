"""
Signal-related events for the trading system.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from .event_bus import Event, EventType, EventPriority


@dataclass
class SignalGeneratedEvent(Event):
    """
    Event emitted when a strategy generates a new trading signal.
    
    This is the primary event that triggers options trading workflow.
    """
    
    def __init__(
        self,
        signal_id: str,
        symbol: str,
        strategy: str,
        action: str,  # 'BUY' or 'SELL'
        entry_price: float,
        stop_loss: float,
        target: float,
        signal_strength: float,
        expected_move_pct: float,
        timeframe: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None,
        priority: EventPriority = EventPriority.HIGH
    ):
        """
        Initialize signal generated event.
        
        Args:
            signal_id: Unique signal identifier
            symbol: Trading symbol (e.g., 'NIFTY', 'BANKNIFTY')
            strategy: Strategy name that generated the signal
            action: 'BUY' or 'SELL'
            entry_price: Entry price for the underlying
            stop_loss: Stop-loss price
            target: Target price
            signal_strength: Signal strength (0-10)
            expected_move_pct: Expected price move percentage
            timeframe: Timeframe (e.g., '5min', '15min')
            source: Source of the signal (strategy instance)
            metadata: Additional strategy-specific data
            priority: Event priority
        """
        data = {
            "signal_id": signal_id,
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
        }
        
        super().__init__(
            event_type=EventType.SIGNAL_GENERATED,
            data=data,
            source=source,
            priority=priority
        )
    
    @property
    def signal_id(self) -> str:
        return self.data["signal_id"]
    
    @property
    def symbol(self) -> str:
        return self.data["symbol"]
    
    @property
    def strategy(self) -> str:
        return self.data["strategy"]
    
    @property
    def action(self) -> str:
        return self.data["action"]
    
    @property
    def entry_price(self) -> float:
        return self.data["entry_price"]
    
    @property
    def stop_loss(self) -> float:
        return self.data["stop_loss"]
    
    @property
    def target(self) -> float:
        return self.data["target"]
    
    @property
    def signal_strength(self) -> float:
        return self.data["signal_strength"]
    
    @property
    def expected_move_pct(self) -> float:
        return self.data["expected_move_pct"]
    
    @property
    def timeframe(self) -> str:
        return self.data["timeframe"]
    
    @property
    def metadata(self) -> Dict[str, Any]:
        return self.data["metadata"]


@dataclass
class SignalActivatedEvent(Event):
    """Event emitted when a signal is activated (order placed)"""
    
    def __init__(
        self,
        signal_id: str,
        order_id: str,
        symbol: str,
        action: str,
        price: float,
        quantity: int,
        source: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        data = {
            "signal_id": signal_id,
            "order_id": order_id,
            "symbol": symbol,
            "action": action,
            "price": price,
            "quantity": quantity,
            "metadata": metadata or {},
        }
        
        super().__init__(
            event_type=EventType.SIGNAL_ACTIVATED,
            data=data,
            source=source,
            priority=EventPriority.HIGH
        )


@dataclass
class SignalUpdatedEvent(Event):
    """Event emitted when a signal is updated"""
    
    def __init__(
        self,
        signal_id: str,
        updates: Dict[str, Any],
        source: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        data = {
            "signal_id": signal_id,
            "updates": updates,
            "metadata": metadata or {},
        }
        
        super().__init__(
            event_type=EventType.SIGNAL_UPDATED,
            data=data,
            source=source,
            priority=EventPriority.NORMAL
        )


@dataclass
class SignalCompletedEvent(Event):
    """Event emitted when a signal is completed (target hit)"""
    
    def __init__(
        self,
        signal_id: str,
        exit_price: float,
        profit_loss: float,
        profit_loss_pct: float,
        exit_reason: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        data = {
            "signal_id": signal_id,
            "exit_price": exit_price,
            "profit_loss": profit_loss,
            "profit_loss_pct": profit_loss_pct,
            "exit_reason": exit_reason,
            "metadata": metadata or {},
        }
        
        super().__init__(
            event_type=EventType.SIGNAL_COMPLETED,
            data=data,
            source=source,
            priority=EventPriority.HIGH
        )


@dataclass
class SignalStoppedEvent(Event):
    """Event emitted when a signal is stopped (stop-loss hit)"""
    
    def __init__(
        self,
        signal_id: str,
        exit_price: float,
        profit_loss: float,
        profit_loss_pct: float,
        exit_reason: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        data = {
            "signal_id": signal_id,
            "exit_price": exit_price,
            "profit_loss": profit_loss,
            "profit_loss_pct": profit_loss_pct,
            "exit_reason": exit_reason,
            "metadata": metadata or {},
        }
        
        super().__init__(
            event_type=EventType.SIGNAL_STOPPED,
            data=data,
            source=source,
            priority=EventPriority.HIGH
        )
