"""
Data Layer Factory for AlphaStock Trading System

Provides a unified interface for creating and managing different data storage backends.
Supports ClickHouse, PostgreSQL, and Redis caching with intelligent fallbacks.
"""

import os
from typing import Dict, List, Optional, Any, Union
import logging
from enum import Enum

from . import DataLayerInterface
from .clickhouse_data_layer import ClickHouseDataLayer
from .postgresql_data_layer import PostgreSQLDataLayer
from .redis_cache_layer import RedisCacheLayer
from ..utils.logger_setup import setup_logger


class DataStorageType(Enum):
    """Supported data storage types."""
    CLICKHOUSE = "clickhouse"
    POSTGRESQL = "postgresql"
    REDIS_CACHE = "redis_cache"


class HybridDataLayer(DataLayerInterface):
    """
    Hybrid data layer that combines primary storage with Redis caching.
    
    Provides:
    - Primary storage (ClickHouse or PostgreSQL)
    - Redis caching for performance
    - Intelligent fallbacks
    - Automatic cache invalidation
    """
    
    def __init__(self, primary_storage: DataLayerInterface, 
                 cache_layer: Optional[RedisCacheLayer] = None):
        """
        Initialize hybrid data layer.
        
        Args:
            primary_storage: Primary data storage backend
            cache_layer: Optional Redis cache layer
        """
        self.primary_storage = primary_storage
        self.cache_layer = cache_layer
        self.logger = setup_logger(name="HybridDataLayer")
        self._initialized = False
    
    async def initialize(self) -> bool:
        """Initialize both primary storage and cache."""
        try:
            # Initialize primary storage
            primary_success = await self.primary_storage.initialize()
            if not primary_success:
                self.logger.error("Failed to initialize primary storage")
                return False
            
            # Initialize cache (optional)
            cache_success = True
            if self.cache_layer:
                cache_success = await self.cache_layer.initialize()
                if not cache_success:
                    self.logger.warning("Failed to initialize cache layer, continuing without cache")
                    self.cache_layer = None
            
            self._initialized = True
            self.logger.info(f"Hybrid data layer initialized (cache: {'enabled' if self.cache_layer else 'disabled'})")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize hybrid data layer: {e}")
            return False
    
    async def close(self):
        """Close both primary storage and cache connections."""
        try:
            if self.primary_storage:
                await self.primary_storage.close()
            
            if self.cache_layer:
                await self.cache_layer.close()
            
            self._initialized = False
            self.logger.info("Hybrid data layer closed")
        except Exception as e:
            self.logger.error(f"Error closing hybrid data layer: {e}")
    
    async def store_market_data(self, symbol: str, asset_type: str,
                               data, runner_name: str) -> bool:
        """Store market data with caching."""
        try:
            # Store in primary storage
            success = await self.primary_storage.store_market_data(
                symbol, asset_type, data, runner_name
            )
            
            # Cache the data if primary storage succeeded
            if success and self.cache_layer:
                await self.cache_layer.cache_market_data(symbol, data, asset_type)
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error storing market data: {e}")
            return False
    
    async def get_market_data(self, symbol: str, start_time=None, end_time=None, limit=None):
        """Get market data with cache-first approach."""
        try:
            # Try cache first for recent data
            if self.cache_layer and not start_time and not end_time and (not limit or limit <= 100):
                cached_data = await self.cache_layer.get_cached_market_data(symbol)
                if cached_data is not None and not cached_data.empty:
                    self.logger.debug(f"Served market data for {symbol} from cache")
                    return cached_data
            
            # Fallback to primary storage
            data = await self.primary_storage.get_market_data(symbol, start_time, end_time, limit)
            
            # Cache the result for future use
            if self.cache_layer and data is not None and not data.empty:
                await self.cache_layer.cache_market_data(symbol, data)
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error getting market data: {e}")
            return None
    
    async def get_latest_market_data(self, symbol: str):
        """Get latest market data with cache-first approach."""
        try:
            # Try cache first
            if self.cache_layer:
                cached_data = await self.cache_layer.get_cached_latest_data(symbol)
                if cached_data is not None:
                    self.logger.debug(f"Served latest data for {symbol} from cache")
                    return cached_data
            
            # Fallback to primary storage
            data = await self.primary_storage.get_latest_market_data(symbol)
            
            # Cache the result
            if self.cache_layer and data is not None:
                # Convert Series to DataFrame for caching
                import pandas as pd
                df = pd.DataFrame([data])
                await self.cache_layer.cache_market_data(symbol, df)
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error getting latest market data: {e}")
            return None
    
    # Delegate other methods to primary storage
    async def store_historical_data(self, symbol: str, asset_type: str, data, timeframe: str) -> bool:
        return await self.primary_storage.store_historical_data(symbol, asset_type, data, timeframe)
    
    async def get_historical_data(self, symbol: str, timeframe: str, start_date, end_date):
        return await self.primary_storage.get_historical_data(symbol, timeframe, start_date, end_date)
    
    async def store_signal(self, signal_data: Dict[str, Any]) -> bool:
        success = await self.primary_storage.store_signal(signal_data)
        if success and self.cache_layer:
            await self.cache_layer.cache_signal(signal_data)
        return success
    
    async def get_signals(self, symbol=None, strategy=None, start_time=None, end_time=None):
        # Try cache for symbol-specific recent signals
        if self.cache_layer and symbol and not start_time and not end_time:
            cached_signals = await self.cache_layer.get_cached_signals_for_symbol(symbol)
            if cached_signals:
                return cached_signals
        
        return await self.primary_storage.get_signals(symbol, strategy, start_time, end_time)
    
    async def store_options_data(self, underlying: str, expiry_date: str, data) -> bool:
        success = await self.primary_storage.store_options_data(underlying, expiry_date, data)
        if success and self.cache_layer:
            await self.cache_layer.cache_options_chain(underlying, expiry_date, data)
        return success
    
    async def get_options_chain(self, underlying: str, expiry_date: str):
        # Try cache first
        if self.cache_layer:
            cached_data = await self.cache_layer.get_cached_options_chain(underlying, expiry_date)
            if cached_data is not None:
                return cached_data
        
        data = await self.primary_storage.get_options_chain(underlying, expiry_date)
        if data is not None and self.cache_layer:
            await self.cache_layer.cache_options_chain(underlying, expiry_date, data)
        
        return data
    
    async def store_performance_data(self, strategy: str, symbol: str, performance_data: Dict[str, Any]) -> bool:
        success = await self.primary_storage.store_performance_data(strategy, symbol, performance_data)
        if success and self.cache_layer:
            await self.cache_layer.cache_performance_data(strategy, symbol, performance_data)
        return success
    
    async def get_performance_summary(self, strategy=None, symbol=None, days: int = 30):
        return await self.primary_storage.get_performance_summary(strategy, symbol, days)
    
    async def execute_query(self, query: str, parameters=None):
        return await self.primary_storage.execute_query(query, parameters)
    
    async def health_check(self) -> Dict[str, Any]:
        primary_health = await self.primary_storage.health_check()
        cache_health = {}
        if self.cache_layer:
            cache_health = await self.cache_layer.health_check()
        
        return {
            'primary_storage': primary_health,
            'cache_layer': cache_health,
            'overall_status': 'healthy' if primary_health.get('status') == 'healthy' else 'degraded'
        }
    
    async def optimize_storage(self) -> bool:
        return await self.primary_storage.optimize_storage()
    
    async def batch_store_market_data(self, batch_data: List[Dict[str, Any]]) -> bool:
        return await self.primary_storage.batch_store_market_data(batch_data)
    
    async def get_symbols_by_asset_type(self, asset_type: str) -> List[str]:
        # Try cache first
        if self.cache_layer:
            cached_symbols = await self.cache_layer.get_cached_symbols_by_asset_type(asset_type)
            if cached_symbols is not None:
                return cached_symbols
        
        symbols = await self.primary_storage.get_symbols_by_asset_type(asset_type)
        if symbols and self.cache_layer:
            await self.cache_layer.cache_symbols_by_asset_type(asset_type, symbols)
        
        return symbols
    
    async def cleanup_old_data(self, days_to_keep: int = 365) -> bool:
        return await self.primary_storage.cleanup_old_data(days_to_keep)


