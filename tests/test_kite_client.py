"""
Comprehensive Kite API Client Tester

Tests all methods of KiteAPIClient to validate API responses and help extend functionality.

Usage:
    Interactive mode (with menu):
        python tests/test_kite_client.py
        python tests/test_kite_client.py --interactive
        python tests/test_kite_client.py -i
    
    Non-interactive mode (run all tests):
        python tests/test_kite_client.py --all
    
Features:
- Interactive menu to select which tests to run
- Tests all get_* methods individually or all at once
- Validates response formats
- Checks data types and structure
- Saves sample responses for reference
- Helps debug API issues
"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta, date
from typing import Dict, Any
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.api.kite_client import KiteAPIClient
from src.utils.secrets_manager import get_secrets_manager


class KiteClientTester:
    """Comprehensive tester for Kite API Client."""
    
    def __init__(self):
        self.secrets = get_secrets_manager()
        self.client = None
        self.test_results = {}
        self.sample_responses = {}
        
        # Test symbols
        self.test_symbols = {
            'equity': ['RELIANCE', 'TCS', 'INFY', 'SBIN'],
            'index': ['NIFTY50', 'BANKNIFTY', 'NIFTYBANK'],
            'futures': ['BANKNIFTY25OCTFUT', 'NIFTY25OCTFUT'],
        }
    
    async def setup(self):
        """Initialize API client."""
        print("\n" + "="*80)
        print("KITE API CLIENT - COMPREHENSIVE TESTER")
        print("="*80)
        
        print("\n[1/2] Initializing API client...")
        self.client = KiteAPIClient(self.secrets)
        
        print("[2/2] Authenticating...")
        try:
            await self.client.initialize()
            
            if self.client.authenticated:
                print("✅ API client initialized and authenticated")
                return True
            else:
                print("❌ Failed to initialize API client")
                print("   Make sure you have run: python scripts/utilities/get_auth_url.py")
                return False
                
        except Exception as e:
            print(f"❌ Exception during initialization: {e}")
            print("   Make sure you have run: python scripts/utilities/get_auth_url.py")
            return False
    
    # ==================== INSTRUMENT METHODS ====================
    
    def test_get_instruments(self):
        """Test: Get instruments list."""
        print("\n" + "="*80)
        print("TEST: get_instruments()")
        print("="*80)
        
        try:
            # Test NFO instruments
            print("\nFetching NFO instruments...")
            instruments = self.client.get_instruments(exchange="NFO")
            
            print(f"\n📊 Result:")
            print(f"  Total Instruments: {len(instruments)}")
            
            if instruments:
                print(f"\n  Sample Instrument:")
                sample = instruments[0]
                for key, value in sample.items():
                    print(f"    {key}: {value}")
                
                # Save all instruments to CSV
                output_dir = project_root / "tests" / "sample_responses"
                output_dir.mkdir(exist_ok=True)
                
                csv_file = output_dir / f"instruments_NSE_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                
                # Convert to DataFrame and save
                df = pd.DataFrame(instruments)
                df.to_csv(csv_file, index=False)
                print(f"\n💾 All {len(instruments)} instruments saved to: {csv_file}")
                
                # Also save summary to JSON
                self.sample_responses['get_instruments'] = {
                    'total_count': len(instruments),
                    'csv_file': str(csv_file),
                    'sample': instruments[:3],
                    'instrument_types': df['instrument_type'].value_counts().to_dict() if 'instrument_type' in df.columns else {},
                    'segments': df['segment'].unique().tolist() if 'segment' in df.columns else []
                }
                
                print(f"\n  Instrument Types:")
                if 'instrument_type' in df.columns:
                    for inst_type, count in df['instrument_type'].value_counts().head(10).items():
                        print(f"    {inst_type}: {count}")
                
                return True
            else:
                print("  ⚠️ No instruments returned")
                return False
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_get_instrument_token(self):
        """Test: Get instrument token for symbols."""
        print("\n" + "="*80)
        print("TEST: get_instrument_token()")
        print("="*80)
        
        results = {}
        all_success = True
        
        # Test symbols with their alternate names for robustness
        test_cases = [
            ('RELIANCE', 'RELIANCE'),
            ('SBIN', 'SBIN'),
            ('BANKNIFTY', 'BANKNIFTY'),
            ('NIFTY 50', 'NIFTY50'),  # Use actual tradingsymbol
        ]
        
        for symbol, display_name in test_cases:
            try:
                token = self.client.get_instrument_token(symbol)
                
                if token:
                    print(f"✅ {display_name:15} → Token: {token}")
                    results[display_name] = token
                else:
                    print(f"❌ {display_name:15} → Token not found")
                    all_success = False
                    
            except Exception as e:
                print(f"❌ {display_name:15} → Error: {e}")
                all_success = False
        
        self.sample_responses['get_instrument_token'] = results
        return all_success
    
    # ==================== MARKET DATA METHODS ====================
    
    def test_get_ltp(self):
        """Test: Get Last Traded Price."""
        print("\n" + "="*80)
        print("TEST: get_ltp()")
        print("="*80)
        
        try:
            # Test single symbol
            print("\n1. Single Symbol:")
            ltp_single = self.client.get_ltp("RELIANCE")
            print(f"  RELIANCE LTP: {ltp_single.get('RELIANCE', 'N/A')}")
            
            # Test multiple symbols
            print("\n2. Multiple Symbols:")
            symbols = ['RELIANCE', 'TCS', 'INFY']
            ltp_multi = self.client.get_ltp(symbols)
            
            for symbol in symbols:
                ltp = ltp_multi.get(symbol, 'N/A')
                print(f"  {symbol:10} → LTP: {ltp}")
            
            # Test index (use actual tradingsymbol)
            print("\n3. Index:")
            idxSymbols = ['NIFTY 50', 'NIFTY BANK', 'NIFTY FIN SERVICE']  # Use actual tradingsymbols
            ltp_index = self.client.get_ltp(idxSymbols)
            print(f"  NIFTY 50 LTP: {ltp_index.get('NIFTY 50', 'N/A')}")
            print(f"  BANK NIFTY LTP: {ltp_index.get('NIFTY BANK', 'N/A')}")
            print(f"  NIFTY FIN SERVICE LTP: {ltp_index.get('NIFTY FIN SERVICE', 'N/A')}")

            self.sample_responses['get_ltp'] = ltp_multi
            
            return len(ltp_multi) > 0
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def test_get_ohlc(self):
        """Test: Get OHLC data."""
        print("\n" + "="*80)
        print("TEST: get_ohlc()")
        print("="*80)
        
        try:
            # Test single symbol
            print("\n1. Single Symbol (RELIANCE):")
            ohlc_single = self.client.get_ohlc("RELIANCE")
            
            if 'RELIANCE' in ohlc_single:
                data = ohlc_single['RELIANCE']
                print(f"  Open:        {data.get('open', 'N/A')}")
                print(f"  High:        {data.get('high', 'N/A')}")
                print(f"  Low:         {data.get('low', 'N/A')}")
                print(f"  Close:       {data.get('close', 'N/A')}")
                print(f"  Last Price:  {data.get('last_price', 'N/A')}")
                print(f"  Volume:      {data.get('volume', 'N/A')}")
            
            # Test multiple symbols
            print("\n2. Multiple Symbols:")
            symbols = ['RELIANCE', 'TCS', 'SBIN']
            ohlc_multi = self.client.get_ohlc(symbols)
            
            for symbol in symbols:
                if symbol in ohlc_multi:
                    data = ohlc_multi[symbol]
                    print(f"  {symbol:10} → O:{data.get('open'):.2f} H:{data.get('high'):.2f} L:{data.get('low'):.2f} C:{data.get('last_price'):.2f} V:{data.get('volume', 0)}")
            
            # Test index
            print("\n3. Index (BANKNIFTY):")
            ohlc_index = self.client.get_ohlc("BANKNIFTY")
            
            if 'BANKNIFTY' in ohlc_index:
                data = ohlc_index['BANKNIFTY']
                print(f"  Open:        {data.get('open', 'N/A')}")
                print(f"  High:        {data.get('high', 'N/A')}")
                print(f"  Low:         {data.get('low', 'N/A')}")
                print(f"  Last Price:  {data.get('last_price', 'N/A')}")
                print(f"  Volume:      {data.get('volume', 'N/A')} (should be 0 for index)")
            
            self.sample_responses['get_ohlc'] = ohlc_multi
            
            return len(ohlc_multi) > 0
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def test_get_quote(self):
        """Test: Get full market quote."""
        print("\n" + "="*80)
        print("TEST: get_quote()")
        print("="*80)
        
        try:
            # Test single symbol
            print("\n1. Single Symbol (RELIANCE):")
            quote_single = self.client.get_quote("RELIANCE")
            
            if 'RELIANCE' in quote_single:
                data = quote_single['RELIANCE']
                print(f"  Instrument Token: {data.get('instrument_token', 'N/A')}")
                print(f"  Last Price:       {data.get('last_price', 'N/A')}")
                print(f"  Last Quantity:    {data.get('last_quantity', 'N/A')}")
                print(f"  Volume:           {data.get('volume', 'N/A')}")
                print(f"  Average Price:    {data.get('average_price', 'N/A')}")
                print(f"  Buy Quantity:     {data.get('buy_quantity', 'N/A')}")
                print(f"  Sell Quantity:    {data.get('sell_quantity', 'N/A')}")
                
                ohlc = data.get('ohlc', {})
                print(f"\n  OHLC:")
                print(f"    Open:  {ohlc.get('open', 'N/A')}")
                print(f"    High:  {ohlc.get('high', 'N/A')}")
                print(f"    Low:   {ohlc.get('low', 'N/A')}")
                print(f"    Close: {ohlc.get('close', 'N/A')}")
                
                print(f"\n  Circuit Limits:")
                print(f"    Lower: {data.get('lower_circuit_limit', 'N/A')}")
                print(f"    Upper: {data.get('upper_circuit_limit', 'N/A')}")
                
                # Show market depth summary
                depth = data.get('depth', {})
                buy_depth = depth.get('buy', [])
                sell_depth = depth.get('sell', [])
                
                if buy_depth and any(b.get('quantity', 0) > 0 for b in buy_depth):
                    print(f"\n  Market Depth (Top Buy):")
                    for i, level in enumerate(buy_depth[:3], 1):
                        if level.get('quantity', 0) > 0:
                            print(f"    Level {i}: ₹{level.get('price', 0):.2f} x {level.get('quantity', 0)} ({level.get('orders', 0)} orders)")
                
                if sell_depth and any(s.get('quantity', 0) > 0 for s in sell_depth):
                    print(f"\n  Market Depth (Top Sell):")
                    for i, level in enumerate(sell_depth[:3], 1):
                        if level.get('quantity', 0) > 0:
                            print(f"    Level {i}: ₹{level.get('price', 0):.2f} x {level.get('quantity', 0)} ({level.get('orders', 0)} orders)")
            
            # Test multiple symbols
            print("\n2. Multiple Symbols:")
            symbols = ['RELIANCE', 'TCS', 'INFY']
            quote_multi = self.client.get_quote(symbols)
            
            for symbol in symbols:
                if symbol in quote_multi:
                    data = quote_multi[symbol]
                    print(f"  {symbol:10} → LTP: ₹{data.get('last_price', 0):.2f} | Vol: {data.get('volume', 0):,} | Avg: ₹{data.get('average_price', 0):.2f}")
            
            # Test with exchange prefix
            print("\n3. With Exchange Prefix:")
            quote_with_exchange = self.client.get_quote("NSE:SBIN")
            if 'SBIN' in quote_with_exchange:
                data = quote_with_exchange['SBIN']
                print(f"  SBIN LTP: ₹{data.get('last_price', 'N/A')}")
                print(f"  Volume: {data.get('volume', 'N/A'):,}")

            # Test multiple index symbols
            print("\n4. Multiple Index Symbols:")
            idxSymbols = ['NIFTY 50', 'NIFTY BANK', 'NIFTY FIN SERVICE']
            quote_multi_idx = self.client.get_quote(idxSymbols)

            for symbol in idxSymbols:
                if symbol in quote_multi_idx:
                    data = quote_multi_idx[symbol]
                    print(f"  {symbol:10} → LTP: ₹{data.get('last_price', 0):.2f} | Vol: {data.get('volume', 0):,} | Avg: ₹{data.get('average_price', 0):.2f}")
            
            # Save sample response (with limited depth data for readability)
            if quote_single:
                sample_data = {}
                for symbol, data in quote_single.items():
                    # Create a copy with limited depth
                    sample = dict(data)
                    if 'depth' in sample:
                        depth = sample['depth']
                        sample['depth'] = {
                            'buy': depth.get('buy', [])[:2],  # Only first 2 levels
                            'sell': depth.get('sell', [])[:2]
                        }
                    sample_data[symbol] = sample
                
                self.sample_responses['get_quote'] = sample_data
            
            return len(quote_multi) > 0
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_get_historical_data(self):
        """Test: Get historical data."""
        print("\n" + "="*80)
        print("TEST: get_historical_data()")
        print("="*80)
        
        try:
            # Test parameters
            symbol = "RELIANCE"
            end_date = date.today()
            start_date = end_date - timedelta(days=7)
            
            print(f"\nFetching {symbol} data:")
            print(f"  From: {start_date}")
            print(f"  To: {end_date}")
            print(f"  Interval: 15minute")
            
            # Fetch data
            df = await self.client.get_historical_data(
                symbol=symbol,
                from_date=start_date,
                to_date=end_date,
                interval="15minute"
            )
            
            if df is not None and not df.empty:
                print(f"\n📊 Result:")
                print(f"  Records: {len(df)}")
                print(f"  Columns: {list(df.columns)}")
                
                # Handle both 'date' and 'timestamp' column names
                date_col = 'date' if 'date' in df.columns else 'timestamp'
                print(f"  Date range: {df[date_col].min()} to {df[date_col].max()}")
                
                print(f"\n  First 3 records:")
                print(df.head(3).to_string(index=False))
                
                print(f"\n  Data Statistics:")
                print(f"    Avg Volume: {df['volume'].mean():.0f}")
                print(f"    Price Range: {df['low'].min():.2f} - {df['high'].max():.2f}")
                
                # Check timezone
                if date_col in df.columns:
                    first_date = df[date_col].iloc[0]
                    if hasattr(first_date, 'tzinfo') and first_date.tzinfo:
                        print(f"    Timezone: {first_date.tzinfo} ✅")
                    else:
                        print(f"    Timezone: Not set ⚠️")
                
                self.sample_responses['get_historical_data'] = {
                    'records': len(df),
                    'columns': list(df.columns),
                    'sample': df.head(3).to_dict('records')
                }
                
                return True
            else:
                print("  ⚠️ No historical data returned")
                print("     This might be normal if market is closed or symbol is invalid")
                return False
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ==================== TRADING METHODS ====================
    
    def test_place_order_paper(self):
        """Test: Place order (Paper Trading)."""
        print("\n" + "="*80)
        print("TEST: place_order() - PAPER TRADING MODE")
        print("="*80)
        
        if not self.client.paper_trading:
            print("⚠️ SKIPPED: Not in paper trading mode")
            print("   This test only runs in paper trading mode for safety")
            return True
        
        try:
            # Test market order
            print("\n1. Market Order (BUY):")
            response = self.client.place_order(
                symbol="RELIANCE",
                transaction_type="BUY",
                quantity=1,
                order_type="MARKET"
            )
            
            print(f"  Order ID: {response.order_id}")
            print(f"  Status: {response.status}")
            print(f"  Message: {response.message}")
            
            # Test limit order
            print("\n2. Limit Order (SELL):")
            response = self.client.place_order(
                symbol="TCS",
                transaction_type="SELL",
                quantity=1,
                order_type="LIMIT",
                price=3500.00
            )
            
            print(f"  Order ID: {response.order_id}")
            print(f"  Status: {response.status}")
            print(f"  Message: {response.message}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def test_get_orders(self):
        """Test: Get orders."""
        print("\n" + "="*80)
        print("TEST: get_orders()")
        print("="*80)
        
        try:
            orders = self.client.get_orders()
            
            print(f"\n📊 Result:")
            print(f"  Total Orders: {len(orders)}")
            
            if orders:
                print(f"\n  Recent Orders:")
                for i, order in enumerate(orders[:3], 1):
                    print(f"\n  Order {i}:")
                    print(f"    Order ID: {order.get('order_id', 'N/A')}")
                    print(f"    Symbol: {order.get('tradingsymbol', 'N/A')}")
                    print(f"    Type: {order.get('transaction_type', 'N/A')}")
                    print(f"    Quantity: {order.get('quantity', 'N/A')}")
                    print(f"    Status: {order.get('status', 'N/A')}")
                
                self.sample_responses['get_orders'] = orders[:3]
            else:
                print("  No orders found")
            
            return True
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def test_get_positions(self):
        """Test: Get positions."""
        print("\n" + "="*80)
        print("TEST: get_positions()")
        print("="*80)
        
        try:
            positions = self.client.get_positions()
            
            print(f"\n📊 Result:")
            print(f"  Total Positions: {len(positions)}")
            
            if positions:
                print(f"\n  Active Positions:")
                for i, pos in enumerate(positions[:3], 1):
                    print(f"\n  Position {i}:")
                    print(f"    Symbol: {pos.get('tradingsymbol', 'N/A')}")
                    print(f"    Quantity: {pos.get('quantity', 'N/A')}")
                    print(f"    P&L: {pos.get('pnl', 'N/A')}")
                
                self.sample_responses['get_positions'] = positions[:3]
            else:
                print("  No open positions")
            
            return True
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def test_get_holdings(self):
        """Test: Get holdings."""
        print("\n" + "="*80)
        print("TEST: get_holdings()")
        print("="*80)
        
        try:
            holdings = self.client.get_holdings()
            
            print(f"\n📊 Result:")
            print(f"  Total Holdings: {len(holdings)}")
            
            if holdings:
                print(f"\n  Holdings:")
                for i, holding in enumerate(holdings[:5], 1):
                    print(f"\n  Holding {i}:")
                    print(f"    Symbol: {holding.get('tradingsymbol', 'N/A')}")
                    print(f"    Quantity: {holding.get('quantity', 'N/A')}")
                    print(f"    Avg Price: {holding.get('average_price', 'N/A')}")
                    print(f"    LTP: {holding.get('last_price', 'N/A')}")
                    print(f"    P&L: {holding.get('pnl', 'N/A')}")
                
                self.sample_responses['get_holdings'] = holdings[:3]
            else:
                print("  No holdings found")
            
            return True
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    # ==================== ACCOUNT METHODS ====================
    
    def test_get_profile(self):
        """Test: Get user profile."""
        print("\n" + "="*80)
        print("TEST: get_profile()")
        print("="*80)
        
        try:
            profile = self.client.get_profile()
            
            print(f"\n📊 Result:")
            print(f"  User ID: {profile.get('user_id', 'N/A')}")
            print(f"  Name: {profile.get('user_name', 'N/A')}")
            print(f"  Email: {profile.get('email', 'N/A')}")
            print(f"  Broker: {profile.get('broker', 'N/A')}")
            print(f"  Products: {', '.join(profile.get('products', []))}")
            print(f"  Exchanges: {', '.join(profile.get('exchanges', []))}")
            
            # Don't save sensitive profile data
            self.sample_responses['get_profile'] = {
                'user_id': '***',
                'broker': profile.get('broker', 'N/A')
            }
            
            return True
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def test_get_margins(self):
        """Test: Get account margins."""
        print("\n" + "="*80)
        print("TEST: get_margins()")
        print("="*80)
        
        try:
            margins = self.client.get_margins()
            
            print(f"\n📊 Result:")
            
            if 'equity' in margins:
                equity = margins['equity']
                print(f"\n  Equity Segment:")
                print(f"    Available: ₹{equity.get('available', {}).get('live_balance', 0):,.2f}")
                print(f"    Used: ₹{equity.get('utilised', {}).get('debits', 0):,.2f}")
            
            if 'commodity' in margins:
                commodity = margins['commodity']
                print(f"\n  Commodity Segment:")
                print(f"    Available: ₹{commodity.get('available', {}).get('live_balance', 0):,.2f}")
                print(f"    Used: ₹{commodity.get('utilised', {}).get('debits', 0):,.2f}")
            
            # Don't save sensitive margin data
            self.sample_responses['get_margins'] = {
                'segments': list(margins.keys())
            }
            
            return True
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    # ==================== PERFORMANCE METHODS ====================
    
    def test_get_performance_metrics(self):
        """Test: Get performance metrics."""
        print("\n" + "="*80)
        print("TEST: get_performance_metrics()")
        print("="*80)
        
        try:
            metrics = self.client.get_performance_metrics()
            
            print(f"\n📊 Result:")
            print(f"  Cache Hit Rate: {metrics.get('cache_hit_rate', 0):.2%}")
            print(f"  Total Requests: {metrics.get('total_requests', 0)}")
            print(f"  Avg Response Time: {metrics.get('avg_response_time', 0):.3f}s")
            
            if 'endpoint_metrics' in metrics:
                print(f"\n  Endpoint Metrics:")
                for endpoint, data in list(metrics['endpoint_metrics'].items())[:5]:
                    print(f"    {endpoint}: {data.get('count', 0)} calls, {data.get('avg_time', 0):.3f}s avg")
            
            self.sample_responses['get_performance_metrics'] = metrics
            
            return True
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    # ==================== TEST RUNNER ====================
    
    def get_all_tests(self):
        """Get all available tests organized by category."""
        return {
            'Instrument Methods': [
                ('get_instruments', self.test_get_instruments),
                ('get_instrument_token', self.test_get_instrument_token),
            ],
            'Market Data Methods': [
                ('get_ltp', self.test_get_ltp),
                ('get_ohlc', self.test_get_ohlc),
                ('get_quote', self.test_get_quote),
                ('get_historical_data', self.test_get_historical_data),
            ],
            'Trading Methods': [
                ('place_order (paper)', self.test_place_order_paper),
                ('get_orders', self.test_get_orders),
                ('get_positions', self.test_get_positions),
                ('get_holdings', self.test_get_holdings),
            ],
            'Account Methods': [
                ('get_profile', self.test_get_profile),
                ('get_margins', self.test_get_margins),
            ],
            'Performance Methods': [
                ('get_performance_metrics', self.test_get_performance_metrics),
            ]
        }
    
    def display_menu(self):
        """Display interactive menu for test selection."""
        tests = self.get_all_tests()
        
        print("\n" + "="*80)
        print("KITE API CLIENT - TEST MENU")
        print("="*80)
        
        print("\nAvailable Tests:\n")
        
        test_index = 1
        test_map = {}
        
        for category, category_tests in tests.items():
            print(f"\n{category}:")
            for test_name, test_func in category_tests:
                print(f"  [{test_index}] {test_name}")
                test_map[test_index] = (test_name, test_func, category)
                test_index += 1
        
        print(f"\n  [0] Run ALL tests")
        print(f"  [Q] Quit")
        
        print("\n" + "="*80)
        
        return test_map
    
    def get_user_selection(self, test_map):
        """Get user's test selection."""
        while True:
            try:
                choice = input("\nEnter your choice (number, 'all', or 'q' to quit): ").strip().lower()
                
                if choice == 'q' or choice == 'quit':
                    return None
                
                if choice == '0' or choice == 'all':
                    return 'all'
                
                choice_num = int(choice)
                if choice_num in test_map:
                    return choice_num
                else:
                    print(f"❌ Invalid choice. Please enter a number between 0 and {len(test_map)}, or 'q' to quit.")
            
            except ValueError:
                print("❌ Invalid input. Please enter a number, 'all', or 'q'.")
            except KeyboardInterrupt:
                print("\n\n⚠️ Test interrupted by user")
                return None
    
    async def run_selected_tests(self, selection, test_map):
        """Run the selected test(s)."""
        all_results = {}
        
        if selection == 'all':
            # Run all tests
            tests = self.get_all_tests()
            
            for category, category_tests in tests.items():
                print("\n" + "="*80)
                print(f"CATEGORY: {category}")
                print("="*80)
                
                for test_name, test_func in category_tests:
                    try:
                        if asyncio.iscoroutinefunction(test_func):
                            result = await test_func()
                        else:
                            result = test_func()
                        
                        all_results[test_name] = result
                        self.test_results[test_name] = {
                            'passed': result,
                            'category': category
                        }
                        
                    except Exception as e:
                        print(f"\n❌ EXCEPTION in {test_name}: {e}")
                        import traceback
                        traceback.print_exc()
                        all_results[test_name] = False
                        self.test_results[test_name] = {
                            'passed': False,
                            'category': category,
                            'error': str(e)
                        }
        else:
            # Run single test
            test_name, test_func, category = test_map[selection]
            
            try:
                if asyncio.iscoroutinefunction(test_func):
                    result = await test_func()
                else:
                    result = test_func()
                
                all_results[test_name] = result
                self.test_results[test_name] = {
                    'passed': result,
                    'category': category
                }
                
            except Exception as e:
                print(f"\n❌ EXCEPTION in {test_name}: {e}")
                import traceback
                traceback.print_exc()
                all_results[test_name] = False
                self.test_results[test_name] = {
                    'passed': False,
                    'category': category,
                    'error': str(e)
                }
        
        # Summary
        if all_results:
            self._print_summary(all_results)
            
            # Save sample responses
            self._save_sample_responses()
        
        return all(all_results.values()) if all_results else False
    
    async def run_interactive(self):
        """Run tests interactively with menu."""
        if not await self.setup():
            return False
        
        while True:
            test_map = self.display_menu()
            selection = self.get_user_selection(test_map)
            
            if selection is None:
                print("\n👋 Exiting test suite...")
                break
            
            success = await self.run_selected_tests(selection, test_map)
            
            # Ask if user wants to run more tests
            print("\n" + "="*80)
            continue_choice = input("Run another test? (y/n): ").strip().lower()
            if continue_choice != 'y' and continue_choice != 'yes':
                print("\n👋 Exiting test suite...")
                break
        
        return True
    
    async def run_all_tests(self):
        """Run all tests (non-interactive mode)."""
        if not await self.setup():
            return False
        
        # Get all tests
        tests = self.get_all_tests()
        
        # Run all tests
        all_results = {}
        
        for category, category_tests in tests.items():
            print("\n" + "="*80)
            print(f"CATEGORY: {category}")
            print("="*80)
            
            for test_name, test_func in category_tests:
                try:
                    if asyncio.iscoroutinefunction(test_func):
                        result = await test_func()
                    else:
                        result = test_func()
                    
                    all_results[test_name] = result
                    self.test_results[test_name] = {
                        'passed': result,
                        'category': category
                    }
                    
                except Exception as e:
                    print(f"\n❌ EXCEPTION in {test_name}: {e}")
                    import traceback
                    traceback.print_exc()
                    all_results[test_name] = False
                    self.test_results[test_name] = {
                        'passed': False,
                        'category': category,
                        'error': str(e)
                    }
        
        # Summary
        self._print_summary(all_results)
        
        # Save sample responses
        self._save_sample_responses()
        
        return all(all_results.values())
    
    def _print_summary(self, results: Dict[str, bool]):
        """Print test summary."""
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        
        passed = sum(1 for r in results.values() if r)
        failed = len(results) - passed
        
        print(f"\nTotal Tests: {len(results)}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"📊 Success Rate: {(passed/len(results)*100):.1f}%")
        
        if failed > 0:
            print(f"\nFailed Tests:")
            for test_name, passed in results.items():
                if not passed:
                    print(f"  ❌ {test_name}")
        
        print("\n" + "="*80)
        if failed == 0:
            print("🎉 ALL TESTS PASSED!")
        else:
            print("⚠️ SOME TESTS FAILED - Review errors above")
        print("="*80)
    
    def _save_sample_responses(self):
        """Save sample responses to file."""
        output_dir = project_root / "tests" / "sample_responses"
        output_dir.mkdir(exist_ok=True)
        
        output_file = output_dir / f"kite_api_responses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(output_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'test_results': self.test_results,
                'sample_responses': self.sample_responses
            }, f, indent=2, default=str)
        
        print(f"\n💾 Sample responses saved to: {output_file}")


async def main():
    """Main function."""
    # Check if running in interactive mode
    # Default to interactive unless --all flag is provided
    run_all = '--all' in sys.argv
    
    tester = KiteClientTester()
    
    if run_all:
        # Non-interactive mode - run all tests
        success = await tester.run_all_tests()
    else:
        # Interactive mode with menu (default)
        success = await tester.run_interactive()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
