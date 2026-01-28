#!/usr/bin/env python3
"""
Import trading signals into ClickHouse
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

if not signals_file.exists():
    print("❌ No signals file found")
    exit(1)

with open(signals_file, 'r') as f:
    signals = json.load(f)

print(f"📈 Found {len(signals)} signals")

# Convert to DataFrame
df = pd.DataFrame(signals)

# Convert timestamp to ClickHouse format
df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')

# Handle NULL values for ClickHouse
df['exit_timestamp'] = df['exit_timestamp'].fillna('1970-01-01 00:00:00')
df['exit_price'] = df['exit_price'].fillna(0)
df['profit_loss'] = df['profit_loss'].fillna(0)
df['order_id'] = df['order_id'].fillna('')

# Select columns that match ClickHouse schema
columns_map = {
    'id': 'signal_id',
    'symbol': 'symbol',
    'strategy': 'strategy_name',
    'signal_type': 'signal_type',
    'entry_price': 'entry_price',
    'stop_loss': 'stop_loss',
    'target': 'target_price',
    'timestamp': 'signal_timestamp',
    'status': 'status',
    'exit_price': 'exit_price',
    'exit_timestamp': 'exit_timestamp',
    'profit_loss': 'profit_loss'
}

# Reorder columns
signal_df = df.rename(columns=columns_map)[list(columns_map.values())]

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

# Show sample
print("\n📈 Sample signals:")
subprocess.run(
    "docker exec alphastock-clickhouse clickhouse-client --database=alphastock --query=\"SELECT signal_id, symbol, strategy_name, signal_type, entry_price, signal_timestamp FROM trading_signals LIMIT 3 FORMAT PrettyCompact\"",
    shell=True
)
