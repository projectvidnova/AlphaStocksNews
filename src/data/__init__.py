"""
Abstract Data Layer Interface for AlphaStock Trading System
Defines the contract for data storage and retrieval operations.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import pandas as pd


class DataLayerInterface(ABC):
    """
    Abstract interface for data storage and retrieval operations.
    
    This interface defines the contract that all data layer implementations
    must follow, ensuring consistency across different storage backends.
    """
    
    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize the data storage backend.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def close(self):
        """Close connections and cleanup resources."""
        pass
    
    # Market Data Operations
    @abstractmethod
    async def store_market_data(self, symbol: str, asset_type: str, 
                               data: pd.DataFrame, runner_name: str) -> bool:
        """
        Store market data for a symbol.
        
        Args:
            symbol: Trading symbol (e.g., 'RELIANCE', 'NIFTY50')
            asset_type: Type of asset (EQUITY, OPTIONS, INDEX, etc.)
            data: DataFrame containing OHLC and other market data
            runner_name: Name of the runner that generated the data
            
        Returns:
            bool: True if storage successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_market_data(self, symbol: str, 
                             start_time: Optional[datetime] = None,
                             end_time: Optional[datetime] = None,
                             limit: Optional[int] = None) -> pd.DataFrame:
        """
        Retrieve market data for a symbol.
        
        Args:
            symbol: Trading symbol
            start_time: Start datetime for data retrieval
            end_time: End datetime for data retrieval
            limit: Maximum number of records to return
            
        Returns:
            pd.DataFrame: Market data with timestamps as index
        """
        pass
    
    @abstractmethod
    async def get_latest_market_data(self, symbol: str) -> Optional[pd.Series]:
        """
        Get the latest market data point for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            pd.Series: Latest market data or None if not found
        """
        pass
    
    # Historical Data Operations
    @abstractmethod
    async def store_historical_data(self, symbol: str, asset_type: str,
                                   data: pd.DataFrame, timeframe: str) -> bool:
        """
        Store historical OHLC data.
        
        Args:
            symbol: Trading symbol
            asset_type: Type of asset
            data: DataFrame with OHLC data
            timeframe: Timeframe (1m, 5m, 15m, 1h, 1d)
            
        Returns:
            bool: True if storage successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_historical_data(self, symbol: str, timeframe: str,
                                 start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """
        Retrieve historical OHLC data.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe (1m, 5m, 15m, 1h, 1d)
            start_date: Start date for data
            end_date: End date for data
            
        Returns:
            pd.DataFrame: Historical OHLC data
        """
        pass
    
    # Signal and Strategy Operations
    @abstractmethod
    async def store_signal(self, signal_data: Dict[str, Any]) -> bool:
        """
        Store trading signal.
        
        Args:
            signal_data: Dictionary containing signal information
            
        Returns:
            bool: True if storage successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_signals(self, symbol: Optional[str] = None,
                         strategy: Optional[str] = None,
                         start_time: Optional[datetime] = None,
                         end_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Retrieve trading signals.
        
        Args:
            symbol: Filter by symbol
            strategy: Filter by strategy name
            start_time: Start datetime for signals
            end_time: End datetime for signals
            
        Returns:
            List of signal dictionaries
        """
        pass
    
    # Options Data Operations
    @abstractmethod
    async def store_options_data(self, underlying: str, expiry_date: str,
                                data: pd.DataFrame) -> bool:
        """
        Store options chain data.
        
        Args:
            underlying: Underlying symbol (e.g., 'NIFTY', 'BANKNIFTY')
            expiry_date: Options expiry date (YYYY-MM-DD)
            data: DataFrame containing options data with Greeks
            
        Returns:
            bool: True if storage successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_options_chain(self, underlying: str, expiry_date: str) -> pd.DataFrame:
        """
        Retrieve options chain data.
        
        Args:
            underlying: Underlying symbol
            expiry_date: Options expiry date (YYYY-MM-DD)
            
        Returns:
            pd.DataFrame: Options chain data
        """
        pass
    
    # Performance and Analytics Operations
    @abstractmethod
    async def store_performance_data(self, strategy: str, symbol: str,
                                   performance_data: Dict[str, Any]) -> bool:
        """
        Store strategy performance metrics.
        
        Args:
            strategy: Strategy name
            symbol: Trading symbol
            performance_data: Performance metrics dictionary
            
        Returns:
            bool: True if storage successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_performance_summary(self, strategy: Optional[str] = None,
                                    symbol: Optional[str] = None,
                                    days: int = 30) -> Dict[str, Any]:
        """
        Get performance summary.
        
        Args:
            strategy: Filter by strategy name
            symbol: Filter by symbol
            days: Number of days to look back
            
        Returns:
            Dictionary containing performance metrics
        """
        pass
    
    # Utility Operations
    @abstractmethod
    async def execute_query(self, query: str, parameters: Optional[Dict] = None) -> Any:
        """
        Execute a custom query.
        
        Args:
            query: SQL query string
            parameters: Query parameters
            
        Returns:
            Query results
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Check the health of the data layer.
        
        Returns:
            Dictionary containing health status information
        """
        pass
    
    @abstractmethod
    async def optimize_storage(self) -> bool:
        """
        Perform storage optimization operations.
        
        Returns:
            bool: True if optimization successful, False otherwise
        """
        pass
    
    # Batch Operations for Performance
    @abstractmethod
    async def batch_store_market_data(self, batch_data: List[Dict[str, Any]]) -> bool:
        """
        Store multiple market data records in a batch.
        
        Args:
            batch_data: List of market data dictionaries
            
        Returns:
            bool: True if all records stored successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_symbols_by_asset_type(self, asset_type: str) -> List[str]:
        """
        Get all symbols for a specific asset type.
        
        Args:
            asset_type: Type of asset (EQUITY, OPTIONS, INDEX, etc.)
            
        Returns:
            List of symbols
        """
        pass
    
    @abstractmethod
    async def cleanup_old_data(self, days_to_keep: int = 365) -> bool:
        """
        Clean up old data beyond the retention period.
        
        Args:
            days_to_keep: Number of days of data to retain
            
        Returns:
            bool: True if cleanup successful, False otherwise
        """
        pass
