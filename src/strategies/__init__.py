"""
Strategies package - Trading strategy implementations for AlphaStocks.

Available strategies:
- MovingAverageCrossoverStrategy: Golden/Death cross trend following
- EMA5AlertCandleStrategy: Subhashish Pani's alert candle intraday strategy
"""

from .ma_crossover_strategy import MovingAverageCrossoverStrategy
from .ema_5_alert_candle_strategy import EMA5AlertCandleStrategy

__all__ = [
    'MovingAverageCrossoverStrategy',
    'EMA5AlertCandleStrategy'
]