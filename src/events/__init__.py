"""
Event-driven architecture for AlphaStocks trading system.
"""

from .event_bus import EventBus, Event, EventType, EventPriority, get_event_bus, set_event_bus
from .signal_events import (
    SignalGeneratedEvent,
    SignalActivatedEvent,
    SignalCompletedEvent,
    SignalStoppedEvent
)
from .trade_events import (
    TradeExecutedEvent,
    TradeExitEvent,
    PositionOpenedEvent,
    PositionClosedEvent
)

__all__ = [
    'EventBus',
    'Event',
    'EventType',
    'EventPriority',
    'get_event_bus',
    'set_event_bus',
    'SignalGeneratedEvent',
    'SignalActivatedEvent',
    'SignalCompletedEvent',
    'SignalStoppedEvent',
    'TradeExecutedEvent',
    'TradeExitEvent',
    'PositionOpenedEvent',
    'PositionClosedEvent',
]
