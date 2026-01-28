#!/usr/bin/env python3
"""
Fix CSV data format for ClickHouse import
Removes timezone info and ensures proper formatting
"""

import pandas as pd
from pathlib import Path
from datetime import datetime

print("🔧 FIXING CSV DATA FOR CLICKHOUSE")
print("=" * 40)

# Find all CSV files in historical data
data_dir = Path('data/historical')
csv_files = list(data_dir.glob('*.csv'))

if not csv_files:
    print("❌ No CSV files found")
    exit(1)

for csv_file in csv_files:
    print(f"📊 Processing: {csv_file}")
    
    try:
        # Read the CSV
        df = pd.read_csv(csv_file)
        print(f"   Rows: {len(df)}")
        
        # Fix timestamp format - remove timezone
        if 'timestamp' in df.columns:
            # Convert to datetime and remove timezone
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['timestamp'] = df['timestamp'].dt.tz_localize(None)
            
            # Format as string without timezone
            df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Create fixed version
        fixed_file = csv_file.parent / f"fixed_{csv_file.name}"
        df.to_csv(fixed_file, index=False)
        print(f"   ✅ Fixed version: {fixed_file}")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")

print("\n🔧 Now importing fixed data...")

# Import the fixed files
import subprocess

for csv_file in data_dir.glob('fixed_*.csv'):
    print(f"📊 Importing: {csv_file}")
    
    try:
        # Import into ClickHouse
        cmd = f"docker exec -i alphastock-clickhouse clickhouse-client --database=alphastock --query=\"INSERT INTO historical_data FORMAT CSVWithNames\" < {csv_file}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"   ✅ Successfully imported")
        else:
            print(f"   ❌ Import failed: {result.stderr}")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

print("\n✅ Data import process complete!")
print("🔍 Check data with: docker exec -it alphastock-clickhouse clickhouse-client --database=alphastock")
