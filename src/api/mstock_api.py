import logging
import time
import json
import websocket
import ssl
import threading
import requests
from urllib.parse import urlencode
import hashlib

from ..utils.logger_setup import setup_logger

# Configure logger
logger = setup_logger("mstock_api")

class MStockAPI:
    """
    API client for MStock trading platform
    Handles authentication, HTTP requests and WebSocket connections
    """
    
    def __init__(self, config):
        """Initialize with configuration"""
        self.config = config
        self.api_key = config["api"]["credentials"]["api_key"]
        self.username = config["api"]["credentials"]["username"]
        self.password = config["api"]["credentials"]["password"]
        self.ws_url = config["api"]["urls"]["ws_url"]
        self.timeout = config["api"]["timeout"]
        self.retry_attempts = config["api"]["retry_attempts"]
        self.retry_delay = config["api"]["retry_delay"]
        
        # API base URLs
        self.base_url = "https://api.mstock.trade/openapi/typea"
        
        # Authentication tokens
        self.request_token = None
        self.access_token = None
        
        # HTTP session with proper headers
        self.session = requests.Session()
        self.session.headers.update({
            'X-Mirae-Version': '1',
            'User-Agent': 'AlphaStock/1.0'
        })
        
        # WebSocket connection
        self.ws = None
        self.ws_callbacks = {
            "on_tick": None,
            "on_error": None
        }
    
    def _make_request(self, method, endpoint, data=None, params=None, require_auth=True):
        """
        Make HTTP request with error handling and retries
        
        Args:
            method (str): HTTP method (GET, POST)
            endpoint (str): API endpoint
            data (dict): Request body data
            params (dict): Query parameters
            require_auth (bool): Whether authentication token is required
            
        Returns:
            dict: Response JSON data
            
        Raises:
            Exception: For API errors or network issues
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Add authentication header if required
        headers = {}
        if require_auth and self.access_token:
            headers['Authorization'] = f'token {self.api_key}:{self.access_token}'
        
        for attempt in range(self.retry_attempts):
            try:
                if method.upper() == 'GET':
                    response = self.session.get(
                        url, 
                        params=params, 
                        headers=headers, 
                        timeout=self.timeout
                    )
                elif method.upper() == 'POST':
                    # Set content type for form data
                    headers['Content-Type'] = 'application/x-www-form-urlencoded'
                    response = self.session.post(
                        url, 
                        data=data, 
                        headers=headers, 
                        timeout=self.timeout
                    )
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                # Handle HTTP status codes
                if response.status_code == 401:
                    error_data = response.json() if response.content else {}
                    error_msg = error_data.get('message', 'Authentication failed')
                    raise Exception(f"Authentication error: {error_msg}")
                
                elif response.status_code == 400:
                    error_data = response.json() if response.content else {}
                    error_msg = error_data.get('message', 'Bad request')
                    raise Exception(f"API error: {error_msg}")
                
                elif response.status_code != 200:
                    raise Exception(f"HTTP {response.status_code}: {response.text}")
                
                # Parse JSON response
                json_data = response.json()
                
                # Check for API-level errors in successful HTTP responses
                if json_data.get('status') == 'error':
                    error_msg = json_data.get('message', 'API returned error')
                    error_type = json_data.get('error_type', 'Unknown')
                    raise Exception(f"{error_type}: {error_msg}")
                
                return json_data
                
            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout on attempt {attempt + 1}")
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay)
                else:
                    raise Exception("Request timed out after all retry attempts")
            
            except requests.exceptions.ConnectionError:
                logger.warning(f"Connection error on attempt {attempt + 1}")
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay)
                else:
                    raise Exception("Connection failed after all retry attempts")
            
            except Exception as e:
                if attempt < self.retry_attempts - 1:
                    logger.warning(f"Request failed on attempt {attempt + 1}: {e}")
                    time.sleep(self.retry_delay)
                else:
                    raise
        
        raise Exception(f"Request failed after {self.retry_attempts} attempts")
    
    def _generate_checksum(self, api_key, request_token):
        """Generate checksum for session token request"""
        checksum_string = f"{api_key}{request_token}W"
        return hashlib.sha256(checksum_string.encode()).hexdigest()
    
    def login(self):
        """Login to get request token"""
        try:
            # Prepare login data
            login_data = {
                'username': self.username,
                'password': self.password
            }
            
            # Make login request
            response = self._make_request(
                method='POST',
                endpoint='/connect/login',
                data=login_data,
                require_auth=False
            )
            
            # Extract request token from response
            if response.get('status') == 'success' and 'data' in response:
                self.request_token = response['data'].get('request_token')
                logger.info("Login successful")
            else:
                raise Exception("Login failed: Invalid response format")
            
            return response
            
        except Exception as e:
            logger.error(f"Login failed: {e}")
            raise
    
    def generate_session(self, request_token=None):
        """Generate session token"""
        if request_token:
            self.request_token = request_token
        
        if not self.request_token:
            raise ValueError("Request token is required. Please login first.")
        
        try:
            # Generate checksum
            checksum = self._generate_checksum(self.api_key, self.request_token)
            
            # Prepare session data
            session_data = {
                'api_key': self.api_key,
                'request_token': self.request_token,
                'checksum': checksum
            }
            
            # Make session request
            response = self._make_request(
                method='POST',
                endpoint='/session/token',
                data=session_data,
                require_auth=False
            )
            
            # Extract access token from response
            if response.get('status') == 'success' and 'data' in response:
                self.access_token = response['data'].get('access_token')
                logger.info("Session generated successfully")
            else:
                raise Exception("Session generation failed: Invalid response format")
            
            return response
            
        except Exception as e:
            logger.error(f"Session generation failed: {e}")
            raise
    
    def get_historical_data(self, security_token, interval, from_date, to_date, symbol_info=None):
        """
        Get historical chart data
        
        Args:
            security_token (str): Security token/instrument token
            interval (str): Time interval (minute, 3minute, 5minute, 10minute, 15minute, 30minute, 60minute, day)
            from_date (str): Start date in YYYY-MM-DD format
            to_date (str): End date in YYYY-MM-DD format  
            symbol_info (str): Symbol info in format 'EXCHANGE:SYMBOL'
            
        Returns:
            dict: Historical data with candles
        """
        if not self.access_token:
            raise ValueError("Access token is required. Please login and generate session first.")
        
        # Format dates with time for API compatibility
        from_datetime = f"{from_date} 09:15:00"
        to_datetime = f"{to_date} 15:30:00"
        
        # Determine the correct exchange based on symbol
        if symbol_info and ":" in symbol_info:
            # For symbols like "NSE:SBIN", extract exchange
            exchange = symbol_info.split(":")[0]
        else:
            # For indices like "NIFTYBANK", try NSE first
            exchange = "NSE"
        
        try:
            # Build endpoint with path parameters
            endpoint = f'/instruments/historical/{exchange}/{security_token}/{interval}'
            
            # Query parameters for date range
            params = {
                'from': from_datetime,
                'to': to_datetime
            }
            
            response = self._make_request(
                method='GET',
                endpoint=endpoint,
                params=params,
                require_auth=True
            )
            
            logger.info(f"Historical data fetched successfully for {exchange}:{security_token} from {from_datetime} to {to_datetime}")
            return response
            
        except Exception as e:
            logger.error(f"Historical data request failed for {exchange}:{security_token}: {e}")
            raise
    
    def get_ltp(self, symbols):
        """
        Get Last Traded Price for symbols
        
        Args:
            symbols (list): List of symbols in format 'EXCHANGE:SYMBOL' (e.g., ['NSE:ACC', 'BSE:ACC'])
            
        Returns:
            dict: LTP data for symbols
        """
        if not self.access_token:
            raise ValueError("Access token is required. Please login and generate session first.")
        
        # Prepare query parameters - multiple 'i' parameters for each symbol
        params = []
        for symbol in symbols:
            params.append(('i', symbol))
        
        try:
            response = self._make_request(
                method='GET',
                endpoint='/instruments/quote/ltp',
                params=params,
                require_auth=True
            )
            
            logger.info(f"LTP data fetched successfully for {symbols}")
            return response
            
        except Exception as e:
            logger.error(f"LTP request failed: {e}")
            raise
    
    def get_ohlc(self, symbols):
        """
        Get OHLC data for symbols
        
        Args:
            symbols (list): List of symbols in format 'EXCHANGE:SYMBOL' (e.g., ['NSE:ACC', 'BSE:ACC'])
            
        Returns:
            dict: OHLC data for symbols
        """
        if not self.access_token:
            raise ValueError("Access token is required. Please login and generate session first.")
        
        # Prepare query parameters - multiple 'i' parameters for each symbol
        params = []
        for symbol in symbols:
            params.append(('i', symbol))
        
        try:
            response = self._make_request(
                method='GET',
                endpoint='/instruments/quote/ohlc',
                params=params,
                require_auth=True
            )
            
            logger.info(f"OHLC data fetched successfully for {symbols}")
            return response
            
        except Exception as e:
            logger.error(f"OHLC request failed: {e}")
            raise
    
    def get_option_chain_master(self, exchange=2):
        """
        Get option chain master data
        
        Args:
            exchange (int): Exchange ID (1-NSE, 2-NFO, 3-CDS, 4-BSE, 5-BFO)
            
        Returns:
            dict: Option chain master data with expiry dates and symbols
        """
        if not self.access_token:
            raise ValueError("Access token is required. Please login and generate session first.")
        
        try:
            endpoint = f'/getoptionchainmaster/{exchange}'
            
            response = self._make_request(
                method='GET',
                endpoint=endpoint,
                require_auth=True
            )
            
            logger.info(f"Option chain master data fetched successfully for exchange {exchange}")
            return response
            
        except Exception as e:
            logger.error(f"Option chain master request failed: {e}")
            raise
    
    def get_option_chain(self, symbol, expiry_date=None, exchange=2, token=None):
        """
        Get option chain for a symbol
        
        Args:
            symbol (str): Underlying symbol (e.g., 'NIFTYFINSERVICE')
            expiry_date (str): Expiry date in timestamp format (optional, gets nearest if not specified)
            exchange (int): Exchange ID (1-NSE, 2-NFO, 3-CDS, 4-BSE, 5-BFO)
            token (str): Instrument token (optional, will try to derive from symbol)
            
        Returns:
            dict: Option chain data with call and put options
        """
        if not self.access_token:
            raise ValueError("Access token is required. Please login and generate session first.")
        
        try:
            # If no expiry_date or token provided, try to get from master data
            if not expiry_date or not token:
                master_data = self.get_option_chain_master(exchange)
                
                if master_data.get('status') == 'success' and 'data' in master_data:
                    data = master_data['data']
                    
                    # Look for the symbol in OPTIDX or OFSTK
                    symbol_found = False
                    for section in ['OPTIDX', 'OFSTK']:
                        if section in data:
                            for entry in data[section]:
                                parts = entry.split(',')
                                if len(parts) >= 2 and parts[0] == symbol:
                                    if not token:
                                        token = parts[1]
                                    
                                    # Get the first available expiry if not provided
                                    if not expiry_date and len(parts) > 2:
                                        # Use the first expiry from the list
                                        expiry_key = parts[2]
                                        if 'dctExp' in data and expiry_key in data['dctExp']:
                                            expiry_date = data['dctExp'][expiry_key]
                                    
                                    symbol_found = True
                                    break
                            
                            if symbol_found:
                                break
                    
                    if not symbol_found:
                        raise Exception(f"Symbol {symbol} not found in option chain master")
            
            if not token:
                raise Exception(f"Could not determine token for symbol {symbol}")
            
            if not expiry_date:
                raise Exception(f"Could not determine expiry date for symbol {symbol}")
            
            # Build endpoint for option chain data
            endpoint = f'/GetOptionChain/{exchange}/{expiry_date}/{token}'
            
            response = self._make_request(
                method='GET',
                endpoint=endpoint,
                require_auth=True
            )
            
            logger.info(f"Option chain fetched successfully for {symbol}")
            return response
            
        except Exception as e:
            logger.error(f"Option chain request failed: {e}")
            raise
    
    def get_option_strikes(self, symbol, option_type="BOTH", expiry_date=None):
        """
        Get option strikes for a symbol
        
        Args:
            symbol (str): Underlying symbol
            option_type (str): "CE", "PE", or "BOTH"
            expiry_date (str): Expiry date (optional)
            
        Returns:
            list: Available strike prices
        """
        try:
            option_chain = self.get_option_chain(symbol, expiry_date)
            if not option_chain or not option_chain.get('success', False):
                return []
            
            strikes = []
            data = option_chain.get('data', [])
            
            for item in data:
                if option_type in ["CE", "BOTH"] and 'call_options' in item:
                    for call in item['call_options']:
                        strike_price = call.get('strike_price')
                        if strike_price and strike_price not in strikes:
                            strikes.append(strike_price)
                
                if option_type in ["PE", "BOTH"] and 'put_options' in item:
                    for put in item['put_options']:
                        strike_price = put.get('strike_price')
                        if strike_price and strike_price not in strikes:
                            strikes.append(strike_price)
            
            return sorted(strikes)
            
        except Exception as e:
            logger.error(f"Error getting option strikes: {e}")
            return []
    
    def find_optimal_option_strike(self, symbol, current_price, signal_type, expiry_date=None):
        """
        Find optimal option strike based on signal and current price
        
        Args:
            symbol (str): Underlying symbol
            current_price (float): Current market price
            signal_type (str): "BUY" or "SELL"
            expiry_date (str): Option expiry date (optional, uses nearest expiry)
            
        Returns:
            dict: Optimal option details with strike, token, etc.
        """
        try:
            option_chain = self.get_option_chain(symbol, expiry_date)
            if not option_chain or not option_chain.get('success', False):
                logger.error(f"Failed to get option chain for {symbol}")
                return None
            
            # For BUY signals, we buy CE options (bullish)
            # For SELL signals, we buy PE options (bearish)
            option_type = "CE" if signal_type == "BUY" else "PE"
            
            best_option = None
            min_price_diff = float('inf')
            
            data = option_chain.get('data', [])
            logger.info(f"Analyzing option chain for {symbol}: {signal_type} signal, current price: ₹{current_price}")
            
            for item in data:
                options_key = 'call_options' if option_type == "CE" else 'put_options'
                
                if options_key in item:
                    for option in item[options_key]:
                        strike_price = option.get('strike_price', 0)
                        ltp = option.get('ltp', 0)
                        volume = option.get('volume', 0)
                        oi = option.get('open_interest', 0)
                        
                        # Skip options with no liquidity
                        if ltp <= 0 or (volume == 0 and oi == 0):
                            continue
                        
                        # For CE (BUY signals): prefer ATM or slightly OTM strikes
                        # For PE (SELL signals): prefer ATM or slightly OTM strikes
                        if option_type == "CE":
                            # For bullish signals, prefer strikes close to current price or slightly OTM
                            # Range: 98% to 105% of current price
                            price_diff = abs(strike_price - current_price)
                            if (strike_price >= current_price * 0.98 and 
                                strike_price <= current_price * 1.05 and 
                                price_diff < min_price_diff and
                                ltp >= 10):  # Minimum premium filter
                                
                                min_price_diff = price_diff
                                best_option = {
                                    'symbol': option.get('trading_symbol', ''),
                                    'token': option.get('token', ''),
                                    'strike_price': strike_price,
                                    'option_type': option_type,
                                    'ltp': ltp,
                                    'bid': option.get('bid', 0),
                                    'ask': option.get('ask', 0),
                                    'volume': volume,
                                    'oi': oi,
                                    'expiry': option.get('expiry', ''),
                                    'underlying_price': current_price,
                                    'moneyness': 'ITM' if strike_price < current_price else ('ATM' if strike_price == current_price else 'OTM')
                                }
                        
                        else:  # PE
                            # For bearish signals, prefer strikes close to current price or slightly OTM
                            # Range: 95% to 102% of current price
                            price_diff = abs(strike_price - current_price)
                            if (strike_price <= current_price * 1.02 and 
                                strike_price >= current_price * 0.95 and 
                                price_diff < min_price_diff and
                                ltp >= 10):  # Minimum premium filter
                                
                                min_price_diff = price_diff
                                best_option = {
                                    'symbol': option.get('trading_symbol', ''),
                                    'token': option.get('token', ''),
                                    'strike_price': strike_price,
                                    'option_type': option_type,
                                    'ltp': ltp,
                                    'bid': option.get('bid', 0),
                                    'ask': option.get('ask', 0),
                                    'volume': volume,
                                    'oi': oi,
                                    'expiry': option.get('expiry', ''),
                                    'underlying_price': current_price,
                                    'moneyness': 'ITM' if strike_price > current_price else ('ATM' if strike_price == current_price else 'OTM')
                                }
            
            if best_option:
                logger.info(f"Selected optimal {option_type} option: {best_option['symbol']} "
                          f"Strike: ₹{best_option['strike_price']} LTP: ₹{best_option['ltp']} "
                          f"({best_option['moneyness']})")
            else:
                logger.warning(f"No suitable {option_type} option found for {symbol} at ₹{current_price}")
            
            return best_option
            
        except Exception as e:
            logger.error(f"Error finding optimal option strike: {e}")
            return None
    
    def connect_websocket(self, on_tick=None, on_error=None):
        """Connect to WebSocket for real-time data"""
        if not self.access_token:
            raise ValueError("Access token is required. Please login and generate session first.")
        
        # Store callbacks
        self.ws_callbacks["on_tick"] = on_tick
        self.ws_callbacks["on_error"] = on_error
        
        # WebSocket URL with authentication
        ws_auth_url = f"{self.ws_url}?api_key={self.api_key}&access_token={self.access_token}"
        
        # WebSocket event handlers
        def on_message(ws, message):
            try:
                data = json.loads(message)
                logger.debug(f"Received WebSocket data: {message}")
                if self.ws_callbacks["on_tick"]:
                    self.ws_callbacks["on_tick"](data)
            except json.JSONDecodeError:
                logger.warning(f"Received non-JSON message: {message}")
        
        def on_ws_error(ws, error):
            logger.error(f"WebSocket error: {error}")
            if self.ws_callbacks["on_error"]:
                self.ws_callbacks["on_error"](error)
        
        def on_close(ws, close_status_code, close_msg):
            logger.info(f"WebSocket connection closed: {close_status_code} - {close_msg}")
        
        def on_open(ws):
            logger.info("WebSocket connection opened")
        
        # Create WebSocket connection
        self.ws = websocket.WebSocketApp(
            ws_auth_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_ws_error,
            on_close=on_close
        )
        
        # Start WebSocket connection in a separate thread
        wst = threading.Thread(target=self.ws.run_forever, kwargs={
            "sslopt": {"cert_reqs": ssl.CERT_NONE},  # Disable SSL certificate verification
            "ping_interval": 30,
            "ping_timeout": 10
        })
        wst.daemon = True
        wst.start()
        
        # Give some time for the connection to establish
        time.sleep(3)
        
        return self.ws
    
    def subscribe_ticks(self, symbols):
        """Subscribe to tick data for symbols"""
        if not self.ws or not self.ws.sock or not self.ws.sock.connected:
            raise ValueError("WebSocket connection is not established")
        
        # Subscribe to ticks for specific symbols
        subscribe_message = {
            "a": "subscribe",
            "v": symbols,
            "m": "tick"
        }
        
        self.ws.send(json.dumps(subscribe_message))
        logger.info(f"Subscribed to tick data for {symbols}")
    
    def close_websocket(self):
        """Close WebSocket connection"""
        if self.ws:
            self.ws.close()
            logger.info("WebSocket connection closed")
    
    # Additional methods from the library
    
    def place_order(self, symbol, exchange, transaction_type, order_type, quantity, 
                   product_type, validity, price=0, trigger_price=0):
        """
        Place an order (Note: This requires order endpoints - not yet implemented)
        
        Args:
            symbol (str): Trading symbol
            exchange (str): Exchange name
            transaction_type (str): BUY or SELL
            order_type (str): MARKET or LIMIT
            quantity (int): Order quantity
            product_type (str): Product type
            validity (str): Order validity
            price (float): Order price for limit orders
            trigger_price (float): Trigger price for SL orders
            
        Returns:
            dict: Order placement response
        """
        if not self.access_token:
            raise ValueError("Access token is required. Please login and generate session first.")
        
        # This would need to be implemented with actual order endpoints
        # For now, raise a not implemented error
        raise NotImplementedError("Order placement endpoints not yet implemented in this refactor")
    
    def get_order_book(self):
        """
        Get order book for logged in user (Note: This requires order endpoints - not yet implemented)
        
        Returns:
            dict: Order book data
        """
        if not self.access_token:
            raise ValueError("Access token is required. Please login and generate session first.")
        
        # This would need to be implemented with actual order endpoints
        # For now, raise a not implemented error
        raise NotImplementedError("Order book endpoints not yet implemented in this refactor")
    
    def get_holdings(self):
        """
        Get holdings for logged in user (Note: This requires portfolio endpoints - not yet implemented)
        
        Returns:
            dict: Holdings data
        """
        if not self.access_token:
            raise ValueError("Access token is required. Please login and generate session first.")
        
        # This would need to be implemented with actual portfolio endpoints
        # For now, raise a not implemented error
        raise NotImplementedError("Holdings endpoints not yet implemented in this refactor")