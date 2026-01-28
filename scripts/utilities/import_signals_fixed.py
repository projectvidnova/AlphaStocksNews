#!/usr/bin/env python3
"""
Import trading signals into ClickHouse with correct schema
"""

import json
import pandas as pd
import subprocess
from pathlib import Path
from datetime import datetime

print("📊 IMPORTING TRADING SIGNALS TO CLICKHOUSE")
print("=" * 45)

# Load signals
signals_file = Path('data/signals/signals.json')

with open(signals_file, 'r') as f:
    signals = json.load(f)

print(f"📈 Found {len(signals)} signals")

# Convert to DataFrame
df = pd.DataFrame(signals)

# Match ClickHouse schema exactly
# id, symbol, strategy, signal_type, entry_price, stop_loss, target, timestamp, status, exit_price, exit_timestamp, profit_loss

# Convert timestamp to ClickHouse format
df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')

# Handle NULL values - use proper NULL representation
df['exit_timestamp'] = df['exit_timestamp'].fillna('\\N')
df['exit_price'] = df['exit_price'].fillna('\\N')
df['profit_loss'] = df['profit_loss'].fillna('\\N')

# Select and reorder columns to match ClickHouse schema
signal_df = df[['id', 'symbol', 'strategy', 'signal_type', 'entry_price', 'stop_loss', 'target', 'timestamp', 'status', 'exit_price', 'exit_timestamp', 'profit_loss']]

# Save as CSV
csv_file = 'trading_signals_import.csv'
signal_df.to_csv(csv_file, index=False)

print(f"💾 Saved signals to {csv_file}")

# Import to ClickHouse
try:
    cmd = f"docker exec -i alphastock-clickhouse clickhouse-client --database=alphastock --query=\"INSERT INTO trading_signals FORMAT CSVWithNames\" < {csv_file}"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Successfully imported signals to ClickHouse")
    else:
        print(f"❌ Import failed: {result.stderr}")
        
except Exception as e:
    print(f"❌ Error: {e}")

# Clean up
Path(csv_file).unlink()

print("\n🎯 VERIFICATION")
print("=" * 15)

# Check count
result = subprocess.run(
    "docker exec alphastock-clickhouse clickhouse-client --database=alphastock --query=\"SELECT COUNT(*) FROM trading_signals\"",
    shell=True, capture_output=True, text=True
)
print(f"📊 Total signals in database: {result.stdout.strip()}")

# Show sample with correct column names
print("\n📈 Sample signals:")
subprocess.run(
    "docker exec alphastock-clickhouse clickhouse-client --database=alphastock --query=\"SELECT id, symbol, strategy, signal_type, entry_price, timestamp FROM trading_signals LIMIT 3 FORMAT PrettyCompact\"",
    shell=True
)
