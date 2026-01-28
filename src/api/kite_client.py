"""
Kite Connect API Client for AlphaStock Trading System
A wrapper around the official Kite Connect Python client with additional features.
"""

import logging
import time
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass

try:
    from kiteconnect import KiteConnect, KiteTicker
    from kiteconnect.exceptions import (
        GeneralException, TokenException, PermissionException,
        OrderException, InputException, DataException, NetworkException
    )
except ImportError:
    print("Kite Connect library not found. Install with: pip install kiteconnect")
    raise

from src.utils.secrets_manager import get_secrets_manager
from src.utils.logger_setup import setup_logger


@dataclass
class MarketData:
    """Market data structure."""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    ltp: float = None  # Last Traded Price


@dataclass
class OrderResponse:
    """Order response structure."""
    order_id: str
    status: str
    message: str
    data: Dict[str, Any] = None


class KiteAPIClient:
    """
    Enhanced Kite Connect API client with trading system integration.
    """
    
    def __init__(self, secrets_manager=None):
        """
        Initialize the Kite API client.
        
        Args:
            secrets_manager: Optional SecretsManager instance
        """
        self.secrets = secrets_manager or get_secrets_manager()
        
        # Set up logging with colored formatter
        self.logger = setup_logger("kite_api_client")
        
        # Get credentials
        self.creds = self.secrets.get_kite_credentials()
        self.api_key = self.creds['api_key']
        self.api_secret = self.creds['api_secret']
        self.access_token = self.creds['access_token']
        
        # Initialize Kite Connect
        self.kite = None
        self.ticker = None
        self.authenticated = False
        
        # Trading settings
        self.trading_config = self.secrets.get_trading_config()
        self.paper_trading = self.trading_config['paper_trading']
        
        # Cache configuration from trading config
        cache_config = self.trading_config.get('kite_api', {}).get('cache', {})
        self.cache_ttl = {
            'instruments': cache_config.get('instruments_ttl', 21600),  # 6 hours default
            'quote': cache_config.get('quote_ttl', 300),  # 5 minutes default
            'default': cache_config.get('default_ttl', 300)  # 5 minutes default
        }
        
        # Enhanced rate limiting with burst capability
        self.rate_limiter = {
            'tokens': 10,  # Burst tokens available
            'max_tokens': 10,
            'refill_rate': 3,  # tokens per second
            'last_refill': time.time()
        }
        
        # Intelligent caching system
        self._cache = {}
        self._cache_expiry = {}
        self._instruments_cache = {}
        self._cache_stats = {'hits': 0, 'misses': 0, 'hit_rate': 0.0}
        
        # Performance monitoring
        self._perf_metrics = {}
        
        # Connection pooling for better performance
        import requests
        self._session = requests.Session()
        self._session.headers.update({
            'X-Kite-Version': '3',
            'User-Agent': 'AlphaStock/1.0'
        })
        
        self.logger.info("Enhanced Kite API client initialized")
        if self.paper_trading:
            self.logger.info("Running in PAPER TRADING mode")
    
    async def initialize(self, auto_authenticate: bool = True):
        """
        Initialize the Kite Connect client with optimizations.
        
        Args:
            auto_authenticate: If True, will automatically handle authentication if needed
        """
        try:
            if not self.api_key:
                raise ValueError("API key not found. Please set KITE_API_KEY in .env.dev")
            
            # Initialize KiteConnect with connection pooling
            self.kite = KiteConnect(
                api_key=self.api_key,
                debug=False,
                timeout=10
            )
            
            # Authenticate if we have access token
            if self.access_token:
                self.kite.set_access_token(self.access_token)
                await self._verify_connection()
                
                # Preload frequently used data
                await self._preload_cache()
            else:
                if auto_authenticate:
                    # Use integrated authentication manager
                    from src.auth import get_auth_manager
                    auth_manager = get_auth_manager(self.secrets)
                    
                    self.logger.info("No access token found. Starting authentication...")
                    authenticated = await auth_manager.ensure_authenticated(interactive=True)
                    
                    if authenticated:
                        # Get the new access token
                        self.access_token = auth_manager.access_token
                        self.kite.set_access_token(self.access_token)
                        await self._verify_connection()
                        await self._preload_cache()
                    else:
                        raise RuntimeError("Authentication failed. Please check your credentials.")
                else:
                    self.logger.warning("No access token found. Need to authenticate first.")
                    self.logger.info("Run authenticate() method to start OAuth flow")
            
            self.logger.info("Enhanced Kite API client initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Kite client: {e}")
            raise
    
    def authenticate(self) -> str:
        """
        Start the authentication process.
        
        Returns:
            Login URL for OAuth flow
        """
        if not self.kite:
            raise RuntimeError("Kite client not initialized. Call initialize() first.")
        
        try:
            # Generate login URL
            login_url = self.kite.login_url()
            self.logger.info("Authentication required")
            self.logger.info(f"Please visit: {login_url}")
            self.logger.info("After login, call generate_session(request_token) with the request token")
            
            return login_url
            
        except Exception as e:
            self.logger.error(f"Error generating login URL: {e}")
            raise
    
    def generate_session(self, request_token: str) -> Dict[str, Any]:
        """
        Generate session with request token.
        
        Args:
            request_token: Request token from OAuth callback
            
        Returns:
            Session data with access token
        """
        try:
            if not self.api_secret:
                raise ValueError("API secret not found. Please set KITE_API_SECRET in .env.dev")
            
            # Generate session
            data = self.kite.generate_session(request_token, api_secret=self.api_secret)
            
            # Store access token
            self.access_token = data["access_token"]
            self.kite.set_access_token(self.access_token)
            
            # Update in secrets manager
            self.secrets.update_access_token(self.access_token)
            
            self.authenticated = True
            self.logger.info("Authentication successful")
            
            return data
            
        except Exception as e:
            self.logger.error(f"Authentication failed: {e}")
            raise
    
    async def _verify_connection(self):
        """Verify API connection."""
        try:
            # Test with a simple API call
            profile = self.kite.profile()
            self.authenticated = True
            self.logger.info(f"Connected as: {profile.get('user_name', 'Unknown')}")
            
        except Exception as e:
            self.logger.error(f"Connection verification failed: {e}")
            self.authenticated = False
            raise
    
    def _rate_limit(self):
        """Enhanced rate limiting with burst capability."""
        current_time = time.time()
        elapsed = current_time - self.rate_limiter['last_refill']
        
        # Refill tokens based on elapsed time
        tokens_to_add = elapsed * self.rate_limiter['refill_rate']
        self.rate_limiter['tokens'] = min(
            self.rate_limiter['max_tokens'],
            self.rate_limiter['tokens'] + tokens_to_add
        )
        self.rate_limiter['last_refill'] = current_time
        
        # Check if we have tokens available
        if self.rate_limiter['tokens'] >= 1:
            self.rate_limiter['tokens'] -= 1
            return True
        else:
            # Calculate wait time
            wait_time = (1 - self.rate_limiter['tokens']) / self.rate_limiter['refill_rate']
            time.sleep(wait_time)
            self.rate_limiter['tokens'] = 0
            return True
    
    def _get_cache_key(self, method: str, *args, **kwargs) -> str:
        """Generate cache key for method and parameters."""
        import hashlib
        key_data = f"{method}:{str(args)}:{str(sorted(kwargs.items()))}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _is_cache_valid(self, key: str, ttl: int = 300) -> bool:
        """Check if cache entry is valid with TTL."""
        if key not in self._cache:
            return False
        
        entry_time, _ = self._cache[key]
        return time.time() < (entry_time + ttl)
    
    def _get_from_cache(self, key: str, ttl: int = 300):
        """Get data from cache if valid."""
        if self._is_cache_valid(key, ttl):
            entry_time, data = self._cache[key]
            self._cache_stats['hits'] += 1
            self._update_cache_hit_rate()
            return data
        
        self._cache_stats['misses'] += 1 
        self._update_cache_hit_rate()
        return None
    
    def _set_cache(self, key: str, data: Any):
        """Set data in cache with timestamp."""
        self._cache[key] = (time.time(), data)
    
    def _update_cache_hit_rate(self):
        """Update cache hit rate statistics."""
        total = self._cache_stats['hits'] + self._cache_stats['misses']
        if total > 0:
            self._cache_stats['hit_rate'] = self._cache_stats['hits'] / total
    
    async def _preload_cache(self):
        """Preload frequently used data for better performance."""
        try:
            self.logger.info("Preloading cache...")
            
            # Preload instruments list
            instruments = self.kite.instruments()
            self._set_cache('all_instruments', instruments)
            
            # Preload user profile
            profile = self.kite.profile()
            self._set_cache('user_profile', profile)
            
            self.logger.info(f"Cache preloaded with {len(self._cache)} entries")
            
        except Exception as e:
            self.logger.warning(f"Cache preload failed: {e}")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics."""
        return {
            'cache_stats': self._cache_stats,
            'cache_size': len(self._cache),
            'rate_limiter': {
                'tokens_available': self.rate_limiter['tokens'],
                'max_tokens': self.rate_limiter['max_tokens'],
                'refill_rate': self.rate_limiter['refill_rate']
            },
            'authentication': {
                'authenticated': self.authenticated,
                'paper_trading': self.paper_trading
            },
            'performance_metrics': getattr(self, '_perf_metrics', {})
        }
    
    def clear_cache(self):
        """Clear all cached data."""
        self._cache.clear()
        self._cache_stats = {'hits': 0, 'misses': 0, 'hit_rate': 0.0}
        self.logger.info("Cache cleared")
    
    def optimize_connection(self):
        """Optimize connection settings for better performance."""
        if self._session:
            # Configure session for better performance
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            # Retry strategy
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504]
            )
            
            adapter = HTTPAdapter(
                max_retries=retry_strategy,
                pool_maxsize=10,
                pool_block=False
            )
            
            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)
            
            self.logger.info("Connection optimization applied")
    
    def _set_cache(self, key: str, value: Any, ttl: int = 300):
        """Set cache entry with TTL."""
        self._cache_expiry[key] = time.time() + ttl
        return value
    
    # Market Data Methods
    
    def get_instruments(self, exchange: str = "NSE") -> List[Dict[str, Any]]:
        """
        Get instruments list for an exchange.
        
        Args:
            exchange: Exchange name (NSE, BSE, etc.)
            
        Returns:
            List of instruments
        """
        cache_key = f"instruments_{exchange}"
        instruments_ttl = self.cache_ttl['instruments']
        
        # Check if we have cached data in _cache (which has timestamps)
        if cache_key in self._cache and self._is_cache_valid(cache_key, instruments_ttl):
            _, instruments = self._cache[cache_key]
            self.logger.info(f"Cache hit for instruments {exchange}")
            self._cache_stats['hits'] += 1
            self._update_cache_hit_rate()
            return instruments
        
        try:
            self._rate_limit()
            self.logger.warning(f"Fetching instruments for {exchange} from API")
            instruments = self.kite.instruments(exchange)
            
            # Cache the result with timestamp and configured TTL
            self._cache[cache_key] = (time.time(), instruments)
            
            self.logger.info(f"Fetched {len(instruments)} instruments for {exchange}")
            self._cache_stats['misses'] += 1
            self._update_cache_hit_rate()
            return instruments
            
        except Exception as e:
            self.logger.error(f"Error fetching instruments: {e}")
            return []
    
    def get_instrument_token(self, symbol: str, exchange: str = "NSE") -> Optional[str]:
        """
        Get instrument token for a symbol.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
            
        Returns:
            Instrument token or None
        """
        instruments = self.get_instruments(exchange)
        
        # Try exact match first
        for instrument in instruments:
            if instrument['tradingsymbol'] == symbol:
                return instrument['instrument_token']
        
        # Try alternate formats for common indices
        if symbol == 'BANKNIFTY':
            # Try "NIFTY BANK" format
            for instrument in instruments:
                if instrument['tradingsymbol'] == 'NIFTY BANK' or instrument.get('name') == 'NIFTY BANK':
                    self.logger.info(f"Found {symbol} as {instrument['tradingsymbol']}")
                    return instrument['instrument_token']
        
        self.logger.warning(f"Instrument token not found for {symbol}")
        return None
    
    def get_ltp(self, symbols: Union[str, List[str]]) -> Dict[str, float]:
        """
        Get Last Traded Price for symbols.
        
        Args:
            symbols: Symbol or list of symbols
            
        Returns:
            Dictionary with symbol -> LTP mapping
        """
        if isinstance(symbols, str):
            symbols = [symbols]
        
        try:
            self._rate_limit()
            
            # Convert symbols to instrument tokens if needed
            tokens = []
            symbol_token_map = {}
            
            for symbol in symbols:
                if symbol.isdigit():  # Already a token
                    tokens.append(symbol)
                    symbol_token_map[symbol] = symbol
                else:
                    token = self.get_instrument_token(symbol)
                    if token:
                        tokens.append(token)
                        symbol_token_map[str(token)] = symbol
            
            if not tokens:
                return {}
            
            # Get LTP data
            ltp_data = self.kite.ltp(tokens)
            
            # Convert back to symbol mapping
            result = {}
            for token, data in ltp_data.items():
                symbol = symbol_token_map.get(token, token)
                result[symbol] = data['last_price']
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error fetching LTP: {e}")
            return {}
    
    def get_ohlc(self, symbols: Union[str, List[str]]) -> Dict[str, Dict[str, float]]:
        """
        Get OHLC data for symbols.
        
        Args:
            symbols: Symbol or list of symbols
            
        Returns:
            Dictionary with OHLC data
        """
        if isinstance(symbols, str):
            symbols = [symbols]
        
        try:
            self._rate_limit()
            
            # Convert symbols to tokens
            tokens = []
            symbol_token_map = {}
            
            for symbol in symbols:
                if symbol.isdigit():
                    tokens.append(symbol)
                    symbol_token_map[symbol] = symbol
                else:
                    token = self.get_instrument_token(symbol)
                    if token:
                        tokens.append(token)
                        symbol_token_map[str(token)] = symbol
            
            if not tokens:
                return {}
            
            # Get OHLC data
            ohlc_data = self.kite.ohlc(tokens)
            
            # Convert to symbol mapping
            result = {}
            for token, data in ohlc_data.items():
                symbol = symbol_token_map.get(token, token)
                ohlc = data.get('ohlc', {})
                result[symbol] = {
                    'open': ohlc.get('open', 0),
                    'high': ohlc.get('high', 0),
                    'low': ohlc.get('low', 0),
                    'close': ohlc.get('close', 0),
                    'last_price': data.get('last_price', 0)
                }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error fetching OHLC: {e}")
            return {}
    
    def get_quote(self, symbols: Union[str, List[str]], exchange: str = "NSE") -> Dict[str, Dict[str, Any]]:
        """
        Get full market quote for symbols including depth, circuit limits, and more.
        
        This provides comprehensive market data including:
        - OHLC data
        - Last traded price, quantity, and time
        - Volume and average price
        - Buy/Sell quantities
        - Market depth (5 levels each for buy and sell)
        - Circuit limits (upper and lower)
        - Open Interest (for F&O instruments)
        
        Args:
            symbols: Symbol or list of symbols (e.g., "RELIANCE" or ["RELIANCE", "INFY"])
            exchange: Exchange name (NSE, NFO, BSE, MCX, CDS) - defaults to NSE
            
        Returns:
            Dictionary with comprehensive quote data for each symbol
            
        Example:
            >>> client.get_quote("INFY")
            {
                "INFY": {
                    "instrument_token": 408065,
                    "timestamp": "2021-06-08 15:45:56",
                    "last_trade_time": "2021-06-08 15:45:52",
                    "last_price": 1412.95,
                    "last_quantity": 5,
                    "buy_quantity": 0,
                    "sell_quantity": 5191,
                    "volume": 7360198,
                    "average_price": 1412.47,
                    "oi": 0,
                    "oi_day_high": 0,
                    "oi_day_low": 0,
                    "net_change": 0,
                    "lower_circuit_limit": 1250.7,
                    "upper_circuit_limit": 1528.6,
                    "ohlc": {
                        "open": 1396,
                        "high": 1421.75,
                        "low": 1395.55,
                        "close": 1389.65
                    },
                    "depth": {
                        "buy": [...],
                        "sell": [...]
                    }
                }
            }
        """
        if isinstance(symbols, str):
            symbols = [symbols]
        
        try:
            self._rate_limit()
            
            # Convert symbols to tokens with exchange prefix
            tokens = []
            symbol_token_map = {}
            
            for symbol in symbols:
                # Check if symbol already has exchange prefix (e.g., "NSE:RELIANCE")
                if ":" in symbol:
                    tokens.append(symbol)
                    # Extract just the symbol name for mapping
                    symbol_name = symbol.split(":")[1]
                    symbol_token_map[symbol] = symbol_name
                elif symbol.isdigit():
                    # Already a token
                    tokens.append(f"{exchange}:{symbol}")
                    symbol_token_map[f"{exchange}:{symbol}"] = symbol
                else:
                    # Get instrument token
                    token = self.get_instrument_token(symbol, exchange)
                    if token:
                        exchange_symbol = f"{exchange}:{symbol}"
                        tokens.append(exchange_symbol)
                        symbol_token_map[exchange_symbol] = symbol
            
            if not tokens:
                self.logger.warning("No valid tokens found for symbols")
                return {}
            
            # Get quote data from Kite API
            quote_data = self.kite.quote(tokens)
            
            # Convert to symbol mapping (remove exchange prefix from keys)
            result = {}
            for exchange_symbol, data in quote_data.items():
                # Get the original symbol name from our mapping
                symbol = symbol_token_map.get(exchange_symbol, exchange_symbol)
                result[symbol] = data
            
            self.logger.info(f"Fetched quotes for {len(result)} symbols")
            return result
            
        except Exception as e:
            self.logger.error(f"Error fetching quote data: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    async def get_historical_data(self, 
                           symbol: str, 
                           from_date: datetime,
                           to_date: datetime,
                           interval: str = "15minute") -> pd.DataFrame:
        """
        Get historical data for a symbol.
        
        Args:
            symbol: Trading symbol
            from_date: Start date
            to_date: End date  
            interval: Data interval (minute, 3minute, 5minute, 15minute, 30minute, 60minute, day)
            
        Returns:
            DataFrame with OHLCV data
        """
        try:
            # Get instrument token
            token = self.get_instrument_token(symbol)
            if not token:
                raise ValueError(f"Token not found for symbol: {symbol}")
            
            self._rate_limit()
            
            # Log the API call details for debugging
            self.logger.debug(f"Fetching historical data: symbol={symbol}, token={token}, from={from_date}, to={to_date}, interval={interval}")
            
            # Fetch historical data
            data = self.kite.historical_data(
                instrument_token=token,
                from_date=from_date,
                to_date=to_date,
                interval=interval
            )
            
            if not data:
                self.logger.warning(f"Empty response from Kite API for {symbol} (token: {token}) from {from_date} to {to_date}")
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(data)
            df['date'] = pd.to_datetime(df['date'])
            
            # Rename 'date' to 'timestamp' for consistency
            df.rename(columns={'date': 'timestamp'}, inplace=True)
            
            self.logger.info(f"Fetched {len(df)} historical records for {symbol}")
            return df
            
        except Exception as e:
            self.logger.error(f"Error fetching historical data for {symbol}: {e}")
            return pd.DataFrame()
    
    # Trading Methods
    
    def place_order(self,
                   symbol: str,
                   transaction_type: str,
                   quantity: int,
                   order_type: str = "MARKET",
                   product: str = "CNC",
                   variety: str = "regular",
                   price: float = None,
                   trigger_price: float = None,
                   validity: str = "DAY",
                   tag: str = "AlphaStock") -> OrderResponse:
        """
        Place an order.
        
        Args:
            symbol: Trading symbol
            transaction_type: BUY or SELL
            quantity: Order quantity
            order_type: Order type (MARKET, LIMIT, SL, SL-M)
            product: Product type (CNC, MIS, NRML)
            variety: Order variety (regular, amo, co, iceberg)
            price: Order price (for LIMIT orders)
            trigger_price: Trigger price (for SL orders)
            validity: Order validity (DAY, IOC)
            tag: Order tag
            
        Returns:
            OrderResponse object
        """
        if self.paper_trading:
            return self._place_paper_order(symbol, transaction_type, quantity, order_type, price)
        
        try:
            self._rate_limit()
            
            order_params = {
                'tradingsymbol': symbol,
                'exchange': 'NSE',  # Default to NSE
                'transaction_type': transaction_type.upper(),
                'quantity': quantity,
                'order_type': order_type.upper(),
                'product': product.upper(),
                'variety': variety.lower(),
                'validity': validity.upper(),
                'tag': tag
            }
            
            if price:
                order_params['price'] = price
            if trigger_price:
                order_params['trigger_price'] = trigger_price
            
            # Place order
            order_id = self.kite.place_order(**order_params)
            
            self.logger.info(f"Order placed: {order_id} for {symbol}")
            
            return OrderResponse(
                order_id=order_id,
                status="SUCCESS",
                message="Order placed successfully",
                data=order_params
            )
            
        except Exception as e:
            self.logger.error(f"Error placing order: {e}")
            return OrderResponse(
                order_id="",
                status="ERROR",
                message=str(e)
            )
    
    def _place_paper_order(self, symbol: str, transaction_type: str, quantity: int, 
                          order_type: str, price: float = None) -> OrderResponse:
        """Place a paper trading order."""
        import uuid
        
        order_id = f"PAPER_{uuid.uuid4().hex[:8]}"
        
        # Get current price if not provided
        if not price:
            quote_data = self.get_quote(symbol)
            price = quote_data.get(symbol, {}).get('last_price', 0)
        
        self.logger.info(f"PAPER TRADE: {transaction_type} {quantity} {symbol} @ {price}")
        
        return OrderResponse(
            order_id=order_id,
            status="SUCCESS", 
            message=f"Paper order placed: {transaction_type} {quantity} {symbol} @ {price}",
            data={'symbol': symbol, 'type': transaction_type, 'quantity': quantity, 'price': price}
        )
    
    def get_orders(self) -> List[Dict[str, Any]]:
        """Get all orders."""
        if self.paper_trading:
            return []  # Paper trading orders would be stored separately
        
        try:
            self._rate_limit()
            orders = self.kite.orders()
            return orders
            
        except Exception as e:
            self.logger.error(f"Error fetching orders: {e}")
            return []
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions."""
        if self.paper_trading:
            return []  # Paper trading positions would be stored separately
        
        try:
            self._rate_limit()
            positions = self.kite.positions()
            return positions.get('net', [])
            
        except Exception as e:
            self.logger.error(f"Error fetching positions: {e}")
            return []
    
    def get_holdings(self) -> List[Dict[str, Any]]:
        """Get current holdings."""
        if self.paper_trading:
            return []
        
        try:
            self._rate_limit()
            holdings = self.kite.holdings()
            return holdings
            
        except Exception as e:
            self.logger.error(f"Error fetching holdings: {e}")
            return []
    
    # WebSocket Methods (for real-time data)
    
    def start_websocket(self, symbols: List[str], on_tick_callback=None):
        """
        Start WebSocket for real-time data.
        
        Args:
            symbols: List of symbols to subscribe
            on_tick_callback: Callback function for tick data
        """
        if not self.access_token:
            raise ValueError("Access token required for WebSocket")
        
        try:
            # Initialize ticker
            self.ticker = KiteTicker(self.api_key, self.access_token)
            
            def on_ticks(ws, ticks):
                if on_tick_callback:
                    on_tick_callback(ticks)
                else:
                    self.logger.debug(f"Received {len(ticks)} ticks")
            
            def on_connect(ws, response):
                self.logger.info("WebSocket connected")
                # Convert symbols to tokens and subscribe
                tokens = []
                for symbol in symbols:
                    token = self.get_instrument_token(symbol)
                    if token:
                        tokens.append(int(token))
                
                if tokens:
                    ws.subscribe(tokens)
                    ws.set_mode(ws.MODE_FULL, tokens)
                    self.logger.info(f"Subscribed to {len(tokens)} instruments")
            
            def on_close(ws, code, reason):
                self.logger.info(f"WebSocket closed: {code} - {reason}")
            
            # Set callbacks
            self.ticker.on_ticks = on_ticks
            self.ticker.on_connect = on_connect
            self.ticker.on_close = on_close
            
            # Start in separate thread
            self.ticker.connect(threaded=True)
            
        except Exception as e:
            self.logger.error(f"Error starting WebSocket: {e}")
            raise
    
    def stop_websocket(self):
        """Stop WebSocket connection."""
        if self.ticker:
            self.ticker.close()
            self.ticker = None
            self.logger.info("WebSocket stopped")
    
    # Utility Methods
    
    def health_check(self) -> bool:
        """Check API health."""
        try:
            if not self.authenticated:
                return False
            
            # Simple API call to check connectivity
            self.kite.margins()
            return True
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
    
    def get_profile(self) -> Dict[str, Any]:
        """Get user profile."""
        try:
            self._rate_limit()
            return self.kite.profile()
        except Exception as e:
            self.logger.error(f"Error fetching profile: {e}")
            return {}
    
    def get_margins(self) -> Dict[str, Any]:
        """Get margin information."""
        try:
            self._rate_limit()
            return self.kite.margins()
        except Exception as e:
            self.logger.error(f"Error fetching margins: {e}")
            return {}


if __name__ == "__main__":
    # Test the Kite API client
    import asyncio
    
    async def test_client():
        client = KiteAPIClient()
        await client.initialize()
        
        if not client.authenticated:
            print("Not authenticated. Starting OAuth flow...")
            login_url = client.authenticate()
            print(f"Visit: {login_url}")
        else:
            print("Testing API calls...")
            profile = client.get_profile()
            print(f"Profile: {profile.get('user_name', 'Unknown')}")
            
            # Test LTP
            ltp = client.get_ltp(["RELIANCE", "INFY"])
            print(f"LTP: {ltp}")
    
    asyncio.run(test_client())
