#!/usr/bin/env python3
"""
AlphaStock Data Viewer
Shows all your trading data in multiple formats and prepares for ClickHouse integration
"""

import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment
load_dotenv('.env.dev')

print("📊 ALPHASTOCK DATA VIEWER")
print("=" * 50)

def view_signals_data():
    """View trading signals data."""
    print("\n🎯 TRADING SIGNALS DATA")
    print("-" * 30)
    
    signals_file = Path('data/signals/signals.json')
    if signals_file.exists():
        try:
            with open(signals_file, 'r') as f:
                signals_data = json.load(f)
            
            print(f"📄 File: {signals_file}")
            print(f"📊 Total signals: {len(signals_data)}")
            print(f"💾 File size: {signals_file.stat().st_size} bytes")
            
            if signals_data:
                print(f"\n📋 Signal Structure:")
                first_signal = signals_data[0]
                for key, value in first_signal.items():
                    print(f"  • {key}: {value}")
                
                # Analyze signals
                symbols = set(signal.get('symbol', 'Unknown') for signal in signals_data)
                strategies = set(signal.get('strategy', 'Unknown') for signal in signals_data)
                signal_types = set(signal.get('signal_type', 'Unknown') for signal in signals_data)
                
                print(f"\n📈 Analysis:")
                print(f"  Symbols: {', '.join(symbols)}")
                print(f"  Strategies: {', '.join(strategies)}")
                print(f"  Signal types: {', '.join(signal_types)}")
                
                return signals_data
        except Exception as e:
            print(f"❌ Error reading signals: {e}")
    else:
        print("❌ No signals data found")
    
    return None

