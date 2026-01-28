"""
Market Data Runner for AlphaStock Trading System

This component continuously collects market data for all configured stocks
at a specified frequency during market hours.
"""

import logging
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import threading
import pandas as pd

from ..utils.logger_setup import setup_logger
from ..utils.market_hours import is_market_open
from ..utils.timezone_utils import get_current_time, is_market_hours

logger = setup_logger("market_data_runner")


class MarketDataRunner:
    """
    Continuously collects market data for all configured symbols.
    
    Runs at configurable frequency (default 5 seconds) and stores data
    in cache for strategies to consume.
    """
    
    def __init__(self, api_client, data_cache, symbols: List[str], interval_seconds: int = 5, data_layer=None):
        """
        Initialize Market Data Runner.
        
        Args:
            api_client: Kite API client for fetching market data
            data_cache: Cache for storing data
            symbols: List of symbols to monitor
            interval_seconds: Data collection frequency in seconds
            data_layer: Optional data layer for database storage
        """
        self.api_client = api_client
        self.data_cache = data_cache
        self.data_layer = data_layer
        self.symbols = symbols
        self.interval_seconds = interval_seconds
        
        # Runtime state
        self.is_running = False
        self.runner_thread = None
        self.last_update_time = {}
        self.error_counts = {}
        self._initial_data_loaded = False
        
        # Data callbacks
        self.callbacks = []
        
        # Statistics
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_updates': 0,
            'successful_updates': 0,
            'failed_updates': 0,
            'last_success_time': None,
            'last_error_time': None,
            'last_successful_update': None
        }
        
        # Alias for backward compatibility
        self.frequency = self.interval_seconds
        
        logger.info(f"Market Data Runner initialized for {len(self.symbols)} symbols")
        logger.info(f"Collection frequency: {self.interval_seconds} seconds")
    
    def add_callback(self, callback):
        """
        Add a callback function that will be called when new data is available.
        
        Args:
            callback: Function that takes (symbol, data) as parameters
        """
        self.callbacks.append(callback)
        logger.debug(f"Added data callback: {callback.__name__ if hasattr(callback, '__name__') else 'anonymous'}")
    
    def add_data_callback(self, callback):
        """Alias for add_callback for backward compatibility."""
        return self.add_callback(callback)
    
    def remove_data_callback(self, callback):
        """Remove a data callback."""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
            logger.debug(f"Removed data callback: {callback.__name__}")
    
    async def _clear_old_market_data(self):
        """Clear old market data from database, keeping only today's data."""
        if not self.data_layer:
            logger.warning("No data layer available, skipping market_data cleanup")
            return
        
        try:
            today = get_current_time().date()
            logger.info(f"Clearing market_data older than {today}...")
            
            # Use ALTER TABLE ... DELETE for ClickHouse (mutation)
            # This is the proper way to delete data in ClickHouse
            query = f"ALTER TABLE market_data DELETE WHERE toDate(timestamp) < '{today}'"
            
            # Execute the mutation
            result = await self.data_layer.execute_query(query)
            
            logger.info(f"Successfully cleared old market_data (older than {today})")
        except Exception as e:
            logger.error(f"Error clearing old market_data: {e}")
            logger.warning("Continuing with data collection despite cleanup error")
    
    async def _fetch_intraday_historical_data(self):
        """
        Fetch historical intraday data from market open (9:15 AM) to current time.
        This ensures we have complete data even if agent starts mid-day.
        """
        if not self.data_layer:
            logger.warning("No data layer available, skipping historical data fetch")
            return
        
        try:
            from ..utils.market_hours import is_market_open
            
            # Check if market is open
            if not is_market_open():
                logger.info("Market is closed, skipping intraday historical data fetch")
                return
            
            # Market opens at 9:15 AM IST
            today = get_current_time().date()
            market_open_time = datetime.combine(today, datetime.strptime("09:15", "%H:%M").time())
            current_time = get_current_time()
            
            # Only fetch if we're past market open
            if current_time < market_open_time:
                logger.info("Market hasn't opened yet, skipping historical data fetch")
                return
            
            logger.info(f"Fetching intraday data from {market_open_time} to {current_time} for {len(self.symbols)} symbols...")
            
            # Fetch historical data for each symbol
            for symbol in self.symbols:
                try:
                    logger.debug(f"Fetching intraday data for {symbol}...")
                    
                    # Fetch 1-minute data from market open to now
                    historical_df = await self.api_client.get_historical_data(
                        symbol=symbol,
                        from_date=market_open_time,
                        to_date=current_time,
                        interval="minute"  # 1-minute data
                    )
                    
                    if historical_df.empty:
                        logger.warning(f"No historical data received for {symbol}")
                        continue
                    
                    # Convert historical data to market_data format
                    market_data_records = []
                    for _, row in historical_df.iterrows():
                        record = {
                            'timestamp': row['timestamp'],
                            'open': row['open'],
                            'high': row['high'],
                            'low': row['low'],
                            'close': row['close'],
                            'ltp': row['close'],  # Use close as LTP for historical
                            'volume': row.get('volume', 0),
                            'turnover': 0.0,
                            'price_change': 0.0,
                            'price_change_pct': 0.0,
                            'volatility': 0.0,
                            'bid_price': 0.0,
                            'ask_price': 0.0,
                            'bid_size': 0,
                            'ask_size': 0,
                            'metadata': ''
                        }
                        market_data_records.append(record)
                    
                    # Convert to DataFrame and store
                    if market_data_records:
                        df = pd.DataFrame(market_data_records)
                        success = await self.data_layer.store_market_data(
                            symbol=symbol,
                            asset_type='EQUITY',
                            data=df,
                            runner_name='market_data_runner'
                        )
                        
                        if success:
                            logger.info(f"Stored {len(market_data_records)} historical records for {symbol}")
                        else:
                            logger.warning(f"Failed to store historical data for {symbol}")
                    
                except Exception as e:
                    logger.error(f"Error fetching historical data for {symbol}: {e}")
            
            logger.info("Completed intraday historical data fetch")
            
        except Exception as e:
            logger.error(f"Error in intraday historical data fetch: {e}")
    
    def start_collection(self):
        """Start the data collection process."""
        if self.is_running:
            logger.warning("Market Data Runner is already running")
            return
        
        self.is_running = True
        self.stats['start_time'] = get_current_time()
        
        # Start in a separate thread
        self.runner_thread = threading.Thread(target=self._run_collection_loop, daemon=True)
        self.runner_thread.start()
        
        logger.info("Market Data Runner started")
    
    def stop_collection(self):
        """Stop the data collection process."""
        if not self.is_running:
            logger.warning("Market Data Runner is not running")
            return
        
        self.is_running = False
        
        if self.runner_thread and self.runner_thread.is_alive():
            self.runner_thread.join(timeout=5)
        
        logger.info("Market Data Runner stopped")
    
    def start(self):
        """Alias for start_collection() for consistency with other runners."""
        return self.start_collection()
    
    def stop(self):
        """Alias for stop_collection() for consistency with other runners."""
        return self.stop_collection()
    
    def _run_collection_loop(self):
        """Main collection loop that runs in a separate thread."""
        logger.info("Market Data Runner collection loop started")
        
        # Initialize data on first run (clear old data and fetch intraday historical)
        if not self._initial_data_loaded and self.data_layer:
            try:
                logger.info("Performing initial data setup...")
                
                # Create new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Clear old market_data (keep only today's data)
                loop.run_until_complete(self._clear_old_market_data())
                
                # Fetch intraday historical data from market open to now
                loop.run_until_complete(self._fetch_intraday_historical_data())
                
                self._initial_data_loaded = True
                logger.info("Initial data setup completed successfully")
                
            except Exception as e:
                logger.error(f"Error in initial data setup: {e}")
                # Continue anyway with real-time collection
        
        while self.is_running:
            start_time = time.time()
            
            try:
                # Check if market is open before collecting data
                if not is_market_open():
                    logger.debug("Market is closed, skipping data collection")
                    # Sleep longer when market is closed to avoid unnecessary checks
                    time.sleep(60)  # Check every minute when market is closed
                    continue
                
                # Collect data for all symbols (only during market hours)
                self._collect_batch_data()
                
                # Update statistics
                self.stats['total_updates'] += 1
                self.stats['successful_updates'] += 1
                self.stats['last_successful_update'] = get_current_time()
                
            except Exception as e:
                logger.error(f"Error in market data collection loop: {e}")
                self.stats['failed_updates'] += 1
            
            # Calculate sleep time to maintain frequency
            elapsed_time = time.time() - start_time
            sleep_time = max(0, self.interval_seconds - elapsed_time)
            
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        logger.info("Market Data Runner collection loop ended")
    
    def _collect_batch_data(self):
        """Collect data for all symbols in batch."""
        if not self.symbols:
            return
        
        try:
            # Use Kite API to get comprehensive quote data for all symbols
            quote_data = self.api_client.get_quote(self.symbols)
            
            if not quote_data:
                logger.warning("No market data received from API")
                return
            
            current_time = get_current_time()
            
            # Process each symbol's data
            for symbol, raw_quote in quote_data.items():
                try:
                    ohlc = raw_quote.get('ohlc', {})
                    last_price = raw_quote.get('last_price', 0)
                    
                    # Create DataFrame with current data matching database schema
                    market_data = pd.DataFrame([{
                        'timestamp': current_time,
                        'open': ohlc.get('open', 0),
                        'high': ohlc.get('high', 0),
                        'low': ohlc.get('low', 0),
                        'close': ohlc.get('close', 0),
                        'ltp': last_price,  # Match database column name
                        'volume': raw_quote.get('volume', 0),
                        'turnover': raw_quote.get('turnover', 0),
                        'price_change': raw_quote.get('change', 0),
                        'price_change_pct': raw_quote.get('change_percent', 0),
                        'volatility': 0.0,  # Can be calculated later
                        'bid_price': raw_quote.get('depth', {}).get('buy', [{}])[0].get('price', 0) if raw_quote.get('depth') else 0,
                        'ask_price': raw_quote.get('depth', {}).get('sell', [{}])[0].get('price', 0) if raw_quote.get('depth') else 0,
                        'bid_size': raw_quote.get('depth', {}).get('buy', [{}])[0].get('quantity', 0) if raw_quote.get('depth') else 0,
                        'ask_size': raw_quote.get('depth', {}).get('sell', [{}])[0].get('quantity', 0) if raw_quote.get('depth') else 0,
                    }])
                    
                    # Store in cache
                    cache_key = f"market_data:{symbol}"
                    
                    # Get existing data from cache
                    existing_data = self.data_cache.get(cache_key)
                    if existing_data is not None and isinstance(existing_data, pd.DataFrame):
                        # Append new data
                        combined_data = pd.concat([existing_data, market_data], ignore_index=True)
                        # Keep only last 100 records to manage memory
                        if len(combined_data) > 100:
                            combined_data = combined_data.tail(100)
                    else:
                        combined_data = market_data
                    
                    # Update cache
                    self.data_cache.set(cache_key, combined_data, ttl=300)  # 5 minute TTL
                    
                    # Store in database if data_layer is available
                    if self.data_layer:
                        try:
                            # Use asyncio to run the async store method in this thread
                            import asyncio
                            try:
                                loop = asyncio.get_event_loop()
                            except RuntimeError:
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                            
                            # Run the async method
                            if loop.is_running():
                                # If loop is already running, use run_coroutine_threadsafe
                                import concurrent.futures
                                future = asyncio.run_coroutine_threadsafe(
                                    self.data_layer.store_market_data(
                                        symbol=symbol,
                                        asset_type='EQUITY',  # Default to EQUITY, could be made configurable
                                        data=market_data,
                                        runner_name='market_data_runner'
                                    ),
                                    loop
                                )
                                future.result(timeout=5)  # Wait up to 5 seconds
                            else:
                                # Loop not running, use run_until_complete
                                loop.run_until_complete(
                                    self.data_layer.store_market_data(
                                        symbol=symbol,
                                        asset_type='EQUITY',
                                        data=market_data,
                                        runner_name='market_data_runner'
                                    )
                                )
                            logger.debug(f"Stored {symbol} data in database")
                        except Exception as e:
                            logger.error(f"Error storing {symbol} data in database: {e}")
                    
                    # Update statistics
                    self.last_update_time[symbol] = current_time
                    self.error_counts[symbol] = 0  # Reset error count on success
                    
                    # Notify callbacks
                    for callback in self.callbacks:
                        try:
                            callback(symbol, combined_data)
                        except Exception as e:
                            logger.error(f"Error in callback for {symbol}: {e}")
                    
                    # Update stats
                    self.stats['successful_requests'] += 1
                
                except Exception as e:
                    logger.error(f"Error processing data for {symbol}: {e}")
                    self._handle_symbol_error(symbol)
            
            self.stats['last_success_time'] = current_time
            logger.info(f"Successfully collected and stored data for {len(quote_data)} symbols")
        
        except Exception as e:
            logger.error(f"Error in batch data collection: {e}")
            self.stats['failed_requests'] += 1
            self.stats['last_error_time'] = get_current_time()
    
    def _handle_symbol_error(self, symbol: str):
        """Handle errors for individual symbols."""
        self.error_counts[symbol] = self.error_counts.get(symbol, 0) + 1
        
        if self.error_counts[symbol] > 5:  # After 5 consecutive errors
            logger.warning(f"Too many errors for {symbol}, temporarily skipping")
            # Could implement logic to temporarily skip problematic symbols
            logger.warning("No symbols configured for data collection")
            return
        
        try:
            # Get market data for all symbols at once
            market_data = self._fetch_market_data_batch(self.symbols)
            
            if not market_data:
                logger.warning("No market data received")
                return
            
            # Process each symbol's data
            for symbol, data in market_data.items():
                if data:
                    self._process_symbol_data(symbol, data)
                else:
                    self._handle_symbol_error(symbol)
            
        except Exception as e:
            logger.error(f"Error in batch data collection: {e}")
            raise
    
    def _fetch_market_data_batch(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Fetch market data for multiple symbols.
        
        Args:
            symbols: List of symbols to fetch data for
            
        Returns:
            Dictionary of symbol -> market data
        """
        market_data = {}
        
        for attempt in range(self.retry_attempts):
            try:
                # Use API client to get comprehensive quote data
                if hasattr(self.api_client, 'get_quote'):
                    # Get comprehensive quote data (includes OHLC, LTP, volume, etc.)
                    quote_response = self.api_client.get_quote(symbols)
                    if quote_response:
                        for symbol, quote_data in quote_response.items():
                            ohlc = quote_data.get('ohlc', {})
                            formatted_data = {
                                'symbol': symbol,
                                'timestamp': get_current_time(),
                                'open': ohlc.get('open', 0),
                                'high': ohlc.get('high', 0),
                                'low': ohlc.get('low', 0),
                                'close': ohlc.get('close', 0),
                                'last_price': quote_data.get('last_price', 0),
                                'ltp': quote_data.get('last_price', 0),
                                'volume': quote_data.get('volume', 0),
                                'average_price': quote_data.get('average_price', 0)
                            }
                            market_data[symbol] = formatted_data
                
                if market_data:
                    break  # Success, exit retry loop
                    
            except Exception as e:
                logger.error(f"API call attempt {attempt + 1} failed: {e}")
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"All API call attempts failed for batch data collection")
        
        return market_data
    
    def _extract_symbol_from_response(self, data_item: Dict[str, Any]) -> Optional[str]:
        """Extract symbol from API response data item."""
        # This depends on the API response format
        # Adjust based on actual MStock API response
        return data_item.get('symbol') or data_item.get('tradingsymbol')
    
    def _format_market_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format raw API data into standard market data structure.
        
        Args:
            raw_data: Raw data from API
            
        Returns:
            Formatted market data dictionary
        """
        current_time = get_current_time()
        
        # Extract standard OHLCV data from API response
        # Adjust field names based on actual MStock API response
        formatted_data = {
            'timestamp': current_time,
            'open': float(raw_data.get('open', 0)),
            'high': float(raw_data.get('high', 0)),
            'low': float(raw_data.get('low', 0)),
            'close': float(raw_data.get('ltp', 0)),  # Use LTP as close
            'volume': int(raw_data.get('volume', 0)),
            'ltp': float(raw_data.get('ltp', 0)),
            'change': float(raw_data.get('change', 0)),
            'change_percent': float(raw_data.get('change_percent', 0))
        }
        
        return formatted_data
    
    def _process_symbol_data(self, symbol: str, data: Dict[str, Any]):
        """
        Process and store data for a specific symbol.
        
        Args:
            symbol: Trading symbol
            data: Market data dictionary
        """
        try:
            # Store in cache if available
            if self.data_cache:
                cache_key = f"market:{symbol}"
                self.data_cache.set(cache_key, data)
            
            # Update last update time
            self.last_update_time[symbol] = get_current_time()
            
            # Reset error count for this symbol
            if symbol in self.error_counts:
                self.error_counts[symbol] = 0
            
            # Call registered callbacks
            for callback in self.data_callbacks:
                try:
                    callback(symbol, data)
                except Exception as e:
                    logger.error(f"Error in data callback {callback.__name__} for {symbol}: {e}")
            
            logger.debug(f"Processed market data for {symbol}: LTP={data.get('ltp', 'N/A')}")
            
        except Exception as e:
            logger.error(f"Error processing data for {symbol}: {e}")
    
    def _handle_symbol_error(self, symbol: str):
        """Handle error for a specific symbol."""
        self.error_counts[symbol] = self.error_counts.get(symbol, 0) + 1
        
        if self.error_counts[symbol] >= 5:
            logger.warning(f"Symbol {symbol} has failed {self.error_counts[symbol]} times")
    
    def get_latest_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get the latest market data for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Latest market data or None if not available
        """
        if not self.data_cache:
            logger.warning("No data cache available")
            return None
        
        cache_key = f"market:{symbol}"
        return self.data_cache.get(cache_key)
    
    def get_symbols(self) -> List[str]:
        """Get list of symbols being tracked."""
        return self.symbols.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get collection statistics.
        
        Returns:
            Dictionary with statistics
        """
        stats = self.stats.copy()
        
        if stats['start_time']:
            stats['uptime_seconds'] = (get_current_time() - stats['start_time']).total_seconds()
        
        if stats['total_updates'] > 0:
            stats['success_rate'] = stats['successful_updates'] / stats['total_updates']
        else:
            stats['success_rate'] = 0.0
        
        stats['is_running'] = self.is_running
        stats['symbols_count'] = len(self.symbols)
        stats['frequency_seconds'] = self.frequency
        
        return stats
    
    def is_data_fresh(self, symbol: str, max_age_seconds: int = 30) -> bool:
        """
        Check if data for a symbol is fresh (within max_age_seconds).
        
        Args:
            symbol: Trading symbol
            max_age_seconds: Maximum age in seconds
            
        Returns:
            True if data is fresh, False otherwise
        """
        if symbol not in self.last_update_time:
            return False
        
        age = (get_current_time() - self.last_update_time[symbol]).total_seconds()
        return age <= max_age_seconds
    
    def __str__(self):
        """String representation of the Market Data Runner."""
        return f"MarketDataRunner(symbols={len(self.symbols)}, freq={self.frequency}s, running={self.is_running})"
