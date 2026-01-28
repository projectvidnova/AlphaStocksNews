#!/usr/bin/env python3
"""
Kite Connect Permission Checker
Tests different data sources and identifies what you can access
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from kiteconnect import KiteConnect

# Load environment
load_dotenv('.env.dev')

# Get credentials
api_key = os.getenv('KITE_API_KEY')
access_token = os.getenv('KITE_ACCESS_TOKEN')

print("🔍 KITE CONNECT PERMISSION ANALYSIS")
print("=" * 60)

if not access_token or access_token == "your_access_token":
    print("❌ No access token found. Please run authentication first.")
    sys.exit(1)

# Initialize Kite Connect
kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

try:
    # Test 1: Check profile and permissions
    print("\n📋 STEP 1: Profile & Permissions Check")
    profile = kite.profile()
    print(f"✅ User: {profile.get('user_name', 'Unknown')}")
    print(f"✅ User ID: {profile.get('user_id', 'Unknown')}")
    print(f"✅ Email: {profile.get('email', 'Unknown')}")
    
    # Check enabled products/exchanges
    exchanges = profile.get('exchanges', [])
    products = profile.get('products', [])
    
    print(f"\n📊 Enabled Exchanges: {', '.join(exchanges) if exchanges else 'None listed'}")
    print(f"🛒 Enabled Products: {', '.join(products) if products else 'None listed'}")
    
    # Test 2: Check different exchange access
    print("\n📊 STEP 2: Exchange Access Test")
    
    exchanges_to_test = ["NSE", "BSE", "NFO", "MCX"]
    accessible_exchanges = []
    
    for exchange in exchanges_to_test:
        try:
            print(f"🔍 Testing {exchange}...")
            instruments = kite.instruments(exchange)
            print(f"✅ {exchange}: {len(instruments)} instruments available")
            accessible_exchanges.append(exchange)
        except Exception as e:
            print(f"❌ {exchange}: {str(e)}")
    
    if not accessible_exchanges:
        print("\n⚠️ No exchanges accessible. This might be a subscription issue.")
        print("💡 Contact Zerodha support to enable data access.")
        sys.exit(1)
    
    # Test 3: Find Bank Nifty alternatives
    print("\n🏦 STEP 3: Finding Bank Nifty Data Sources")
    
    bank_nifty_alternatives = []
    
    # Try NSE first (most common)
    if "NSE" in accessible_exchanges:
        try:
            nse_instruments = kite.instruments("NSE")
            
            # Look for Bank Nifty related instruments
            bank_nifty_candidates = []
            for inst in nse_instruments:
                name = inst.get('name', '').upper()
                symbol = inst.get('tradingsymbol', '').upper() 
                
                if any(keyword in name or keyword in symbol for keyword in ['BANKNIFTY', 'BANK NIFTY', 'NIFTY BANK']):
                    bank_nifty_candidates.append({
                        'symbol': inst.get('tradingsymbol'),
                        'name': inst.get('name'),
                        'token': inst.get('instrument_token'),
                        'exchange': 'NSE'
                    })
            
            print(f"🔍 Found {len(bank_nifty_candidates)} Bank Nifty candidates in NSE")
            
            # Show first few candidates
            for i, candidate in enumerate(bank_nifty_candidates[:5]):
                print(f"   {i+1}. {candidate['symbol']} - {candidate['name']} (Token: {candidate['token']})")
                
            bank_nifty_alternatives.extend(bank_nifty_candidates[:3])  # Take first 3
            
        except Exception as e:
            print(f"❌ NSE instrument fetch failed: {e}")
    
    # Test 4: Historical data access test
    print("\n📈 STEP 4: Historical Data Access Test")
    
    if not bank_nifty_alternatives:
        print("⚠️ No Bank Nifty instruments found. Testing with NIFTY 50...")
        # Fallback to NIFTY 50 (more commonly available)
        try:
            nse_instruments = kite.instruments("NSE")
            nifty_instruments = [inst for inst in nse_instruments 
                               if 'NIFTY' in inst.get('name', '').upper() 
                               and 'BANK' not in inst.get('name', '').upper()]
            
            if nifty_instruments:
                bank_nifty_alternatives = [{
                    'symbol': nifty_instruments[0].get('tradingsymbol'),
                    'name': nifty_instruments[0].get('name'),
                    'token': nifty_instruments[0].get('instrument_token'),
                    'exchange': 'NSE'
                }]
                print(f"✅ Using fallback: {bank_nifty_alternatives[0]['symbol']}")
        except:
            pass
    
    # Test historical data with found alternatives
    success_count = 0
    date_to = datetime.now()
    date_from = date_to - timedelta(days=5)  # Test with 5 days
    
    for alt in bank_nifty_alternatives[:3]:  # Test first 3
        symbol = alt['symbol']
        token = alt['token']
        
        print(f"\n🔍 Testing historical data for {symbol} (Token: {token})")
        
        for interval in ['day', '5minute', '15minute']:  # Test different intervals
            try:
                print(f"   📊 Testing {interval} data...")
                data = kite.historical_data(
                    instrument_token=token,
                    from_date=date_from,
                    to_date=date_to,
                    interval=interval
                )
                
                if data and len(data) > 0:
                    print(f"   ✅ {interval}: {len(data)} data points")
                    print(f"   📊 Sample: {data[-1]['date']} | Close: {data[-1]['close']}")
                    success_count += 1
                    
                    # If we found working data, break
                    if success_count > 0:
                        print(f"\n🎉 SUCCESS! Found working data source:")
                        print(f"   Symbol: {symbol}")
                        print(f"   Token: {token}")
                        print(f"   Interval: {interval}")
                        print(f"   Data points: {len(data)}")
                        break
                else:
                    print(f"   ⚠️ {interval}: No data returned")
                    
            except Exception as e:
                print(f"   ❌ {interval}: {str(e)[:50]}...")
        
        if success_count > 0:
            break
    
    # Final recommendations
    print(f"\n🎯 FINAL ANALYSIS")
    print("=" * 40)
    
    if success_count > 0:
        print("✅ GOOD NEWS: Historical data access is working!")
        print("💡 Your API has sufficient permissions for basic data.")
        print("📊 You can proceed with the trading system setup.")
    else:
        print("❌ ISSUE: No historical data access found.")
        print("🔧 SOLUTIONS:")
        print("   1. Contact Zerodha support to enable historical data API")
        print("   2. Check if your API app has 'Historical Data' permission")
        print("   3. Verify your account has data subscription")
        print("   4. Try with a different time range or symbol")
    
    print(f"\n📞 If issues persist:")
    print("   • Email: kiteconnect@zerodha.com")
    print("   • Include your API key and user ID")
    print("   • Mention 'Historical Data API access needed'")

except Exception as e:
    print(f"❌ Analysis failed: {e}")
    
print(f"\n🏁 Permission analysis complete!")