def fetch_and_view_live_data():
    """Fetch and display live Bank Nifty data."""
    print("\n🔴 LIVE BANK NIFTY DATA")
    print("-" * 30)
    
    try:
        from kiteconnect import KiteConnect
        
        api_key = os.getenv('KITE_API_KEY')
        access_token = os.getenv('KITE_ACCESS_TOKEN')
        
        if not api_key or not access_token:
            print("❌ API credentials not found")
            return None
        
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        
        print("✅ Connected to Kite API")
        
        # Fetch Bank Nifty data
        bank_nifty_token = "260105"
        to_date = datetime.now()
        from_date = to_date - timedelta(days=5)
        
        print(f"📅 Fetching data: {from_date.date()} to {to_date.date()}")
        
        # Try different intervals
        intervals = ['day', '15minute', '5minute']
        live_data = None
        
        for interval in intervals:
            try:
                print(f"  🔍 Trying {interval} data...")
                data = kite.historical_data(
                    instrument_token=bank_nifty_token,
                    from_date=from_date,
                    to_date=to_date,
                    interval=interval
                )
                
                if data:
                    print(f"  ✅ Got {len(data)} data points")
                    live_data = {'interval': interval, 'data': data}
                    break
                else:
                    print(f"  ❌ No data for {interval}")
                    
            except Exception as e:
                print(f"  ❌ {interval} failed: {str(e)[:50]}...")
        
        if live_data:
            data = live_data['data']
            interval = live_data['interval']
            
            print(f"\n📊 BANK NIFTY DATA ({interval.upper()})")
            print("-" * 40)
            print(f"Total points: {len(data)}")
            
            # Show recent data in table format
            print(f"\n📈 Recent Data Points:")
            print("Date/Time              Open      High      Low       Close     Volume")
            print("-" * 70)
            
            for point in data[-5:]:  # Last 5 points
                date_str = point['date'].strftime('%Y-%m-%d %H:%M')
                print(f"{date_str:20} {point['open']:8.2f} {point['high']:8.2f} {point['low']:8.2f} {point['close']:8.2f} {point['volume']:8}")
            
            # Save to file for ClickHouse import later
            data_dir = Path('data/historical')
            data_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            json_file = data_dir / f"banknifty_{interval}_{timestamp}.json"
            csv_file = data_dir / f"banknifty_{interval}_{timestamp}.csv"
            
            # Save as JSON
            with open(json_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            print(f"\n💾 Saved JSON: {json_file}")
            
            # Save as CSV (ClickHouse friendly)
            df_data = []
            for point in data:
                df_data.append({
                    'symbol': 'BANKNIFTY',
                    'timeframe': interval,
                    'timestamp': point['date'],
                    'open': point['open'],
                    'high': point['high'],
                    'low': point['low'],
                    'close': point['close'],
                    'volume': point['volume']
                })
            
            df = pd.DataFrame(df_data)
            df.to_csv(csv_file, index=False)
            print(f"💾 Saved CSV: {csv_file}")
            print(f"📊 Ready for ClickHouse import!")
            
            return live_data
            
    except Exception as e:
        print(f"❌ Error fetching live data: {e}")
    
    return None

def create_clickhouse_import_script(data_file=None):
    """Create script to import data into ClickHouse when available."""
    print("\n🏠 CLICKHOUSE IMPORT PREPARATION")
    print("-" * 30)
    
    import_script = """#!/bin/bash

# ClickHouse Data Import Script
# Run this when ClickHouse is available

echo "🏠 Importing data into ClickHouse..."

# Option 1: Using Docker ClickHouse
if command -v docker &> /dev/null && docker ps | grep -q clickhouse; then
    echo "✅ Using Docker ClickHouse"
    
    # Import historical data
    for csv_file in data/historical/*.csv; do
        if [[ -f "$csv_file" ]]; then
            echo "📊 Importing $csv_file..."
            docker exec -i alphastock-clickhouse clickhouse-client --database=alphastock --query="
            INSERT INTO historical_data FORMAT CSV" < "$csv_file"
        fi
    done
    
    echo "✅ Data import complete!"
    echo "🔍 View data: docker exec -it alphastock-clickhouse clickhouse-client --database=alphastock"
    
# Option 2: Using local ClickHouse installation  
elif command -v clickhouse-client &> /dev/null; then
    echo "✅ Using local ClickHouse"
    
    for csv_file in data/historical/*.csv; do
        if [[ -f "$csv_file" ]]; then
            echo "📊 Importing $csv_file..."
            clickhouse-client --database=alphastock --query="
            INSERT INTO historical_data FORMAT CSV" < "$csv_file"
        fi
    done
    
    echo "✅ Data import complete!"
    echo "🔍 View data: clickhouse-client --database=alphastock"
    
else
    echo "❌ ClickHouse not found"
    echo "💡 Options:"
    echo "   1. Install Docker and run: ./setup_clickhouse_docker.sh"
    echo "   2. Or install ClickHouse locally"
fi
"""
    
    import_file = Path('import_to_clickhouse.sh')
    with open(import_file, 'w') as f:
        f.write(import_script)
    
    os.chmod(import_file, 0o755)
    print(f"✅ Created: {import_file}")
    print("💡 Run this script when ClickHouse is available")

def show_clickhouse_queries():
    """Show example ClickHouse queries for your data."""
    print("\n🔍 CLICKHOUSE QUERIES (For When Available)")
    print("-" * 30)
    
    queries = [
        {
            'name': 'View Recent Data',
            'query': 'SELECT * FROM historical_data ORDER BY timestamp DESC LIMIT 10'
        },
        {
            'name': 'Bank Nifty Summary',
            'query': '''SELECT 
    symbol,
    timeframe,
    COUNT(*) as data_points,
    MIN(timestamp) as first_date,
    MAX(timestamp) as last_date,
    AVG(close) as avg_price
FROM historical_data 
WHERE symbol = 'BANKNIFTY' 
GROUP BY symbol, timeframe'''
        },
        {
            'name': 'Daily Price Range',
            'query': '''SELECT 
    toDate(timestamp) as date,
    MIN(low) as daily_low,
    MAX(high) as daily_high,
    (MAX(high) - MIN(low)) as range
FROM historical_data 
WHERE symbol = 'BANKNIFTY'
GROUP BY toDate(timestamp)
ORDER BY date DESC'''
        },
        {
            'name': 'Moving Average',
            'query': '''SELECT 
    timestamp,
    close,
    avg(close) OVER (
        ORDER BY timestamp 
        ROWS 9 PRECEDING
    ) as sma_10
FROM historical_data 
WHERE symbol = 'BANKNIFTY' 
ORDER BY timestamp DESC 
LIMIT 20'''
        }
    ]
    
    for query in queries:
        print(f"\n📊 {query['name']}:")
        print(f"   {query['query']}")
    
    # Save queries to file
    queries_file = Path('clickhouse_queries.sql')
    with open(queries_file, 'w') as f:
        f.write("-- AlphaStock ClickHouse Queries\\n\\n")
        for query in queries:
            f.write(f"-- {query['name']}\\n")
            f.write(f"{query['query']};\\n\\n")
    
    print(f"\\n💾 Saved queries to: {queries_file}")

def main():
    """Main viewer function."""
    
    # View existing signals data
    signals_data = view_signals_data()
    
    # Fetch and view live data
    live_data = fetch_and_view_live_data()
    
    # Create ClickHouse preparation scripts
    create_clickhouse_import_script()
    show_clickhouse_queries()
    
    # Summary
    print("\\n" + "=" * 50)
    print("📋 DATA VIEWING SUMMARY")
    print("=" * 50)
    
    print("\\n🎯 CURRENT DATA:")
    if signals_data:
        print(f"  ✅ Trading signals: {len(signals_data)} entries")
    
    if live_data:
        print(f"  ✅ Live Bank Nifty: {len(live_data['data'])} points ({live_data['interval']})")
    
    print("\\n📁 FILES CREATED:")
    print("  ✅ import_to_clickhouse.sh - Import script")
    print("  ✅ clickhouse_queries.sql - Example queries")
    
    if live_data:
        print("  ✅ data/historical/*.csv - ClickHouse-ready data")
        print("  ✅ data/historical/*.json - Backup data")
    
    print("\\n🏠 FOR CLICKHOUSE ACCESS:")
    print("  1. Install Docker Desktop")
    print("  2. Run: ./setup_clickhouse_docker.sh")
    print("  3. Run: ./import_to_clickhouse.sh")
    print("  4. Query: docker exec -it alphastock-clickhouse clickhouse-client --database=alphastock")
    
    print("\\n📊 TO VIEW DATA NOW:")
    print("  • Check data/historical/ folder")
    print("  • Open CSV files in Excel/Numbers")
    print("  • Use clickhouse_queries.sql when ClickHouse is ready")

if __name__ == "__main__":
    try:
        # Install pandas if not available
        try:
            import pandas as pd
        except ImportError:
            print("📦 Installing pandas for data processing...")
            import subprocess
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pandas'])
            import pandas as pd
        
        main()
        
    except KeyboardInterrupt:
        print("\\n🛑 Viewer stopped by user")
    except Exception as e:
        print(f"\\n❌ Viewer error: {e}")
        import traceback
        traceback.print_exc()
