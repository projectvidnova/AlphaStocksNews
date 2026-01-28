"""
Base Strategy Interface for AlphaStock Trading System

This module provides the abstract base class that all trading strategies must implement.
It ensures consistent interface across all strategies and provides common functionality.
"""

import logging
import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional, Union

from ..utils.logger_setup import setup_logger

logger = setup_logger("base_strategy")


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.
    
    All strategies must implement the analyze method and follow the consistent
    interface pattern for integration with the main trading system.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize base strategy with configuration.
        
        Args:
            config: Strategy configuration dictionary
        """
        self.config = config
        self.strategy_config = config.get('parameters', {})
        self.signal_manager = None
        self.logger = setup_logger(f"{self.__class__.__name__}")
        
        # Common parameters that most strategies will use
        self.enabled = config.get('enabled', True)
        self.symbols = config.get('symbols', [])
        
        # Initialize strategy-specific parameters
        self._init_parameters()
        
        self.logger.info(f"Initialized {self.__class__.__name__} with config: {self.strategy_config}")
    
    def _init_parameters(self):
        """
        Initialize strategy-specific parameters from config.
        Override in child classes to set specific parameters.
        """
        pass
    
    def set_signal_manager(self, signal_manager):
        """
        Set the signal manager for this strategy.
        
        Args:
            signal_manager: SignalManager instance for handling signals
        """
        self.signal_manager = signal_manager
        self.logger.debug("Signal manager set")
    
    def combine_data(self, historical_data: pd.DataFrame, realtime_data: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Combine historical and real-time data for analysis.
        
        Args:
            historical_data: Historical OHLCV data
            realtime_data: Optional real-time OHLCV data
            
        Returns:
            Combined DataFrame with consistent column structure
        """
        try:
            if realtime_data is None or realtime_data.empty:
                return historical_data.copy()
            
            # Ensure consistent column names (handle both cases)
            combined_data = historical_data.copy()
            
            # Standardize column names to lowercase if needed
            if 'Close' in combined_data.columns:
                combined_data.columns = [col.lower() for col in combined_data.columns]
            
            if 'Close' in realtime_data.columns:
                realtime_data_clean = realtime_data.copy()
                realtime_data_clean.columns = [col.lower() for col in realtime_data_clean.columns]
            else:
                realtime_data_clean = realtime_data.copy()
            
            # Ensure timestamp is datetime and set as index
            if 'timestamp' in combined_data.columns:
                combined_data['timestamp'] = pd.to_datetime(combined_data['timestamp'])
                combined_data = combined_data.set_index('timestamp')
            
            if 'timestamp' in realtime_data_clean.columns:
                realtime_data_clean['timestamp'] = pd.to_datetime(realtime_data_clean['timestamp'])
                realtime_data_clean = realtime_data_clean.set_index('timestamp')
            
            # Combine data
            combined_data = pd.concat([combined_data, realtime_data_clean])
            combined_data = combined_data.sort_index()
            
            # Remove duplicates, keeping the most recent
            combined_data = combined_data[~combined_data.index.duplicated(keep='last')]
            
            return combined_data
            
        except Exception as e:
            self.logger.error(f"Error combining data: {e}")
            return historical_data.copy()
    
    def validate_data(self, data: pd.DataFrame, min_periods: int = 50) -> bool:
        """
        Validate that data has sufficient length and required columns.
        
        Args:
            data: DataFrame to validate
            min_periods: Minimum number of periods required
            
        Returns:
            True if data is valid, False otherwise
        """
        if data is None or data.empty:
            self.logger.warning("Data is empty or None")
            return False
        
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.warning(f"Missing required columns: {missing_columns}")
            return False
        
        if len(data) < min_periods:
            self.logger.warning(f"Insufficient data: {len(data)} < {min_periods}")
            return False
        
        return True
    
    def calculate_returns(self, data: pd.DataFrame, periods: int = 1) -> pd.Series:
        """
        Calculate returns for the given data.
        
        Args:
            data: DataFrame with price data
            periods: Number of periods for return calculation
            
        Returns:
            Series of returns
        """
        return data['close'].pct_change(periods=periods)
    
    def calculate_volatility(self, data: pd.DataFrame, window: int = 20) -> pd.Series:
        """
        Calculate rolling volatility.
        
        Args:
            data: DataFrame with price data
            window: Rolling window size
            
        Returns:
            Series of rolling volatility
        """
        returns = self.calculate_returns(data)
        return returns.rolling(window=window).std() * np.sqrt(252)  # Annualized volatility
    
    def add_signal_to_manager(self, signal_data: Dict[str, Any]):
        """
        Add a signal to the signal manager if available.
        
        Args:
            signal_data: Dictionary containing signal information
        """
        if self.signal_manager and signal_data:
            try:
                self.signal_manager.add_signal(
                    symbol=signal_data['symbol'],
                    strategy=signal_data['strategy'],
                    signal_type=signal_data['signal_type'],
                    entry_price=signal_data['entry_price'],
                    stop_loss_pct=self._calculate_stop_loss_pct(signal_data),
                    target_pct=self._calculate_target_pct(signal_data),
                    metadata=signal_data.get('metadata', {})
                )
                self.logger.info(f"Added signal: {signal_data['signal_type']} {signal_data['symbol']}")
            except Exception as e:
                self.logger.error(f"Error adding signal to manager: {e}")
    
    def _calculate_stop_loss_pct(self, signal_data: Dict[str, Any]) -> float:
        """Calculate stop loss percentage from signal data."""
        if 'stop_loss_price' in signal_data and 'entry_price' in signal_data:
            entry = signal_data['entry_price']
            stop = signal_data['stop_loss_price']
            return abs(stop - entry) / entry * 100
        return 2.0  # Default 2% stop loss
    
    def _calculate_target_pct(self, signal_data: Dict[str, Any]) -> float:
        """Calculate target percentage from signal data."""
        if 'target_price' in signal_data and 'entry_price' in signal_data:
            entry = signal_data['entry_price']
            target = signal_data['target_price']
            return abs(target - entry) / entry * 100
        return 3.0  # Default 3% target
    
    @abstractmethod
    def analyze(self, symbol: str, historical_data: pd.DataFrame, realtime_data: Optional[pd.DataFrame] = None) -> Optional[Dict[str, Any]]:
        """
        Main analysis method that must be implemented by all strategies.
        
        Args:
            symbol: Trading symbol to analyze
            historical_data: Historical OHLCV data
            realtime_data: Optional real-time OHLCV data
            
        Returns:
            Dictionary containing signal information or None if no signal
            
        Expected return format:
        {
            'symbol': str,
            'strategy': str,
            'signal_type': str,  # 'BUY' or 'SELL'
            'entry_price': float,
            'target_price': float,
            'stop_loss_price': float,
            'confidence': int,  # 0-100
            'timestamp': datetime,
            'metadata': dict  # Strategy-specific additional data
        }
        """
        pass
    
    def get_signal_strength(self, signal_data: Dict[str, Any]) -> int:
        """
        Calculate signal strength/confidence (0-100).
        Can be overridden by child classes for custom confidence calculation.
        
        Args:
            signal_data: Signal data dictionary
            
        Returns:
            Confidence score (0-100)
        """
        return signal_data.get('confidence', 50)
    
    def calculate_risk_reward(self, entry_price: float, target_price: float, stop_loss_price: float) -> Dict[str, float]:
        """
        Calculate risk-reward metrics.
        
        Args:
            entry_price: Entry price
            target_price: Target price
            stop_loss_price: Stop loss price
            
        Returns:
            Dictionary with risk-reward metrics
        """
        risk = abs(entry_price - stop_loss_price)
        reward = abs(target_price - entry_price)
        
        risk_pct = (risk / entry_price) * 100
        reward_pct = (reward / entry_price) * 100
        risk_reward_ratio = reward / risk if risk > 0 else 0
        
        return {
            'risk_amount': risk,
            'reward_amount': reward,
            'risk_pct': risk_pct,
            'reward_pct': reward_pct,
            'risk_reward_ratio': risk_reward_ratio
        }
    
    def __str__(self):
        """String representation of the strategy."""
        return f"{self.__class__.__name__}(enabled={self.enabled}, symbols={len(self.symbols)})"
    
    def __repr__(self):
        """Detailed string representation."""
        return f"{self.__class__.__name__}(config={self.strategy_config})"
