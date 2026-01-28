#!/usr/bin/env python3
"""
Kite Connect Authentication Helper for AlphaStock
Helps users authenticate with Kite Connect API and get access tokens.
"""

import asyncio
import sys
from src.api.kite_client import KiteAPIClient
from src.utils.secrets_manager import get_secrets_manager


async def authenticate_kite():
    """Interactive authentication with Kite Connect."""
    print("🔑 Kite Connect Authentication Helper")
    print("=" * 50)
    
    # Check if we have API credentials
    secrets = get_secrets_manager()
    creds = secrets.get_kite_credentials()
    
    if not creds['api_key']:
        print("❌ API Key not found!")
        print("Please add your KITE_API_KEY to .env.dev file")
        print("Get your API key from: https://developers.kite.trade/")
        return False
    
    if not creds['api_secret']:
        print("❌ API Secret not found!")
        print("Please add your KITE_API_SECRET to .env.dev file")
        return False
    
    print(f"✅ API Key found: {creds['api_key'][:8]}...")
    
    # Check if already authenticated
    if creds['access_token']:
        print("✅ Access token found, testing connection...")
        
        client = KiteAPIClient()
        await client.initialize()
        
        if client.authenticated:
            profile = client.get_profile()
            print(f"✅ Already authenticated as: {profile.get('user_name', 'Unknown')}")
            print(f"   User ID: {profile.get('user_id', 'Unknown')}")
            print(f"   Email: {profile.get('email', 'Unknown')}")
            return True
        else:
            print("❌ Access token invalid, need to re-authenticate")
    
    # Start authentication process
    print("\n🚀 Starting authentication process...")
    
    try:
        client = KiteAPIClient()
        await client.initialize()
        
        # Get login URL
        login_url = client.authenticate()
        
        print(f"\n📋 Please follow these steps:")
        print(f"1. Visit the following URL in your browser:")
        print(f"   {login_url}")
        print(f"2. Login with your Zerodha credentials")
        print(f"3. After successful login, you'll be redirected to a URL like:")
        print(f"   https://127.0.0.1:5000/?request_token=XXXXXX&action=login&status=success")
        print(f"4. Copy the 'request_token' value from the URL")
        
        # Get request token from user
        request_token = input(f"\n🔑 Please paste the request_token here: ").strip()
        
        if not request_token:
            print("❌ No request token provided")
            return False
        
        print(f"\n🔄 Generating session with request token...")
        
        # Generate session
        session_data = client.generate_session(request_token)
        
        print(f"✅ Authentication successful!")
        print(f"   Access Token: {session_data['access_token'][:10]}...")
        print(f"   User ID: {session_data.get('user_id', 'Unknown')}")
        print(f"   User Name: {session_data.get('user_name', 'Unknown')}")
        
        # Test the connection
        profile = client.get_profile()
        print(f"\n📊 Profile Information:")
        print(f"   Name: {profile.get('user_name', 'Unknown')}")
        print(f"   Email: {profile.get('email', 'Unknown')}")
        print(f"   User Type: {profile.get('user_type', 'Unknown')}")
        print(f"   Broker: {profile.get('broker', 'Unknown')}")
        
        print(f"\n💡 Your access token has been automatically saved.")
        print(f"   You can now use the AlphaStock trading system!")
        
        return True
        
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return False


