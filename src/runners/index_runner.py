"""
Index Runner for AlphaStock Trading System
Handles market indices like Nifty50, Bank Nifty, etc.
"""

import pandas as pd
from datetime import datetime
from typing import Dict, List, Any
from .base_runner import BaseRunner
from ..utils.timezone_utils import get_current_time, is_market_hours


class IndexRunner(BaseRunner):
    """
    Handles market indices data collection.
    
    Manages:
    - Index values (Nifty50, Bank Nifty, etc.)
    - Index constituents
    - Sectoral indices
    - Index futures
    """
    
    def __init__(self, api_client, data_cache, indices: List[str], 
                 interval_seconds: int = 5):
        """
        Initialize Index Runner.
        
        Args:
            api_client: Kite API client
            data_cache: Data cache
            indices: List of index symbols
            interval_seconds: Collection frequency
        """
        super().__init__(
            api_client=api_client,
            data_cache=data_cache,
            symbols=indices,
            interval_seconds=interval_seconds,
            runner_name="IndexRunner"
        )
        
        # Index-specific settings
        self.index_constituents: Dict[str, List[str]] = {}
        self.sectoral_indices = [
            'NIFTYBANK', 'NIFTYIT', 'NIFTYFMCG', 'NIFTYPHARMA', 
            'NIFTYAUTO', 'NIFTYMETAL', 'NIFTYREALTY', 'NIFTYENERGY'
        ]
        
        self.logger.info(f"Index Runner initialized for {len(indices)} indices")
    
    def get_asset_type(self) -> str:
        """Return asset type."""
        return "INDEX"
    
    def fetch_market_data(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Fetch index data.
        
        Args:
            symbols: List of index symbols
            
        Returns:
            Dictionary with index data
        """
        try:
            # Get comprehensive quote data for indices (includes OHLC, LTP, volume, etc.)
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
                        'index_type': self._get_index_type(symbol),
                        'sector': self._get_index_sector(symbol)
                    }
                    
                    combined_data[symbol] = data
            
            self.logger.debug(f"Fetched index data for {len(combined_data)} indices")
            return combined_data
            
        except Exception as e:
            self.logger.error(f"Error fetching index data: {e}")
            return {}
    
    def process_data(self, symbol: str, raw_data: Any) -> pd.DataFrame:
        """
        Process raw index data.
        
        Args:
            symbol: Index symbol
            raw_data: Raw market data
            
        Returns:
            Processed DataFrame
        """
        try:
            current_time = get_current_time()
            
            # Extract basic OHLC data
            open_price = raw_data.get('open', 0)
            high_price = raw_data.get('high', 0)
            low_price = raw_data.get('low', 0)
            close_price = raw_data.get('close', 0)
            ltp = raw_data.get('ltp', raw_data.get('last_price', close_price))
            volume = raw_data.get('volume', 0)
            
            # Calculate index-specific metrics
            price_change = ltp - close_price if close_price > 0 else 0
            price_change_pct = (price_change / close_price * 100) if close_price > 0 else 0
            
            # Calculate volatility (simplified)
            volatility = self._calculate_volatility(symbol, ltp)
            
            # Calculate support/resistance levels
            support_resistance = self._calculate_support_resistance(symbol, high_price, low_price)
            
            # Create DataFrame
            df = pd.DataFrame([{
                'timestamp': current_time,
                'symbol': symbol,
                'asset_type': 'INDEX',
                'index_type': raw_data.get('index_type', 'UNKNOWN'),
                'sector': raw_data.get('sector', 'BROAD_MARKET'),
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'ltp': ltp,
                'volume': volume,
                'price_change': price_change,
                'price_change_pct': price_change_pct,
                'volatility': volatility,
                'support_level': support_resistance.get('support', 0),
                'resistance_level': support_resistance.get('resistance', 0),
                'market_sentiment': self._get_market_sentiment(price_change_pct, volatility),
                'is_trading': self._is_trading_hours(),
            }])
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error processing index data for {symbol}: {e}")
            return pd.DataFrame()
    
    def _get_index_type(self, symbol: str) -> str:
        """Determine index type."""
        symbol_upper = symbol.upper()
        
        if 'NIFTY50' in symbol_upper or symbol_upper == 'NIFTY':
            return 'BROAD_MARKET'
        elif 'BANK' in symbol_upper:
            return 'SECTORAL'
        elif any(sector in symbol_upper for sector in ['IT', 'PHARMA', 'AUTO', 'METAL', 'FMCG']):
            return 'SECTORAL'
        elif 'MIDCAP' in symbol_upper or 'SMALLCAP' in symbol_upper:
            return 'MARKET_CAP'
        else:
            return 'OTHER'
    
    def _get_index_sector(self, symbol: str) -> str:
        """Get sector for sectoral indices."""
        symbol_upper = symbol.upper()
        
        sector_mapping = {
            'BANK': 'BANKING',
            'IT': 'INFORMATION_TECHNOLOGY',
            'PHARMA': 'PHARMACEUTICALS',
            'AUTO': 'AUTOMOBILE',
            'METAL': 'METALS',
            'FMCG': 'CONSUMER_GOODS',
            'REALTY': 'REAL_ESTATE',
            'ENERGY': 'ENERGY',
            'MEDIA': 'MEDIA',
            'INFRA': 'INFRASTRUCTURE'
        }
        
        for key, sector in sector_mapping.items():
            if key in symbol_upper:
                return sector
        
        return 'BROAD_MARKET'
    
    def _calculate_volatility(self, symbol: str, current_price: float) -> float:
        """Calculate simple volatility based on price movements."""
        try:
            # Get historical data for volatility calculation
            historical_data = self.get_latest_data(symbol)
            if historical_data is None or len(historical_data) < 5:
                return 0.0
            
            # Calculate rolling volatility based on last 5 data points
            prices = historical_data['ltp'].tail(5).tolist() + [current_price]
            returns = [(prices[i] / prices[i-1] - 1) for i in range(1, len(prices))]
            
            if len(returns) > 1:
                volatility = pd.Series(returns).std() * 100  # Convert to percentage
                return round(volatility, 2)
            
            return 0.0
            
        except Exception:
            return 0.0
    
    def _calculate_support_resistance(self, symbol: str, high: float, low: float) -> Dict[str, float]:
        """Calculate basic support and resistance levels."""
        try:
            historical_data = self.get_latest_data(symbol)
            if historical_data is None or len(historical_data) < 10:
                return {'support': low, 'resistance': high}
            
            # Use recent highs and lows
            recent_data = historical_data.tail(20)
            support = recent_data['low'].min()
            resistance = recent_data['high'].max()
            
            return {
                'support': round(support, 2),
                'resistance': round(resistance, 2)
            }
            
        except Exception:
            return {'support': low, 'resistance': high}
    
    def _get_market_sentiment(self, price_change_pct: float, volatility: float) -> str:
        """Determine market sentiment."""
        if price_change_pct > 1.0:
            return 'BULLISH'
        elif price_change_pct < -1.0:
            return 'BEARISH'
        elif volatility > 2.0:
            return 'VOLATILE'
        else:
            return 'NEUTRAL'
    
    def _is_trading_hours(self) -> bool:
        """Check if market is in trading hours."""
        try:
            from src.utils.market_hours import is_market_open
            return is_market_open()
        except:
            return True  # Default to true if unable to check
    
    def get_market_overview(self) -> Dict[str, Any]:
        """Get overall market overview based on indices."""
        overview = {
            'timestamp': get_current_time().isoformat(),
            'indices': {},
            'market_sentiment': 'NEUTRAL',
            'volatility_level': 'NORMAL',
            'sector_performance': {}
        }
        
        total_change = 0
        total_volatility = 0
        active_indices = 0
        
        for symbol in self.symbols:
            latest_data = self.get_latest_data(symbol)
            if latest_data is not None and not latest_data.empty:
                latest_row = latest_data.iloc[-1]
                
                overview['indices'][symbol] = {
                    'ltp': latest_row['ltp'],
                    'change_pct': latest_row['price_change_pct'],
                    'volatility': latest_row.get('volatility', 0),
                    'sentiment': latest_row.get('market_sentiment', 'NEUTRAL')
                }
                
                total_change += latest_row['price_change_pct']
                total_volatility += latest_row.get('volatility', 0)
                active_indices += 1
                
                # Sectoral performance
                sector = latest_row.get('sector', 'BROAD_MARKET')
                if sector not in overview['sector_performance']:
                    overview['sector_performance'][sector] = []
                overview['sector_performance'][sector].append({
                    'symbol': symbol,
                    'change_pct': latest_row['price_change_pct']
                })
        
        # Calculate overall sentiment
        if active_indices > 0:
            avg_change = total_change / active_indices
            avg_volatility = total_volatility / active_indices
            
            if avg_change > 0.5:
                overview['market_sentiment'] = 'BULLISH'
            elif avg_change < -0.5:
                overview['market_sentiment'] = 'BEARISH'
            else:
                overview['market_sentiment'] = 'NEUTRAL'
            
            if avg_volatility > 2.0:
                overview['volatility_level'] = 'HIGH'
            elif avg_volatility > 1.0:
                overview['volatility_level'] = 'MEDIUM'
            else:
                overview['volatility_level'] = 'LOW'
        
        return overview
    
    def get_sectoral_performance(self) -> Dict[str, Any]:
        """Get sectoral indices performance."""
        sectoral_data = {}
        
        for symbol in self.symbols:
            latest_data = self.get_latest_data(symbol)
            if latest_data is not None and not latest_data.empty:
                latest_row = latest_data.iloc[-1]
                sector = latest_row.get('sector', 'UNKNOWN')
                
                if sector not in sectoral_data:
                    sectoral_data[sector] = []
                
                sectoral_data[sector].append({
                    'symbol': symbol,
                    'ltp': latest_row['ltp'],
                    'change_pct': latest_row['price_change_pct'],
                    'volatility': latest_row.get('volatility', 0)
                })
        
        # Sort sectors by performance
        for sector in sectoral_data:
            sectoral_data[sector].sort(key=lambda x: x['change_pct'], reverse=True)
        
        return sectoral_data
    
    def get_index_correlations(self) -> Dict[str, float]:
        """Calculate correlations between indices (simplified)."""
        correlations = {}
        
        # This would require historical data analysis
        # For now, return placeholder correlations
        
        if 'NIFTY50' in self.symbols and 'BANKNIFTY' in self.symbols:
            correlations['NIFTY50_BANKNIFTY'] = 0.85  # Typical correlation
        
        return correlations
    
    def get_index_summary(self) -> Dict[str, Any]:
        """Get index runner summary."""
        total_indices = len(self.symbols)
        active_indices = 0
        bullish_count = 0
        bearish_count = 0
        
        for symbol in self.symbols:
            latest_data = self.get_latest_data(symbol)
            if latest_data is not None and not latest_data.empty:
                active_indices += 1
                latest_row = latest_data.iloc[-1]
                
                if latest_row['price_change_pct'] > 0:
                    bullish_count += 1
                elif latest_row['price_change_pct'] < 0:
                    bearish_count += 1
        
        return {
            'total_indices': total_indices,
            'active_indices': active_indices,
            'bullish_indices': bullish_count,
            'bearish_indices': bearish_count,
            'neutral_indices': active_indices - bullish_count - bearish_count
        }
