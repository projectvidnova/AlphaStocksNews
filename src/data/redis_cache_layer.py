"""
Redis Cache Layer for AlphaStock Trading System

Provides ultra-fast caching for frequently accessed data.
Used in conjunction with primary data storage for optimal performance.
"""

import asyncio
import json
import pickle
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import pandas as pd
import logging

import redis.asyncio as redis
import redis.exceptions

from ..utils.logger_setup import setup_logger
from ..utils.timezone_utils import get_current_time, to_ist, to_utc, is_market_hours


class RedisCacheLayer:
    """
    Redis-based caching layer for high-performance data access.
    
    Provides:
    - Real-time market data caching
    - Symbol lookup caching
    - Strategy result caching
    - Session data management
    """
    
    def __init__(self, host: str = 'localhost', port: int = 6379,
                 db: int = 0, password: Optional[str] = None,
                 max_connections: int = 20):
        """
        Initialize Redis cache layer.
        
        Args:
            host: Redis server host
            port: Redis server port
            db: Redis database number
            password: Redis password (if required)
            max_connections: Maximum connections in pool
        """
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.max_connections = max_connections
        
        self.pool = None
        self.redis = None
        self.logger = setup_logger(name="RedisCacheLayer")
        self._initialized = False
        
        # Cache key prefixes
        self.PREFIXES = {
            'market_data': 'md',
            'latest_data': 'ld',
            'symbols': 'sym',
            'signals': 'sig',
            'options': 'opt',
            'performance': 'perf',
            'session': 'sess',
            'analytics': 'ana'
        }
        
        # Default TTL values (seconds)
        self.TTL = {
            'market_data': 300,      # 5 minutes
            'latest_data': 30,       # 30 seconds
            'symbols': 3600,         # 1 hour
            'signals': 1800,         # 30 minutes
            'options': 180,          # 3 minutes
            'performance': 900,      # 15 minutes
            'session': 86400,        # 24 hours
            'analytics': 600         # 10 minutes
        }
    
    async def initialize(self) -> bool:
        """Initialize Redis connection."""
        try:
            # Create connection pool
            self.pool = redis.ConnectionPool(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                max_connections=self.max_connections,
                decode_responses=False,  # Handle binary data
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Create Redis client
            self.redis = redis.Redis(connection_pool=self.pool)
            
            # Test connection
            await self.redis.ping()
            
            # Set up Redis configuration
            await self._setup_redis_config()
            
            self._initialized = True
            self.logger.info("Redis cache layer initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Redis cache layer: {e}")
            return False
    
    async def close(self):
        """Close Redis connections."""
        try:
            if self.redis:
                await self.redis.aclose()
                self.redis = None
            
            if self.pool:
                await self.pool.aclose()
                self.pool = None
            
            self._initialized = False
            self.logger.info("Redis cache layer closed")
        except Exception as e:
            self.logger.error(f"Error closing Redis cache layer: {e}")
    
    async def _setup_redis_config(self):
        """Set up Redis configuration for optimal performance."""
        try:
            # Configure Redis for better performance
            config_commands = [
                ('maxmemory-policy', 'allkeys-lru'),  # Evict least recently used keys
                ('tcp-keepalive', '60'),              # Keep connections alive
                ('timeout', '0'),                     # No timeout
            ]
            
            for key, value in config_commands:
                try:
                    await self.redis.config_set(key, value)
                except Exception as e:
                    self.logger.debug(f"Could not set Redis config {key}: {e}")
            
            self.logger.debug("Redis configuration optimized")
            
        except Exception as e:
            self.logger.warning(f"Could not optimize Redis configuration: {e}")
    
    def _make_key(self, prefix: str, *args) -> str:
        """Create a standardized cache key."""
        key_parts = [self.PREFIXES.get(prefix, prefix)]
        key_parts.extend(str(arg) for arg in args)
        return ':'.join(key_parts)
    
    async def _serialize_data(self, data: Any) -> bytes:
        """Serialize data for Redis storage."""
        try:
            if isinstance(data, pd.DataFrame):
                # Use pickle for DataFrames (more efficient than JSON)
                return pickle.dumps(data.to_dict('records'))
            elif isinstance(data, pd.Series):
                return pickle.dumps(data.to_dict())
            elif isinstance(data, (dict, list)):
                return json.dumps(data).encode('utf-8')
            else:
                return pickle.dumps(data)
        except Exception as e:
            self.logger.error(f"Error serializing data: {e}")
            return pickle.dumps(data)
    
    async def _deserialize_data(self, data: bytes, data_type: str = 'auto') -> Any:
        """Deserialize data from Redis."""
        try:
            if data_type == 'json':
                return json.loads(data.decode('utf-8'))
            elif data_type == 'dataframe':
                records = pickle.loads(data)
                return pd.DataFrame(records)
            else:
                # Auto-detect or use pickle
                try:
                    return pickle.loads(data)
                except:
                    return json.loads(data.decode('utf-8'))
        except Exception as e:
            self.logger.error(f"Error deserializing data: {e}")
            return None
    
    # Market Data Caching
    async def cache_market_data(self, symbol: str, data: pd.DataFrame, 
                               asset_type: str = '') -> bool:
        """Cache market data for a symbol."""
        try:
            if not self._initialized or data.empty:
                return False
            
            key = self._make_key('market_data', symbol, asset_type)
            serialized_data = await self._serialize_data(data)
            
            await self.redis.setex(
                key, 
                self.TTL['market_data'], 
                serialized_data
            )
            
            # Also cache the latest data point separately for faster access
            if not data.empty:
                latest_key = self._make_key('latest_data', symbol)
                latest_data = await self._serialize_data(data.iloc[-1])
                await self.redis.setex(
                    latest_key,
                    self.TTL['latest_data'],
                    latest_data
                )
            
            self.logger.debug(f"Cached market data for {symbol}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error caching market data for {symbol}: {e}")
            return False
    
    async def get_cached_market_data(self, symbol: str, 
                                   asset_type: str = '') -> Optional[pd.DataFrame]:
        """Retrieve cached market data for a symbol."""
        try:
            if not self._initialized:
                return None
            
            key = self._make_key('market_data', symbol, asset_type)
            data = await self.redis.get(key)
            
            if data:
                return await self._deserialize_data(data, 'dataframe')
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting cached market data for {symbol}: {e}")
            return None
    
    async def get_cached_latest_data(self, symbol: str) -> Optional[pd.Series]:
        """Retrieve the latest cached data point for a symbol."""
        try:
            if not self._initialized:
                return None
            
            key = self._make_key('latest_data', symbol)
            data = await self.redis.get(key)
            
            if data:
                data_dict = await self._deserialize_data(data)
                return pd.Series(data_dict)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting cached latest data for {symbol}: {e}")
            return None
    
    # Symbol and Metadata Caching
    async def cache_symbols_by_asset_type(self, asset_type: str, 
                                        symbols: List[str]) -> bool:
        """Cache symbols list for an asset type."""
        try:
            if not self._initialized:
                return False
            
            key = self._make_key('symbols', asset_type)
            serialized_data = await self._serialize_data(symbols)
            
            await self.redis.setex(
                key,
                self.TTL['symbols'],
                serialized_data
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error caching symbols for {asset_type}: {e}")
            return False
    
    async def get_cached_symbols_by_asset_type(self, asset_type: str) -> Optional[List[str]]:
        """Retrieve cached symbols for an asset type."""
        try:
            if not self._initialized:
                return None
            
            key = self._make_key('symbols', asset_type)
            data = await self.redis.get(key)
            
            if data:
                return await self._deserialize_data(data)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting cached symbols for {asset_type}: {e}")
            return None
    
    # Signal Caching
    async def cache_signal(self, signal_data: Dict[str, Any]) -> bool:
        """Cache a trading signal."""
        try:
            if not self._initialized:
                return False
            
            signal_id = signal_data.get('signal_id', 
                                      f"{signal_data.get('symbol', 'unknown')}_{int(get_current_time().timestamp())}")
            key = self._make_key('signals', signal_id)
            
            serialized_data = await self._serialize_data(signal_data)
            
            await self.redis.setex(
                key,
                self.TTL['signals'],
                serialized_data
            )
            
            # Add to symbol-specific signals list
            symbol = signal_data.get('symbol')
            if symbol:
                list_key = self._make_key('signals', 'by_symbol', symbol)
                await self.redis.lpush(list_key, signal_id)
                await self.redis.expire(list_key, self.TTL['signals'])
                
                # Keep only recent signals (last 100)
                await self.redis.ltrim(list_key, 0, 99)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error caching signal: {e}")
            return False
    
    async def get_cached_signals_for_symbol(self, symbol: str) -> List[Dict[str, Any]]:
        """Retrieve cached signals for a symbol."""
        try:
            if not self._initialized:
                return []
            
            list_key = self._make_key('signals', 'by_symbol', symbol)
            signal_ids = await self.redis.lrange(list_key, 0, -1)
            
            signals = []
            for signal_id in signal_ids:
                key = self._make_key('signals', signal_id.decode())
                data = await self.redis.get(key)
                if data:
                    signal = await self._deserialize_data(data)
                    signals.append(signal)
            
            return signals
            
        except Exception as e:
            self.logger.error(f"Error getting cached signals for {symbol}: {e}")
            return []
    
    # Options Data Caching
    async def cache_options_chain(self, underlying: str, expiry_date: str,
                                 data: pd.DataFrame) -> bool:
        """Cache options chain data."""
        try:
            if not self._initialized or data.empty:
                return False
            
            key = self._make_key('options', underlying, expiry_date)
            serialized_data = await self._serialize_data(data)
            
            await self.redis.setex(
                key,
                self.TTL['options'],
                serialized_data
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error caching options chain for {underlying}: {e}")
            return False
    
    async def get_cached_options_chain(self, underlying: str, 
                                     expiry_date: str) -> Optional[pd.DataFrame]:
        """Retrieve cached options chain data."""
        try:
            if not self._initialized:
                return None
            
            key = self._make_key('options', underlying, expiry_date)
            data = await self.redis.get(key)
            
            if data:
                return await self._deserialize_data(data, 'dataframe')
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting cached options chain for {underlying}: {e}")
            return None
    
    # Performance and Analytics Caching
    async def cache_performance_data(self, strategy: str, symbol: str,
                                   performance_data: Dict[str, Any]) -> bool:
        """Cache strategy performance data."""
        try:
            if not self._initialized:
                return False
            
            key = self._make_key('performance', strategy, symbol)
            serialized_data = await self._serialize_data(performance_data)
            
            await self.redis.setex(
                key,
                self.TTL['performance'],
                serialized_data
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error caching performance data: {e}")
            return False
    
    async def get_cached_performance_data(self, strategy: str, 
                                        symbol: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached performance data."""
        try:
            if not self._initialized:
                return None
            
            key = self._make_key('performance', strategy, symbol)
            data = await self.redis.get(key)
            
            if data:
                return await self._deserialize_data(data)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting cached performance data: {e}")
            return None
    
    # Analytics Caching
    async def cache_analytics_result(self, analysis_type: str, 
                                   result_data: Any, ttl_override: Optional[int] = None) -> bool:
        """Cache analytics result."""
        try:
            if not self._initialized:
                return False
            
            key = self._make_key('analytics', analysis_type, int(get_current_time().timestamp() // 60))  # Minute-level caching
            serialized_data = await self._serialize_data(result_data)
            
            ttl = ttl_override or self.TTL['analytics']
            await self.redis.setex(key, ttl, serialized_data)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error caching analytics result: {e}")
            return False
    
    async def get_cached_analytics_result(self, analysis_type: str) -> Optional[Any]:
        """Retrieve cached analytics result."""
        try:
            if not self._initialized:
                return None
            
            # Check last few minutes for cached results
            current_minute = int(get_current_time().timestamp() // 60)
            for i in range(5):  # Check last 5 minutes
                key = self._make_key('analytics', analysis_type, current_minute - i)
                data = await self.redis.get(key)
                if data:
                    return await self._deserialize_data(data)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting cached analytics result: {e}")
            return None
    
    # Utility Methods
    async def invalidate_symbol_cache(self, symbol: str):
        """Invalidate all cached data for a symbol."""
        try:
            if not self._initialized:
                return
            
            # Find all keys for this symbol
            patterns = [
                f"{self.PREFIXES['market_data']}:{symbol}:*",
                f"{self.PREFIXES['latest_data']}:{symbol}",
                f"{self.PREFIXES['signals']}:by_symbol:{symbol}",
                f"{self.PREFIXES['performance']}:*:{symbol}",
            ]
            
            for pattern in patterns:
                keys = await self.redis.keys(pattern)
                if keys:
                    await self.redis.delete(*keys)
            
            self.logger.debug(f"Invalidated cache for {symbol}")
            
        except Exception as e:
            self.logger.error(f"Error invalidating cache for {symbol}: {e}")
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            if not self._initialized:
                return {}
            
            # Get Redis info
            info = await self.redis.info()
            
            # Count keys by prefix
            key_counts = {}
            for prefix_name, prefix in self.PREFIXES.items():
                pattern = f"{prefix}:*"
                keys = await self.redis.keys(pattern)
                key_counts[prefix_name] = len(keys)
            
            return {
                'total_keys': info.get('db0', {}).get('keys', 0),
                'memory_used': info.get('used_memory_human', '0B'),
                'hits': info.get('keyspace_hits', 0),
                'misses': info.get('keyspace_misses', 0),
                'hit_rate': round(info.get('keyspace_hits', 0) / 
                                max(1, info.get('keyspace_hits', 0) + info.get('keyspace_misses', 0)) * 100, 2),
                'key_counts': key_counts
            }
            
        except Exception as e:
            self.logger.error(f"Error getting cache stats: {e}")
            return {}
    
    async def cleanup_expired_keys(self):
        """Manually cleanup expired keys."""
        try:
            if not self._initialized:
                return
            
            # This is usually handled by Redis automatically,
            # but we can do some manual cleanup if needed
            await self.redis.eval("""
                local expired = 0
                local keys = redis.call('keys', '*')
                for i=1,#keys do
                    if redis.call('ttl', keys[i]) == -1 then
                        redis.call('del', keys[i])
                        expired = expired + 1
                    end
                end
                return expired
            """, 0)
            
            self.logger.debug("Cleaned up expired keys")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up expired keys: {e}")
    
    async def flush_cache(self, pattern: Optional[str] = None):
        """Flush cache (optionally by pattern)."""
        try:
            if not self._initialized:
                return
            
            if pattern:
                keys = await self.redis.keys(pattern)
                if keys:
                    await self.redis.delete(*keys)
                    self.logger.info(f"Flushed {len(keys)} keys matching pattern: {pattern}")
            else:
                await self.redis.flushdb()
                self.logger.info("Flushed entire cache database")
            
        except Exception as e:
            self.logger.error(f"Error flushing cache: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Redis health."""
        try:
            if not self._initialized:
                return {'status': 'not_initialized'}
            
            # Test basic operations
            test_key = 'health_check_test'
            await self.redis.setex(test_key, 10, 'test_value')
            value = await self.redis.get(test_key)
            await self.redis.delete(test_key)
            
            if value != b'test_value':
                return {'status': 'unhealthy', 'error': 'Read/write test failed'}
            
            # Get server info
            info = await self.redis.info()
            
            return {
                'status': 'healthy',
                'version': info.get('redis_version', 'unknown'),
                'uptime': info.get('uptime_in_seconds', 0),
                'memory_usage': info.get('used_memory_human', '0B'),
                'connected_clients': info.get('connected_clients', 0)
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
