"""
Candle Aggregator - Converts real-time tick data into OHLCV candles

This module aggregates incoming tick data (e.g., 5-second updates) into proper
OHLCV candles matching the strategy's configured timeframe (e.g., 15-minute candles).

Key Features:
- Automatic candle period detection based on timeframe
- Proper OHLC calculation from tick data
- Volume aggregation
- Thread-safe operations
- Completed candle notifications
- Market hours validation (stops at 3:30 PM IST)
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from collections import defaultdict
import threading
from ..utils.logger_setup import setup_logger
from ..utils.market_hours import is_market_open
from ..utils.timezone_utils import get_current_time, to_ist, to_utc, is_market_hours

logger = setup_logger("candle_aggregator")


class CandleAggregator:
    """
    Aggregates real-time tick data into OHLCV candles for specified timeframe.
    
    Usage:
        aggregator = CandleAggregator(timeframe='15minute')
        aggregator.add_tick('SBIN', tick_data)
        candles = aggregator.get_candles('SBIN', count=100)
    """
    
    def __init__(self, timeframe: str = '15minute'):
        """
        Initialize candle aggregator.
        
        Args:
            timeframe: Candle timeframe ('1minute', '5minute', '15minute', '60minute', 'day')
        """
        self.timeframe = timeframe
        self.timeframe_minutes = self._parse_timeframe(timeframe)
        
        # Current building candles per symbol
        self.current_candles: Dict[str, Dict] = {}
        
        # Completed candles per symbol (circular buffer)
        self.completed_candles: Dict[str, List[Dict]] = defaultdict(list)
        self.max_completed_candles = 2000  # Keep last 2000 completed candles
        
        # Callbacks for completed candles
        self.candle_completion_callbacks: List[Callable] = []
        
        # Thread safety
        self.lock = threading.Lock()
        
        logger.info(f"CandleAggregator initialized for {timeframe} timeframe ({self.timeframe_minutes} minutes)")
    
    def _parse_timeframe(self, timeframe: str) -> int:
        """
        Parse timeframe string to minutes.
        
        Args:
            timeframe: Timeframe string
            
        Returns:
            Number of minutes in timeframe
        """
        timeframe = timeframe.lower()
        
        if 'minute' in timeframe:
            return int(timeframe.replace('minute', ''))
        elif 'hour' in timeframe:
            return int(timeframe.replace('hour', '')) * 60
        elif timeframe == 'day':
            return 24 * 60
        else:
            logger.warning(f"Unknown timeframe '{timeframe}', defaulting to 15 minutes")
            return 15
    
    def _get_candle_start_time(self, timestamp: datetime) -> datetime:
        """
        Get the start time of the candle that contains this timestamp.
        
        Args:
            timestamp: Current timestamp
            
        Returns:
            Start time of the candle period
        """
        if self.timeframe_minutes >= 1440:  # Daily or larger
            return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        elif self.timeframe_minutes >= 60:  # Hourly
            hour_offset = (timestamp.hour // (self.timeframe_minutes // 60)) * (self.timeframe_minutes // 60)
            return timestamp.replace(hour=hour_offset, minute=0, second=0, microsecond=0)
        else:  # Minutes
            minute_offset = (timestamp.minute // self.timeframe_minutes) * self.timeframe_minutes
            return timestamp.replace(minute=minute_offset, second=0, microsecond=0)
    
    def _init_candle(self, start_time: datetime, tick_data: Dict) -> Dict:
        """
        Initialize a new candle with first tick data.
        
        Args:
            start_time: Candle start time
            tick_data: First tick data for this candle
            
        Returns:
            Initialized candle dictionary
        """
        price = tick_data.get('ltp', tick_data.get('close', tick_data.get('last_price', 0)))
        
        return {
            'timestamp': start_time,
            'start_time': start_time,
            'end_time': start_time + timedelta(minutes=self.timeframe_minutes),
            'open': price,
            'high': price,
            'low': price,
            'close': price,
            'volume': tick_data.get('volume', 0),
            'turnover': tick_data.get('turnover', 0),
            'tick_count': 1,
            'symbol': tick_data.get('symbol', ''),
            'asset_type': tick_data.get('asset_type', 'EQUITY')
        }
    
    def _update_candle(self, candle: Dict, tick_data: Dict) -> None:
        """
        Update existing candle with new tick data.
        
        Args:
            candle: Candle dictionary to update
            tick_data: New tick data
        """
        price = tick_data.get('ltp', tick_data.get('close', tick_data.get('last_price', 0)))
        
        # Update OHLC
        candle['high'] = max(candle['high'], price)
        candle['low'] = min(candle['low'], price)
        candle['close'] = price  # Last price becomes close
        
        # Update volume (accumulate)
        candle['volume'] += tick_data.get('volume', 0)
        candle['turnover'] += tick_data.get('turnover', 0)
        candle['tick_count'] += 1
    
    def add_tick(self, symbol: str, tick_data: Dict) -> Optional[Dict]:
        """
        Add a tick and aggregate into candles.
        
        Args:
            symbol: Trading symbol
            tick_data: Tick data dictionary with keys: timestamp, ltp/close, volume, etc.
            
        Returns:
            Completed candle if a new candle period started, None otherwise
        """
        with self.lock:
            try:
                # Check if market is open - reject ticks after market close (3:30 PM IST)
                if not is_market_open():
                    logger.debug(f"Market is closed, rejecting tick for {symbol} to prevent data corruption")
                    return None
                
                timestamp = tick_data.get('timestamp', get_current_time())
                if isinstance(timestamp, str):
                    timestamp = pd.to_datetime(timestamp)
                
                candle_start = self._get_candle_start_time(timestamp)
                
                completed_candle = None
                
                # Check if we have a current candle for this symbol
                if symbol not in self.current_candles:
                    # First tick for this symbol - initialize candle
                    self.current_candles[symbol] = self._init_candle(candle_start, tick_data)
                    logger.debug(f"Started new candle for {symbol} at {candle_start}")
                else:
                    current_candle = self.current_candles[symbol]
                    
                    # Check if tick belongs to current candle period
                    if current_candle['start_time'] == candle_start:
                        # Same period - update existing candle
                        self._update_candle(current_candle, tick_data)
                    else:
                        # New period - complete old candle and start new one
                        completed_candle = current_candle.copy()
                        self._store_completed_candle(symbol, completed_candle)
                        
                        # Start new candle
                        self.current_candles[symbol] = self._init_candle(candle_start, tick_data)
                        
                        logger.debug(f"Completed {self.timeframe} candle for {symbol}: "
                                   f"O={completed_candle['open']:.2f} H={completed_candle['high']:.2f} "
                                   f"L={completed_candle['low']:.2f} C={completed_candle['close']:.2f} "
                                   f"V={completed_candle['volume']}")
                        
                        # Notify callbacks
                        self._notify_candle_completion(symbol, completed_candle)
                
                return completed_candle
                
            except Exception as e:
                logger.error(f"Error adding tick for {symbol}: {e}")
                return None
    
    def _store_completed_candle(self, symbol: str, candle: Dict) -> None:
        """
        Store completed candle in history (circular buffer).
        
        Args:
            symbol: Trading symbol
            candle: Completed candle dictionary
        """
        self.completed_candles[symbol].append(candle)
        
        # Maintain max size (circular buffer)
        if len(self.completed_candles[symbol]) > self.max_completed_candles:
            self.completed_candles[symbol] = self.completed_candles[symbol][-self.max_completed_candles:]
    
    def get_candles(self, symbol: str, count: Optional[int] = None, 
                   include_incomplete: bool = False) -> pd.DataFrame:
        """
        Get completed candles for a symbol.
        
        Args:
            symbol: Trading symbol
            count: Number of recent candles to return (None = all)
            include_incomplete: Include currently building candle
            
        Returns:
            DataFrame with OHLCV candles
        """
        with self.lock:
            candles = self.completed_candles.get(symbol, []).copy()
            
            # Add current incomplete candle if requested
            if include_incomplete and symbol in self.current_candles:
                candles.append(self.current_candles[symbol].copy())
            
            if not candles:
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(candles)
            
            # Limit count if specified
            if count is not None and len(df) > count:
                df = df.tail(count)
            
            return df
    
    def get_current_candle(self, symbol: str) -> Optional[Dict]:
        """
        Get the currently building candle for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Current candle dictionary or None
        """
        with self.lock:
            return self.current_candles.get(symbol, None)
    
    def register_candle_completion_callback(self, callback: Callable) -> None:
        """
        Register a callback to be called when a candle is completed.
        
        Args:
            callback: Function(symbol, candle_dict) to call
        """
        self.candle_completion_callbacks.append(callback)
        logger.debug(f"Registered candle completion callback: {callback.__name__}")
    
    def _notify_candle_completion(self, symbol: str, candle: Dict) -> None:
        """
        Notify all registered callbacks of candle completion.
        
        Args:
            symbol: Trading symbol
            candle: Completed candle dictionary
        """
        for callback in self.candle_completion_callbacks:
            try:
                callback(symbol, candle)
            except Exception as e:
                logger.error(f"Error in candle completion callback: {e}")
    
    def get_statistics(self) -> Dict:
        """
        Get aggregator statistics.
        
        Returns:
            Statistics dictionary
        """
        with self.lock:
            return {
                'timeframe': self.timeframe,
                'timeframe_minutes': self.timeframe_minutes,
                'active_symbols': len(self.current_candles),
                'total_completed_candles': sum(len(candles) for candles in self.completed_candles.values()),
                'symbols_tracked': list(self.completed_candles.keys())
            }
    
    def clear_symbol(self, symbol: str) -> None:
        """
        Clear all data for a symbol.
        
        Args:
            symbol: Trading symbol to clear
        """
        with self.lock:
            if symbol in self.current_candles:
                del self.current_candles[symbol]
            if symbol in self.completed_candles:
                del self.completed_candles[symbol]
            logger.info(f"Cleared aggregator data for {symbol}")