class DataLayerFactory:
    """
    Factory for creating data layer instances.
    
    Supports multiple storage backends and configuration options.
    """
    
    def __init__(self):
        self.logger = setup_logger(name="DataLayerFactory")
    
    def create_clickhouse_layer(self, **kwargs) -> ClickHouseDataLayer:
        """Create ClickHouse data layer."""
        config = {
            'host': os.getenv('CLICKHOUSE_HOST', 'localhost'),
            'port': int(os.getenv('CLICKHOUSE_PORT', '8123')),
            'database': os.getenv('CLICKHOUSE_DATABASE', 'alphastock'),
            'username': os.getenv('CLICKHOUSE_USERNAME', 'default'),
            'password': os.getenv('CLICKHOUSE_PASSWORD', ''),
            'pool_size': int(os.getenv('CLICKHOUSE_POOL_SIZE', '10'))
        }
        
        # Filter out unsupported keys from kwargs
        valid_keys = {'host', 'port', 'database', 'username', 'password', 'pool_size'}
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_keys}
        config.update(filtered_kwargs)
        
        return ClickHouseDataLayer(**config)
    
    def create_postgresql_layer(self, **kwargs) -> PostgreSQLDataLayer:
        """Create PostgreSQL data layer."""
        config = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': int(os.getenv('POSTGRES_PORT', '5432')),
            'database': os.getenv('POSTGRES_DATABASE', 'alphastock'),
            'username': os.getenv('POSTGRES_USERNAME', 'postgres'),
            'password': os.getenv('POSTGRES_PASSWORD', ''),
            'pool_size': int(os.getenv('POSTGRES_POOL_SIZE', '20')),
            'max_overflow': int(os.getenv('POSTGRES_MAX_OVERFLOW', '30'))
        }
        config.update(kwargs)
        
        return PostgreSQLDataLayer(**config)
    
    def create_redis_cache_layer(self, **kwargs) -> RedisCacheLayer:
        """Create Redis cache layer."""
        config = {
            'host': os.getenv('REDIS_HOST', 'localhost'),
            'port': int(os.getenv('REDIS_PORT', '6379')),
            'db': int(os.getenv('REDIS_DB', '0')),
            'password': os.getenv('REDIS_PASSWORD', None),
            'max_connections': int(os.getenv('REDIS_MAX_CONNECTIONS', '20'))
        }
        config.update(kwargs)
        
        return RedisCacheLayer(**config)
    
    def create_hybrid_layer(self, primary_type: DataStorageType = DataStorageType.CLICKHOUSE,
                           enable_cache: bool = True, **kwargs) -> HybridDataLayer:
        """
        Create hybrid data layer with primary storage and optional caching.
        
        Args:
            primary_type: Primary storage type (ClickHouse or PostgreSQL)
            enable_cache: Whether to enable Redis caching
            **kwargs: Additional configuration parameters
            
        Returns:
            HybridDataLayer instance
        """
        # Create primary storage
        if primary_type == DataStorageType.CLICKHOUSE:
            primary_storage = self.create_clickhouse_layer(**kwargs.get('clickhouse', {}))
        elif primary_type == DataStorageType.POSTGRESQL:
            primary_storage = self.create_postgresql_layer(**kwargs.get('postgresql', {}))
        else:
            raise ValueError(f"Unsupported primary storage type: {primary_type}")
        
        # Create cache layer if enabled
        cache_layer = None
        if enable_cache:
            try:
                cache_layer = self.create_redis_cache_layer(**kwargs.get('redis', {}))
            except Exception as e:
                self.logger.warning(f"Failed to create Redis cache layer: {e}")
        
        return HybridDataLayer(primary_storage, cache_layer)
    
    def create_from_config(self, config: Dict[str, Any]) -> DataLayerInterface:
        """
        Create data layer from configuration dictionary.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            DataLayerInterface instance
        """
        storage_type = config.get('type', 'postgresql').lower()
        
        # Handle cache configuration - can be dict, string, or boolean
        cache_config = config.get('cache', {})
        if isinstance(cache_config, str):
            # If cache is a string like "none" or "redis", handle accordingly
            enable_cache = cache_config.lower() not in ['none', 'false', 'disabled']
            cache_config = config.get('redis', {}) if enable_cache else {}
        elif isinstance(cache_config, dict):
            enable_cache = cache_config.get('enabled', True)
        else:
            enable_cache = bool(cache_config)
            cache_config = config.get('redis', {})
        
        if storage_type == 'clickhouse':
            primary_type = DataStorageType.CLICKHOUSE
        elif storage_type == 'postgresql':
            primary_type = DataStorageType.POSTGRESQL
        else:
            raise ValueError(f"Unknown storage type: {storage_type}")
        
        # Extract configuration for each component
        kwargs = {
            'clickhouse': config.get('clickhouse', {}),
            'postgresql': config.get('postgresql', {}),
            'redis': cache_config
        }
        
        return self.create_hybrid_layer(primary_type, enable_cache, **kwargs)
    
    def get_recommended_config(self) -> Dict[str, Any]:
        """Get recommended configuration for production use."""
        return {
            'type': 'clickhouse',  # ClickHouse recommended for time series
            'clickhouse': {
                'host': 'localhost',
                'port': 8123,
                'database': 'alphastock',
                'username': 'default',
                'password': '',
                'pool_size': 10
            },
            'postgresql': {  # Fallback option
                'host': 'localhost',
                'port': 5432,
                'database': 'alphastock',
                'username': 'postgres',
                'password': '',
                'pool_size': 20,
                'max_overflow': 30
            },
            'cache': {
                'enabled': True,
                'host': 'localhost',
                'port': 6379,
                'db': 0,
                'password': None,
                'max_connections': 20
            }
        }
    
    def get_development_config(self) -> Dict[str, Any]:
        """Get configuration suitable for development."""
        return {
            'type': 'postgresql',  # PostgreSQL easier to set up for development
            'postgresql': {
                'host': 'localhost',
                'port': 5432,
                'database': 'alphastock_dev',
                'username': 'postgres',
                'password': '',
                'pool_size': 5,
                'max_overflow': 10
            },
            'cache': {
                'enabled': False  # Disable cache for simpler development setup
            }
        }
    
    async def test_connection(self, data_layer: DataLayerInterface) -> bool:
        """Test data layer connection."""
        try:
            success = await data_layer.initialize()
            if success:
                health = await data_layer.health_check()
                await data_layer.close()
                return health.get('status') in ['healthy', 'active']
            return False
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False


# Global factory instance
data_layer_factory = DataLayerFactory()