async def test_api_connection():
    """Test API connection and show account details."""
    print("\n🔍 Testing API Connection...")
    print("-" * 30)
    
    try:
        client = KiteAPIClient()
        await client.initialize()
        
        if not client.authenticated:
            print("❌ Not authenticated. Please run authentication first.")
            return False
        
        # Test basic API calls
        print("✅ API Connection: OK")
        
        # Get profile
        profile = client.get_profile()
        print(f"📋 User: {profile.get('user_name', 'Unknown')}")
        
        # Get margins
        margins = client.get_margins()
        if margins:
            equity = margins.get('equity', {})
            print(f"💰 Available Cash: ₹{equity.get('available', {}).get('cash', 0):,.2f}")
            print(f"📊 Total Balance: ₹{equity.get('net', 0):,.2f}")
        
        # Test market data
        print("\n📈 Testing Market Data...")
        test_symbols = ["RELIANCE", "INFY", "SBIN"]
        ltp_data = client.get_ltp(test_symbols)
        
        if ltp_data:
            print("✅ Market Data: OK")
            for symbol, price in ltp_data.items():
                print(f"   {symbol}: ₹{price:,.2f}")
        else:
            print("⚠️ Market Data: No data (market might be closed)")
        
        # Test instruments
        instruments = client.get_instruments("NSE")
        print(f"📋 NSE Instruments: {len(instruments)} available")
        
        return True
        
    except Exception as e:
        print(f"❌ API Test failed: {e}")
        return False


async def show_account_summary():
    """Show detailed account summary."""
    print("\n💼 Account Summary")
    print("=" * 30)
    
    try:
        client = KiteAPIClient()
        await client.initialize()
        
        if not client.authenticated:
            print("❌ Not authenticated")
            return
        
        # Profile
        profile = client.get_profile()
        print(f"👤 Name: {profile.get('user_name', 'Unknown')}")
        print(f"📧 Email: {profile.get('email', 'Unknown')}")
        print(f"🏢 Broker: {profile.get('broker', 'Unknown')}")
        print(f"📱 User Type: {profile.get('user_type', 'Unknown')}")
        
        # Margins
        margins = client.get_margins()
        if margins:
            print(f"\n💰 Account Funds:")
            equity = margins.get('equity', {})
            commodity = margins.get('commodity', {})
            
            print(f"   Equity Available: ₹{equity.get('available', {}).get('cash', 0):,.2f}")
            print(f"   Equity Used: ₹{equity.get('utilised', {}).get('debits', 0):,.2f}")
            print(f"   Total Equity: ₹{equity.get('net', 0):,.2f}")
            
            if commodity:
                print(f"   Commodity Available: ₹{commodity.get('available', {}).get('cash', 0):,.2f}")
        
        # Holdings
        holdings = client.get_holdings()
        if holdings:
            print(f"\n📊 Holdings ({len(holdings)} positions):")
            for holding in holdings[:5]:  # Show top 5
                symbol = holding.get('tradingsymbol', 'Unknown')
                quantity = holding.get('quantity', 0)
                pnl = holding.get('pnl', 0)
                print(f"   {symbol}: {quantity} shares (P&L: ₹{pnl:,.2f})")
        
        # Positions
        positions = client.get_positions()
        if positions:
            print(f"\n📈 Open Positions ({len(positions)}):")
            for position in positions[:5]:  # Show top 5
                symbol = position.get('tradingsymbol', 'Unknown')
                quantity = position.get('quantity', 0)
                pnl = position.get('pnl', 0)
                print(f"   {symbol}: {quantity} (P&L: ₹{pnl:,.2f})")
        
    except Exception as e:
        print(f"❌ Error getting account summary: {e}")


def show_help():
    """Show help information."""
    print("""
🔑 Kite Connect Authentication Helper

Commands:
  auth     - Start authentication process
  test     - Test API connection
  account  - Show account summary
  help     - Show this help message

Setup Instructions:
1. Get API credentials from https://developers.kite.trade/
2. Add credentials to .env.dev file:
   KITE_API_KEY=your_api_key
   KITE_API_SECRET=your_api_secret
3. Run: python auth_helper.py auth
4. Follow the authentication steps

For questions or issues, check the logs or documentation.
    """)


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        command = "help"
    else:
        command = sys.argv[1].lower()
    
    if command == "auth":
        success = await authenticate_kite()
        if success:
            await test_api_connection()
    elif command == "test":
        await test_api_connection()
    elif command == "account":
        await show_account_summary()
    elif command == "help":
        show_help()
    else:
        print(f"Unknown command: {command}")
        show_help()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
