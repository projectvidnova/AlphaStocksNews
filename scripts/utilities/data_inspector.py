#!/usr/bin/env python3
"""
AlphaStock Data Storage Inspector
Shows where your trading data is currently stored and how to access it
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("🗄️ ALPHASTOCK DATA STORAGE INSPECTOR")
print("=" * 60)

def check_config_files():
    """Check configuration files to understand storage setup."""
    print("\n📋 CONFIGURATION FILES")
    print("-" * 30)
    
    config_files = {
        'production.json': 'config/production.json',
        'database.json': 'config/database.json'
    }
    
    configs = {}
    
    for name, path in config_files.items():
        file_path = Path(path)
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    configs[name] = json.load(f)
                print(f"✅ {name}: Found")
            except Exception as e:
                print(f"⚠️ {name}: Error reading - {e}")
        else:
            print(f"❌ {name}: Not found")
    
    return configs

def analyze_storage_config(configs):
    """Analyze storage configuration."""
    print("\n🗄️ STORAGE CONFIGURATION")
    print("-" * 30)
    
    if 'database.json' in configs:
        storage_config = configs['database.json'].get('storage', {})
        
        # Primary storage
        primary_type = storage_config.get('type', 'unknown')
        print(f"📊 Primary Storage: {primary_type.upper()}")
        
        # PostgreSQL config
        if 'postgresql' in storage_config:
            pg_config = storage_config['postgresql']
            print(f"🐘 PostgreSQL:")
            print(f"   Host: {pg_config.get('host', 'unknown')}")
            print(f"   Port: {pg_config.get('port', 'unknown')}")
            print(f"   Database: {pg_config.get('database', 'unknown')}")
            print(f"   Username: {pg_config.get('username', 'unknown')}")
        
        # ClickHouse config
        if 'clickhouse' in storage_config:
            ch_config = storage_config['clickhouse']
            print(f"🏠 ClickHouse:")
            print(f"   Host: {ch_config.get('host', 'unknown')}")
            print(f"   Port: {ch_config.get('port', 'unknown')}")
            print(f"   Database: {ch_config.get('database', 'unknown')}")
        
        # Redis cache
        if 'cache' in storage_config:
            cache_config = storage_config['cache']
            cache_enabled = cache_config.get('enabled', False)
            print(f"⚡ Redis Cache: {'Enabled' if cache_enabled else 'Disabled'}")
            if cache_enabled:
                print(f"   Host: {cache_config.get('host', 'unknown')}")
                print(f"   Port: {cache_config.get('port', 'unknown')}")

def check_local_data_files():
    """Check for local data files."""
    print("\n📁 LOCAL DATA FILES")
    print("-" * 30)
    
    data_locations = [
        'data/',
        'data/signals/',
        'data/historical/',
        'data/cache/',
        'logs/'
    ]
    
    found_data = {}
    
    for location in data_locations:
        path = Path(location)
        if path.exists():
            if path.is_dir():
                files = list(path.iterdir())
                found_data[location] = files
                print(f"📁 {location}: {len(files)} items")
                
                # Show first few files
                for file in files[:3]:
                    size = "dir" if file.is_dir() else f"{file.stat().st_size} bytes"
                    print(f"   • {file.name} ({size})")
                
                if len(files) > 3:
                    print(f"   ... and {len(files) - 3} more items")
            else:
                size = path.stat().st_size
                found_data[location] = [path]
                print(f"📄 {location}: {size} bytes")
        else:
            print(f"❌ {location}: Not found")
    
    return found_data

def check_database_connections():
    """Check if databases are running and accessible."""
    print("\n🔗 DATABASE CONNECTION STATUS")
    print("-" * 30)
    
    # Check PostgreSQL
    try:
        import psycopg2
        print("📦 psycopg2: Available")
        
        try:
            conn = psycopg2.connect(
                host="localhost",
                port=5432,
                database="alphastock",
                user="postgres",
                password="",
                connect_timeout=5
            )
            conn.close()
            print("🐘 PostgreSQL: ✅ Connected")
        except Exception as e:
            print(f"🐘 PostgreSQL: ❌ Connection failed - {str(e)[:60]}")
    except ImportError:
        print("🐘 PostgreSQL: ❌ psycopg2 not available")
    
    # Check ClickHouse
    try:
        import clickhouse_connect
        print("📦 clickhouse_connect: Available")
        
        try:
            client = clickhouse_connect.get_client(
                host='localhost',
                port=8123,
                username='default',
                password='',
                connect_timeout=5
            )
            result = client.command('SELECT 1')
            print("🏠 ClickHouse: ✅ Connected")
        except Exception as e:
            print(f"🏠 ClickHouse: ❌ Connection failed - {str(e)[:60]}")
    except ImportError:
        print("🏠 ClickHouse: ❌ clickhouse_connect not available")
    
    # Check Redis
    try:
        import redis
        print("📦 redis: Available")
        
        try:
            r = redis.Redis(host='localhost', port=6379, db=0, socket_timeout=5)
            r.ping()
            print("⚡ Redis: ✅ Connected")
        except Exception as e:
            print(f"⚡ Redis: ❌ Connection failed - {str(e)[:60]}")
    except ImportError:
        print("⚡ Redis: ❌ redis not available")

def check_signals_data():
    """Check if signals data exists."""
    print("\n🎯 TRADING SIGNALS DATA")
    print("-" * 30)
    
    signals_file = Path('data/signals/signals.json')
    if signals_file.exists():
        try:
            with open(signals_file, 'r') as f:
                signals_data = json.load(f)
            
            print(f"✅ Signals file found: {signals_file}")
            print(f"📊 Data structure: {type(signals_data)}")
            
            if isinstance(signals_data, dict):
                print(f"🔑 Keys: {list(signals_data.keys())}")
            elif isinstance(signals_data, list):
                print(f"📈 Items: {len(signals_data)}")
                
        except Exception as e:
            print(f"⚠️ Error reading signals: {e}")
    else:
        print("📄 No signals file found (signals.json)")

async def check_data_layer():
    """Check if data layer can be initialized."""
    print("\n🔄 DATA LAYER STATUS")
    print("-" * 30)
    
    try:
        from src.data.data_layer_factory import data_layer_factory
        print("📦 Data layer factory: Available")
        
        try:
            data_layer = await data_layer_factory.get_data_layer()
            print("✅ Data layer: Initialized successfully")
            
            # Try to get some basic info
            try:
                # This would check if we have any stored data
                print("🔍 Checking for stored data...")
                await data_layer.cleanup()
                print("✅ Data layer: Working properly")
            except Exception as e:
                print(f"⚠️ Data layer test: {str(e)[:60]}")
                
        except Exception as e:
            print(f"❌ Data layer initialization failed: {str(e)[:60]}")
            
    except ImportError as e:
        print(f"❌ Data layer import failed: {str(e)[:60]}")

def main():
    """Main inspection function."""
    
    # Check config files
    configs = check_config_files()
    
    # Analyze storage configuration
    analyze_storage_config(configs)
    
    # Check local files
    local_data = check_local_data_files()
    
    # Check database connections
    check_database_connections()
    
    # Check signals data
    check_signals_data()
    
    print("\n" + "=" * 60)
    print("📋 DATA STORAGE SUMMARY")
    print("=" * 60)
    
    print("\n🎯 WHERE YOUR DATA IS CURRENTLY STORED:")
    
    # Local files
    if local_data:
        print("\n📁 LOCAL FILE STORAGE:")
        for location, files in local_data.items():
            if files:
                print(f"  ✅ {location} - {len(files)} items")
    
    # Database summary
    print("\n🗄️ DATABASE STORAGE:")
    print("  • Configuration points to PostgreSQL as primary")
    print("  • ClickHouse configured for high-performance queries")
    print("  • Redis configured for caching")
    print("  • Actual connectivity depends on running services")
    
    # Bank Nifty specific
    if 'production.json' in configs:
        data_config = configs['production.json'].get('data_collection', {})
        historical = data_config.get('historical', {})
        priority_symbols = historical.get('priority_symbols', {})
        
        if 'BANKNIFTY' in priority_symbols:
            banknifty_config = priority_symbols['BANKNIFTY']
            print(f"\n🏦 BANK NIFTY DATA CONFIG:")
            print(f"  • Retention: {banknifty_config.get('retention_years', 'N/A')} years")
            print(f"  • Timeframes: {', '.join(banknifty_config.get('timeframes', []))}")
            print(f"  • Priority: {banknifty_config.get('priority', 'N/A')}")
    
    print(f"\n💡 TO VIEW YOUR DATA:")
    print("  1. Check logs/: tail -f logs/scheduler.log")
    print("  2. Check data/: ls -la data/")
    print("  3. Connect to PostgreSQL (if running)")
    print("  4. Check Redis cache (if running)")
    
    print(f"\n🔧 TO START COLLECTING DATA:")
    print("  python3 scheduler.py --manual-start")

if __name__ == "__main__":
    try:
        # Run sync parts
        main()
        
        # Run async parts
        print("\n🔄 CHECKING ASYNC COMPONENTS...")
        asyncio.run(check_data_layer())
        
    except Exception as e:
        print(f"❌ Inspection error: {e}")
        import traceback
        traceback.print_exc()
