#!/usr/bin/env python3
"""
AlphaStock System Readiness Check
Validates all components before deployment
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
import os

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
os.chdir(project_root)

async def main():
    print("="*80)
    print("🔍 ALPHASTOCK DEPLOYMENT READINESS CHECK")
    print("="*80)
    print()
    
    results = {
        'authentication': False,
        'database': False,
        'historical_data': False,
        'strategies': False,
        'paper_trading': False
    }
    
    # 1. Check Authentication
    print("1️⃣  Checking Authentication...")
    try:
        from dotenv import load_dotenv
        import os
        load_dotenv('.env.dev')
        from kiteconnect import KiteConnect
        
        api_key = os.getenv('KITE_API_KEY')
        access_token = os.getenv('KITE_ACCESS_TOKEN')
        
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        profile = kite.profile()
        
        print(f"   ✅ Authenticated as: {profile.get('user_name')}")
        print(f"   ✅ Broker: {profile.get('broker')}")
        results['authentication'] = True
    except Exception as e:
        print(f"   ❌ Authentication failed: {e}")
        print(f"   💡 Run: python scripts/utilities/generate_access_token.py")
    
    print()
    
    # 2. Check Database
    print("2️⃣  Checking Database Connection...")
    try:
        from src.data.clickhouse_data_layer import ClickHouseDataLayer
        import json
        
        with open('config/database.json') as f:
            db_config = json.load(f)['development']
        
        db = ClickHouseDataLayer(db_config)
        if db.health_check():
            print("   ✅ ClickHouse database connected")
            results['database'] = True
        else:
            print("   ❌ Database health check failed")
    except Exception as e:
        print(f"   ❌ Database connection failed: {e}")
        print(f"   💡 Check: docker ps | grep clickhouse")
    
    print()
    
    # 3. Check Historical Data
    print("3️⃣  Checking Historical Data...")
    try:
        from src.core.historical_data_manager import HistoricalDataManager
        from src.utils.secrets_manager import get_secrets_manager
        
        secrets = get_secrets_manager()
        
        # Quick test fetch
        from src.api.kite_client import KiteAPIClient
        client = KiteAPIClient(secrets)
        await client.initialize()
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=3)
        
        df = await client.get_historical_data(
            symbol='BANKNIFTY',
            from_date=start_date,
            to_date=end_date,
            interval='day'
        )
        
        if not df.empty and 'timestamp' in df.columns:
            print(f"   ✅ Can fetch Bank Nifty data: {len(df)} records")
            print(f"   ✅ Data format correct (has timestamp column)")
            results['historical_data'] = True
        else:
            print(f"   ❌ Data fetch returned empty or incorrect format")
    except Exception as e:
        print(f"   ❌ Data fetch test failed: {e}")
    
    print()
    
    # 4. Check Strategies Configuration
    print("4️⃣  Checking Strategy Configuration...")
    try:
        import json
        with open('config/production.json') as f:
            config = json.load(f)
        
        strategies = config.get('strategies', {})
        if strategies:
            print(f"   ✅ Found {len(strategies)} configured strategies:")
            for name in strategies.keys():
                print(f"      • {name}")
            results['strategies'] = True
        else:
            print("   ❌ No strategies configured")
    except Exception as e:
        print(f"   ❌ Strategy check failed: {e}")
    
    print()
    
    # 5. Check Paper Trading Mode
    print("5️⃣  Checking Paper Trading Mode...")
    try:
        from dotenv import load_dotenv
        import os
        load_dotenv('.env.dev')
        
        paper_trading = os.getenv('PAPER_TRADING', 'true').lower() == 'true'
        if paper_trading:
            print("   ✅ Paper trading ENABLED (safe mode)")
            results['paper_trading'] = True
        else:
            print("   ⚠️  Paper trading DISABLED - LIVE TRADING MODE!")
            print("   💡 Set PAPER_TRADING=true in .env.dev for safe testing")
    except Exception as e:
        print(f"   ❌ Paper trading check failed: {e}")
    
    print()
    print("="*80)
    print("📊 READINESS SUMMARY")
    print("="*80)
    
    passed = sum(results.values())
    total = len(results)
    
    for check, status in results.items():
        status_icon = "✅" if status else "❌"
        print(f"{status_icon} {check.replace('_', ' ').title()}")
    
    print()
    print(f"Score: {passed}/{total} checks passed")
    print()
    
    if passed == total:
        print("🎉 SYSTEM READY FOR DEPLOYMENT!")
        print()
        print("Next steps:")
        print("  1. Review config/production.json for strategy parameters")
        print("  2. Run: python complete_workflow.py (to download full historical data)")
        print("  3. Run: python main.py (to start trading)")
        print()
        return 0
    else:
        print("⚠️  SYSTEM NOT READY - Fix the issues above before deploying")
        print()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
