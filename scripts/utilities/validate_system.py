#!/usr/bin/env python3
"""
Simplified System Validation
Tests API data retrieval and validates your system is ready for scheduler
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from kiteconnect import KiteConnect

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment
load_dotenv('.env.dev')

print("🎯 ALPHASTOCK SYSTEM VALIDATION")
print("=" * 50)

def test_api_data_retrieval():
    """Test API data retrieval with real Bank Nifty data."""
    print("\n📊 Testing Bank Nifty Data Retrieval")
    
    try:
        # Initialize Kite Connect
        api_key = os.getenv('KITE_API_KEY')
        access_token = os.getenv('KITE_ACCESS_TOKEN')
        
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        
        # Test different timeframes
        bank_nifty_token = "260105"
        to_date = datetime.now()
        
        test_cases = [
            {'days': 1, 'interval': '5minute', 'desc': 'Intraday (5min)'},
            {'days': 7, 'interval': '15minute', 'desc': 'Weekly (15min)'},
            {'days': 30, 'interval': 'day', 'desc': 'Monthly (daily)'}
        ]
        
        results = {}
        
        for test in test_cases:
            try:
                from_date = to_date - timedelta(days=test['days'])
                
                print(f"\\n  📈 Testing {test['desc']}")
                print(f"     Period: {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}")
                
                data = kite.historical_data(
                    instrument_token=bank_nifty_token,
                    from_date=from_date,
                    to_date=to_date,
                    interval=test['interval']
                )
                
                if data:
                    results[test['interval']] = {
                        'count': len(data),
                        'latest': data[-1],
                        'success': True
                    }
                    
                    latest = data[-1]
                    print(f"     ✅ {len(data)} data points")
                    print(f"     📊 Latest: {latest['date']} | Close: {latest['close']}")
                else:
                    results[test['interval']] = {'success': False}
                    print(f"     ❌ No data received")
                    
            except Exception as e:
                results[test['interval']] = {'success': False, 'error': str(e)}
                print(f"     ❌ Error: {str(e)[:60]}...")
        
        return results
        
    except Exception as e:
        print(f"❌ API test failed: {e}")
        return None

def validate_scheduler_readiness():
    """Validate scheduler components are ready."""
    print("\\n⏰ Validating Scheduler Readiness")
    
    checks = {
        'scheduler_file': False,
        'main_file': False,
        'orchestrator': False,
        'config': False,
        'env_complete': False
    }
    
    # Check scheduler file
    scheduler_path = Path('scheduler.py')
    if scheduler_path.exists():
        checks['scheduler_file'] = True
        print("  ✅ scheduler.py exists")
    else:
        print("  ❌ scheduler.py missing")
    
    # Check main file  
    main_path = Path('main.py')
    if main_path.exists():
        checks['main_file'] = True
        print("  ✅ main.py exists")
    else:
        print("  ❌ main.py missing")
    
    # Check orchestrator
    orchestrator_path = Path('src/orchestrator.py')
    if orchestrator_path.exists():
        checks['orchestrator'] = True
        print("  ✅ orchestrator.py exists")
    else:
        print("  ❌ orchestrator.py missing")
    
    # Check config
    config_path = Path('config/production.json')
    if config_path.exists():
        checks['config'] = True
        print("  ✅ production.json exists")
    else:
        print("  ❌ production.json missing")
    
    # Check environment completeness
    required_env = ['KITE_API_KEY', 'KITE_API_SECRET', 'KITE_ACCESS_TOKEN']
    missing_env = []
    
    for var in required_env:
        value = os.getenv(var)
        if not value or value == 'your_access_token':
            missing_env.append(var)
    
    if not missing_env:
        checks['env_complete'] = True
        print("  ✅ Environment variables complete")
    else:
        print(f"  ❌ Missing env vars: {', '.join(missing_env)}")
    
    return checks

def main():
    """Main validation function."""
    
    # Test 1: API Data Retrieval
    print("\\n🔍 PHASE 1: API Data Validation")
    api_results = test_api_data_retrieval()
    
    # Test 2: Scheduler Readiness  
    print("\\n🔍 PHASE 2: Scheduler Readiness")
    scheduler_checks = validate_scheduler_readiness()
    
    # Summary
    print("\\n" + "="*50)
    print("📋 VALIDATION SUMMARY")
    print("="*50)
    
    # API Results
    if api_results:
        working_intervals = [k for k, v in api_results.items() if v.get('success', False)]
        print(f"✅ API Data Access: {len(working_intervals)}/3 timeframes working")
        
        for interval, result in api_results.items():
            if result.get('success'):
                print(f"  ✅ {interval}: {result['count']} data points available")
            else:
                print(f"  ❌ {interval}: Failed")
    else:
        print("❌ API Data Access: Failed")
    
    # Scheduler Results
    ready_components = sum(scheduler_checks.values())
    print(f"\\n🤖 Scheduler Readiness: {ready_components}/5 components ready")
    
    for component, status in scheduler_checks.items():
        status_icon = "✅" if status else "❌"
        print(f"  {status_icon} {component.replace('_', ' ').title()}")
    
    # Overall Assessment
    print("\\n🎯 OVERALL ASSESSMENT")
    print("-" * 30)
    
    if api_results and len([k for k, v in api_results.items() if v.get('success', False)]) >= 2:
        print("✅ API Integration: EXCELLENT")
        print("  • Multiple timeframes working")
        print("  • Real Bank Nifty data flowing")
        print("  • Ready for automated data collection")
    else:
        print("⚠️ API Integration: NEEDS ATTENTION")
    
    if ready_components >= 4:
        print("\\n✅ System Architecture: READY") 
        print("  • Core components present")
        print("  • Configuration available")
        print("  • Ready for scheduler deployment")
    else:
        print("\\n⚠️ System Architecture: INCOMPLETE")
        print("  • Missing components need attention")
    
    # Next Steps
    print("\\n🚀 NEXT STEPS")
    print("-" * 20)
    
    if api_results and ready_components >= 4:
        print("🎉 YOUR SYSTEM IS READY FOR DEPLOYMENT!")
        print("\\n📋 To start automated trading:")
        print("  1. Run: ./setup_automation.sh")
        print("  2. Test: python3 scheduler.py --manual-start")
        print("  3. Monitor: tail -f logs/scheduler.log")
        print("\\n💡 Your system will automatically:")
        print("  • Start at 8:15 AM (pre-market validation)")
        print("  • Trade 9:15 AM - 3:30 PM (Bank Nifty focus)")
        print("  • Stop at 3:30 PM with post-analysis")
    else:
        if not api_results:
            print("🔧 Fix API access first")
            print("  • Verify your API credentials")
            print("  • Check historical data permissions")
        
        if ready_components < 4:
            print("🔧 Complete system setup")
            print("  • Run missing component installation")
            print("  • Verify configuration files")
    
    return api_results is not None and ready_components >= 4

if __name__ == "__main__":
    try:
        success = main()
        if success:
            print("\\n🎯 System validation: SUCCESS! 🚀")
            sys.exit(0)
        else:
            print("\\n⚠️ System validation: NEEDS ATTENTION")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\\n🛑 Validation stopped by user")
        sys.exit(1)
    except Exception as e:
        print(f"\\n❌ Validation error: {e}")
        sys.exit(1)
