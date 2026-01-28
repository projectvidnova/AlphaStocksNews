"""
Commodity Runner for AlphaStock Trading System
Handles commodity instruments like Gold, Silver, Crude Oil, etc.
"""

import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
from .base_runner import BaseRunner
from ..utils.timezone_utils import get_current_time, is_market_hours


class CommodityRunner(BaseRunner):
    """
    Handles commodity instruments data collection.
    
    Manages:
    - Precious metals (Gold, Silver)
    - Energy commodities (Crude Oil, Natural Gas)
    - Agricultural commodities
    - Base metals (Copper, Zinc, etc.)
    """
    
    def __init__(self, api_client, data_cache, commodities: List[str], 
                 interval_seconds: int = 10):
        """
        Initialize Commodity Runner.
        
        Args:
            api_client: Kite API client
            data_cache: Data cache
            commodities: List of commodity symbols
            interval_seconds: Collection frequency
        """
        super().__init__(
            api_client=api_client,
            data_cache=data_cache,
            symbols=commodities,
            interval_seconds=interval_seconds,
            runner_name="CommodityRunner"
        )
        
        # Commodity categories
        self.commodity_categories = {
            'PRECIOUS_METALS': ['GOLD', 'SILVER', 'GOLDM', 'SILVERM'],
            'ENERGY': ['CRUDEOIL', 'NATURALGAS', 'CRUDEOILM', 'NATURALGASM'],
            'BASE_METALS': ['COPPER', 'ZINC', 'NICKEL', 'ALUMINIUM', 'LEAD'],
            'AGRICULTURAL': ['WHEAT', 'RICE', 'SUGAR', 'COTTON', 'SOYBEAN', 'MAIZE']
        }
        
        # Trading units and lot sizes
        self.commodity_specs = {
            'GOLD': {'unit': 'grams', 'lot_size': 100, 'tick_size': 1},
            'SILVER': {'unit': 'kg', 'lot_size': 30, 'tick_size': 1},
            'CRUDEOIL': {'unit': 'barrels', 'lot_size': 100, 'tick_size': 1},
            'NATURALGAS': {'unit': 'mmBtu', 'lot_size': 1250, 'tick_size': 0.10},
            'COPPER': {'unit': 'kg', 'lot_size': 2500, 'tick_size': 0.05},
        }
        
        self.logger.info(f"Commodity Runner initialized for {len(commodities)} commodities")
    
    def get_asset_type(self) -> str:
        """Return asset type."""
        return "COMMODITY"
    
    def fetch_market_data(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Fetch commodity data.
        
        Args:
            symbols: List of commodity symbols
            
        Returns:
            Dictionary with commodity data
        """
        try:
            # Get comprehensive quote data from MCX exchange (commodities are traded on MCX)
            quote_data = self.api_client.get_quote(symbols, exchange="MCX")
            
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
                        'category': self._get_commodity_category(symbol),
                        'specs': self.commodity_specs.get(symbol, {})
                    }
                    
                    combined_data[symbol] = data
            
            self.logger.debug(f"Fetched commodity data for {len(combined_data)} instruments")
            return combined_data
            
        except Exception as e:
            self.logger.error(f"Error fetching commodity data: {e}")
            return {}
    
    def process_data(self, symbol: str, raw_data: Any) -> pd.DataFrame:
        """
        Process raw commodity data.
        
        Args:
            symbol: Commodity symbol
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
            
            # Calculate commodity-specific metrics
            price_change = ltp - close_price if close_price > 0 else 0
            price_change_pct = (price_change / close_price * 100) if close_price > 0 else 0
            
            # Calculate volatility
            volatility = self._calculate_volatility(symbol, ltp)
            
            # Calculate technical indicators
            rsi = self._calculate_rsi(symbol, ltp)
            moving_avg_20 = self._calculate_moving_average(symbol, ltp, 20)
            
            # Get commodity specifications
            specs = self.commodity_specs.get(symbol, {})
            lot_size = specs.get('lot_size', 1)
            tick_size = specs.get('tick_size', 0.01)
            
            # Calculate position metrics
            notional_value = ltp * lot_size
            margin_requirement = self._calculate_margin_requirement(symbol, ltp)
            
            # Create DataFrame
            df = pd.DataFrame([{
                'timestamp': current_time,
                'symbol': symbol,
                'asset_type': 'COMMODITY',
                'category': raw_data.get('category', 'UNKNOWN'),
                'unit': specs.get('unit', 'units'),
                'lot_size': lot_size,
                'tick_size': tick_size,
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'ltp': ltp,
                'volume': volume,
                'price_change': price_change,
                'price_change_pct': price_change_pct,
                'volatility': volatility,
                'rsi': rsi,
                'moving_avg_20': moving_avg_20,
                'notional_value': notional_value,
                'margin_requirement': margin_requirement,
                'commodity_trend': self._get_commodity_trend(price_change_pct, rsi),
                'seasonal_factor': self._get_seasonal_factor(symbol),
                'is_trading': self._is_commodity_trading_hours(symbol),
            }])
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error processing commodity data for {symbol}: {e}")
            return pd.DataFrame()
    
    def _get_commodity_category(self, symbol: str) -> str:
        """Get commodity category."""
        symbol_upper = symbol.upper()
        
        for category, commodities in self.commodity_categories.items():
            if any(commodity in symbol_upper for commodity in commodities):
                return category
        
        return 'OTHER'
    
    def _calculate_volatility(self, symbol: str, current_price: float) -> float:
        """Calculate commodity volatility."""
        try:
            historical_data = self.get_latest_data(symbol)
            if historical_data is None or len(historical_data) < 10:
                return 0.0
            
            # Use last 10 data points for volatility
            prices = historical_data['ltp'].tail(10).tolist() + [current_price]
            returns = [(prices[i] / prices[i-1] - 1) for i in range(1, len(prices))]
            
            if len(returns) > 1:
                volatility = pd.Series(returns).std() * 100
                return round(volatility, 2)
            
            return 0.0
            
        except Exception:
            return 0.0
    
    def _calculate_rsi(self, symbol: str, current_price: float) -> float:
        """Calculate RSI for commodity."""
        try:
            historical_data = self.get_latest_data(symbol)
            if historical_data is None or len(historical_data) < 14:
                return 50.0  # Neutral RSI
            
            prices = historical_data['ltp'].tail(14).tolist() + [current_price]
            
            # Calculate price changes
            deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
            
            # Separate gains and losses
            gains = [delta if delta > 0 else 0 for delta in deltas]
            losses = [-delta if delta < 0 else 0 for delta in deltas]
            
            # Calculate average gains and losses
            avg_gain = sum(gains) / len(gains) if gains else 0
            avg_loss = sum(losses) / len(losses) if losses else 0
            
            if avg_loss == 0:
                return 100.0
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return round(rsi, 2)
            
        except Exception:
            return 50.0
    
    def _calculate_moving_average(self, symbol: str, current_price: float, period: int) -> float:
        """Calculate moving average."""
        try:
            historical_data = self.get_latest_data(symbol)
            if historical_data is None or len(historical_data) < period - 1:
                return current_price
            
            prices = historical_data['ltp'].tail(period - 1).tolist() + [current_price]
            return round(sum(prices) / len(prices), 2)
            
        except Exception:
            return current_price
    
    def _calculate_margin_requirement(self, symbol: str, price: float) -> float:
        """Calculate approximate margin requirement."""
        try:
            specs = self.commodity_specs.get(symbol, {})
            lot_size = specs.get('lot_size', 1)
            
            # Approximate margin as percentage of notional value
            margin_percentage = {
                'GOLD': 0.04,      # 4%
                'SILVER': 0.05,    # 5%
                'CRUDEOIL': 0.06,  # 6%
                'NATURALGAS': 0.08, # 8%
                'COPPER': 0.05,    # 5%
            }
            
            margin_pct = margin_percentage.get(symbol, 0.05)  # Default 5%
            notional_value = price * lot_size
            margin = notional_value * margin_pct
            
            return round(margin, 2)
            
        except Exception:
            return 0.0
    
    def _get_commodity_trend(self, price_change_pct: float, rsi: float) -> str:
        """Determine commodity trend."""
        if price_change_pct > 2.0 and rsi > 70:
            return 'STRONG_BULLISH'
        elif price_change_pct > 0.5 and rsi > 50:
            return 'BULLISH'
        elif price_change_pct < -2.0 and rsi < 30:
            return 'STRONG_BEARISH'
        elif price_change_pct < -0.5 and rsi < 50:
            return 'BEARISH'
        else:
            return 'SIDEWAYS'
    
    def _get_seasonal_factor(self, symbol: str) -> str:
        """Get seasonal factor for commodity."""
        current_month = get_current_time().month
        
        # Simplified seasonal patterns
        seasonal_patterns = {
            'GOLD': {
                'months': [10, 11, 12, 1, 2],  # Wedding season, festivals
                'factor': 'POSITIVE'
            },
            'SILVER': {
                'months': [10, 11, 12, 1, 2],
                'factor': 'POSITIVE'
            },
            'CRUDEOIL': {
                'months': [11, 12, 1, 2],  # Winter demand
                'factor': 'POSITIVE'
            },
            'NATURALGAS': {
                'months': [11, 12, 1, 2, 3],  # Heating season
                'factor': 'POSITIVE'
            }
        }
        
        pattern = seasonal_patterns.get(symbol, {})
        if current_month in pattern.get('months', []):
            return pattern.get('factor', 'NEUTRAL')
        else:
            return 'NEUTRAL'
    
    def _is_commodity_trading_hours(self, symbol: str) -> bool:
        """Check if commodity is in trading hours."""
        # Commodities have different trading hours
        # This is a simplified implementation
        try:
            current_hour = get_current_time().hour
            
            # Most commodities trade during market hours
            if 9 <= current_hour <= 15:  # 9:00 AM to 3:30 PM
                return True
            
            # Some commodities have extended hours
            energy_commodities = ['CRUDEOIL', 'NATURALGAS']
            if symbol in energy_commodities and 9 <= current_hour <= 23:
                return True
            
            return False
            
        except:
            return True  # Default to true if unable to check
    
    def get_commodity_correlation(self) -> Dict[str, float]:
        """Get correlations between commodities."""
        correlations = {}
        
        # Simplified correlation matrix
        # In practice, this would be calculated from historical data
        correlation_matrix = {
            ('GOLD', 'SILVER'): 0.75,
            ('CRUDEOIL', 'NATURALGAS'): 0.60,
            ('COPPER', 'ZINC'): 0.70,
            ('GOLD', 'CRUDEOIL'): -0.15,  # Often negative correlation
        }
        
        for (symbol1, symbol2), correlation in correlation_matrix.items():
            if symbol1 in self.symbols and symbol2 in self.symbols:
                correlations[f"{symbol1}_{symbol2}"] = correlation
        
        return correlations
    
    def get_commodity_seasonality(self) -> Dict[str, Dict]:
        """Get seasonality information for commodities."""
        seasonality = {}
        
        for symbol in self.symbols:
            latest_data = self.get_latest_data(symbol)
            if latest_data is not None and not latest_data.empty:
                latest_row = latest_data.iloc[-1]
                
                seasonality[symbol] = {
                    'current_seasonal_factor': latest_row.get('seasonal_factor', 'NEUTRAL'),
                    'category': latest_row.get('category', 'UNKNOWN'),
                    'typical_seasonal_pattern': self._get_typical_seasonal_pattern(symbol)
                }
        
        return seasonality
    
    def _get_typical_seasonal_pattern(self, symbol: str) -> str:
        """Get typical seasonal pattern description."""
        patterns = {
            'GOLD': 'Strong in Oct-Feb (wedding season, festivals)',
            'SILVER': 'Strong in Oct-Feb (wedding season, industrial demand)',
            'CRUDEOIL': 'Strong in winter months (heating demand)',
            'NATURALGAS': 'Strong in Nov-Mar (heating season)',
            'COPPER': 'Strong in Q1 (construction season)',
        }
        
        return patterns.get(symbol, 'No clear seasonal pattern')
    
    def get_commodity_summary(self) -> Dict[str, Any]:
        """Get commodity runner summary."""
        summary = {
            'total_commodities': len(self.symbols),
            'categories': {},
            'performance': {
                'gainers': [],
                'losers': [],
                'high_volatility': []
            },
            'margin_requirements': {},
            'seasonal_outlook': {}
        }
        
        for symbol in self.symbols:
            latest_data = self.get_latest_data(symbol)
            if latest_data is not None and not latest_data.empty:
                latest_row = latest_data.iloc[-1]
                
                # Category breakdown
                category = latest_row.get('category', 'UNKNOWN')
                if category not in summary['categories']:
                    summary['categories'][category] = 0
                summary['categories'][category] += 1
                
                # Performance tracking
                change_pct = latest_row['price_change_pct']
                volatility = latest_row.get('volatility', 0)
                
                if change_pct > 1.0:
                    summary['performance']['gainers'].append({
                        'symbol': symbol,
                        'change_pct': change_pct
                    })
                elif change_pct < -1.0:
                    summary['performance']['losers'].append({
                        'symbol': symbol,
                        'change_pct': change_pct
                    })
                
                if volatility > 3.0:
                    summary['performance']['high_volatility'].append({
                        'symbol': symbol,
                        'volatility': volatility
                    })
                
                # Margin requirements
                summary['margin_requirements'][symbol] = latest_row.get('margin_requirement', 0)
                
                # Seasonal outlook
                summary['seasonal_outlook'][symbol] = latest_row.get('seasonal_factor', 'NEUTRAL')
        
        # Sort performance lists
        summary['performance']['gainers'].sort(key=lambda x: x['change_pct'], reverse=True)
        summary['performance']['losers'].sort(key=lambda x: x['change_pct'])
        summary['performance']['high_volatility'].sort(key=lambda x: x['volatility'], reverse=True)
        
        return summary
    
    def get_commodity_alerts(self, price_threshold: float = 2.0, 
                           volatility_threshold: float = 5.0) -> List[Dict[str, Any]]:
        """Generate commodity alerts based on thresholds."""
        alerts = []
        
        for symbol in self.symbols:
            latest_data = self.get_latest_data(symbol)
            if latest_data is not None and not latest_data.empty:
                latest_row = latest_data.iloc[-1]
                
                change_pct = latest_row['price_change_pct']
                volatility = latest_row.get('volatility', 0)
                rsi = latest_row.get('rsi', 50)
                
                # Price movement alerts
                if abs(change_pct) >= price_threshold:
                    alerts.append({
                        'symbol': symbol,
                        'type': 'PRICE_MOVEMENT',
                        'severity': 'HIGH' if abs(change_pct) >= price_threshold * 1.5 else 'MEDIUM',
                        'message': f"{symbol} moved {change_pct:.2f}%",
                        'value': change_pct,
                        'timestamp': latest_row['timestamp']
                    })
                
                # Volatility alerts
                if volatility >= volatility_threshold:
                    alerts.append({
                        'symbol': symbol,
                        'type': 'HIGH_VOLATILITY',
                        'severity': 'MEDIUM',
                        'message': f"{symbol} high volatility: {volatility:.2f}%",
                        'value': volatility,
                        'timestamp': latest_row['timestamp']
                    })
                
                # RSI alerts
                if rsi >= 80:
                    alerts.append({
                        'symbol': symbol,
                        'type': 'OVERBOUGHT',
                        'severity': 'LOW',
                        'message': f"{symbol} overbought (RSI: {rsi:.2f})",
                        'value': rsi,
                        'timestamp': latest_row['timestamp']
                    })
                elif rsi <= 20:
                    alerts.append({
                        'symbol': symbol,
                        'type': 'OVERSOLD',
                        'severity': 'LOW',
                        'message': f"{symbol} oversold (RSI: {rsi:.2f})",
                        'value': rsi,
                        'timestamp': latest_row['timestamp']
                    })
        
        return alerts
