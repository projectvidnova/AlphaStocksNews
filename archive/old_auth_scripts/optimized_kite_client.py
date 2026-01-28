"""
Enhanced Kite API Client with Optimizations
Hybrid approach: SDK with performance optimizations and direct API fallbacks
"""

import asyncio
import json
import logging
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass
from functools import wraps
import hashlib

try:
    from kiteconnect import KiteConnect, KiteTicker
    from kiteconnect.exceptions import (
        GeneralException, TokenException, PermissionException,
        OrderException, InputException, DataException, NetworkException
    )
except ImportError:
    print("Kite Connect library not found. Install with: pip install kiteconnect")
    raise

from src.utils.secrets_manager import get_secrets_manager
from src.utils.logger_setup import setup_logger


@dataclass
class MarketData:
    """Market data structure with enhanced fields."""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    ltp: float = None
    change: float = None
    change_percent: float = None


@dataclass 
class CacheEntry:
    """Cache entry with TTL."""
    data: Any
    timestamp: float
    ttl: int
    
    def is_valid(self) -> bool:
        return time.time() < (self.timestamp + self.ttl)


def performance_monitor(func):
    """Decorator to monitor API call performance."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        start_time = time.time()
        try:
            result = func(self, *args, **kwargs)
            duration = time.time() - start_time
            self.logger.debug(f"{func.__name__} completed in {duration:.3f}s")
            
            # Update performance metrics
            if not hasattr(self, '_perf_metrics'):
                self._perf_metrics = {}
            
            if func.__name__ not in self._perf_metrics:
                self._perf_metrics[func.__name__] = {'calls': 0, 'total_time': 0, 'avg_time': 0}
            
            metrics = self._perf_metrics[func.__name__]
            metrics['calls'] += 1
            metrics['total_time'] += duration
            metrics['avg_time'] = metrics['total_time'] / metrics['calls']
            
            return result
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"{func.__name__} failed after {duration:.3f}s: {e}")
            raise
    return wrapper


class OptimizedKiteClient:
    """
    Optimized Kite Connect client with performance enhancements.
    Uses SDK as primary method with direct API fallbacks.
    """
    
    def __init__(self, secrets_manager=None):
        """Initialize the optimized Kite client."""
        self.secrets = secrets_manager or get_secrets_manager()
        self.logger = setup_logger(name="optimized_kite_client", level="INFO")
        
        # Get credentials
        self.creds = self.secrets.get_kite_credentials()
        self.api_key = self.creds['api_key']
        self.api_secret = self.creds['api_secret']
        self.access_token = self.creds['access_token']
        
        # Initialize SDK client
        self.kite = None
        self.ticker = None
        self.authenticated = False
        
        # Direct API session for fallbacks
        self.session = requests.Session()
        self.session.headers.update({
            'X-Kite-Version': '3',
            'User-Agent': 'AlphaStock/1.0'
        })
        
        # Enhanced caching system
        self._cache = {}
        self._cache_stats = {'hits': 0, 'misses': 0, 'hit_rate': 0.0}
        
        # Performance monitoring
        self._perf_metrics = {}
        self._connection_pool_size = 10
        
        # Rate limiting with burst capability
        self._rate_limiter = {
            'tokens': 10,  # Burst tokens
            'max_tokens': 10,
            'refill_rate': 3,  # tokens per second
            'last_refill': time.time()
        }
        
        # Trading configuration
        self.trading_config = self.secrets.get_trading_config()
        self.paper_trading = self.trading_config['paper_trading']
        
        self.logger.info("Optimized Kite client initialized")
    
    async def initialize(self):
        """Initialize with connection pooling optimization."""
        try:
            # Initialize KiteConnect with session reuse
            self.kite = KiteConnect(
                api_key=self.api_key,
                debug=False,
                timeout=10,
                proxies=None,
                pool_maxsize=self._connection_pool_size
            )
            
            if self.access_token:
                self.kite.set_access_token(self.access_token)
                await self._verify_connection_optimized()
            else:
                self.logger.warning("No access token found")
            
            # Preload frequently used data
            await self._preload_cache()
            
            self.logger.info("Optimized Kite client ready")
            
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            raise
    
    def _refill_rate_limiter(self):
        """Smart rate limiter with burst capability."""
        now = time.time()
        elapsed = now - self._rate_limiter['last_refill']
        
        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self._rate_limiter['refill_rate']
        self._rate_limiter['tokens'] = min(
            self._rate_limiter['max_tokens'],
            self._rate_limiter['tokens'] + tokens_to_add
        )
        self._rate_limiter['last_refill'] = now
    
    def _acquire_rate_limit_token(self) -> bool:
        """Acquire a rate limit token."""
        self._refill_rate_limiter()
        
        if self._rate_limiter['tokens'] >= 1:
            self._rate_limiter['tokens'] -= 1
            return True
        return False
    
    def _get_cache_key(self, method: str, *args, **kwargs) -> str:
        """Generate cache key."""
        key_data = f"{method}:{str(args)}:{str(sorted(kwargs.items()))}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Get data from cache."""
        if key in self._cache:
            entry = self._cache[key]
            if entry.is_valid():
                self._cache_stats['hits'] += 1
                self._update_cache_hit_rate()
                return entry.data
            else:
                # Clean expired entry
                del self._cache[key]
        
        self._cache_stats['misses'] += 1
        self._update_cache_hit_rate()
        return None
    
    def _set_cache(self, key: str, data: Any, ttl: int = 300):
        """Set data in cache."""
        self._cache[key] = CacheEntry(
            data=data,
            timestamp=time.time(),
            ttl=ttl
        )
    
    def _update_cache_hit_rate(self):
        """Update cache hit rate statistics."""
        total = self._cache_stats['hits'] + self._cache_stats['misses']
        if total > 0:
            self._cache_stats['hit_rate'] = self._cache_stats['hits'] / total
    
    @performance_monitor
    async def get_historical_data_optimized(
        self, 
        symbol: str, 
        from_date: datetime, 
        to_date: datetime, 
        interval: str = "day"
    ) -> pd.DataFrame:
        """
        Get historical data with intelligent caching and fallback.
        """
        # Generate cache key
        cache_key = self._get_cache_key(
            'historical_data', symbol, from_date.date(), to_date.date(), interval
        )
        
        # Check cache first
        cached_data = self._get_from_cache(cache_key)
        if cached_data is not None:
            self.logger.debug(f"Cache hit for {symbol} historical data")
            return cached_data
        
        # Rate limiting
        if not self._acquire_rate_limit_token():
            await asyncio.sleep(0.5)  # Wait if rate limited
        
        try:
            # Primary: Use SDK
            instrument_token = await self._get_instrument_token(symbol)
            
            data = self.kite.historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval=interval
            )
            
            # Convert to DataFrame with optimizations
            df = pd.DataFrame(data)
            if not df.empty:
                df['symbol'] = symbol
                df['timeframe'] = interval
                # Cache for 5 minutes (longer for daily data)
                cache_ttl = 300 if interval == 'minute' else 3600
                self._set_cache(cache_key, df, cache_ttl)
            
            return df
            
        except Exception as e:
            self.logger.warning(f"SDK failed for {symbol}: {e}")
            # Fallback to direct API
            return await self._get_historical_data_direct_api(
                symbol, from_date, to_date, interval
            )
    
    async def _get_historical_data_direct_api(
        self, 
        symbol: str, 
        from_date: datetime, 
        to_date: datetime, 
        interval: str
    ) -> pd.DataFrame:
        """Fallback direct API implementation."""
        try:
            instrument_token = await self._get_instrument_token(symbol)
            
            url = f"https://api.kite.trade/instruments/historical/{instrument_token}/{interval}"
            params = {
                'from': from_date.strftime('%Y-%m-%d'),
                'to': to_date.strftime('%Y-%m-%d')
            }
            headers = {
                'Authorization': f'token {self.api_key}:{self.access_token}',
                'X-Kite-Version': '3'
            }
            
            response = self.session.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data['status'] == 'success':
                df = pd.DataFrame(data['data']['candles'])
                if not df.empty:
                    df.columns = ['date', 'open', 'high', 'low', 'close', 'volume', 'oi']
                    df['date'] = pd.to_datetime(df['date'])
                    df['symbol'] = symbol
                    df['timeframe'] = interval
                
                return df
            else:
                raise Exception(f"API error: {data.get('message', 'Unknown error')}")
                
        except Exception as e:
            self.logger.error(f"Direct API fallback failed: {e}")
            return pd.DataFrame()  # Return empty DataFrame
    
    @performance_monitor
    async def _get_instrument_token(self, symbol: str) -> int:
        """Get instrument token with caching."""
        cache_key = self._get_cache_key('instrument_token', symbol)
        
        cached_token = self._get_from_cache(cache_key)
        if cached_token is not None:
            return cached_token
        
        try:
            # Get instruments list (cached for 1 hour)
            instruments_key = 'all_instruments'
            instruments = self._get_from_cache(instruments_key)
            
            if instruments is None:
                instruments = self.kite.instruments()
                self._set_cache(instruments_key, instruments, 3600)  # Cache for 1 hour
            
            # Find instrument token
            for instrument in instruments:
                if instrument['tradingsymbol'] == symbol:
                    token = instrument['instrument_token']
                    self._set_cache(cache_key, token, 3600)  # Cache for 1 hour
                    return token
            
            raise ValueError(f"Instrument token not found for {symbol}")
            
        except Exception as e:
            self.logger.error(f"Error getting instrument token for {symbol}: {e}")
            raise
    
    async def _verify_connection_optimized(self):
        """Optimized connection verification."""
        try:
            # Use a lightweight API call
            profile = self.kite.profile()
            self.authenticated = True
            self.logger.info(f"Connected as: {profile.get('user_name', 'Unknown')}")
            
            # Test WebSocket connection
            if hasattr(self, 'ticker') and self.ticker:
                self.logger.info("WebSocket connection ready")
            
        except Exception as e:
            self.logger.error(f"Connection verification failed: {e}")
            self.authenticated = False
            raise
    
    async def _preload_cache(self):
        """Preload frequently used data."""
        try:
            # Preload instruments
            self.logger.info("Preloading instruments cache...")
            instruments = self.kite.instruments()
            self._set_cache('all_instruments', instruments, 3600)
            
            # Preload user profile
            profile = self.kite.profile()
            self._set_cache('user_profile', profile, 1800)
            
            self.logger.info("Cache preloaded successfully")
            
        except Exception as e:
            self.logger.warning(f"Cache preload failed: {e}")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            'api_calls': self._perf_metrics,
            'cache_stats': self._cache_stats,
            'cache_size': len(self._cache),
            'rate_limiter': {
                'tokens_available': self._rate_limiter['tokens'],
                'max_tokens': self._rate_limiter['max_tokens']
            }
        }
    
    def clear_cache(self):
        """Clear all cached data."""
        self._cache.clear()
        self._cache_stats = {'hits': 0, 'misses': 0, 'hit_rate': 0.0}
        self.logger.info("Cache cleared")


# Export the optimized client
__all__ = ['OptimizedKiteClient', 'MarketData']
