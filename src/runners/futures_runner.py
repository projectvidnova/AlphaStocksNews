"""
Futures Runner for AlphaStock Trading System
Handles futures contracts across different asset classes.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from .base_runner import BaseRunner
from ..utils.timezone_utils import get_current_time, is_market_hours


class FuturesRunner(BaseRunner):
    """
    Handles futures contracts data collection.
    
    Manages:
    - Stock futures (individual stock contracts)
    - Index futures (Nifty, Bank Nifty futures)
    - Commodity futures
    - Currency futures
    """
    
    def __init__(self, api_client, data_cache, futures: List[str], 
                 interval_seconds: int = 5):
        """
        Initialize Futures Runner.
        
        Args:
            api_client: Kite API client
            data_cache: Data cache
            futures: List of futures symbols
            interval_seconds: Collection frequency
        """
        super().__init__(
            api_client=api_client,
            data_cache=data_cache,
            symbols=futures,
            interval_seconds=interval_seconds,
            runner_name="FuturesRunner"
        )
        
        # Futures categories
        self.futures_categories = {
            'STOCK_FUTURES': ['FUT'],  # Individual stock futures
            'INDEX_FUTURES': ['NIFTY', 'BANKNIFTY', 'FINNIFTY'],
            'COMMODITY_FUTURES': ['GOLD', 'SILVER', 'CRUDEOIL', 'NATURALGAS'],
            'CURRENCY_FUTURES': ['USDINR', 'EURINR', 'GBPINR', 'JPYINR']
        }
        
        # Contract specifications
        self.futures_specs = self._initialize_futures_specs()
        
        self.logger.info(f"Futures Runner initialized for {len(futures)} contracts")
    
    def _initialize_futures_specs(self) -> Dict[str, Dict]:
        """Initialize futures contract specifications."""
        return {
            'NIFTY_FUT': {
                'lot_size': 50,
                'tick_size': 0.05,
                'margin_percentage': 0.10,
                'underlying': 'NIFTY50'
            },
            'BANKNIFTY_FUT': {
                'lot_size': 25,
                'tick_size': 0.05,
                'margin_percentage': 0.12,
                'underlying': 'BANKNIFTY'
            },
            'FINNIFTY_FUT': {
                'lot_size': 40,
                'tick_size': 0.05,
                'margin_percentage': 0.11,
                'underlying': 'FINNIFTY'
            },
            # Default specs for stock futures
            'DEFAULT_STOCK_FUT': {
                'lot_size': 1,  # Will be determined per stock
                'tick_size': 0.05,
                'margin_percentage': 0.15,
                'underlying': 'STOCK'
            }
        }
    
    def get_asset_type(self) -> str:
        """Return asset type."""
        return "FUTURES"
    
    def fetch_market_data(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Fetch futures data.
        
        Args:
            symbols: List of futures symbols
            
        Returns:
            Dictionary with futures data
        """
        try:
            # Get comprehensive quote data from NFO exchange (futures are traded on NFO)
            quote_data = self.api_client.get_quote(symbols, exchange="NFO")
            
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
                        'oi': raw_quote.get('oi', 0),  # Open Interest for futures
                        'oi_day_high': raw_quote.get('oi_day_high', 0),
                        'oi_day_low': raw_quote.get('oi_day_low', 0),
                        'category': self._get_futures_category(symbol),
                        'specs': self._get_contract_specs(symbol),
                        'expiry_info': self._get_expiry_info(symbol),
                        'underlying_data': self._get_underlying_data(symbol)
                    }
                    
                    combined_data[symbol] = data
            
            self.logger.debug(f"Fetched futures data for {len(combined_data)} contracts")
            return combined_data
            
        except Exception as e:
            self.logger.error(f"Error fetching futures data: {e}")
            return {}
    
    def process_data(self, symbol: str, raw_data: Any) -> pd.DataFrame:
        """
        Process raw futures data.
        
        Args:
            symbol: Futures symbol
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
            oi = raw_data.get('oi', 0)  # Open Interest
            
            # Get contract specifications
            specs = raw_data.get('specs', {})
            lot_size = specs.get('lot_size', 1)
            margin_pct = specs.get('margin_percentage', 0.15)
            
            # Calculate futures-specific metrics
            price_change = ltp - close_price if close_price > 0 else 0
            price_change_pct = (price_change / close_price * 100) if close_price > 0 else 0
            
            # Expiry information
            expiry_info = raw_data.get('expiry_info', {})
            days_to_expiry = expiry_info.get('days_to_expiry', 0)
            
            # Underlying asset data
            underlying_data = raw_data.get('underlying_data', {})
            underlying_price = underlying_data.get('price', ltp)
            
            # Calculate basis and premium
            basis = ltp - underlying_price if underlying_price > 0 else 0
            premium_pct = (basis / underlying_price * 100) if underlying_price > 0 else 0
            
            # Calculate position metrics
            notional_value = ltp * lot_size
            margin_requirement = notional_value * margin_pct
            
            # Technical indicators
            volatility = self._calculate_volatility(symbol, ltp)
            rsi = self._calculate_rsi(symbol, ltp)
            
            # Futures-specific indicators
            cost_of_carry = self._calculate_cost_of_carry(symbol, basis, days_to_expiry)
            rollover_pressure = self._calculate_rollover_pressure(symbol, days_to_expiry, volume, oi)
            
            # Create DataFrame
            df = pd.DataFrame([{
                'timestamp': current_time,
                'symbol': symbol,
                'asset_type': 'FUTURES',
                'category': raw_data.get('category', 'UNKNOWN'),
                'underlying_symbol': specs.get('underlying', 'UNKNOWN'),
                'lot_size': lot_size,
                'margin_percentage': margin_pct,
                'days_to_expiry': days_to_expiry,
                'expiry_date': expiry_info.get('expiry_date', ''),
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'ltp': ltp,
                'volume': volume,
                'open_interest': oi,
                'price_change': price_change,
                'price_change_pct': price_change_pct,
                'underlying_price': underlying_price,
                'basis': basis,
                'premium_pct': premium_pct,
                'notional_value': notional_value,
                'margin_requirement': margin_requirement,
                'volatility': volatility,
                'rsi': rsi,
                'cost_of_carry': cost_of_carry,
                'rollover_pressure': rollover_pressure,
                'futures_trend': self._get_futures_trend(price_change_pct, basis, volume, oi),
                'expiry_proximity': self._get_expiry_proximity(days_to_expiry),
                'is_trading': self._is_trading_hours(),
            }])
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error processing futures data for {symbol}: {e}")
            return pd.DataFrame()
    
    def _get_futures_category(self, symbol: str) -> str:
        """Get futures category."""
        symbol_upper = symbol.upper()
        
        for category, keywords in self.futures_categories.items():
            if any(keyword in symbol_upper for keyword in keywords):
                return category
        
        return 'OTHER_FUTURES'
    
    def _get_contract_specs(self, symbol: str) -> Dict[str, Any]:
        """Get contract specifications for futures."""
        symbol_upper = symbol.upper()
        
        # Check specific contract specs
        for spec_key, specs in self.futures_specs.items():
            if spec_key.replace('_FUT', '') in symbol_upper:
                return specs
        
        # Default to stock futures specs
        return self.futures_specs['DEFAULT_STOCK_FUT']
    
    def _get_expiry_info(self, symbol: str) -> Dict[str, Any]:
        """Extract expiry information from symbol."""
        try:
            # This would typically parse the symbol to extract expiry date
            # For now, returning placeholder logic
            current_date = get_current_time()
            
            # Simplified expiry calculation (last Thursday of month)
            if current_date.day <= 25:  # Current month
                expiry_month = current_date.month
                expiry_year = current_date.year
            else:  # Next month
                if current_date.month == 12:
                    expiry_month = 1
                    expiry_year = current_date.year + 1
                else:
                    expiry_month = current_date.month + 1
                    expiry_year = current_date.year
            
            # Find last Thursday of the month
            import calendar
            last_day = calendar.monthrange(expiry_year, expiry_month)[1]
            expiry_date = datetime(expiry_year, expiry_month, last_day)
            
            # Move to last Thursday
            while expiry_date.weekday() != 3:  # 3 = Thursday
                expiry_date -= timedelta(days=1)
            
            days_to_expiry = (expiry_date - current_date).days
            
            return {
                'expiry_date': expiry_date.strftime('%Y-%m-%d'),
                'days_to_expiry': max(0, days_to_expiry)
            }
            
        except Exception:
            return {
                'expiry_date': '',
                'days_to_expiry': 0
            }
    
    def _get_underlying_data(self, symbol: str) -> Dict[str, Any]:
        """Get underlying asset data."""
        try:
            # This would fetch underlying asset price
            # For now, returning placeholder
            return {
                'price': 0,
                'change_pct': 0
            }
            
        except Exception:
            return {
                'price': 0,
                'change_pct': 0
            }
    
    def _calculate_volatility(self, symbol: str, current_price: float) -> float:
        """Calculate futures volatility."""
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
        """Calculate RSI for futures."""
        try:
            historical_data = self.get_latest_data(symbol)
            if historical_data is None or len(historical_data) < 14:
                return 50.0
            
            prices = historical_data['ltp'].tail(14).tolist() + [current_price]
            
            # Calculate RSI
            deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
            gains = [delta if delta > 0 else 0 for delta in deltas]
            losses = [-delta if delta < 0 else 0 for delta in deltas]
            
            avg_gain = sum(gains) / len(gains) if gains else 0
            avg_loss = sum(losses) / len(losses) if losses else 0
            
            if avg_loss == 0:
                return 100.0
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return round(rsi, 2)
            
        except Exception:
            return 50.0
    
    def _calculate_cost_of_carry(self, symbol: str, basis: float, 
                                days_to_expiry: int) -> float:
        """Calculate annualized cost of carry."""
        try:
            if days_to_expiry <= 0:
                return 0.0
            
            # Simplified cost of carry calculation
            # In practice, this would use risk-free rate and dividends
            annualized_basis = (basis / days_to_expiry) * 365 if days_to_expiry > 0 else 0
            return round(annualized_basis, 2)
            
        except Exception:
            return 0.0
    
    def _calculate_rollover_pressure(self, symbol: str, days_to_expiry: int, 
                                   volume: int, oi: int) -> str:
        """Calculate rollover pressure indicator."""
        try:
            if days_to_expiry > 7:
                return 'NONE'
            
            # High volume and decreasing OI indicates rollover pressure
            historical_data = self.get_latest_data(symbol)
            if historical_data is not None and len(historical_data) > 1:
                prev_oi = historical_data.iloc[-1].get('open_interest', 0)
                oi_change = oi - prev_oi if prev_oi > 0 else 0
                
                volume_oi_ratio = volume / oi if oi > 0 else 0
                
                if oi_change < 0 and volume_oi_ratio > 0.5:
                    return 'HIGH'
                elif volume_oi_ratio > 0.3:
                    return 'MEDIUM'
                else:
                    return 'LOW'
            
            return 'UNKNOWN'
            
        except Exception:
            return 'UNKNOWN'
    
    def _get_futures_trend(self, price_change_pct: float, basis: float, 
                          volume: int, oi: int) -> str:
        """Determine futures trend based on multiple factors."""
        trend_score = 0
        
        # Price movement contribution
        if price_change_pct > 1.0:
            trend_score += 2
        elif price_change_pct > 0.5:
            trend_score += 1
        elif price_change_pct < -1.0:
            trend_score -= 2
        elif price_change_pct < -0.5:
            trend_score -= 1
        
        # Basis contribution (contango vs backwardation)
        if basis > 0:  # Contango
            trend_score += 1
        elif basis < 0:  # Backwardation
            trend_score -= 1
        
        # Volume and OI contribution
        volume_oi_ratio = volume / oi if oi > 0 else 0
        if volume_oi_ratio > 0.5:  # High activity
            if price_change_pct > 0:
                trend_score += 1
            else:
                trend_score -= 1
        
        # Determine trend
        if trend_score >= 3:
            return 'STRONG_BULLISH'
        elif trend_score >= 1:
            return 'BULLISH'
        elif trend_score <= -3:
            return 'STRONG_BEARISH'
        elif trend_score <= -1:
            return 'BEARISH'
        else:
            return 'SIDEWAYS'
    
    def _get_expiry_proximity(self, days_to_expiry: int) -> str:
        """Get expiry proximity indicator."""
        if days_to_expiry <= 3:
            return 'VERY_CLOSE'
        elif days_to_expiry <= 7:
            return 'CLOSE'
        elif days_to_expiry <= 15:
            return 'MEDIUM'
        else:
            return 'FAR'
    
    def _is_trading_hours(self) -> bool:
        """Check if market is in trading hours."""
        try:
            from src.utils.market_hours import is_market_open
            return is_market_open()
        except:
            return True
    
    def get_futures_chain_analysis(self) -> Dict[str, Any]:
        """Analyze futures chain for different expiries."""
        chain_analysis = {}
        
        # Group futures by underlying
        underlying_groups = {}
        
        for symbol in self.symbols:
            latest_data = self.get_latest_data(symbol)
            if latest_data is not None and not latest_data.empty:
                latest_row = latest_data.iloc[-1]
                underlying = latest_row.get('underlying_symbol', 'UNKNOWN')
                
                if underlying not in underlying_groups:
                    underlying_groups[underlying] = []
                
                underlying_groups[underlying].append({
                    'symbol': symbol,
                    'ltp': latest_row['ltp'],
                    'volume': latest_row['volume'],
                    'oi': latest_row['open_interest'],
                    'days_to_expiry': latest_row['days_to_expiry'],
                    'basis': latest_row['basis']
                })
        
        # Analyze each underlying's chain
        for underlying, contracts in underlying_groups.items():
            # Sort by expiry
            contracts.sort(key=lambda x: x['days_to_expiry'])
            
            chain_analysis[underlying] = {
                'total_contracts': len(contracts),
                'total_volume': sum(c['volume'] for c in contracts),
                'total_oi': sum(c['oi'] for c in contracts),
                'term_structure': [
                    {
                        'expiry': c['days_to_expiry'],
                        'price': c['ltp'],
                        'basis': c['basis']
                    } for c in contracts
                ],
                'most_active_contract': max(contracts, key=lambda x: x['volume'])['symbol'] if contracts else None,
                'highest_oi_contract': max(contracts, key=lambda x: x['oi'])['symbol'] if contracts else None
            }
        
        return chain_analysis
    
    def get_rollover_analysis(self, days_threshold: int = 10) -> Dict[str, Any]:
        """Analyze rollover activity for futures near expiry."""
        rollover_analysis = {
            'contracts_near_expiry': [],
            'rollover_recommendations': [],
            'volume_analysis': {}
        }
        
        for symbol in self.symbols:
            latest_data = self.get_latest_data(symbol)
            if latest_data is not None and not latest_data.empty:
                latest_row = latest_data.iloc[-1]
                days_to_expiry = latest_row['days_to_expiry']
                
                if days_to_expiry <= days_threshold:
                    contract_info = {
                        'symbol': symbol,
                        'days_to_expiry': days_to_expiry,
                        'rollover_pressure': latest_row['rollover_pressure'],
                        'volume': latest_row['volume'],
                        'oi': latest_row['open_interest'],
                        'ltp': latest_row['ltp']
                    }
                    
                    rollover_analysis['contracts_near_expiry'].append(contract_info)
                    
                    # Rollover recommendation
                    if latest_row['rollover_pressure'] in ['HIGH', 'MEDIUM']:
                        rollover_analysis['rollover_recommendations'].append({
                            'symbol': symbol,
                            'action': 'CONSIDER_ROLLOVER',
                            'reason': f"High rollover pressure, {days_to_expiry} days to expiry"
                        })
        
        return rollover_analysis
    
    def get_basis_analysis(self) -> Dict[str, Any]:
        """Analyze basis (premium/discount) across futures."""
        basis_analysis = {
            'contango_contracts': [],
            'backwardation_contracts': [],
            'fair_value_contracts': [],
            'statistics': {}
        }
        
        basis_values = []
        
        for symbol in self.symbols:
            latest_data = self.get_latest_data(symbol)
            if latest_data is not None and not latest_data.empty:
                latest_row = latest_data.iloc[-1]
                basis = latest_row['basis']
                premium_pct = latest_row['premium_pct']
                
                basis_values.append(basis)
                
                contract_info = {
                    'symbol': symbol,
                    'basis': basis,
                    'premium_pct': premium_pct,
                    'days_to_expiry': latest_row['days_to_expiry']
                }
                
                if premium_pct > 0.5:  # Contango
                    basis_analysis['contango_contracts'].append(contract_info)
                elif premium_pct < -0.5:  # Backwardation
                    basis_analysis['backwardation_contracts'].append(contract_info)
                else:  # Fair value
                    basis_analysis['fair_value_contracts'].append(contract_info)
        
        # Calculate statistics
        if basis_values:
            basis_analysis['statistics'] = {
                'average_basis': round(sum(basis_values) / len(basis_values), 2),
                'max_basis': max(basis_values),
                'min_basis': min(basis_values),
                'total_contracts': len(basis_values)
            }
        
        return basis_analysis
    
    def get_futures_summary(self) -> Dict[str, Any]:
        """Get futures runner summary."""
        summary = {
            'total_contracts': len(self.symbols),
            'categories': {},
            'expiry_distribution': {
                'very_close': 0,  # <= 3 days
                'close': 0,       # <= 7 days
                'medium': 0,      # <= 15 days
                'far': 0          # > 15 days
            },
            'performance': {
                'gainers': [],
                'losers': []
            },
            'risk_metrics': {
                'high_volatility_contracts': [],
                'high_margin_contracts': []
            }
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
                
                # Expiry distribution
                expiry_proximity = latest_row['expiry_proximity']
                if expiry_proximity == 'VERY_CLOSE':
                    summary['expiry_distribution']['very_close'] += 1
                elif expiry_proximity == 'CLOSE':
                    summary['expiry_distribution']['close'] += 1
                elif expiry_proximity == 'MEDIUM':
                    summary['expiry_distribution']['medium'] += 1
                else:
                    summary['expiry_distribution']['far'] += 1
                
                # Performance
                change_pct = latest_row['price_change_pct']
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
                
                # Risk metrics
                volatility = latest_row.get('volatility', 0)
                margin_req = latest_row.get('margin_requirement', 0)
                
                if volatility > 3.0:
                    summary['risk_metrics']['high_volatility_contracts'].append({
                        'symbol': symbol,
                        'volatility': volatility
                    })
                
                if margin_req > 100000:  # 1 lakh margin
                    summary['risk_metrics']['high_margin_contracts'].append({
                        'symbol': symbol,
                        'margin_requirement': margin_req
                    })
        
        return summary
