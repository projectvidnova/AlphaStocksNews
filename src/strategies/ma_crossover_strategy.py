"""
Moving Average Crossover Strategy Implementation

This strategy uses the intersection of short-term and long-term moving averages
to generate buy and sell signals (Golden Cross and Death Cross patterns).
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from ..core.base_strategy import BaseStrategy
from ..utils.logger_setup import setup_logger
from ..utils.timezone_utils import get_current_time, to_ist, to_utc, is_market_hours

logger = setup_logger("ma_crossover_strategy")


class MovingAverageCrossoverStrategy(BaseStrategy):
    """
    Moving Average Crossover Strategy Implementation.
    
    Uses EMA or SMA crossovers to identify trend changes:
    - Golden Cross: Fast MA crosses above Slow MA (Bullish)
    - Death Cross: Fast MA crosses below Slow MA (Bearish)
    """
    
    def _init_parameters(self):
        """Initialize strategy-specific parameters from config."""
        self.fast_period = self.strategy_config.get('fast_period', 9)
        self.slow_period = self.strategy_config.get('slow_period', 21)
        self.ma_type = self.strategy_config.get('ma_type', 'EMA')
        self.min_trend_strength = self.strategy_config.get('min_trend_strength', 0.5)
        self.volume_confirmation = self.strategy_config.get('volume_confirmation', True)
        self.target_pct = self.strategy_config.get('target_pct', 2.0)
        self.stop_loss_pct = self.strategy_config.get('stop_loss_pct', 1.0)
        
        # Validation
        if self.fast_period >= self.slow_period:
            raise ValueError(f"Fast period ({self.fast_period}) must be less than slow period ({self.slow_period})")
        
        if self.ma_type not in ['SMA', 'EMA']:
            raise ValueError(f"Invalid MA type: {self.ma_type}. Must be 'SMA' or 'EMA'")
        
        self.logger.info(f"MA Crossover Strategy initialized: {self.fast_period}/{self.slow_period} {self.ma_type}")
    
    def calculate_moving_averages(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate fast and slow moving averages.
        
        Args:
            data: DataFrame with OHLCV data
            
        Returns:
            DataFrame with added moving average columns
        """
        data = data.copy()
        
        try:
            if self.ma_type == 'EMA':
                data['fast_ma'] = data['close'].ewm(span=self.fast_period, adjust=False).mean()
                data['slow_ma'] = data['close'].ewm(span=self.slow_period, adjust=False).mean()
            else:  # SMA
                data['fast_ma'] = data['close'].rolling(window=self.fast_period).mean()
                data['slow_ma'] = data['close'].rolling(window=self.slow_period).mean()
            
            # Remove NaN values
            data.dropna(inplace=True)
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error calculating moving averages: {e}")
            raise
    
    def detect_crossovers(self, data: pd.DataFrame) -> Tuple[bool, bool]:
        """
        Detect golden cross and death cross patterns.
        
        Args:
            data: DataFrame with fast_ma and slow_ma columns
            
        Returns:
            Tuple of (golden_cross, death_cross) booleans
        """
        if len(data) < 2:
            return False, False
        
        try:
            # Current and previous MA values
            fast_current = data['fast_ma'].iloc[-1]
            fast_previous = data['fast_ma'].iloc[-2]
            slow_current = data['slow_ma'].iloc[-1]
            slow_previous = data['slow_ma'].iloc[-2]
            
            # Golden Cross (Bullish) - Fast MA crosses above Slow MA
            golden_cross = (fast_current > slow_current and 
                           fast_previous <= slow_previous)
            
            # Death Cross (Bearish) - Fast MA crosses below Slow MA
            death_cross = (fast_current < slow_current and 
                          fast_previous >= slow_previous)
            
            return golden_cross, death_cross
            
        except Exception as e:
            self.logger.error(f"Error detecting crossovers: {e}")
            return False, False
    
    def calculate_trend_strength(self, data: pd.DataFrame) -> float:
        """
        Measure trend strength using MA separation and price momentum.
        
        Args:
            data: DataFrame with MA and price data
            
        Returns:
            Trend strength score (0-1)
        """
        try:
            fast_ma = data['fast_ma'].iloc[-1]
            slow_ma = data['slow_ma'].iloc[-1]
            current_price = data['close'].iloc[-1]
            
            # MA separation as percentage of current price
            ma_separation = abs(fast_ma - slow_ma) / current_price
            
            # Price momentum over last 5 periods
            price_momentum = abs(data['close'].pct_change(periods=5).iloc[-1])
            
            # Volume momentum (if volume confirmation enabled)
            volume_momentum = 0
            if self.volume_confirmation and 'volume' in data.columns:
                current_vol = data['volume'].iloc[-1]
                avg_vol = data['volume'].rolling(window=10).mean().iloc[-1]
                volume_momentum = min(1.0, current_vol / avg_vol - 1) if avg_vol > 0 else 0
            
            # Combine factors (weighted average)
            trend_strength = (ma_separation * 0.4 + 
                            price_momentum * 0.4 + 
                            volume_momentum * 0.2)
            
            return min(1.0, trend_strength)
            
        except Exception as e:
            self.logger.error(f"Error calculating trend strength: {e}")
            return 0.0
    
    def check_volume_confirmation(self, data: pd.DataFrame) -> bool:
        """
        Confirm signal with volume analysis.
        
        Args:
            data: DataFrame with volume data
            
        Returns:
            True if volume confirms the signal
        """
        if not self.volume_confirmation or 'volume' not in data.columns:
            return True  # Skip volume check if not enabled or no volume data
        
        try:
            current_volume = data['volume'].iloc[-1]
            avg_volume = data['volume'].rolling(window=20).mean().iloc[-1]
            
            # Volume should be at least 20% above average
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            return volume_ratio >= 1.2
            
        except Exception as e:
            self.logger.error(f"Error checking volume confirmation: {e}")
            return False
    
    def calculate_confidence(self, data: pd.DataFrame, trend_strength: float, volume_confirmed: bool) -> int:
        """
        Calculate signal confidence score (0-100).
        
        Args:
            data: DataFrame with market data
            trend_strength: Calculated trend strength
            volume_confirmed: Whether volume confirms the signal
            
        Returns:
            Confidence score (0-100)
        """
        try:
            base_confidence = 60
            
            # Trend strength contribution (0-25 points)
            strength_score = trend_strength * 25
            
            # Volume confirmation (0-10 points)
            volume_score = 10 if volume_confirmed else 0
            
            # MA separation quality (0-15 points)
            fast_ma = data['fast_ma'].iloc[-1]
            slow_ma = data['slow_ma'].iloc[-1]
            current_price = data['close'].iloc[-1]
            
            ma_separation_pct = abs(fast_ma - slow_ma) / current_price
            separation_score = min(15, ma_separation_pct * 1000)  # Scale up for typical values
            
            total_confidence = base_confidence + strength_score + volume_score + separation_score
            
            return max(30, min(95, int(total_confidence)))
            
        except Exception as e:
            self.logger.error(f"Error calculating confidence: {e}")
            return 50
    
    def calculate_targets_and_stops(self, current_price: float, signal_type: str) -> Tuple[float, float]:
        """
        Calculate target and stop loss prices.
        
        Args:
            current_price: Current market price
            signal_type: 'BUY' or 'SELL'
            
        Returns:
            Tuple of (target_price, stop_loss_price)
        """
        if signal_type == 'BUY':
            target_price = current_price * (1 + self.target_pct / 100)
            stop_loss_price = current_price * (1 - self.stop_loss_pct / 100)
        else:  # SELL
            target_price = current_price * (1 - self.target_pct / 100)
            stop_loss_price = current_price * (1 + self.stop_loss_pct / 100)
        
        return target_price, stop_loss_price
    
    def analyze(self, symbol: str, historical_data: pd.DataFrame, realtime_data: Optional[pd.DataFrame] = None) -> Optional[Dict[str, Any]]:
        """
        Main analysis method for Moving Average Crossover Strategy.
        
        Args:
            symbol: Trading symbol to analyze
            historical_data: Historical OHLCV data
            realtime_data: Optional real-time OHLCV data
            
        Returns:
            Dictionary containing signal information or None if no signal
        """
        try:
            # Combine historical and real-time data
            combined_data = self.combine_data(historical_data, realtime_data)
            
            # Validate data
            min_periods = max(self.fast_period, self.slow_period) + 5
            if not self.validate_data(combined_data, min_periods):
                self.logger.debug(f"Insufficient or invalid data for {symbol}")
                return None
            
            # Calculate moving averages
            combined_data = self.calculate_moving_averages(combined_data)
            
            if len(combined_data) < 2:
                self.logger.debug(f"Insufficient data after MA calculation for {symbol}")
                return None
            
            # Detect crossovers
            golden_cross, death_cross = self.detect_crossovers(combined_data)
            
            if not (golden_cross or death_cross):
                self.logger.debug(f"No crossover detected for {symbol}")
                return None
            
            # Calculate trend strength
            trend_strength = self.calculate_trend_strength(combined_data)
            
            if trend_strength < self.min_trend_strength:
                self.logger.debug(f"Trend strength too weak for {symbol}: {trend_strength} < {self.min_trend_strength}")
                return None
            
            # Volume confirmation
            volume_confirmed = self.check_volume_confirmation(combined_data)
            
            if self.volume_confirmation and not volume_confirmed:
                self.logger.debug(f"Volume confirmation failed for {symbol}")
                return None
            
            # Determine signal type
            signal_type = 'BUY' if golden_cross else 'SELL'
            current_price = combined_data['close'].iloc[-1]
            
            # Calculate targets and stops
            target_price, stop_loss_price = self.calculate_targets_and_stops(current_price, signal_type)
            
            # Calculate confidence
            confidence = self.calculate_confidence(combined_data, trend_strength, volume_confirmed)
            
            # Create signal data
            signal_data = {
                'symbol': symbol,
                'strategy': 'ma_crossover',
                'signal_type': signal_type,
                'entry_price': current_price,
                'target_price': target_price,
                'stop_loss_price': stop_loss_price,
                'confidence': confidence,
                'timestamp': combined_data.index[-1] if hasattr(combined_data.index[-1], 'strftime') else get_current_time(),
                'metadata': {
                    'fast_ma': combined_data['fast_ma'].iloc[-1],
                    'slow_ma': combined_data['slow_ma'].iloc[-1],
                    'fast_period': self.fast_period,
                    'slow_period': self.slow_period,
                    'ma_type': self.ma_type,
                    'trend_strength': trend_strength,
                    'volume_confirmed': volume_confirmed,
                    'crossover_type': 'golden_cross' if golden_cross else 'death_cross',
                    'ma_separation_pct': abs(combined_data['fast_ma'].iloc[-1] - combined_data['slow_ma'].iloc[-1]) / current_price * 100
                }
            }
            
            # Add to signal manager if available
            self.add_signal_to_manager(signal_data)
            
            self.logger.info(f"MA Crossover signal generated for {symbol}: {signal_type} at {current_price:.2f} (confidence: {confidence}%)")
            
            return signal_data
            
        except Exception as e:
            self.logger.error(f"Error in MA crossover analysis for {symbol}: {e}")
            return None
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """
        Get strategy information and current parameters.
        
        Returns:
            Dictionary with strategy information
        """
        return {
            'name': 'Moving Average Crossover',
            'type': 'Trend Following',
            'parameters': {
                'fast_period': self.fast_period,
                'slow_period': self.slow_period,
                'ma_type': self.ma_type,
                'min_trend_strength': self.min_trend_strength,
                'volume_confirmation': self.volume_confirmation,
                'target_pct': self.target_pct,
                'stop_loss_pct': self.stop_loss_pct
            },
            'description': f'Uses {self.fast_period}/{self.slow_period} {self.ma_type} crossover to detect trend changes',
            'best_conditions': 'Strongly trending markets with sustained directional movement',
            'signals': ['Golden Cross (BUY)', 'Death Cross (SELL)']
        }
