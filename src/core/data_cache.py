"""
Simple In-Memory Data Cache for AlphaStock Trading System

Provides a simple in-memory cache with TTL support for storing market data
and other frequently accessed information.
"""

import logging
import time
from typing import Dict, Any, Optional
from threading import Lock
import json

from ..utils.logger_setup import setup_logger

logger = setup_logger("data_cache")


class SimpleDataCache:
    """
    Simple in-memory cache with TTL (Time To Live) support.
    
    Thread-safe implementation suitable for caching market data and other
    frequently accessed information.
    """
    
    def __init__(self, default_ttl: int = 300):
        """
        Initialize the data cache.
        
        Args:
            default_ttl: Default time-to-live in seconds (5 minutes default)
        """
        self.default_ttl = default_ttl
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
        
        logger.info(f"Data cache initialized with default TTL: {default_ttl} seconds")
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set a value in the cache.
        
        Args:
            key: Cache key
            value: Value to store
            ttl: Time-to-live in seconds (uses default if None)
        """
        if ttl is None:
            ttl = self.default_ttl
        
        expiry_time = time.time() + ttl if ttl > 0 else None
        
        with self._lock:
            self._cache[key] = {
                'value': value,
                'expiry': expiry_time,
                'created': time.time()
            }
        
        logger.debug(f"Cache SET: {key} (TTL: {ttl}s)")
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get a value from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            if key not in self._cache:
                logger.debug(f"Cache MISS: {key}")
                return None
            
            entry = self._cache[key]
            
            # Check if expired
            if entry['expiry'] is not None and time.time() > entry['expiry']:
                del self._cache[key]
                logger.debug(f"Cache EXPIRED: {key}")
                return None
            
            logger.debug(f"Cache HIT: {key}")
            return entry['value']
    
    def delete(self, key: str) -> bool:
        """
        Delete a key from the cache.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if key existed and was deleted, False otherwise
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Cache DELETE: {key}")
                return True
            return False
    
    def exists(self, key: str) -> bool:
        """
        Check if a key exists and is not expired.
        
        Args:
            key: Cache key to check
            
        Returns:
            True if key exists and is valid, False otherwise
        """
        return self.get(key) is not None
    
    def clear(self) -> None:
        """Clear all entries from the cache."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cache cleared: {count} entries removed")
    
    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from the cache.
        
        Returns:
            Number of expired entries removed
        """
        current_time = time.time()
        expired_keys = []
        
        with self._lock:
            for key, entry in self._cache.items():
                if entry['expiry'] is not None and current_time > entry['expiry']:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._cache[key]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            total_entries = len(self._cache)
            expired_count = 0
            current_time = time.time()
            
            for entry in self._cache.values():
                if entry['expiry'] is not None and current_time > entry['expiry']:
                    expired_count += 1
            
            active_entries = total_entries - expired_count
            
            # Calculate cache size (approximate)
            cache_size_bytes = 0
            try:
                cache_size_bytes = len(json.dumps(self._cache, default=str))
            except:
                cache_size_bytes = 0
            
            return {
                'total_entries': total_entries,
                'active_entries': active_entries,
                'expired_entries': expired_count,
                'cache_size_bytes': cache_size_bytes,
                'default_ttl': self.default_ttl
            }
    
    def get_keys(self, pattern: str = None) -> list:
        """
        Get all cache keys, optionally filtered by pattern.
        
        Args:
            pattern: Optional string pattern to filter keys
            
        Returns:
            List of cache keys
        """
        with self._lock:
            keys = list(self._cache.keys())
            
            if pattern:
                keys = [key for key in keys if pattern in key]
            
            return keys
    
    def set_ttl(self, key: str, ttl: int) -> bool:
        """
        Update TTL for an existing key.
        
        Args:
            key: Cache key
            ttl: New TTL in seconds
            
        Returns:
            True if key exists and TTL was updated, False otherwise
        """
        with self._lock:
            if key not in self._cache:
                return False
            
            entry = self._cache[key]
            entry['expiry'] = time.time() + ttl if ttl > 0 else None
            
            logger.debug(f"Cache TTL updated: {key} -> {ttl}s")
            return True
    
    def get_ttl(self, key: str) -> Optional[int]:
        """
        Get remaining TTL for a key.
        
        Args:
            key: Cache key
            
        Returns:
            Remaining TTL in seconds or None if key doesn't exist/no expiry
        """
        with self._lock:
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            if entry['expiry'] is None:
                return None
            
            remaining = entry['expiry'] - time.time()
            return max(0, int(remaining))
    
    def __len__(self) -> int:
        """Return number of entries in cache."""
        with self._lock:
            return len(self._cache)
    
    def __contains__(self, key: str) -> bool:
        """Check if key exists in cache (supports 'in' operator)."""
        return self.exists(key)
    
    def __str__(self) -> str:
        """String representation of the cache."""
        stats = self.get_stats()
        return f"SimpleDataCache(entries={stats['active_entries']}, ttl={self.default_ttl}s)"
