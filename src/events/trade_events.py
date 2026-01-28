"""
Trade and position-related events for the trading system.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from .event_bus import Event, EventType, EventPriority


@dataclass
class TradeExecutedEvent(Event):
    """Event emitted when a trade is executed"""
    
    def __init__(
        self,
        trade_id: str,
        signal_id: str,
        symbol: str,
        option_symbol: str,
        strike: float,
        option_type: str,  # 'CE' or 'PE'
        action: str,  # 'BUY' or 'SELL'
        quantity: int,
        entry_price: float,
        order_id: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize trade executed event.
        
        Args:
            trade_id: Unique trade identifier
            signal_id: ID of the signal that triggered this trade
            symbol: Underlying symbol
            option_symbol: Full option symbol
            strike: Strike price
            option_type: 'CE' or 'PE'
            action: 'BUY' or 'SELL'
            quantity: Number of contracts
            entry_price: Entry premium price
            order_id: Exchange order ID
            source: Source component
            metadata: Additional data
        """
        data = {
            "trade_id": trade_id,
            "signal_id": signal_id,
            "symbol": symbol,
            "option_symbol": option_symbol,
            "strike": strike,
            "option_type": option_type,
            "action": action,
            "quantity": quantity,
            "entry_price": entry_price,
            "order_id": order_id,
            "metadata": metadata or {},
        }
        
        super().__init__(
            event_type=EventType.TRADE_EXECUTED,
            data=data,
            source=source,
            priority=EventPriority.HIGH
        )


@dataclass
class TradeExitEvent(Event):
    """Event emitted when a trade is exited"""
    
    def __init__(
        self,
        trade_id: str,
        exit_price: float,
        exit_reason: str,
        profit_loss: float,
        profit_loss_pct: float,
        order_id: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        data = {
            "trade_id": trade_id,
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "profit_loss": profit_loss,
            "profit_loss_pct": profit_loss_pct,
            "order_id": order_id,
            "metadata": metadata or {},
        }
        
        super().__init__(
            event_type=EventType.TRADE_EXIT,
            data=data,
            source=source,
            priority=EventPriority.HIGH
        )


@dataclass
class PositionOpenedEvent(Event):
    """Event emitted when a position is opened"""
    
    def __init__(
        self,
        position_id: str,
        signal_id: str,
        symbol: str,
        option_symbol: str,
        strike: float,
        option_type: str,
        quantity: int,
        entry_premium: float,
        stop_loss_premium: float,
        target_premium: float,
        source: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize position opened event.
        
        Args:
            position_id: Unique position identifier
            signal_id: ID of the signal that triggered this position
            symbol: Underlying symbol
            option_symbol: Full option symbol
            strike: Strike price
            option_type: 'CE' or 'PE'
            quantity: Number of contracts
            entry_premium: Entry premium price
            stop_loss_premium: Stop-loss premium
            target_premium: Target premium
            source: Source component
            metadata: Additional data
        """
        data = {
            "position_id": position_id,
            "signal_id": signal_id,
            "symbol": symbol,
            "option_symbol": option_symbol,
            "strike": strike,
            "option_type": option_type,
            "quantity": quantity,
            "entry_premium": entry_premium,
            "stop_loss_premium": stop_loss_premium,
            "target_premium": target_premium,
            "metadata": metadata or {},
        }
        
        super().__init__(
            event_type=EventType.POSITION_OPENED,
            data=data,
            source=source,
            priority=EventPriority.HIGH
        )


@dataclass
class PositionUpdatedEvent(Event):
    """Event emitted when a position is updated"""
    
    def __init__(
        self,
        position_id: str,
        current_premium: float,
        unrealized_pnl: float,
        unrealized_pnl_pct: float,
        updates: Dict[str, Any],
        source: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        data = {
            "position_id": position_id,
            "current_premium": current_premium,
            "unrealized_pnl": unrealized_pnl,
            "unrealized_pnl_pct": unrealized_pnl_pct,
            "updates": updates,
            "metadata": metadata or {},
        }
        
        super().__init__(
            event_type=EventType.POSITION_UPDATED,
            data=data,
            source=source,
            priority=EventPriority.NORMAL
        )


@dataclass
class PositionClosedEvent(Event):
    """Event emitted when a position is closed"""
    
    def __init__(
        self,
        position_id: str,
        exit_premium: float,
        exit_reason: str,
        realized_pnl: float,
        realized_pnl_pct: float,
        holding_duration_seconds: float,
        source: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        data = {
            "position_id": position_id,
            "exit_premium": exit_premium,
            "exit_reason": exit_reason,
            "realized_pnl": realized_pnl,
            "realized_pnl_pct": realized_pnl_pct,
            "holding_duration_seconds": holding_duration_seconds,
            "metadata": metadata or {},
        }
        
        super().__init__(
            event_type=EventType.POSITION_CLOSED,
            data=data,
            source=source,
            priority=EventPriority.HIGH
        )


@dataclass
class OrderPlacedEvent(Event):
    """Event emitted when an order is placed"""
    
    def __init__(
        self,
        order_id: str,
        symbol: str,
        action: str,
        quantity: int,
        order_type: str,
        price: Optional[float],
        source: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        data = {
            "order_id": order_id,
            "symbol": symbol,
            "action": action,
            "quantity": quantity,
            "order_type": order_type,
            "price": price,
            "metadata": metadata or {},
        }
        
        super().__init__(
            event_type=EventType.ORDER_PLACED,
            data=data,
            source=source,
            priority=EventPriority.HIGH
        )


@dataclass
class OrderFilledEvent(Event):
    """Event emitted when an order is filled"""
    
    def __init__(
        self,
        order_id: str,
        filled_quantity: int,
        filled_price: float,
        source: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        data = {
            "order_id": order_id,
            "filled_quantity": filled_quantity,
            "filled_price": filled_price,
            "metadata": metadata or {},
        }
        
        super().__init__(
            event_type=EventType.ORDER_FILLED,
            data=data,
            source=source,
            priority=EventPriority.HIGH
        )
