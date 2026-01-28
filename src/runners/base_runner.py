"""
Base Runner for AlphaStock Trading System
Abstract base class for all market data runners.
"""

import logging
import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
import pandas as pd

from ..utils.logger_setup import setup_logger
from ..utils.timezone_utils import get_current_time, is_market_hours


class BaseRunner(ABC):
    """
    Abstract base class for all market data runners.
    
    Each runner is responsible for:
    - Collecting market data for specific asset types
    - Processing and caching data
    - Notifying subscribers of updates
    - Managing errors and retries
    """
    
    def __init__(self, 
                 api_client,
                 data_cache,
                 symbols: List[str],
                 interval_seconds: int = 5,
                 runner_name: str = "BaseRunner"):
        """
        Initialize base runner.
        
        Args:
            api_client: API client for data fetching
            data_cache: Cache for storing data
            symbols: List of symbols to monitor
            interval_seconds: Collection frequency
            runner_name: Name for logging
        """
        self.api_client = api_client
        self.data_cache = data_cache
        self.symbols = symbols
        self.interval_seconds = interval_seconds
        self.runner_name = runner_name
        
        # Logging
        self.logger = setup_logger(f"runner.{runner_name.lower()}")
        
        # Threading
        self.is_running = False
        self.runner_thread = None
        
        # Callbacks for data updates
        self.callbacks: List[Callable] = []
        
        # Error tracking
        self.error_counts: Dict[str, int] = {}
        self.last_update_time: Dict[str, datetime] = {}
        
        # Statistics
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'last_success_time': None,
            'last_error_time': None,
            'symbols_processed': 0
        }
        
        self.logger.info(f"{self.runner_name} initialized for {len(self.symbols)} symbols")
    
    @abstractmethod
    def get_asset_type(self) -> str:
        """Return the asset type this runner handles."""
        pass
    
    @abstractmethod
    def fetch_market_data(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Fetch market data for symbols.
        
        Args:
            symbols: List of symbols to fetch
            
        Returns:
            Dictionary with symbol -> data mapping
        """
        pass
    
    @abstractmethod
    def process_data(self, symbol: str, raw_data: Any) -> pd.DataFrame:
        """
        Process raw market data into standardized format.
        
        Args:
            symbol: Symbol being processed
            raw_data: Raw data from API
            
        Returns:
            Processed DataFrame
        """
        pass
    
    def add_callback(self, callback: Callable[[str, pd.DataFrame], None]):
        """Add callback for data updates."""
        self.callbacks.append(callback)
        self.logger.debug(f"Added callback, total: {len(self.callbacks)}")
    
    def remove_callback(self, callback: Callable):
        """Remove callback."""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
    
    def start(self):
        """Start the runner."""
        if self.is_running:
            self.logger.warning(f"{self.runner_name} is already running")
            return
        
        self.is_running = True
        
        # Start in separate thread
        self.runner_thread = threading.Thread(
            target=self._run_collection_loop,
            name=f"{self.runner_name}Thread",
            daemon=True
        )
        self.runner_thread.start()
        
        self.logger.info(f"{self.runner_name} started")
    
    def stop(self):
        """Stop the runner."""
        if not self.is_running:
            self.logger.warning(f"{self.runner_name} is not running")
            return
        
        self.is_running = False
        
        if self.runner_thread and self.runner_thread.is_alive():
            self.runner_thread.join(timeout=5)
        
        self.logger.info(f"{self.runner_name} stopped")
    
    def _run_collection_loop(self):
        """Main collection loop running in separate thread."""
        self.logger.info(f"{self.runner_name} collection loop started")
        
        while self.is_running:
            start_time = time.time()
            
            try:
                self._collect_batch_data()
                self.stats['successful_requests'] += 1
                self.stats['last_success_time'] = get_current_time()
                
            except Exception as e:
                self.logger.error(f"Error in {self.runner_name} collection loop: {e}")
                self.stats['failed_requests'] += 1
                self.stats['last_error_time'] = get_current_time()
            
            # Maintain frequency
            elapsed_time = time.time() - start_time
            sleep_time = max(0, self.interval_seconds - elapsed_time)
            
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        self.logger.info(f"{self.runner_name} collection loop ended")
    
    def _collect_batch_data(self):
        """Collect data for all symbols."""
        if not self.symbols:
            return
        
        try:
            # Fetch raw data
            raw_data = self.fetch_market_data(self.symbols)
            
            if not raw_data:
                self.logger.warning(f"No data received from {self.get_asset_type()} API")
                return
            
            current_time = get_current_time()
            processed_count = 0
            
            # Process each symbol
            for symbol, data in raw_data.items():
                try:
                    # Process raw data
                    processed_df = self.process_data(symbol, data)
                    
                    # Store in cache
                    self._store_in_cache(symbol, processed_df)
                    
                    # Update tracking
                    self.last_update_time[symbol] = current_time
                    self.error_counts[symbol] = 0
                    
                    # Notify callbacks
                    self._notify_callbacks(symbol, processed_df)
                    
                    processed_count += 1
                    
                except Exception as e:
                    self.logger.error(f"Error processing {symbol}: {e}")
                    self._handle_symbol_error(symbol)
            
            # Update stats
            self.stats['total_requests'] += 1
            self.stats['symbols_processed'] = processed_count
            
            self.logger.debug(f"Processed {processed_count} symbols in {self.runner_name}")
            
        except Exception as e:
            self.logger.error(f"Error in batch collection: {e}")
            raise
    
    def _store_in_cache(self, symbol: str, data: pd.DataFrame):
        """Store processed data in cache."""
        cache_key = f"{self.get_asset_type().lower()}:{symbol}"
        
        # Get existing data
        existing_data = self.data_cache.get(cache_key)
        
        if existing_data is not None and isinstance(existing_data, pd.DataFrame):
            # Append new data
            combined_data = pd.concat([existing_data, data], ignore_index=True)
            # Keep only last 500 records to manage memory
            if len(combined_data) > 500:
                combined_data = combined_data.tail(500)
        else:
            combined_data = data
        
        # Store with TTL
        self.data_cache.set(cache_key, combined_data, ttl=600)  # 10 minute TTL
    
    def _notify_callbacks(self, symbol: str, data: pd.DataFrame):
        """Notify all callbacks of data update."""
        for callback in self.callbacks:
            try:
                callback(symbol, data)
            except Exception as e:
                self.logger.error(f"Error in callback for {symbol}: {e}")
    
    def _handle_symbol_error(self, symbol: str):
        """Handle errors for individual symbols."""
        self.error_counts[symbol] = self.error_counts.get(symbol, 0) + 1
        
        if self.error_counts[symbol] > 10:
            self.logger.warning(f"Too many errors for {symbol} in {self.runner_name}")
    
    def get_cache_key(self, symbol: str) -> str:
        """Get cache key for symbol."""
        return f"{self.get_asset_type().lower()}:{symbol}"
    
    def get_latest_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Get latest data for symbol from cache."""
        cache_key = self.get_cache_key(symbol)
        return self.data_cache.get(cache_key)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get runner statistics."""
        return {
            'runner_name': self.runner_name,
            'asset_type': self.get_asset_type(),
            'is_running': self.is_running,
            'symbols_count': len(self.symbols),
            'interval_seconds': self.interval_seconds,
            'callbacks_count': len(self.callbacks),
            'stats': self.stats.copy(),
            'error_counts': self.error_counts.copy()
        }
    
    def health_check(self) -> bool:
        """Check if runner is healthy."""
        if not self.is_running:
            return False
        
        # Check if we've had recent successful updates
        if self.stats['last_success_time']:
            time_since_success = get_current_time() - self.stats['last_success_time']
            if time_since_success > timedelta(minutes=5):  # No success in 5 minutes
                return False
        
        return True
    
    def __str__(self):
        return f"{self.runner_name}({self.get_asset_type()}, {len(self.symbols)} symbols)"
    
    def __repr__(self):
        return (f"{self.__class__.__name__}("
                f"runner_name='{self.runner_name}', "
                f"asset_type='{self.get_asset_type()}', "
                f"symbols={len(self.symbols)}, "
                f"running={self.is_running})")


class RunnerManager:
    """
    Manages multiple runners for different asset types.
    """
    
    def __init__(self, data_cache):
        """Initialize runner manager."""
        self.data_cache = data_cache
        self.runners: Dict[str, BaseRunner] = {}
        self.logger = setup_logger("runner_manager")
        
        self.logger.info("Runner Manager initialized")
    
    def add_runner(self, name: str, runner: BaseRunner):
        """Add a runner."""
        self.runners[name] = runner
        self.logger.info(f"Added runner: {name} ({runner.get_asset_type()})")
    
    def remove_runner(self, name: str):
        """Remove a runner."""
        if name in self.runners:
            runner = self.runners[name]
            if runner.is_running:
                runner.stop()
            del self.runners[name]
            self.logger.info(f"Removed runner: {name}")
    
    def start_all(self):
        """Start all runners."""
        for name, runner in self.runners.items():
            try:
                runner.start()
            except Exception as e:
                self.logger.error(f"Error starting runner {name}: {e}")
    
    def stop_all(self):
        """Stop all runners."""
        for name, runner in self.runners.items():
            try:
                runner.stop()
            except Exception as e:
                self.logger.error(f"Error stopping runner {name}: {e}")
    
    def get_runner(self, name: str) -> Optional[BaseRunner]:
        """Get a runner by name."""
        return self.runners.get(name)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for all runners."""
        return {
            name: runner.get_stats()
            for name, runner in self.runners.items()
        }
    
    def health_check(self) -> Dict[str, bool]:
        """Check health of all runners."""
        return {
            name: runner.health_check()
            for name, runner in self.runners.items()
        }
