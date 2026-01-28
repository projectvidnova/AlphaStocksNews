"""
Subhashish Pani's 5 EMA Alert Candle Strategy Implementation

This is an intraday trading strategy using 15-minute chart data with a sophisticated
alert candle mechanism for entry timing.

Strategy Rules:
1. Calculate 5-period EMA on 15-minute candles
2. Identify "Alert Candle" - first candle that closes:
   - SELL: Fully above 5 EMA without touching it (low > EMA)
   - BUY: Fully below 5 EMA without touching it (high < EMA)
3. Shift Alert Candle if next candle:
   - Closes in same direction (above/below EMA)
   - Does NOT break previous Alert Candle's high (for SELL) or low (for BUY)
4. Entry Trigger:
   - SELL: When candle breaks Alert Candle's low
   - BUY: When candle breaks Alert Candle's high
5. Stop Loss: 2-candle swing high (SELL) or swing low (BUY)
6. Target: Minimum 3x risk (1:3 risk-reward ratio)
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from collections import deque

from ..core.base_strategy import BaseStrategy
from ..utils.logger_setup import setup_logger
from ..utils.timezone_utils import get_current_time, to_ist, to_utc, is_market_hours

logger = setup_logger("ema_5_alert_candle_strategy")


class EMA5AlertCandleStrategy(BaseStrategy):
    """
    Subhashish Pani's 5 EMA Alert Candle Strategy for intraday trading.
    
    Uses a sophisticated alert candle mechanism with dynamic shifting to
    capture strong trending moves with precise entry timing.
    """
    
    def _init_parameters(self):
        """Initialize strategy-specific parameters from config."""
        self.ema_period = self.strategy_config.get('ema_period', 5)
        self.swing_lookback = self.strategy_config.get('swing_lookback', 2)
        self.min_risk_reward = self.strategy_config.get('min_risk_reward', 3.0)
        self.min_candle_gap_pct = self.strategy_config.get('min_candle_gap_pct', 0.05)  # Minimum gap from EMA
        
        # Lookback window for alert candle scanning (to avoid processing entire history)
        # This is the maximum number of candles to look back for alert candle detection
        self.alert_scan_window = self.strategy_config.get('alert_scan_window', 50)
        
        self.logger.info(f"EMA 5 Alert Candle Strategy initialized: EMA={self.ema_period}, RR>={self.min_risk_reward}")
    
    def calculate_ema(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate 5-period EMA.
        
        Args:
            data: DataFrame with OHLCV data
            
        Returns:
            DataFrame with added 'ema_5' column
        """
        data = data.copy()
        
        try:
            data['ema_5'] = data['close'].ewm(span=self.ema_period, adjust=False).mean()
            
            # Remove NaN values from initial EMA calculation
            data.dropna(subset=['ema_5'], inplace=True)
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error calculating EMA: {e}")
            raise
    
    def is_alert_candle_sell(self, candle: pd.Series, ema_value: float) -> bool:
        """
        Check if candle qualifies as SELL alert candle.
        
        Alert Candle SELL: Candle closes fully above EMA without touching it.
        - Low > EMA (candle never touched EMA)
        - Close > EMA (confirms above)
        
        Args:
            candle: Single candle (row from DataFrame)
            ema_value: EMA value at this candle
            
        Returns:
            True if this is a valid SELL alert candle
        """
        # Candle must be fully above EMA
        fully_above = candle['low'] > ema_value and candle['close'] > ema_value
        
        # Optional: Check for minimum gap (to avoid noise)
        gap_pct = ((candle['low'] - ema_value) / ema_value) * 100
        sufficient_gap = gap_pct >= self.min_candle_gap_pct
        
        return fully_above and sufficient_gap
    
    def is_alert_candle_buy(self, candle: pd.Series, ema_value: float) -> bool:
        """
        Check if candle qualifies as BUY alert candle.
        
        Alert Candle BUY: Candle closes fully below EMA without touching it.
        - High < EMA (candle never touched EMA)
        - Close < EMA (confirms below)
        
        Args:
            candle: Single candle (row from DataFrame)
            ema_value: EMA value at this candle
            
        Returns:
            True if this is a valid BUY alert candle
        """
        # Candle must be fully below EMA
        fully_below = candle['high'] < ema_value and candle['close'] < ema_value
        
        # Optional: Check for minimum gap (to avoid noise)
        gap_pct = ((ema_value - candle['high']) / ema_value) * 100
        sufficient_gap = gap_pct >= self.min_candle_gap_pct
        
        return fully_below and sufficient_gap
    
    def should_shift_alert_candle_sell(self, current_candle: pd.Series, alert_candle: pd.Series, 
                                       ema_value: float) -> bool:
        """
        Check if SELL alert candle should be shifted to current candle.
        
        Shift conditions (SELL):
        1. Current candle closes above EMA (continues bearish setup)
        2. Current candle does NOT break previous alert candle's HIGH
        
        Args:
            current_candle: Current candle
            alert_candle: Previous alert candle
            ema_value: EMA value at current candle
            
        Returns:
            True if alert candle should shift to current candle
        """
        # Must still be fully above EMA
        still_above = self.is_alert_candle_sell(current_candle, ema_value)
        
        # Must NOT break previous alert candle's high (no bullish reversal)
        no_breakout = current_candle['high'] <= alert_candle['high']
        
        return still_above and no_breakout
    
    def should_shift_alert_candle_buy(self, current_candle: pd.Series, alert_candle: pd.Series,
                                      ema_value: float) -> bool:
        """
        Check if BUY alert candle should be shifted to current candle.
        
        Shift conditions (BUY):
        1. Current candle closes below EMA (continues bullish setup)
        2. Current candle does NOT break previous alert candle's LOW
        
        Args:
            current_candle: Current candle
            alert_candle: Previous alert candle
            ema_value: EMA value at current candle
            
        Returns:
            True if alert candle should shift to current candle
        """
        # Must still be fully below EMA
        still_below = self.is_alert_candle_buy(current_candle, ema_value)
        
        # Must NOT break previous alert candle's low (no bearish reversal)
        no_breakdown = current_candle['low'] >= alert_candle['low']
        
        return still_below and no_breakdown
    
    def check_sell_entry_trigger(self, current_candle: pd.Series, alert_candle: pd.Series) -> bool:
        """
        Check if SELL entry is triggered.
        
        Entry Trigger (SELL): Current candle breaks alert candle's LOW
        
        Args:
            current_candle: Current candle
            alert_candle: Alert candle
            
        Returns:
            True if SELL entry triggered
        """
        return current_candle['low'] < alert_candle['low']
    
    def check_buy_entry_trigger(self, current_candle: pd.Series, alert_candle: pd.Series) -> bool:
        """
        Check if BUY entry is triggered.
        
        Entry Trigger (BUY): Current candle breaks alert candle's HIGH
        
        Args:
            current_candle: Current candle
            alert_candle: Alert candle
            
        Returns:
            True if BUY entry triggered
        """
        return current_candle['high'] > alert_candle['high']
    
    def calculate_swing_high(self, data: pd.DataFrame, current_idx: int) -> float:
        """
        Calculate recent swing high for stop loss (SELL trades).
        
        Args:
            data: DataFrame with OHLCV data
            current_idx: Current candle index
            
        Returns:
            Swing high price
        """
        # Look back at last N candles for swing high
        start_idx = max(0, current_idx - self.swing_lookback)
        swing_high = data.iloc[start_idx:current_idx + 1]['high'].max()
        
        return swing_high
    
    def calculate_swing_low(self, data: pd.DataFrame, current_idx: int) -> float:
        """
        Calculate recent swing low for stop loss (BUY trades).
        
        Args:
            data: DataFrame with OHLCV data
            current_idx: Current candle index
            
        Returns:
            Swing low price
        """
        # Look back at last N candles for swing low
        start_idx = max(0, current_idx - self.swing_lookback)
        swing_low = data.iloc[start_idx:current_idx + 1]['low'].min()
        
        return swing_low
    
    def find_alert_candle_and_signal(self, symbol: str, data: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Scan data for alert candle and check for entry triggers (STATELESS).
        
        This implements the core strategy logic:
        1. Scan recent candles for alert candles (fully above/below EMA)
        2. Track and shift alert candles as we scan forward
        3. Check for entry triggers (break of alert candle high/low)
        4. Calculate stop loss and targets
        
        IMPORTANT: This method is STATELESS - no persistent state between calls.
        Each call rescans the recent window to find current alert state.
        
        Args:
            symbol: Trading symbol
            data: DataFrame with OHLCV and EMA data
            
        Returns:
            Signal dictionary or None
        """
        # Determine scan window (last N candles to check for alert patterns)
        # This should be enough to catch alert candles that haven't triggered yet
        scan_start_idx = max(0, len(data) - self.alert_scan_window)
        
        # Track alert candle as we scan forward
        alert_candle_idx = None
        alert_type = None  # 'BUY' or 'SELL'
        alert_candle = None
        
        # Scan through recent candles
        for idx in range(scan_start_idx, len(data)):
            candle = data.iloc[idx]
            ema_value = candle['ema_5']
            
            # If we have an active alert candle, check for entry trigger FIRST
            if alert_candle_idx is not None:
                # Check for entry trigger (highest priority)
                if alert_type == 'SELL' and self.check_sell_entry_trigger(candle, alert_candle):
                    # SELL signal triggered!
                    # FIX #3: Use trigger candle's low (actual break point) as entry
                    entry_price = candle['low']
                    stop_loss = self.calculate_swing_high(data, idx)
                    
                    # Validate stop loss is above entry (for SELL)
                    if stop_loss <= entry_price:
                        self.logger.warning(f"{symbol}: Invalid SELL stop loss ({stop_loss:.2f}) <= entry ({entry_price:.2f}), skipping")
                        return None
                    
                    risk = stop_loss - entry_price
                    target_price = entry_price - (risk * self.min_risk_reward)
                    
                    return self._create_signal(
                        symbol=symbol,
                        signal_type='SELL',
                        entry_price=entry_price,
                        stop_loss_price=stop_loss,
                        target_price=target_price,
                        candle=candle,
                        alert_candle=alert_candle,
                        ema_value=ema_value,
                        risk=risk
                    )
                
                elif alert_type == 'BUY' and self.check_buy_entry_trigger(candle, alert_candle):
                    # BUY signal triggered!
                    # FIX #3: Use trigger candle's high (actual break point) as entry
                    entry_price = candle['high']
                    stop_loss = self.calculate_swing_low(data, idx)
                    
                    # Validate stop loss is below entry (for BUY)
                    if stop_loss >= entry_price:
                        self.logger.warning(f"{symbol}: Invalid BUY stop loss ({stop_loss:.2f}) >= entry ({entry_price:.2f}), skipping")
                        return None
                    
                    risk = entry_price - stop_loss
                    target_price = entry_price + (risk * self.min_risk_reward)
                    
                    return self._create_signal(
                        symbol=symbol,
                        signal_type='BUY',
                        entry_price=entry_price,
                        stop_loss_price=stop_loss,
                        target_price=target_price,
                        candle=candle,
                        alert_candle=alert_candle,
                        ema_value=ema_value,
                        risk=risk
                    )
                
                # Check if alert candle should be SHIFTED
                if alert_type == 'SELL' and self.should_shift_alert_candle_sell(candle, alert_candle, ema_value):
                    # Shift alert candle to current candle
                    self.logger.debug(f"{symbol}: Shifting SELL alert candle from idx {alert_candle_idx} to {idx}")
                    alert_candle_idx = idx
                    alert_candle = candle
                
                elif alert_type == 'BUY' and self.should_shift_alert_candle_buy(candle, alert_candle, ema_value):
                    # Shift alert candle to current candle
                    self.logger.debug(f"{symbol}: Shifting BUY alert candle from idx {alert_candle_idx} to {idx}")
                    alert_candle_idx = idx
                    alert_candle = candle
            
            else:
                # No alert candle yet - look for new one
                if self.is_alert_candle_sell(candle, ema_value):
                    # Found SELL alert candle
                    self.logger.debug(f"{symbol}: New SELL alert candle detected at idx {idx}, price={candle['close']:.2f}, EMA={ema_value:.2f}")
                    alert_candle_idx = idx
                    alert_type = 'SELL'
                    alert_candle = candle
                
                elif self.is_alert_candle_buy(candle, ema_value):
                    # Found BUY alert candle
                    self.logger.debug(f"{symbol}: New BUY alert candle detected at idx {idx}, price={candle['close']:.2f}, EMA={ema_value:.2f}")
                    alert_candle_idx = idx
                    alert_type = 'BUY'
                    alert_candle = candle
        
        # No signal triggered in this scan
        # (Alert candle may exist but hasn't been broken yet - will check again on next call)
        if alert_candle_idx is not None:
            self.logger.debug(f"{symbol}: Alert candle active at idx {alert_candle_idx} ({alert_type}), waiting for trigger")
        
        return None
    
    def _create_signal(self, symbol: str, signal_type: str, entry_price: float,
                      stop_loss_price: float, target_price: float, candle: pd.Series,
                      alert_candle: pd.Series, ema_value: float, risk: float) -> Dict[str, Any]:
        """
        Create signal dictionary with all metadata.
        
        Args:
            symbol: Trading symbol
            signal_type: 'BUY' or 'SELL'
            entry_price: Entry price
            stop_loss_price: Stop loss price
            target_price: Target price
            candle: Current candle that triggered entry
            alert_candle: Alert candle that set up the trade
            ema_value: Current EMA value
            risk: Risk amount per share
            
        Returns:
            Signal dictionary
        """
        reward = abs(target_price - entry_price)
        risk_reward_ratio = reward / risk if risk > 0 else 0
        
        # Calculate confidence based on risk-reward and EMA gap
        ema_gap_pct = abs(alert_candle['close'] - ema_value) / ema_value * 100
        
        # Higher confidence for:
        # - Better risk-reward ratios
        # - Larger gaps from EMA (stronger moves)
        confidence = min(95, int(60 + (risk_reward_ratio * 5) + (ema_gap_pct * 20)))
        
        signal_data = {
            'symbol': symbol,
            'strategy': 'ema_5_alert_candle',
            'signal_type': signal_type,
            'entry_price': entry_price,
            'target_price': target_price,
            'stop_loss_price': stop_loss_price,
            'confidence': confidence,
            'timestamp': candle.name if hasattr(candle, 'name') else get_current_time(),
            'metadata': {
                'ema_period': self.ema_period,
                'ema_value': ema_value,
                'alert_candle_price': alert_candle['close'],
                'alert_candle_high': alert_candle['high'],
                'alert_candle_low': alert_candle['low'],
                'trigger_candle_price': candle['close'],
                'risk_amount': risk,
                'reward_amount': reward,
                'risk_reward_ratio': risk_reward_ratio,
                'ema_gap_pct': ema_gap_pct,
                'swing_lookback': self.swing_lookback
            }
        }
        
        return signal_data
    
    def analyze(self, symbol: str, historical_data: pd.DataFrame, 
               realtime_data: Optional[pd.DataFrame] = None) -> Optional[Dict[str, Any]]:
        """
        Main analysis method for EMA 5 Alert Candle Strategy.
        
        Args:
            symbol: Trading symbol to analyze
            historical_data: Historical 15-minute OHLCV data
            realtime_data: Optional real-time 15-minute OHLCV data
            
        Returns:
            Dictionary containing signal information or None if no signal
        """
        try:
            # Combine historical and real-time data
            combined_data = self.combine_data(historical_data, realtime_data)
            
            # Validate data (need at least EMA period + swing lookback + buffer)
            min_periods = self.ema_period + self.swing_lookback + 10
            if not self.validate_data(combined_data, min_periods):
                self.logger.debug(f"Insufficient or invalid data for {symbol}")
                return None
            
            # Calculate 5 EMA
            combined_data = self.calculate_ema(combined_data)
            
            if len(combined_data) < min_periods:
                self.logger.debug(f"Insufficient data after EMA calculation for {symbol}")
                return None
            
            # Find alert candle and check for entry signals
            signal = self.find_alert_candle_and_signal(symbol, combined_data)
            
            if signal:
                # Add to signal manager
                self.add_signal_to_manager(signal)
                
                self.logger.info(
                    f"EMA 5 Alert Candle signal: {signal['signal_type']} {symbol} @ {signal['entry_price']:.2f} "
                    f"(SL: {signal['stop_loss_price']:.2f}, Target: {signal['target_price']:.2f}, "
                    f"RR: {signal['metadata']['risk_reward_ratio']:.2f})"
                )
                
                return signal
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error in EMA 5 Alert Candle analysis for {symbol}: {e}", exc_info=True)
            return None
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """
        Get strategy information and current parameters.
        
        Returns:
            Dictionary with strategy information
        """
        return {
            'name': 'EMA 5 Alert Candle (Subhashish Pani)',
            'type': 'Intraday Trend Following',
            'timeframe': '15 minutes',
            'parameters': {
                'ema_period': self.ema_period,
                'swing_lookback': self.swing_lookback,
                'min_risk_reward': self.min_risk_reward,
                'min_candle_gap_pct': self.min_candle_gap_pct
            },
            'description': 'Alert candle strategy with dynamic shifting for precise entry timing',
            'best_conditions': 'Strong intraday trends with clear EMA respect/rejection',
            'signals': [
                'SELL: Candle fully above EMA → breaks alert low',
                'BUY: Candle fully below EMA → breaks alert high'
            ],
            'key_features': [
                'Dynamic alert candle shifting',
                'Swing-based stop loss (2-candle lookback)',
                'Minimum 1:3 risk-reward ratio',
                'Intraday-only (15-minute chart)'
            ]
        }
