"""
Historical Data Cache - Smart caching layer for historical market data

This module implements intelligent caching with auto-refresh capabilities to minimize
database queries while keeping data fresh. Only queries the database when:
1. Cache is empty (first request)
2. Cache is stale (data older than refresh interval)
3. Requested period extends beyond cached data

Key Features:
- Per-symbol, per-timeframe caching
- Automatic refresh based on configurable interval
- Memory-efficient (only keeps required lookback periods)
- Thread-safe operations
- Lazy loading (fetch on demand)
"""

import pandas as pd
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from collections import defaultdict
import threading
from ..utils.logger_setup import setup_logger
from ..utils.timezone_utils import get_current_time, to_ist, to_utc, is_market_hours

logger = setup_logger("historical_data_cache")


class HistoricalDataCache:
    """
    Smart cache for historical market data with auto-refresh.
    
    Usage:
        cache = HistoricalDataCache(data_layer, refresh_interval=300)
        df = cache.get_historical('SBIN', '15minute', periods=1000)
    """
    
    def __init__(self, data_layer, refresh_interval_seconds: int = 300):
        """
        Initialize historical data cache.
        
        Args:
            data_layer: ClickHouse data layer instance for database queries
            refresh_interval_seconds: How often to refresh cache (default 5 minutes)
        """
        self.data_layer = data_layer
        self.refresh_interval = timedelta(seconds=refresh_interval_seconds)
        
        # Cache structure: {symbol: {timeframe: {'data': DataFrame, 'last_refresh': datetime}}}
        self.cache: Dict[str, Dict[str, Dict]] = defaultdict(lambda: defaultdict(dict))
        
        # Cache statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'refreshes': 0,
            'db_queries': 0
        }
        
        # Thread safety
        self.lock = threading.Lock()
        
        logger.info(f"HistoricalDataCache initialized with {refresh_interval_seconds}s refresh interval")
    
    def get_historical(self, symbol: str, timeframe: str, periods: int,
                      asset_type: str = 'EQUITY') -> pd.DataFrame:
        """
        Get historical data from cache or database.
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe ('1minute', '5minute', '15minute', '60minute', 'day')
            periods: Number of candles to retrieve
            asset_type: Asset type ('EQUITY', 'OPTIONS', 'FUTURES')
            
        Returns:
            DataFrame with historical OHLCV data
        """
        with self.lock:
            cache_key = f"{symbol}_{timeframe}_{asset_type}"
            
            # Check if we have cached data
            if self._has_valid_cache(symbol, timeframe):
                cached_data = self.cache[symbol][timeframe]['data']
                
                # Check if cached data has enough periods
                if len(cached_data) >= periods:
                    self.stats['hits'] += 1
                    logger.debug(f"Cache HIT for {cache_key}: returning {periods} from {len(cached_data)} cached")
                    return cached_data.tail(periods).copy()
                else:
                    logger.debug(f"Cache has only {len(cached_data)} periods, need {periods} - fetching more")
            
            # Cache miss or insufficient data - fetch from database
            self.stats['misses'] += 1
            logger.debug(f"Cache MISS for {cache_key}: fetching from database")
            
            data = self._fetch_from_database(symbol, timeframe, periods, asset_type)
            
            # Update cache
            self._update_cache(symbol, timeframe, data)
            
            return data
    
    def _has_valid_cache(self, symbol: str, timeframe: str) -> bool:
        """
        Check if cached data exists and is still fresh.
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe
            
        Returns:
            True if cache is valid, False otherwise
        """
        if symbol not in self.cache or timeframe not in self.cache[symbol]:
            return False
        
        cache_entry = self.cache[symbol][timeframe]
        
        # Check if data exists
        if 'data' not in cache_entry or cache_entry['data'].empty:
            return False
        
        # Check if cache is stale
        last_refresh = cache_entry.get('last_refresh')
        if last_refresh is None:
            return False
        
        is_fresh = (get_current_time() - last_refresh) < self.refresh_interval
        
        if not is_fresh:
            logger.debug(f"Cache for {symbol} {timeframe} is stale (age: {get_current_time() - last_refresh})")
        
        return is_fresh
    
    def _fetch_from_database(self, symbol: str, timeframe: str, 
                            periods: int, asset_type: str) -> pd.DataFrame:
        """
        Fetch historical data from database.
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe
            periods: Number of periods to fetch
            asset_type: Asset type
            
        Returns:
            DataFrame with historical data
        """
        try:
            self.stats['db_queries'] += 1
            
            # Calculate time range based on timeframe and periods
            timeframe_minutes = self._parse_timeframe_to_minutes(timeframe)
            
            # Stock market trades ~6.5 hours per day, not 24 hours
            # So we need more calendar days to get the required number of candles
            trading_hours_per_day = 6.5  # 9:15 AM to 3:30 PM
            trading_minutes_per_day = trading_hours_per_day * 60  # ~390 minutes
            
            # Calculate how many calendar days we need
            # Add 50% buffer for weekends and holidays
            required_trading_days = (periods * timeframe_minutes) / trading_minutes_per_day
            lookback_days = int(required_trading_days * 1.5) + 10  # 50% buffer + 10 days safety
            
            end_time = get_current_time()
            start_time = end_time - timedelta(days=lookback_days)
            
            logger.info(f"Fetching {periods} {timeframe} candles for {symbol} from database "
                       f"({start_time.date()} to {end_time.date()}, {lookback_days} days lookback)")
            
            # Query database for historical data (handle async call)
            # Since we're called from sync context, we need to run the async method
            try:
                # Check if we're already in an async event loop
                try:
                    loop = asyncio.get_running_loop()
                    # We're in an async context - use run_coroutine_threadsafe
                    import concurrent.futures
                    
                    # Create a new thread to run the async call
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(
                            asyncio.run,
                            self.data_layer.get_historical_data(
                                symbol=symbol,
                                timeframe=timeframe,
                                start_date=start_time,
                                end_date=end_time
                            )
                        )
                        df = future.result(timeout=30)  # 30 second timeout
                        
                except RuntimeError:
                    # No running event loop - normal case, use asyncio.run directly
                    df = asyncio.run(self.data_layer.get_historical_data(
                        symbol=symbol,
                        timeframe=timeframe,
                        start_date=start_time,
                        end_date=end_time
                    ))
            except Exception as async_error:
                logger.error(f"Error in async call to get_historical_data: {async_error}")
                raise
            
            if df.empty:
                logger.warning(f"No historical data found for {symbol} {timeframe}")
                return pd.DataFrame()
            
            # Log raw data info
            logger.debug(f"Raw data from database: {len(df)} rows, columns: {df.columns.tolist()}")
            if len(df) > 0 and 'timestamp' in df.columns:
                logger.debug(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
            
            # Check if data needs aggregation
            # If we queried for specific timeframe and got data, it should already be in that timeframe
            # Only aggregate if data is in different timeframe (e.g., got 1-min data when we need 15-min)
            needs_aggregation = False
            
            # Check if we have a 'timeframe' column in the data
            if 'timeframe' in df.columns:
                actual_timeframe = df['timeframe'].iloc[0] if len(df) > 0 else None
                if actual_timeframe and actual_timeframe != timeframe:
                    needs_aggregation = True
                    logger.debug(f"Data timeframe ({actual_timeframe}) doesn't match requested ({timeframe}), will aggregate")
            else:
                # No timeframe column - assume data is already in correct format from query
                # Since we passed timeframe to get_historical_data(), database should return correct data
                logger.debug(f"No timeframe column in data, assuming database returned {timeframe} data directly")
                needs_aggregation = False
            
            # Only aggregate if needed
            if needs_aggregation:
                df_before_agg = len(df)
                df = self._aggregate_to_timeframe(df, timeframe)
                if df_before_agg != len(df):
                    logger.info(f"Aggregated {df_before_agg} rows -> {len(df)} {timeframe} candles for {symbol}")
            else:
                logger.debug(f"Skipping aggregation - data already in {timeframe} format")
            
            # Limit to requested periods
            if len(df) > periods:
                df = df.tail(periods)
            
            logger.info(f"Fetched {len(df)} {timeframe} candles for {symbol} (requested {periods})")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return pd.DataFrame()
    
    def _parse_timeframe_to_minutes(self, timeframe: str) -> int:
        """
        Parse timeframe string to minutes.
        
        Args:
            timeframe: Timeframe string
            
        Returns:
            Number of minutes
        """
        timeframe = timeframe.lower()
        
        if 'minute' in timeframe:
            return int(timeframe.replace('minute', ''))
        elif 'hour' in timeframe:
            return int(timeframe.replace('hour', '')) * 60
        elif timeframe == 'day':
            return 24 * 60
        else:
            return 15  # Default to 15 minutes
    
    def _aggregate_to_timeframe(self, df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """
        Aggregate tick/minute data to requested timeframe.
        
        Args:
            df: Input DataFrame with tick or minute data
            timeframe: Target timeframe
            
        Returns:
            Aggregated DataFrame
        """
        if df.empty:
            return df
        
        # Ensure timestamp is datetime index
        if 'timestamp' in df.columns:
            df = df.set_index('timestamp')
        
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        
        # Determine resampling rule
        timeframe = timeframe.lower()
        if timeframe == '1minute':
            rule = '1T'
        elif timeframe == '5minute':
            rule = '5T'
        elif timeframe == '15minute':
            rule = '15T'
        elif timeframe == '60minute' or timeframe == '1hour':
            rule = '60T'
        elif timeframe == 'day':
            rule = 'D'
        else:
            logger.warning(f"Unknown timeframe '{timeframe}', using as-is")
            return df.reset_index()
        
        # Aggregate OHLCV data
        agg_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }
        
        # Add optional columns if present
        if 'turnover' in df.columns:
            agg_dict['turnover'] = 'sum'
        if 'symbol' in df.columns:
            agg_dict['symbol'] = 'first'
        if 'asset_type' in df.columns:
            agg_dict['asset_type'] = 'first'
        
        # Resample and aggregate
        df_agg = df.resample(rule).agg(agg_dict).dropna()
        
        return df_agg.reset_index()
    
    def _update_cache(self, symbol: str, timeframe: str, data: pd.DataFrame) -> None:
        """
        Update cache with new data.
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe
            data: DataFrame to cache
        """
        self.cache[symbol][timeframe] = {
            'data': data.copy(),
            'last_refresh': get_current_time()
        }
        self.stats['refreshes'] += 1
        logger.debug(f"Updated cache for {symbol} {timeframe}: {len(data)} candles")
    
    def preload(self, symbols: list, timeframes: list, periods: int,
               asset_type: str = 'EQUITY') -> None:
        """
        Preload cache for multiple symbols and timeframes.
        
        Args:
            symbols: List of trading symbols
            timeframes: List of timeframes to preload
            periods: Number of periods to load
            asset_type: Asset type
        """
        logger.info(f"Preloading cache for {len(symbols)} symbols, {len(timeframes)} timeframes")
        
        total = len(symbols) * len(timeframes)
        count = 0
        
        for symbol in symbols:
            for timeframe in timeframes:
                count += 1
                logger.debug(f"Preloading {symbol} {timeframe} ({count}/{total})")
                self.get_historical(symbol, timeframe, periods, asset_type)
        
        logger.info(f"Cache preload complete: {self.get_statistics()}")
    
    def refresh_symbol(self, symbol: str, timeframe: str, periods: int,
                      asset_type: str = 'EQUITY') -> pd.DataFrame:
        """
        Force refresh cache for a symbol.
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe
            periods: Number of periods
            asset_type: Asset type
            
        Returns:
            Refreshed DataFrame
        """
        with self.lock:
            logger.debug(f"Force refresh cache for {symbol} {timeframe}")
            
            # Invalidate cache
            if symbol in self.cache and timeframe in self.cache[symbol]:
                del self.cache[symbol][timeframe]
            
            # Fetch fresh data
            return self.get_historical(symbol, timeframe, periods, asset_type)
    
    def clear_cache(self) -> None:
        """Clear entire cache."""
        with self.lock:
            self.cache.clear()
            logger.info("Cache cleared")
    
    def clear_symbol(self, symbol: str) -> None:
        """
        Clear cache for specific symbol.
        
        Args:
            symbol: Trading symbol to clear
        """
        with self.lock:
            if symbol in self.cache:
                del self.cache[symbol]
                logger.info(f"Cleared cache for {symbol}")
    
    def get_statistics(self) -> Dict:
        """
        Get cache statistics.
        
        Returns:
            Statistics dictionary
        """
        with self.lock:
            total_requests = self.stats['hits'] + self.stats['misses']
            hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
            
            cached_symbols = len(self.cache)
            total_cached_entries = sum(len(timeframes) for timeframes in self.cache.values())
            
            return {
                'cache_hits': self.stats['hits'],
                'cache_misses': self.stats['misses'],
                'hit_rate_percent': round(hit_rate, 2),
                'db_queries': self.stats['db_queries'],
                'refreshes': self.stats['refreshes'],
                'cached_symbols': cached_symbols,
                'cached_entries': total_cached_entries,
                'refresh_interval_seconds': self.refresh_interval.total_seconds()
            }
