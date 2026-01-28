"""
Equity Runner for AlphaStock Trading System
Handles NSE/BSE equity stocks data collection.
"""

import pandas as pd
from datetime import datetime
from typing import Dict, List, Any
from .base_runner import BaseRunner
from ..utils.timezone_utils import get_current_time, is_market_hours


class EquityRunner(BaseRunner):
    """
    Handles equity stocks from NSE and BSE.
    
    Collects OHLCV data, corporate actions, and fundamental data
    for equity stocks.
    """
    
    def __init__(self, api_client, data_cache, symbols: List[str], 
                 exchange: str = "NSE", interval_seconds: int = 5):
        """
        Initialize Equity Runner.
        
        Args:
            api_client: Kite API client
            data_cache: Data cache
            symbols: List of equity symbols
            exchange: Exchange (NSE/BSE)
            interval_seconds: Collection frequency
        """
        self.exchange = exchange
        super().__init__(
            api_client=api_client,
            data_cache=data_cache,
            symbols=symbols,
            interval_seconds=interval_seconds,
            runner_name=f"EquityRunner_{exchange}"
        )
        
        # Equity-specific settings
        self.include_fundamentals = False  # Can be enabled for fundamental data
        self.corporate_actions = {}  # Track corporate actions
        
        self.logger.info(f"Equity Runner initialized for {exchange} with {len(symbols)} stocks")
    
    def get_asset_type(self) -> str:
        """Return asset type."""
        return f"EQUITY_{self.exchange}"
    
    def fetch_market_data(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Fetch equity market data using Kite API.
        
        Args:
            symbols: List of equity symbols
            
        Returns:
            Dictionary with symbol -> market data
        """
        try:
            # Get comprehensive quote data from Kite API (includes OHLC, LTP, volume, depth, etc.)
            quote_data = self.api_client.get_quote(symbols)
            
            # Transform quote data to expected format
            combined_data = {}
            
            for symbol in symbols:
                if symbol in quote_data:
                    raw_quote = quote_data[symbol]
                    ohlc = raw_quote.get('ohlc', {})
                    
                    # Extract and combine data
                    data = {
                        'open': ohlc.get('open', 0),
                        'high': ohlc.get('high', 0),
                        'low': ohlc.get('low', 0),
                        'close': ohlc.get('close', 0),
                        'last_price': raw_quote.get('last_price', 0),
                        'ltp': raw_quote.get('last_price', 0),
                        'volume': raw_quote.get('volume', 0),
                        'average_price': raw_quote.get('average_price', 0),
                        'buy_quantity': raw_quote.get('buy_quantity', 0),
                        'sell_quantity': raw_quote.get('sell_quantity', 0)
                    }
                    
                    combined_data[symbol] = data
            
            self.logger.debug(f"Fetched equity data for {len(combined_data)} symbols")
            return combined_data
            
        except Exception as e:
            self.logger.error(f"Error fetching equity data: {e}")
            return {}
    
    def process_data(self, symbol: str, raw_data: Any) -> pd.DataFrame:
        """
        Process raw equity data into standardized DataFrame.
        
        Args:
            symbol: Stock symbol
            raw_data: Raw OHLC data from API
            
        Returns:
            Processed DataFrame with equity data
        """
        try:
            current_time = get_current_time()
            
            # Extract data fields
            open_price = raw_data.get('open', 0)
            high_price = raw_data.get('high', 0)
            low_price = raw_data.get('low', 0)
            close_price = raw_data.get('close', 0)
            ltp = raw_data.get('ltp', raw_data.get('last_price', close_price))
            volume = raw_data.get('volume', 0)
            
            # Calculate additional fields
            price_change = ltp - close_price if close_price > 0 else 0
            price_change_pct = (price_change / close_price * 100) if close_price > 0 else 0
            
            # Create DataFrame
            df = pd.DataFrame([{
                'timestamp': current_time,
                'symbol': symbol,
                'exchange': self.exchange,
                'asset_type': 'EQUITY',
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'ltp': ltp,
                'volume': volume,
                'price_change': price_change,
                'price_change_pct': price_change_pct,
                'market_cap': self._get_market_cap(symbol, ltp),  # If available
                'sector': self._get_sector(symbol),  # If available
                'is_trading': self._is_trading_hours(),
            }])
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error processing equity data for {symbol}: {e}")
            # Return empty DataFrame with proper structure
            return pd.DataFrame(columns=[
                'timestamp', 'symbol', 'exchange', 'asset_type', 'open', 'high', 'low', 
                'close', 'ltp', 'volume', 'price_change', 'price_change_pct'
            ])
    
    def _get_market_cap(self, symbol: str, ltp: float) -> float:
        """Get market cap if available (placeholder)."""
        # This would require additional API calls or cached data
        return 0.0
    
    def _get_sector(self, symbol: str) -> str:
        """Get sector information if available (placeholder)."""
        # This would require cached sector mapping
        return "Unknown"
    
    def _is_trading_hours(self) -> bool:
        """Check if market is in trading hours."""
        from src.utils.market_hours import is_market_open
        return is_market_open()
    
    def get_top_gainers(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get top gaining stocks.
        
        Args:
            limit: Number of top gainers to return
            
        Returns:
            List of top gaining stocks
        """
        gainers = []
        
        for symbol in self.symbols:
            latest_data = self.get_latest_data(symbol)
            if latest_data is not None and not latest_data.empty:
                latest_row = latest_data.iloc[-1]
                if latest_row['price_change_pct'] > 0:
                    gainers.append({
                        'symbol': symbol,
                        'ltp': latest_row['ltp'],
                        'change_pct': latest_row['price_change_pct'],
                        'volume': latest_row['volume']
                    })
        
        # Sort by change percentage
        gainers.sort(key=lambda x: x['change_pct'], reverse=True)
        return gainers[:limit]
    
    def get_top_losers(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get top losing stocks.
        
        Args:
            limit: Number of top losers to return
            
        Returns:
            List of top losing stocks
        """
        losers = []
        
        for symbol in self.symbols:
            latest_data = self.get_latest_data(symbol)
            if latest_data is not None and not latest_data.empty:
                latest_row = latest_data.iloc[-1]
                if latest_row['price_change_pct'] < 0:
                    losers.append({
                        'symbol': symbol,
                        'ltp': latest_row['ltp'],
                        'change_pct': latest_row['price_change_pct'],
                        'volume': latest_row['volume']
                    })
        
        # Sort by change percentage (ascending for losers)
        losers.sort(key=lambda x: x['change_pct'])
        return losers[:limit]
    
    def get_high_volume_stocks(self, volume_threshold: int = 1000000) -> List[Dict[str, Any]]:
        """
        Get stocks with high volume.
        
        Args:
            volume_threshold: Minimum volume threshold
            
        Returns:
            List of high volume stocks
        """
        high_volume = []
        
        for symbol in self.symbols:
            latest_data = self.get_latest_data(symbol)
            if latest_data is not None and not latest_data.empty:
                latest_row = latest_data.iloc[-1]
                if latest_row['volume'] > volume_threshold:
                    high_volume.append({
                        'symbol': symbol,
                        'ltp': latest_row['ltp'],
                        'volume': latest_row['volume'],
                        'change_pct': latest_row['price_change_pct']
                    })
        
        # Sort by volume
        high_volume.sort(key=lambda x: x['volume'], reverse=True)
        return high_volume
    
    def get_equity_summary(self) -> Dict[str, Any]:
        """
        Get summary of equity market data.
        
        Returns:
            Summary statistics
        """
        total_symbols = len(self.symbols)
        active_symbols = 0
        total_volume = 0
        gainers_count = 0
        losers_count = 0
        
        for symbol in self.symbols:
            latest_data = self.get_latest_data(symbol)
            if latest_data is not None and not latest_data.empty:
                active_symbols += 1
                latest_row = latest_data.iloc[-1]
                total_volume += latest_row['volume']
                
                if latest_row['price_change_pct'] > 0:
                    gainers_count += 1
                elif latest_row['price_change_pct'] < 0:
                    losers_count += 1
        
        return {
            'total_symbols': total_symbols,
            'active_symbols': active_symbols,
            'total_volume': total_volume,
            'gainers_count': gainers_count,
            'losers_count': losers_count,
            'unchanged_count': active_symbols - gainers_count - losers_count,
            'exchange': self.exchange
        }
