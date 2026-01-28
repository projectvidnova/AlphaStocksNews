"""
Historical Data Manager for AlphaStock Trading System

Manages long-term historical data for backtesting and analysis.
Handles data fetching, storage, and validation with configurable retention policies.
"""

import asyncio
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Tuple
import json
from pathlib import Path

from ..api.kite_client import KiteAPIClient
from ..data import DataLayerInterface
from ..utils.logger_setup import setup_logger
from ..utils.timezone_utils import get_current_time, to_ist, to_utc, is_market_hours


class HistoricalDataManager:
    """
    Manages historical data collection, storage, and analysis.
    
    Features:
    - Automatic data gap detection and filling
    - Configurable retention policies
    - Data validation and quality checks
    - Bulk data operations for performance
    - Analysis-ready data formatting
    """
    
    def __init__(self, api_client: KiteAPIClient, data_layer: DataLayerInterface, config: Dict[str, Any] = None):
        """
        Initialize Historical Data Manager.
        
        Args:
            api_client: Kite API client for data fetching
            data_layer: Data storage layer
            config: Configuration dictionary
        """
        self.api_client = api_client
        self.data_layer = data_layer
        self.config = config or {}
        self.logger = setup_logger("HistoricalDataManager")
        
        # Configuration
        self.default_retention_years = self.config.get('historical_data', {}).get('retention_years', 2)
        self.default_timeframes = self.config.get('historical_data', {}).get('timeframes', ['1minute', '5minute', '15minute', '1day'])
        self.batch_size = self.config.get('historical_data', {}).get('batch_size', 1000)
        self.max_api_calls_per_minute = self.config.get('historical_data', {}).get('max_api_calls_per_minute', 100)
        
        # Priority symbols configuration
        self.priority_symbols = {
            'NIFTY BANK': {
                'exchange': 'NSE',
                'asset_type': 'INDEX',
                'priority': 1,
                'timeframes': ['1minute', '5minute', '15minute', '1day'],
                'retention_years': 3
            },
            'NIFTY 50': {
                'exchange': 'NSE',
                'asset_type': 'INDEX',
                'priority': 2,
                'timeframes': ['5minute', '15minute', '1day'],
                'retention_years': 3
            },
            'SBIN': {
                'exchange': 'NSE',
                'asset_type': 'EQUITY',
                'priority': 3,
                'timeframes': ['15minute', '1day'],
                'retention_years': 2
            },
            'RELIANCE': {
                'exchange': 'NSE',
                'asset_type': 'EQUITY',
                'priority': 3,
                'timeframes': ['15minute', '1day'],
                'retention_years': 2
            }
        }
        
        # API rate limiting
        self.api_call_count = 0
        self.api_call_reset_time = get_current_time()
    
    async def ensure_historical_data(self, symbol: str, asset_type: str = None, 
                                   timeframes: List[str] = None, years_back: int = None) -> Dict[str, bool]:
        """
        Ensure historical data exists for a symbol, fetch if missing.
        
        Args:
            symbol: Symbol to check
            asset_type: Asset type (EQUITY, INDEX, etc.)
            timeframes: List of timeframes to check
            years_back: Number of years of data to maintain
            
        Returns:
            Dict mapping timeframe to success status
        """
        self.logger.info(f"Ensuring historical data for {symbol}")
        
        # Get symbol configuration
        symbol_config = self.priority_symbols.get(symbol, {})
        asset_type = asset_type or symbol_config.get('asset_type', 'EQUITY')
        timeframes = timeframes or symbol_config.get('timeframes', self.default_timeframes)
        years_back = years_back or symbol_config.get('retention_years', self.default_retention_years)
        
        results = {}
        
        for timeframe in timeframes:
            try:
                # Check existing data
                data_status = await self._check_data_completeness(symbol, timeframe, years_back)
                
                if data_status['is_complete']:
                    self.logger.info(f"{symbol} {timeframe}: Data is complete ({data_status['records']} records)")
                    results[timeframe] = True
                else:
                    # Calculate days to fetch
                    days_to_fetch = (data_status['end_date'] - data_status['start_date']).days
                    self.logger.info(f"{symbol} {timeframe}: Missing data from {data_status['start_date']} to {data_status['end_date']} ({days_to_fetch} days)")
                    
                    # Fetch missing data
                    success = await self._fetch_and_store_historical_data(
                        symbol, asset_type, timeframe, 
                        data_status['start_date'], data_status['end_date']
                    )
                    results[timeframe] = success
                    
            except Exception as e:
                self.logger.error(f"Error ensuring data for {symbol} {timeframe}: {e}")
                results[timeframe] = False
        
        return results
    
    def _get_last_trading_day(self) -> date:
        """
        Get the last trading day (excludes weekends and today).
        
        Returns the most recent date that should have complete historical data:
        - If today is Monday-Friday and market hours have passed, returns yesterday (unless weekend)
        - Automatically skips weekends
        - Does not account for holidays (API will return empty for those)
        
        Returns:
            Last trading day as date object
        """
        current_date = date.today()
        current_time = get_current_time().time()
        
        # Market closes at 3:30 PM IST
        # If current time is after 4:00 PM, we can consider yesterday's data complete
        market_close_time = datetime.strptime("16:00", "%H:%M").time()
        
        # Start from yesterday (today's data is never complete until after close)
        last_trading_day = current_date - timedelta(days=1)
        
        # Skip backwards over weekends
        while last_trading_day.weekday() >= 5:  # 5=Saturday, 6=Sunday
            last_trading_day = last_trading_day - timedelta(days=1)
        
        day_name = last_trading_day.strftime("%A")
        self.logger.debug(f"Last trading day calculated as: {last_trading_day} ({day_name})")
        
        return last_trading_day
    
    async def _check_data_completeness(self, symbol: str, timeframe: str, years_back: int) -> Dict[str, Any]:
        """
        Check if historical data is complete for a symbol.
        
        This method checks the most recent date in existing data and determines
        if we need to fetch data from that date to the last trading day. We use the
        last trading day (skipping weekends) because:
        1. Today's data is incomplete until market close
        2. Weekends have no trading data
        3. This avoids unnecessary API calls for non-trading days
        
        Note: Holidays are not detected here - the API will simply return empty data
        for those days, which is expected behavior.
        """
        # Get the last trading day (automatically skips weekends and today)
        end_date = self._get_last_trading_day()
        start_date = end_date - timedelta(days=years_back * 365)
        
        try:
            # Get existing data from database - just check the latest records
            existing_data = await self.data_layer.get_historical_data(symbol, timeframe, start_date, end_date)
            
            if existing_data is None or existing_data.empty:
                self.logger.debug(f"No existing data found for {symbol} {timeframe}")
                return {
                    'is_complete': False,
                    'records': 0,
                    'start_date': start_date,
                    'end_date': end_date,
                    'last_date': None
                }
            
            self.logger.info(f"Found {len(existing_data)} existing records for {symbol} {timeframe}")
            
            # Determine the timestamp column name (could be 'timestamp', 'date', or 'time')
            timestamp_col = None
            for col in ['timestamp', 'date', 'time']:
                if col in existing_data.columns:
                    timestamp_col = col
                    break
            
            if timestamp_col is None:
                self.logger.error(f"No timestamp column found in data. Columns: {list(existing_data.columns)}")
                # Assume data exists but we can't check completeness - fetch from retention start
                return {
                    'is_complete': False,
                    'records': len(existing_data),
                    'start_date': start_date,
                    'end_date': end_date,
                    'last_date': None
                }
            
            # Find the most recent date in existing data
            existing_data['date'] = pd.to_datetime(existing_data[timestamp_col]).dt.date
            latest_date = existing_data['date'].max()
            
            # Calculate days since latest data
            days_since_latest = (end_date - latest_date).days
            
            # Add day of week info for better understanding
            today_name = date.today().strftime("%A")
            end_date_name = end_date.strftime("%A")
            latest_date_name = latest_date.strftime("%A")
            
            self.logger.info(
                f"{symbol} {timeframe}: Latest data from {latest_date} ({latest_date_name}), "
                f"{days_since_latest} days ago. Target end_date: {end_date} ({end_date_name}), "
                f"Today: {date.today()} ({today_name})"
            )
            
            # Check if we need to fetch new data
            # Consider data complete if latest data is from the target end date (last trading day)
            if days_since_latest <= 0:
                self.logger.info(f"{symbol} {timeframe}: Data is up-to-date ({len(existing_data)} records)")
                return {
                    'is_complete': True,
                    'records': len(existing_data),
                    'start_date': start_date,
                    'end_date': end_date,
                    'last_date': latest_date
                }
            
            # Data is outdated - we need to fetch from the day after latest_date to today
            fetch_start_date = latest_date + timedelta(days=1)
            
            self.logger.info(f"{symbol} {timeframe}: Missing data from {fetch_start_date} to {end_date}")
            
            return {
                'is_complete': False,
                'records': len(existing_data),
                'start_date': fetch_start_date,  # Only fetch from after the latest data
                'end_date': end_date,
                'last_date': latest_date
            }
            
        except Exception as e:
            self.logger.error(f"Error checking data completeness for {symbol} {timeframe}: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return {
                'is_complete': False,
                'records': 0,
                'start_date': start_date,
                'end_date': end_date,
                'last_date': None
            }
    
    async def _fetch_and_store_historical_data(self, symbol: str, asset_type: str, 
                                             timeframe: str, start_date: date, end_date: date) -> bool:
        """Fetch and store historical data from API."""
        try:
            self.logger.info(f"Fetching historical data for {symbol} {timeframe} from {start_date} to {end_date}")
            
            if not self.api_client:
                self.logger.error("API client not available")
                return False
            
            # Rate limiting check
            await self._check_rate_limits()
            
            # Convert timeframe for Kite API
            kite_interval = self._convert_timeframe_to_kite(timeframe)
            
            # Fetch data in chunks to avoid API limits
            all_data = []
            current_start = start_date
            
            # Convert dates to datetime for API calls (include full day)
            # When fetching data, we need to ensure the end datetime is AFTER the start
            # For a single day (e.g., Oct 8 to Oct 8), we fetch from start of Oct 8 to start of Oct 9
            while current_start <= end_date:
                # Calculate chunk end date (30 days max per request)
                chunk_end = min(current_start + timedelta(days=30), end_date)
                
                # Convert to datetime objects with time components
                # Start: Beginning of the day (00:00:00)
                # End: Beginning of next day (00:00:00) to include full day
                from_datetime = datetime.combine(current_start, datetime.min.time())
                to_datetime = datetime.combine(chunk_end + timedelta(days=1), datetime.min.time())
                
                try:
                    # Get historical data from Kite API
                    self.logger.debug(
                        f"API call: get_historical_data(symbol={symbol}, "
                        f"from={from_datetime.date()} 00:00, to={to_datetime.date()} 00:00, "
                        f"interval={kite_interval}) - Fetching {(chunk_end - current_start).days + 1} day(s)"
                    )
                    
                    historical_data = await self.api_client.get_historical_data(
                        symbol=symbol,
                        from_date=from_datetime,
                        to_date=to_datetime,
                        interval=kite_interval
                    )
                    
                    if historical_data is not None and not historical_data.empty:
                        # Add metadata
                        historical_data['symbol'] = symbol
                        historical_data['asset_type'] = asset_type
                        historical_data['timeframe'] = timeframe
                        all_data.append(historical_data)
                        
                        self.logger.info(
                            f"[SUCCESS] Fetched {len(historical_data)} records for {symbol} "
                            f"from {current_start} to {chunk_end} (requested: {from_datetime.date()} to {to_datetime.date()})"
                        )
                    else:
                        self.logger.warning(
                            f"[NO DATA] No data returned from API for {symbol} {current_start} to {chunk_end} "
                            f"(requested: {from_datetime.date()} to {to_datetime.date()}) - "
                            f"Data might not be available yet (typical 1-day delay)"
                        )
                    
                    # Update API call tracking
                    self.api_call_count += 1
                    
                    # Rate limiting delay
                    await asyncio.sleep(0.6)  # 100 calls per minute = 0.6s delay
                    
                except Exception as e:
                    self.logger.error(
                        f"[ERROR] Error fetching data chunk {current_start} to {chunk_end}: {e}"
                    )
                
                current_start = chunk_end + timedelta(days=1)
            
            if not all_data:
                self.logger.warning(
                    f"No historical data fetched for {symbol} from {start_date} to {end_date}. "
                    f"This is normal if: (1) Data not yet available from exchange (typical 1-day delay), "
                    f"(2) Market holiday, or (3) Symbol name mismatch"
                )
                return False
            
            # Combine all data
            combined_data = pd.concat(all_data, ignore_index=True)
            
            # Data validation and cleaning
            combined_data = self._clean_and_validate_data(combined_data)
            
            # Store in database
            success = await self.data_layer.store_historical_data(symbol, asset_type, combined_data, timeframe)
            
            if success:
                self.logger.info(f"Successfully stored {len(combined_data)} historical records for {symbol} {timeframe}")
            else:
                self.logger.error(f"Failed to store historical data for {symbol} {timeframe}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error fetching historical data for {symbol}: {e}")
            return False
    
    def _convert_timeframe_to_kite(self, timeframe: str) -> str:
        """Convert internal timeframe to Kite API format."""
        mapping = {
            '1minute': 'minute',
            '5minute': '5minute',
            '15minute': '15minute',
            '30minute': '30minute',
            '1hour': '60minute',
            '1day': 'day'
        }
        return mapping.get(timeframe, 'day')
    
    def _clean_and_validate_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Clean and validate historical data."""
        if data.empty:
            return data
        
        # Remove duplicates
        initial_len = len(data)
        data = data.drop_duplicates(subset=['timestamp', 'symbol'], keep='last')
        
        # Remove invalid data
        data = data.dropna(subset=['open', 'high', 'low', 'close'])
        data = data[data['high'] >= data['low']]
        data = data[data['high'] >= data['open']]
        data = data[data['high'] >= data['close']]
        data = data[data['low'] <= data['open']]
        data = data[data['low'] <= data['close']]
        data = data[data['volume'] >= 0]
        
        # Sort by timestamp
        data = data.sort_values('timestamp').reset_index(drop=True)
        
        cleaned_len = len(data)
        if initial_len != cleaned_len:
            self.logger.info(f"Data cleaning: {initial_len} -> {cleaned_len} records")
        
        return data
    
    async def _check_rate_limits(self):
        """Check and enforce API rate limits."""
        now = get_current_time()
        
        # Reset counter every minute
        if (now - self.api_call_reset_time).total_seconds() >= 60:
            self.api_call_count = 0
            self.api_call_reset_time = now
        
        # Check if we're approaching the limit
        if self.api_call_count >= self.max_api_calls_per_minute:
            sleep_time = 60 - (now - self.api_call_reset_time).total_seconds()
            if sleep_time > 0:
                self.logger.info(f"Rate limit reached, sleeping for {sleep_time:.1f} seconds")
                await asyncio.sleep(sleep_time)
                self.api_call_count = 0
                self.api_call_reset_time = get_current_time()
    
    async def initialize_priority_symbols(self) -> Dict[str, Dict[str, bool]]:
        """Initialize historical data for all priority symbols."""
        self.logger.info("Initializing historical data for priority symbols")
        
        results = {}
        
        # Sort symbols by priority
        sorted_symbols = sorted(
            self.priority_symbols.items(), 
            key=lambda x: x[1].get('priority', 999)
        )
        
        for symbol, config in sorted_symbols:
            self.logger.info(f"Processing priority symbol: {symbol}")
            
            try:
                symbol_results = await self.ensure_historical_data(
                    symbol=symbol,
                    asset_type=config['asset_type'],
                    timeframes=config['timeframes'],
                    years_back=config['retention_years']
                )
                results[symbol] = symbol_results
                
                # Brief pause between symbols
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error processing {symbol}: {e}")
                results[symbol] = {'error': str(e)}
        
        return results
    
    async def get_analysis_data(self, symbol: str, timeframe: str = '15minute', 
                              days_back: int = 30) -> Optional[pd.DataFrame]:
        """
        Get analysis-ready historical data for a symbol.
        
        Args:
            symbol: Symbol to analyze
            timeframe: Data timeframe
            days_back: Number of days to include
            
        Returns:
            Analysis-ready DataFrame with technical indicators
        """
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days_back)
            
            # Get raw historical data
            data = await self.data_layer.get_historical_data(symbol, timeframe, start_date, end_date)
            
            if data is None or data.empty:
                self.logger.warning(f"No historical data found for {symbol}")
                return None
            
            # Convert to analysis format
            analysis_data = data.copy()
            analysis_data['timestamp'] = pd.to_datetime(analysis_data['timestamp'])
            analysis_data = analysis_data.sort_values('timestamp').reset_index(drop=True)
            
            # Add technical indicators
            analysis_data = self._add_technical_indicators(analysis_data)
            
            self.logger.info(f"Retrieved {len(analysis_data)} records for analysis: {symbol} ({timeframe})")
            return analysis_data
            
        except Exception as e:
            self.logger.error(f"Error getting analysis data for {symbol}: {e}")
            return None
    
    def _add_technical_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Add common technical indicators to the data."""
        if data.empty:
            return data
        
        # Simple Moving Averages
        data['sma_10'] = data['close'].rolling(window=10).mean()
        data['sma_20'] = data['close'].rolling(window=20).mean()
        data['sma_50'] = data['close'].rolling(window=50).mean()
        
        # Exponential Moving Averages
        data['ema_10'] = data['close'].ewm(span=10).mean()
        data['ema_20'] = data['close'].ewm(span=20).mean()
        
        # Volume indicators
        data['volume_sma_20'] = data['volume'].rolling(window=20).mean()
        data['volume_ratio'] = data['volume'] / data['volume_sma_20']
        
        # Price change indicators
        data['price_change'] = data['close'].pct_change()
        data['price_change_5'] = data['close'].pct_change(periods=5)
        
        # Volatility
        data['volatility_10'] = data['price_change'].rolling(window=10).std()
        
        return data
    
    async def cleanup_old_data(self, symbol: str = None) -> Dict[str, int]:
        """Clean up old historical data based on retention policies."""
        self.logger.info("Cleaning up old historical data")
        
        cleanup_results = {}
        
        symbols_to_clean = [symbol] if symbol else list(self.priority_symbols.keys())
        
        for sym in symbols_to_clean:
            config = self.priority_symbols.get(sym, {})
            retention_years = config.get('retention_years', self.default_retention_years)
            
            try:
                # Calculate cutoff date
                cutoff_date = date.today() - timedelta(days=retention_years * 365)
                
                # This would be implemented in the data layer
                deleted_count = await self.data_layer.cleanup_old_data(days_to_keep=retention_years * 365)
                
                cleanup_results[sym] = deleted_count
                self.logger.info(f"Cleaned up {deleted_count} old records for {sym}")
                
            except Exception as e:
                self.logger.error(f"Error cleaning up data for {sym}: {e}")
                cleanup_results[sym] = 0
        
        return cleanup_results
    
    async def generate_data_report(self) -> Dict[str, Any]:
        """Generate a comprehensive data availability report."""
        self.logger.info("Generating historical data report")
        
        report = {
            'timestamp': get_current_time().isoformat(),
            'symbols': {},
            'summary': {
                'total_symbols': 0,
                'total_records': 0,
                'data_quality_score': 0.0
            }
        }
        
        for symbol, config in self.priority_symbols.items():
            symbol_report = {
                'asset_type': config['asset_type'],
                'timeframes': {},
                'quality_score': 0.0
            }
            
            total_records = 0
            quality_scores = []
            
            for timeframe in config['timeframes']:
                try:
                    # Check data status
                    status = await self._check_data_completeness(symbol, timeframe, config['retention_years'])
                    
                    # Calculate days since last update
                    if status['last_date']:
                        days_since_update = (date.today() - status['last_date']).days
                    else:
                        days_since_update = 999
                    
                    # For completeness, consider data complete if up-to-date (within 2 days)
                    completeness = 1.0 if status['is_complete'] else max(0.0, 1.0 - (days_since_update / 365))
                    
                    timeframe_report = {
                        'records': status['records'],
                        'completeness': completeness,
                        'last_update': status['last_date'].isoformat() if status['last_date'] else None,
                        'days_since_update': days_since_update,
                        'is_complete': status['is_complete']
                    }
                    
                    symbol_report['timeframes'][timeframe] = timeframe_report
                    total_records += status['records']
                    quality_scores.append(timeframe_report['completeness'])
                    
                except Exception as e:
                    self.logger.error(f"Error in report for {symbol} {timeframe}: {e}")
                    symbol_report['timeframes'][timeframe] = {'error': str(e)}
            
            # Calculate symbol quality score
            if quality_scores:
                symbol_report['quality_score'] = sum(quality_scores) / len(quality_scores)
            
            report['symbols'][symbol] = symbol_report
            report['summary']['total_records'] += total_records
        
        report['summary']['total_symbols'] = len(self.priority_symbols)
        
        # Calculate overall quality score
        quality_scores = [data['quality_score'] for data in report['symbols'].values() if data['quality_score'] > 0]
        if quality_scores:
            report['summary']['data_quality_score'] = sum(quality_scores) / len(quality_scores)
        
        return report
