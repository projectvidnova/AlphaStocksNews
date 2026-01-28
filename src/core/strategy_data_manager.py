"""
Strategy Data Manager - Coordinates historical and real-time data for strategies

This module acts as the central coordinator between:
1. HistoricalDataCache (historical OHLCV data)
2. CandleAggregator (real-time tick-to-candle conversion)
3. Strategy configuration (per-strategy data requirements)

It seamlessly merges historical and real-time candles to provide strategies with
the complete dataset they need for analysis.

Key Features:
- Per-strategy data requirements from config
- Seamless merge of historical + real-time data
- Validates data quality and completeness
- Handles timeframe mismatches
- Memory-efficient data slicing
"""

import pandas as pd
from datetime import datetime
from typing import Dict, Optional, Tuple
from ..utils.logger_setup import setup_logger

logger = setup_logger("strategy_data_manager")


class StrategyDataManager:
    """
    Manages data provisioning for trading strategies.
    
    Coordinates between historical cache and real-time aggregator to provide
    strategies with properly prepared OHLCV data matching their requirements.
    
    Usage:
        manager = StrategyDataManager(config, data_layer, candle_aggregator, historical_cache)
        df = manager.get_strategy_data('SBIN', strategy_config)
    """
    
    def __init__(self, config: Dict, data_layer, 
                 candle_aggregator, historical_cache):
        """
        Initialize strategy data manager.
        
        Args:
            config: Global configuration dictionary
            data_layer: ClickHouse data layer instance
            candle_aggregator: CandleAggregator instance for real-time candles
            historical_cache: HistoricalDataCache instance for historical data
        """
        self.config = config
        self.data_layer = data_layer
        self.candle_aggregator = candle_aggregator
        self.historical_cache = historical_cache
        
        logger.info("StrategyDataManager initialized")
    
    def get_strategy_data(self, symbol: str, strategy_config: Dict,
                         asset_type: str = 'EQUITY') -> pd.DataFrame:
        """
        Get complete dataset for a strategy (historical + real-time).
        
        Args:
            symbol: Trading symbol
            strategy_config: Strategy configuration with timeframe and lookback
            asset_type: Asset type ('EQUITY', 'OPTIONS', 'FUTURES')
            
        Returns:
            DataFrame with complete OHLCV data ready for strategy analysis
        """
        try:
            # Extract strategy data requirements
            timeframe = strategy_config.get('timeframe', '15minute')
            lookback_config = strategy_config.get('historical_lookback', {})
            periods = lookback_config.get('periods', 1000)
            min_periods = lookback_config.get('min_periods', 50)
            
            realtime_config = strategy_config.get('realtime_aggregation', {})
            use_realtime = realtime_config.get('enabled', True)
            
            logger.debug(f"Getting data for {symbol}: timeframe={timeframe}, periods={periods}, "
                        f"realtime={use_realtime}")
            
            # Step 1: Get historical data from cache
            historical_df = self._get_historical_data(symbol, timeframe, periods, asset_type)
            
            # Step 2: Get real-time candles if enabled
            realtime_df = pd.DataFrame()
            if use_realtime:
                realtime_df = self._get_realtime_candles(symbol, timeframe, include_incomplete=True)
            
            # Step 3: Merge historical and real-time data
            merged_df = self._merge_data(historical_df, realtime_df, timeframe)
            
            # Step 4: Validate data quality
            validation = self._validate_data(merged_df, min_periods, periods, symbol, timeframe)
            
            if not validation['is_valid']:
                logger.warning(f"Data validation failed for {symbol}: {validation['message']}")
            
            # Step 5: Limit to requested periods
            if len(merged_df) > periods:
                merged_df = merged_df.tail(periods)
            
            logger.info(f"Prepared data for {symbol}: {len(merged_df)} {timeframe} candles "
                       f"(historical: {len(historical_df)}, realtime: {len(realtime_df)})")
            
            return merged_df
            
        except Exception as e:
            logger.error(f"Error getting strategy data for {symbol}: {e}")
            return pd.DataFrame()
    
    def _get_historical_data(self, symbol: str, timeframe: str, 
                            periods: int, asset_type: str) -> pd.DataFrame:
        """
        Get historical data from cache.
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe
            periods: Number of periods
            asset_type: Asset type
            
        Returns:
            DataFrame with historical data
        """
        try:
            df = self.historical_cache.get_historical(symbol, timeframe, periods, asset_type)
            
            if df.empty:
                logger.warning(f"No historical data available for {symbol} {timeframe}")
            else:
                logger.debug(f"Retrieved {len(df)} historical {timeframe} candles for {symbol}")
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting historical data for {symbol}: {e}")
            return pd.DataFrame()
    
    def _get_realtime_candles(self, symbol: str, timeframe: str,
                             include_incomplete: bool = True) -> pd.DataFrame:
        """
        Get real-time candles from aggregator.
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe (must match aggregator's timeframe)
            include_incomplete: Include currently building candle
            
        Returns:
            DataFrame with real-time candles
        """
        try:
            # Note: This assumes aggregator is running with the same timeframe
            # In multi-timeframe scenarios, we'd need multiple aggregators or
            # a more sophisticated aggregation system
            
            df = self.candle_aggregator.get_candles(
                symbol=symbol,
                count=100,  # Get recent real-time candles
                include_incomplete=include_incomplete
            )
            
            if not df.empty:
                logger.debug(f"Retrieved {len(df)} real-time {timeframe} candles for {symbol}")
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting real-time candles for {symbol}: {e}")
            return pd.DataFrame()
    
    def _merge_data(self, historical_df: pd.DataFrame, realtime_df: pd.DataFrame,
                   timeframe: str) -> pd.DataFrame:
        """
        Merge historical and real-time data seamlessly.
        
        Args:
            historical_df: Historical data DataFrame
            realtime_df: Real-time data DataFrame
            timeframe: Candle timeframe
            
        Returns:
            Merged DataFrame
        """
        # If no historical data, return real-time only
        if historical_df.empty:
            return realtime_df.copy()
        
        # If no real-time data, return historical only
        if realtime_df.empty:
            return historical_df.copy()
        
        try:
            # Ensure both have timestamp column
            if 'timestamp' not in historical_df.columns:
                if isinstance(historical_df.index, pd.DatetimeIndex):
                    historical_df = historical_df.reset_index()
            
            if 'timestamp' not in realtime_df.columns:
                if isinstance(realtime_df.index, pd.DatetimeIndex):
                    realtime_df = realtime_df.reset_index()
            
            # Convert timestamps to datetime
            historical_df['timestamp'] = pd.to_datetime(historical_df['timestamp'])
            realtime_df['timestamp'] = pd.to_datetime(realtime_df['timestamp'])
            
            # Find cutoff time (where historical ends)
            cutoff_time = historical_df['timestamp'].max()
            
            # Get only NEW real-time candles (after historical)
            new_realtime = realtime_df[realtime_df['timestamp'] > cutoff_time].copy()
            
            if new_realtime.empty:
                logger.debug(f"No new real-time candles to add (historical ends at {cutoff_time})")
                return historical_df
            
            # Concatenate historical + new real-time
            merged_df = pd.concat([historical_df, new_realtime], ignore_index=True)
            
            # Remove duplicates based on timestamp (keep last)
            merged_df = merged_df.drop_duplicates(subset=['timestamp'], keep='last')
            
            # Sort by timestamp
            merged_df = merged_df.sort_values('timestamp').reset_index(drop=True)
            
            logger.debug(f"Merged data: {len(historical_df)} historical + {len(new_realtime)} "
                        f"new realtime = {len(merged_df)} total candles")
            
            return merged_df
            
        except Exception as e:
            logger.error(f"Error merging data: {e}")
            # On error, return historical only
            return historical_df.copy()
    
    def _validate_data(self, df: pd.DataFrame, min_periods: int, 
                      requested_periods: int, symbol: str, timeframe: str) -> Dict:
        """
        Validate data quality and completeness.
        
        Args:
            df: Data DataFrame to validate
            min_periods: Minimum acceptable periods
            requested_periods: Requested periods
            symbol: Trading symbol (for logging)
            timeframe: Candle timeframe (for logging)
            
        Returns:
            Validation result dictionary
        """
        if df.empty:
            return {
                'is_valid': False,
                'message': 'No data available',
                'periods': 0,
                'min_periods': min_periods,
                'requested_periods': requested_periods
            }
        
        actual_periods = len(df)
        
        # Check if we have minimum required periods
        if actual_periods < min_periods:
            return {
                'is_valid': False,
                'message': f'Insufficient data: {actual_periods} < {min_periods} min required',
                'periods': actual_periods,
                'min_periods': min_periods,
                'requested_periods': requested_periods
            }
        
        # Check for missing OHLCV columns
        required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return {
                'is_valid': False,
                'message': f'Missing required columns: {missing_columns}',
                'periods': actual_periods,
                'min_periods': min_periods,
                'requested_periods': requested_periods
            }
        
        # Check for NaN values in critical columns
        critical_cols = ['open', 'high', 'low', 'close']
        nan_counts = df[critical_cols].isna().sum()
        
        if nan_counts.any():
            return {
                'is_valid': False,
                'message': f'NaN values found in critical columns: {nan_counts[nan_counts > 0].to_dict()}',
                'periods': actual_periods,
                'min_periods': min_periods,
                'requested_periods': requested_periods
            }
        
        # Calculate completeness percentage
        completeness_percent = round((actual_periods / requested_periods * 100), 2)
        
        # Only warn if we have less than requested AND less than 50% complete
        if actual_periods < requested_periods:
            if completeness_percent < 50:
                # Serious shortage - warn
                message = f'Partial data: {actual_periods} of {requested_periods} requested periods ({completeness_percent}%)'
                logger.warning(f"{symbol} {timeframe}: {message}")
            else:
                # Have enough data (>50%) - just debug log
                message = f'Partial data: {actual_periods} of {requested_periods} requested periods ({completeness_percent}%)'
                logger.debug(f"{symbol} {timeframe}: {message} - sufficient for analysis")
        
        return {
            'is_valid': True,
            'message': 'Data validation passed' if actual_periods >= requested_periods else f'Partial data ({completeness_percent}%)',
            'periods': actual_periods,
            'min_periods': min_periods,
            'requested_periods': requested_periods,
            'completeness_percent': completeness_percent
        }
    
    def preload_strategies(self, strategies: Dict, symbols: list) -> None:
        """
        Preload historical data for all strategies.
        
        Args:
            strategies: Strategy configurations dictionary
            symbols: List of trading symbols
        """
        logger.info(f"Preloading data for {len(strategies)} strategies, {len(symbols)} symbols")
        
        # Extract unique timeframes and periods from strategies
        timeframe_periods = {}
        for strategy_name, strategy_config in strategies.items():
            if not strategy_config.get('enabled', False):
                continue
            
            timeframe = strategy_config.get('timeframe', '15minute')
            lookback = strategy_config.get('historical_lookback', {})
            periods = lookback.get('periods', 1000)
            
            # Track maximum periods needed per timeframe
            if timeframe not in timeframe_periods:
                timeframe_periods[timeframe] = periods
            else:
                timeframe_periods[timeframe] = max(timeframe_periods[timeframe], periods)
        
        logger.info(f"Preload requirements: {timeframe_periods}")
        
        # Preload cache for all timeframe/period combinations
        for timeframe, periods in timeframe_periods.items():
            logger.info(f"Preloading {timeframe} data ({periods} periods) for {len(symbols)} symbols")
            self.historical_cache.preload(symbols, [timeframe], periods)
        
        logger.info("Strategy data preload complete")
    
    def get_cache_statistics(self) -> Dict:
        """
        Get cache statistics.
        
        Returns:
            Statistics dictionary
        """
        cache_stats = self.historical_cache.get_statistics()
        aggregator_stats = self.candle_aggregator.get_statistics()
        
        return {
            'cache': cache_stats,
            'aggregator': aggregator_stats
        }
