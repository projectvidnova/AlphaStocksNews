"""
Options Runner for AlphaStock Trading System
Handles options (CE/PE) data collection and analysis.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from .base_runner import BaseRunner
from ..utils.timezone_utils import get_current_time, is_market_hours


class OptionsRunner(BaseRunner):
    """
    Handles options data collection and processing.
    
    Manages:
    - Options chain data
    - Strike selection
    - Greeks calculation
    - Expiry management
    - IV analysis
    """
    
    def __init__(self, api_client, data_cache, underlying_symbols: List[str], 
                 interval_seconds: int = 10):
        """
        Initialize Options Runner.
        
        Args:
            api_client: Kite API client
            data_cache: Data cache
            underlying_symbols: List of underlying symbols (NIFTY, BANKNIFTY, etc.)
            interval_seconds: Collection frequency
        """
        self.underlying_symbols = underlying_symbols
        self.options_symbols = []  # Will be populated with actual option symbols
        
        super().__init__(
            api_client=api_client,
            data_cache=data_cache,
            symbols=[],  # Will be populated after getting option chains
            interval_seconds=interval_seconds,
            runner_name="OptionsRunner"
        )
        
        # Options-specific settings
        self.strike_range = 10  # Number of strikes above/below ATM
        self.expiry_months = 2  # Number of expiry months to track
        
        # Load underlying symbol mapping from config
        from src.utils.secrets_manager import get_secrets_manager
        secrets_manager = get_secrets_manager()
        config = secrets_manager.get_trading_config()
        self.underlying_mapping = config.get('underlying_symbol_mapping', {})
        
        if not self.underlying_mapping:
            self.logger.warning("No underlying_symbol_mapping found in config. Using default mapping.")
            # Fallback to basic mapping
            self.underlying_mapping = {
                'NIFTY': {'nse_symbol': 'NIFTY 50', 'nfo_name': 'NIFTY'},
                'BANKNIFTY': {'nse_symbol': 'NIFTY BANK', 'nfo_name': 'BANKNIFTY'},
                'FINNIFTY': {'nse_symbol': 'NIFTY FIN SERVICE', 'nfo_name': 'FINNIFTY'}
            }
        
        # Options chain cache
        self.options_chains: Dict[str, pd.DataFrame] = {}
        self.last_chain_update: Dict[str, datetime] = {}
        
        # Greeks calculation settings
        self.risk_free_rate = 0.06  # 6% risk-free rate
        
        self.logger.info(f"Options Runner initialized for {len(underlying_symbols)} underlyings")
        self.logger.info(f"Loaded symbol mapping for {len(self.underlying_mapping)} underlyings")
        
        # Initialize options chains
        self._initialize_options_chains()
    
    def get_asset_type(self) -> str:
        """Return asset type."""
        return "OPTIONS"
    
    def _get_underlying_price(self, underlying: str) -> float:
        """
        Get current price of underlying asset.
        
        Uses the mapping configuration to translate symbol names between exchanges.
        For example: "NIFTY" (config) → "NIFTY 50" (NSE symbol for quote)
        
        Args:
            underlying: Underlying symbol from config (e.g., "NIFTY", "BANKNIFTY")
            
        Returns:
            Current price or 0 if not available
        """
        try:
            # Get the NSE symbol from mapping
            mapping = self.underlying_mapping.get(underlying, {})
            nse_symbol = mapping.get('nse_symbol', underlying)
            exchange = mapping.get('exchange', 'NSE')
            
            self.logger.debug(f"Getting price for {underlying}: NSE symbol={nse_symbol}, exchange={exchange}")
            
            # Get quote from appropriate exchange
            quote_data = self.api_client.get_quote([nse_symbol], exchange=exchange)
            
            if quote_data and nse_symbol in quote_data:
                price = quote_data[nse_symbol].get('last_price', 0)
                if price > 0:
                    self.logger.debug(f"Got price for {underlying}: {price}")
                    return price
                else:
                    self.logger.warning(f"Invalid price (0) for {underlying}")
            else:
                self.logger.warning(f"No quote data for {underlying} (NSE symbol: {nse_symbol})")
            
            return 0
            
        except Exception as e:
            self.logger.error(f"Error getting underlying price for {underlying}: {e}")
            return 0
    
    def _initialize_options_chains(self):
        """Initialize options chains for underlying symbols."""
        try:
            for underlying in self.underlying_symbols:
                self._update_options_chain(underlying)
        except Exception as e:
            self.logger.error(f"Error initializing options chains: {e}")
    
    def _update_options_chain(self, underlying: str):
        """Update options chain for underlying symbol."""
        try:
            # Get the NFO name from mapping (might be different from config name)
            mapping = self.underlying_mapping.get(underlying, {})
            nfo_name = mapping.get('nfo_name', underlying)
            
            self.logger.info(f"Updating options chain for {underlying} (NFO name: {nfo_name})")
            
            # Get instruments from NFO exchange
            instruments = self.api_client.get_instruments("NFO")  # Options segment
            
            if not instruments:
                self.logger.warning(f"No instruments fetched from NFO exchange")
                return
            
            # Filter options for this underlying using the NFO name
            underlying_options = [
                inst for inst in instruments 
                if inst.get('name', '').upper() == nfo_name.upper()
                and inst.get('instrument_type') in ['CE', 'PE']
            ]
            
            self.logger.info(f"Found {len(underlying_options)} options for {underlying} in NFO")
            
            # Create options chain DataFrame
            chain_data = []
            for option in underlying_options:
                chain_data.append({
                    'symbol': option.get('tradingsymbol'),
                    'underlying': underlying,
                    'instrument_token': option.get('instrument_token'),
                    'strike': option.get('strike', 0),
                    'expiry': option.get('expiry'),
                    'option_type': option.get('instrument_type'),  # CE or PE
                    'lot_size': option.get('lot_size', 1),
                })
            
            if chain_data:
                chain_df = pd.DataFrame(chain_data)
                chain_df['expiry'] = pd.to_datetime(chain_df['expiry'])
                
                # Store in cache
                self.options_chains[underlying] = chain_df
                self.last_chain_update[underlying] = get_current_time()
                
                # Update symbols list for this underlying
                relevant_options = self._filter_relevant_options(underlying, chain_df)
                self.options_symbols.extend(relevant_options['symbol'].tolist())
                
                self.logger.info(f"Updated options chain for {underlying}: {len(relevant_options)} options")
        
        except Exception as e:
            self.logger.error(f"Error updating options chain for {underlying}: {e}")
    
    def _filter_relevant_options(self, underlying: str, chain_df: pd.DataFrame) -> pd.DataFrame:
        """Filter to get relevant options based on strike range and expiry."""
        try:
            # Get current underlying price using the helper method
            # This will automatically use the correct NSE symbol from mapping
            current_price = self._get_underlying_price(underlying)
            
            if current_price == 0:
                self.logger.warning(f"Could not get price for {underlying}, cannot filter options")
                return pd.DataFrame()
            
            # Filter by expiry (current and next month)
            current_date = get_current_time()
            relevant_expiries = chain_df[
                (chain_df['expiry'] >= current_date) &
                (chain_df['expiry'] <= current_date + timedelta(days=60))
            ]['expiry'].unique()
            
            # Filter by strike range (ATM ± strike_range)
            strike_min = current_price * 0.85  # 15% OTM
            strike_max = current_price * 1.15  # 15% OTM
            
            filtered_df = chain_df[
                (chain_df['strike'] >= strike_min) &
                (chain_df['strike'] <= strike_max) &
                (chain_df['expiry'].isin(relevant_expiries))
            ].copy()
            
            return filtered_df
            
        except Exception as e:
            self.logger.error(f"Error filtering options for {underlying}: {e}")
            return pd.DataFrame()
    
    def fetch_market_data(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Fetch options market data.
        
        Args:
            symbols: List of option symbols
            
        Returns:
            Dictionary with options data
        """
        if not symbols:
            symbols = self.options_symbols
        
        try:
            # Get comprehensive quote data for options from NFO exchange
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
                        'oi': raw_quote.get('oi', 0),  # Open Interest for options
                        'oi_day_high': raw_quote.get('oi_day_high', 0),
                        'oi_day_low': raw_quote.get('oi_day_low', 0),
                        'buy_quantity': raw_quote.get('buy_quantity', 0),
                        'sell_quantity': raw_quote.get('sell_quantity', 0)
                    }
                    
                    # Add option-specific metadata
                    option_info = self._parse_option_symbol(symbol)
                    if option_info:
                        data.update(option_info)
                    
                    combined_data[symbol] = data
            
            self.logger.debug(f"Fetched options data for {len(combined_data)} contracts")
            return combined_data
            
        except Exception as e:
            self.logger.error(f"Error fetching options data: {e}")
            return {}
    
    def process_data(self, symbol: str, raw_data: Any) -> pd.DataFrame:
        """
        Process raw options data.
        
        Args:
            symbol: Option symbol
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
            
            # Get option metadata
            underlying = raw_data.get('underlying', '')
            strike = raw_data.get('strike', 0)
            option_type = raw_data.get('option_type', '')
            expiry = raw_data.get('expiry', '')
            
            # Calculate Greeks (simplified)
            greeks = self._calculate_greeks(symbol, ltp, strike, option_type, expiry)
            
            # Calculate other metrics
            price_change = ltp - close_price if close_price > 0 else 0
            price_change_pct = (price_change / close_price * 100) if close_price > 0 else 0
            
            # Create DataFrame
            df = pd.DataFrame([{
                'timestamp': current_time,
                'symbol': symbol,
                'underlying': underlying,
                'asset_type': 'OPTION',
                'option_type': option_type,
                'strike': strike,
                'expiry': expiry,
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'ltp': ltp,
                'volume': volume,
                'price_change': price_change,
                'price_change_pct': price_change_pct,
                'delta': greeks.get('delta', 0),
                'gamma': greeks.get('gamma', 0),
                'theta': greeks.get('theta', 0),
                'vega': greeks.get('vega', 0),
                'iv': greeks.get('iv', 0),  # Implied Volatility
                'time_to_expiry': greeks.get('tte', 0),
                'moneyness': self._calculate_moneyness(ltp, strike, underlying),
            }])
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error processing options data for {symbol}: {e}")
            return pd.DataFrame()
    
    def _parse_option_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Parse option symbol to extract metadata."""
        try:
            # Example: NIFTY24DEC25000CE
            # This parsing logic depends on the symbol format from Kite
            parts = symbol.split('CE') if 'CE' in symbol else symbol.split('PE')
            if len(parts) == 2:
                base_part = parts[0]
                option_type = 'CE' if 'CE' in symbol else 'PE'
                
                # Extract strike (last digits before CE/PE)
                strike_str = ''.join(filter(str.isdigit, base_part[-8:]))
                strike = float(strike_str) if strike_str else 0
                
                # Extract underlying (everything before date/strike)
                underlying = base_part.split('24')[0] if '24' in base_part else base_part[:5]
                
                return {
                    'underlying': underlying,
                    'strike': strike,
                    'option_type': option_type,
                    'expiry': ''  # Would need proper date parsing
                }
        except:
            pass
        return None
    
    def _calculate_greeks(self, symbol: str, price: float, strike: float, 
                         option_type: str, expiry: str) -> Dict[str, float]:
        """Calculate options Greeks (simplified Black-Scholes)."""
        try:
            # This is a simplified calculation
            # In production, you'd use a proper options pricing library
            
            # Get underlying price
            underlying = self._parse_option_symbol(symbol)
            if not underlying:
                return {}
            
            underlying_symbol = underlying.get('underlying', '')
            S = self._get_underlying_price(underlying_symbol)  # Underlying price
            if S == 0:
                return {}
            K = strike  # Strike price
            
            # Time to expiry (simplified)
            tte = 30 / 365  # Assume 30 days for now
            
            # Simplified Greeks calculation
            if option_type == 'CE':  # Call option
                delta = 0.6 if S > K else 0.3  # Simplified
            else:  # Put option
                delta = -0.3 if S < K else -0.6  # Simplified
            
            return {
                'delta': delta,
                'gamma': 0.01,  # Simplified
                'theta': -0.05,  # Time decay
                'vega': 0.1,    # Volatility sensitivity
                'iv': 20.0,     # Implied volatility %
                'tte': tte
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating Greeks for {symbol}: {e}")
            return {}
    
    def _calculate_moneyness(self, option_price: float, strike: float, underlying: str) -> str:
        """Calculate option moneyness (ITM/ATM/OTM)."""
        try:
            underlying_price = self._get_underlying_price(underlying)
            if underlying_price == 0:
                return "UNKNOWN"
            
            # For calls
            if underlying_price > strike * 1.02:
                return "ITM"
            elif underlying_price < strike * 0.98:
                return "OTM"
            else:
                return "ATM"
                
        except:
            return "UNKNOWN"
    
    def get_options_chain(self, underlying: str, expiry: Optional[str] = None) -> pd.DataFrame:
        """
        Get complete options chain for underlying.
        
        Args:
            underlying: Underlying symbol
            expiry: Specific expiry (optional)
            
        Returns:
            Options chain DataFrame
        """
        try:
            if underlying not in self.options_chains:
                self._update_options_chain(underlying)
            
            chain_df = self.options_chains.get(underlying, pd.DataFrame())
            
            if expiry and not chain_df.empty:
                chain_df = chain_df[chain_df['expiry'] == expiry]
            
            return chain_df
            
        except Exception as e:
            self.logger.error(f"Error getting options chain for {underlying}: {e}")
            return pd.DataFrame()
    
    def get_atm_strikes(self, underlying: str) -> Dict[str, float]:
        """Get ATM (At The Money) strikes for underlying."""
        try:
            current_price = self._get_underlying_price(underlying)
            if current_price == 0:
                return {}
            
            # Find nearest strikes
            chain_df = self.get_options_chain(underlying)
            if chain_df.empty:
                return {}
            
            # Get unique strikes and find closest to current price
            strikes = sorted(chain_df['strike'].unique())
            atm_strike = min(strikes, key=lambda x: abs(x - current_price))
            
            return {
                'underlying_price': current_price,
                'atm_strike': atm_strike,
                'strikes_available': strikes
            }
            
        except Exception as e:
            self.logger.error(f"Error getting ATM strikes for {underlying}: {e}")
            return {}
    
    def get_options_summary(self) -> Dict[str, Any]:
        """Get options market summary."""
        total_contracts = len(self.options_symbols)
        active_contracts = 0
        total_volume = 0
        
        # Get data for active contracts
        for symbol in self.options_symbols:
            latest_data = self.get_latest_data(symbol)
            if latest_data is not None and not latest_data.empty:
                active_contracts += 1
                latest_row = latest_data.iloc[-1]
                total_volume += latest_row.get('volume', 0)
        
        return {
            'total_contracts': total_contracts,
            'active_contracts': active_contracts,
            'total_volume': total_volume,
            'underlyings_tracked': len(self.underlying_symbols),
            'last_update': get_current_time().isoformat()
        }
